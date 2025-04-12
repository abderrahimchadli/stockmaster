#!/usr/bin/env python
"""
Automated setup script for StockMaster Shopify app
This script will:
1. Check environment variables and credentials
2. Validate database connection
3. Update existing installations if needed
4. Generate a working installation URL
5. Provide next steps for installation
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

# Load environment variables
load_dotenv()
print("✅ Environment variables loaded")

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
        subprocess.run(["python", "manage.py", "migrate"], check=True)
        print("✅ Migrations applied successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error applying migrations: {str(e)}")
        return False

def check_active_stores():
    """Check for active stores in the database"""
    try:
        active_stores = ShopifyStore.objects.filter(is_active=True)
        count = active_stores.count()
        
        if count > 0:
            print(f"ℹ️ Found {count} active store(s) in the database:")
            for store in active_stores:
                print(f"   - {store.shop_url} (last access: {store.last_access})")
                
            answer = input("Would you like to deactivate these stores for a fresh installation? (y/n): ")
            if answer.lower() == 'y':
                active_stores.update(is_active=False, access_token=None)
                print("✅ All stores have been deactivated")
        else:
            print("✅ No active stores found in the database")
            
        return True
    except Exception as e:
        print(f"❌ Error checking active stores: {str(e)}")
        return False

def generate_install_url():
    """Generate a clean app installation URL for a specific store"""
    print("\nGenerating Shopify installation URL...")
    shop = input("Enter your Shopify store domain (e.g., 'your-store.myshopify.com'): ")
    
    # Normalize shop URL
    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"
    
    # Check if the store is accessible
    try:
        response = requests.get(f"https://{shop}/admin", timeout=5)
        if response.status_code >= 400:
            print(f"❌ Warning: Could not access {shop} (Status code: {response.status_code})")
            print("This might be an invalid store or it's not accessible.")
            proceed = input("Do you want to proceed anyway? (y/n): ")
            if proceed.lower() != 'y':
                return False
    except requests.RequestException:
        print(f"❌ Warning: Could not connect to {shop}")
        print("This might be an invalid store or it's not accessible.")
        proceed = input("Do you want to proceed anyway? (y/n): ")
        if proceed.lower() != 'y':
            return False
    
    # Build installation URL
    api_key = settings.SHOPIFY_CLIENT_ID
    scopes = settings.SHOPIFY_API_SCOPES
    redirect_uri = f"{settings.APP_URL}/auth/callback/"
    
    # Construct the install URL
    install_url = f"https://{shop}/admin/oauth/authorize?client_id={api_key}&scope={scopes}&redirect_uri={urllib.parse.quote(redirect_uri)}"
    
    print("\n============ INSTALLATION URL ============")
    print(f"Please visit this URL to install the app:\n")
    print(install_url)
    print("\nThis will initiate the OAuth flow and set up a new access token.")
    
    return True

def check_callback_url():
    """Check if the callback URL is properly configured"""
    callback_url = f"{settings.APP_URL}/auth/callback/"
    print(f"\nVerifying callback URL: {callback_url}")
    print("Make sure this URL matches EXACTLY what you've configured in your Shopify Partner Dashboard.")
    print("Your app's Allowed redirection URL(s) should include:")
    print(f"- {callback_url}")
    print("\nIf these don't match, authentication will fail with 'invalid_request: The redirect_uri is not whitelisted'")
    
    return True

def start_dev_server():
    """Ask if user wants to start the development server"""
    answer = input("\nWould you like to start the development server now? (y/n): ")
    if answer.lower() == 'y':
        print("\nStarting development server...")
        print("Press Ctrl+C to stop the server")
        
        try:
            # Start Django development server
            process = subprocess.Popen(["python", "manage.py", "runserver", "0.0.0.0:8000"])
            
            # Give time for server to start
            time.sleep(3)
            
            print("\n✅ Server started successfully")
            print(f"Your app should now be accessible at {settings.APP_URL}")
            print("After installation, your app should redirect to the Shopify admin")
            
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nStopping server...")
            process.send_signal(signal.SIGTERM)
            process.wait()
            print("Server stopped")
        
    return True

def main():
    """Main function to run the automated setup"""
    print("\n==== StockMaster App Automated Setup ====\n")
    
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
    if not generate_install_url():
        return False
    
    # Ask to start development server
    if not start_dev_server():
        return False
    
    print("\n✅ Setup completed successfully")
    return True

if __name__ == "__main__":
    main() 