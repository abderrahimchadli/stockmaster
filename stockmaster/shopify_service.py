#!/usr/bin/env python3
"""
Shopify Authentication Service for StockMaster
This service script:
1. Starts and maintains the Django server
2. Handles automatic installation and authentication
3. Monitors the server status
4. Can be run as a system service
"""
import os
import sys
import time
import signal
import subprocess
import logging
import requests
import urllib.parse
from dotenv import load_dotenv
import datetime
import json
import socket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("shopify_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("shopify_service")

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

# Set up directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# Configuration
SERVER_PORT = int(os.environ.get('SERVER_PORT', 8000))
STORE_DOMAIN = os.environ.get('SHOPIFY_STORE_DOMAIN', "test-store.myshopify.com")
CLIENT_ID = os.environ.get('SHOPIFY_CLIENT_ID')
CLIENT_SECRET = os.environ.get('SHOPIFY_CLIENT_SECRET')
APP_URL = os.environ.get('APP_URL')
API_SCOPES = os.environ.get('SHOPIFY_API_SCOPES')
HEALTH_CHECK_INTERVAL = 60  # seconds

# Variables to track state
server_process = None
is_running = True

def setup_django():
    """Setup Django environment"""
    logger.info("Setting up Django environment")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    try:
        import django
        django.setup()
        logger.info("Django setup successful")
        return True
    except Exception as e:
        logger.error(f"Django setup failed: {e}")
        return False

def run_migrations():
    """Run database migrations"""
    logger.info("Running database migrations")
    try:
        result = subprocess.run(
            ["python3", "manage.py", "migrate"], 
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"Migrations completed: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Migration failed: {e.stderr}")
        return False

def start_server():
    """Start the Django development server"""
    global server_process
    
    logger.info(f"Starting Django server on port {SERVER_PORT}")
    try:
        # Check if port is already in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', SERVER_PORT))
        sock.close()
        
        if result == 0:
            logger.warning(f"Port {SERVER_PORT} is already in use")
            # Attempt to kill any process using this port
            try:
                subprocess.run(["pkill", "-f", f"runserver 0.0.0.0:{SERVER_PORT}"], check=False)
                logger.info("Killed existing server process")
                time.sleep(2)  # Give it time to shut down
            except Exception as e:
                logger.error(f"Failed to kill existing process: {e}")
        
        server_process = subprocess.Popen(
            ["python3", "manage.py", "runserver", f"0.0.0.0:{SERVER_PORT}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        time.sleep(5)
        
        if server_process.poll() is None:
            logger.info(f"Server started successfully with PID {server_process.pid}")
            
            # Save PID to file
            with open('server.pid', 'w') as f:
                f.write(str(server_process.pid))
                
            return True
        else:
            stdout, stderr = server_process.communicate()
            logger.error(f"Server failed to start: {stderr}")
            return False
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        return False

def check_server_health():
    """Check if the server is still running and responding"""
    global server_process
    
    # Check if process is running
    if server_process and server_process.poll() is not None:
        logger.warning("Server process has stopped")
        stdout, stderr = server_process.communicate()
        logger.error(f"Server output: {stderr}")
        return False
    
    # Check if server is responding
    try:
        response = requests.get(f"http://localhost:{SERVER_PORT}/", timeout=5)
        if response.status_code == 200:
            logger.debug("Server health check passed")
            return True
        else:
            logger.warning(f"Server returned unexpected status code: {response.status_code}")
            return False
    except requests.RequestException as e:
        logger.warning(f"Server health check failed: {e}")
        return False

def restart_server():
    """Restart the server if it's not responding"""
    global server_process
    
    logger.info("Restarting server")
    
    if server_process:
        try:
            server_process.terminate()
            server_process.wait(timeout=10)
        except Exception as e:
            logger.warning(f"Error terminating server: {e}")
            try:
                server_process.kill()
            except:
                pass
    
    return start_server()

def generate_install_url():
    """Generate a Shopify app installation URL"""
    shop = STORE_DOMAIN
    
    # Normalize shop URL
    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"
    
    logger.info(f"Generating installation URL for {shop}")
    
    # Build installation URL
    redirect_uri = f"{APP_URL}/auth/callback/"
    
    # Construct the install URL
    install_url = f"https://{shop}/admin/oauth/authorize?client_id={CLIENT_ID}&scope={API_SCOPES}&redirect_uri={urllib.parse.quote(redirect_uri)}"
    
    logger.info(f"Installation URL: {install_url}")
    
    # Save URL to file for easy access
    with open('installation_url.txt', 'w') as f:
        f.write(install_url)
    
    return install_url

def shutdown():
    """Gracefully shutdown the service"""
    global server_process, is_running
    
    logger.info("Shutting down service")
    is_running = False
    
    if server_process:
        try:
            server_process.terminate()
            server_process.wait(timeout=5)
            logger.info("Server process terminated")
        except Exception as e:
            logger.warning(f"Error terminating server: {e}")
            try:
                server_process.kill()
                logger.info("Server process killed")
            except:
                pass

def signal_handler(sig, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {sig}")
    shutdown()
    sys.exit(0)

def main():
    """Main service function"""
    global is_running
    
    logger.info("Starting Shopify Authentication Service")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Setup Django
    if not setup_django():
        logger.error("Failed to setup Django, exiting")
        return 1
    
    # Run migrations
    if not run_migrations():
        logger.warning("Migrations failed, but continuing...")
    
    # Start server
    if not start_server():
        logger.error("Failed to start server, exiting")
        return 1
    
    # Generate installation URL
    install_url = generate_install_url()
    logger.info("Service started successfully")
    logger.info(f"Use this URL to install the app: {install_url}")
    
    # Main service loop
    last_health_check = time.time()
    while is_running:
        try:
            # Perform health check at intervals
            current_time = time.time()
            if current_time - last_health_check > HEALTH_CHECK_INTERVAL:
                if not check_server_health():
                    logger.warning("Health check failed, restarting server")
                    restart_server()
                last_health_check = current_time
            
            # Sleep to avoid high CPU usage
            time.sleep(10)
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(30)  # Wait longer if there's an error
    
    logger.info("Service stopped")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 