#!/usr/bin/env python3
"""
Fully automated installation script for StockMaster Shopify app
This script will:
1. Check environment variables and credentials
2. Validate database connection
3. Reset any active stores
4. Apply all migrations
5. Start the server automatically
6. Output a complete installation URL

No user interaction is required - all values are preset.
"""
import os
import sys
import django
import time
import urllib.parse
import requests
from dotenv import load_dotenv
import subprocess
import signal
import json

# Load environment variables first
load_dotenv()
print("✅ Environment variables loaded")

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

try:
    django.setup()
    print("✅ Django setup successful")
except Exception as e:
    print(f"❌ Error during Django setup: {str(e)}")
    sys.exit(1)

# Import Django components
from django.conf import settings
from django.db import connection
from django.db.utils import OperationalError
from apps.accounts.models import ShopifyStore

# CONFIGURATION - UPDATE THESE VALUES OR SET ENVIRONMENT VARIABLES
# Store domain to use for installation - defaults to environment variable or test-store
STORE_DOMAIN = os.environ.get('SHOPIFY_STORE_DOMAIN', "test-store.myshopify.com")
# Whether to deactivate existing stores
DEACTIVATE_EXISTING_STORES = True
# Whether to start the server automatically
START_SERVER = True
# Server port (default: 8000)
SERVER_PORT = int(os.environ.get('SERVER_PORT', 8000))

def check_credentials():
    """Check if necessary Shopify credentials are set in environment variables"""
    required_vars = {
        'SHOPIFY_CLIENT_ID': settings.SHOPIFY_CLIENT_ID,
        'SHOPIFY_CLIENT_SECRET': settings.SHOPIFY_CLIENT_SECRET,
        'APP_URL': settings.APP_URL,
        'SHOPIFY_API_SCOPES': settings.SHOPIFY_API_SCOPES
    }
    
    missing_vars = []
    for var_name, var_value in required_vars.items():
        if not var_value:
            missing_vars.append(var_name)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your .env file and restart the script.")
        return False
    
    print("✅ All required credentials are set")
    
    # Print credentials info for verification
    print(f"   - SHOPIFY_CLIENT_ID: {settings.SHOPIFY_CLIENT_ID[:5]}...{settings.SHOPIFY_CLIENT_ID[-5:]}")
    print(f"   - APP_URL: {settings.APP_URL}")
    print(f"   - SHOPIFY_API_SCOPES: {settings.SHOPIFY_API_SCOPES}")
    
    return True

def check_database_connection():
    """Check if the database connection is working"""
    try:
        connection.ensure_connection()
        print("✅ Database connection successful")
        return True
    except OperationalError as e:
        print(f"❌ Database connection error: {str(e)}")
        return False

def run_migrations():
    """Run pending database migrations"""
    try:
        print("Running database migrations...")
        subprocess.run(["python3", "manage.py", "migrate"], check=True)
        print("✅ Migrations applied successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error applying migrations: {str(e)}")
        return False

def check_active_stores():
    """Check for active stores in the database and deactivate them"""
    try:
        active_stores = ShopifyStore.objects.filter(is_active=True)
        count = active_stores.count()
        
        if count > 0:
            print(f"ℹ️ Found {count} active store(s) in the database:")
            for store in active_stores:
                print(f"   - {store.shop_url} (last access: {store.last_access})")
                
            if DEACTIVATE_EXISTING_STORES:
                active_stores.update(is_active=False, access_token=None)
                print("✅ All stores have been deactivated")
            else:
                print("ℹ️ Existing stores kept active per configuration")
        else:
            print("✅ No active stores found in the database")
            
        return True
    except Exception as e:
        print(f"❌ Error checking active stores: {str(e)}")
        return False

def generate_install_url():
    """Generate a clean app installation URL for the configured store"""
    print("\nGenerating Shopify installation URL...")
    shop = STORE_DOMAIN
    
    # Normalize shop URL
    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"
    
    print(f"Using store domain: {shop}")
    
    # Check if the store is accessible
    try:
        response = requests.get(f"https://{shop}/admin", timeout=5)
        if response.status_code >= 400:
            print(f"⚠️ Warning: Could not access {shop} (Status code: {response.status_code})")
            print("This might be an invalid store or it's not accessible.")
            print("Proceeding anyway as this is an automated script.")
    except requests.RequestException:
        print(f"⚠️ Warning: Could not connect to {shop}")
        print("This might be an invalid store or it's not accessible.")
        print("Proceeding anyway as this is an automated script.")
    
    # Build installation URL with proper components
    api_key = settings.SHOPIFY_CLIENT_ID
    scopes = settings.SHOPIFY_API_SCOPES
    
    # Use the exact URL that's registered in Shopify app settings (with trailing slash)
    redirect_uri = f"{settings.APP_URL}/auth/callback/"
    
    # Construct the install URL
    install_url = f"https://{shop}/admin/oauth/authorize?client_id={api_key}&scope={scopes}&redirect_uri={urllib.parse.quote(redirect_uri)}"
    
    print("\n============ INSTALLATION URL ============")
    print(f"Please visit this URL to install the app:\n")
    print(install_url)
    print("\nThis will initiate the OAuth flow and set up a new access token.")
    
    return install_url

def check_callback_url():
    """Check if the callback URL is properly configured"""
    callback_url = f"{settings.APP_URL}/auth/callback/"
    print(f"\nVerifying callback URL: {callback_url}")
    print("Make sure this URL matches EXACTLY what you've configured in your Shopify Partner Dashboard.")
    print("Your app's Allowed redirection URL(s) should include:")
    print(f"- {callback_url}")
    
    # Check if the redirect URI is already in settings
    allowed_redirects = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if settings.APP_URL in allowed_redirects or f"{settings.APP_URL}/" in allowed_redirects:
        print("✅ App URL is in CSRF_TRUSTED_ORIGINS - good!")
    else:
        print("⚠️ Warning: Your APP_URL is not in CSRF_TRUSTED_ORIGINS")
        print("This might cause CSRF validation failures during authentication")
    
    return True

def start_dev_server():
    """Start the development server automatically"""
    if not START_SERVER:
        print("\nServer auto-start disabled in configuration.")
        return True
        
    print(f"\nStarting development server on port {SERVER_PORT}...")
    
    try:
        # Start Django development server in a separate process
        server_process = subprocess.Popen(
            ["python3", "manage.py", "runserver", f"0.0.0.0:{SERVER_PORT}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Give time for server to start
        time.sleep(3)
        
        # Check if the process is still running
        if server_process.poll() is None:
            print("\n✅ Server started successfully at PID:", server_process.pid)
            print(f"Your app should now be accessible at {settings.APP_URL}")
            print("After installation, your app should redirect to the Shopify admin")
            print("\nIMPORTANT: The server is running in the background.")
            print("To stop it, you'll need to kill the process with:")
            print(f"kill {server_process.pid}")
            
            # Save PID to file for easier management
            with open('server.pid', 'w') as f:
                f.write(str(server_process.pid))
            print(f"Server PID saved to server.pid")
            
            # Return the process in case the caller wants to manage it
            return server_process
        else:
            stdout, stderr = server_process.communicate()
            print("❌ Server failed to start. Error output:")
            print(stderr.decode('utf-8'))
            return False
            
    except Exception as e:
        print(f"\n❌ Error starting server: {str(e)}")
        return False

def main():
    """Main function to run the automated setup"""
    print("\n==== StockMaster App Automated Installation ====\n")
    
    # Check credentials
    if not check_credentials():
        return False
    
    # Check database connection
    if not check_database_connection():
        return False
    
    # Run migrations if needed
    if not run_migrations():
        return False
    
    # Check for active stores
    if not check_active_stores():
        return False
    
    # Check callback URL configuration
    if not check_callback_url():
        return False
    
    # Generate installation URL
    install_url = generate_install_url()
    
    # Start development server
    server_process = start_dev_server()
    
    print("\n✅ Automated installation completed successfully")
    print("\nInstallation URL (copy this to install the app):")
    print(install_url)
    
    # Optional: Create a file with the installation URL for easy access
    with open('installation_url.txt', 'w') as f:
        f.write(install_url)
    print("\nThe installation URL has also been saved to 'installation_url.txt'")
    
    return True

if __name__ == "__main__":
    main() 