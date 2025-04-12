#!/usr/bin/env python
"""
Script to verify Shopify app credentials and generate a fresh installation link.
This will help ensure your app can be properly installed after manual uninstallation.
"""
import os
import sys
import django
import urllib.parse
import requests
import logging
from dotenv import load_dotenv

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

# Import settings
from django.conf import settings
from apps.accounts.models import ShopifyStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def check_credentials():
    """Check if Shopify API credentials are correctly configured."""
    print("\nChecking Shopify API credentials...")
    
    client_id = settings.SHOPIFY_CLIENT_ID
    client_secret = settings.SHOPIFY_CLIENT_SECRET
    app_url = settings.APP_URL
    scopes = settings.SHOPIFY_API_SCOPES
    
    # Check if credentials exist
    if not client_id:
        logger.error("❌ SHOPIFY_CLIENT_ID is missing")
        return False
    else:
        logger.info(f"✅ SHOPIFY_CLIENT_ID: {client_id[:5]}...{client_id[-5:]}")
    
    if not client_secret:
        logger.error("❌ SHOPIFY_CLIENT_SECRET is missing")
        return False
    else:
        logger.info(f"✅ SHOPIFY_CLIENT_SECRET: {client_secret[:5]}...{client_secret[-5:]}")
    
    if not app_url:
        logger.error("❌ APP_URL is missing")
        return False
    else:
        logger.info(f"✅ APP_URL: {app_url}")
    
    if not scopes:
        logger.error("❌ SHOPIFY_API_SCOPES is missing")
        return False
    else:
        logger.info(f"✅ SHOPIFY_API_SCOPES: {scopes}")
    
    return True

def check_allowed_redirect_uris():
    """Check and display the configured redirect URIs."""
    print("\nConfigured redirect URIs:")
    print("1. https://cloud-549585597.onetsolutions.network/auth/callback/")
    print("2. https://cloud-549585597.onetsolutions.network/auth/shopify/callback/")
    
    print("\nMake sure these exact URIs are configured in your Shopify App settings.")
    print("When installing, we'll use the first one.")

def check_active_stores():
    """Check if there are any active stores in the database."""
    try:
        stores = ShopifyStore.objects.filter(is_active=True)
        count = stores.count()
        
        print(f"\nActive stores in database: {count}")
        
        if count > 0:
            print("\nExisting stores:")
            for store in stores:
                print(f"- {store.shop_url} (ID: {store.id}, Token: {store.access_token[:5]}...{store.access_token[-5:] if store.access_token else 'None'})")
                
            # Ask if user wants to delete existing stores
            response = input("\nDo you want to delete existing stores and start fresh? (y/n): ")
            if response.lower() == 'y':
                for store in stores:
                    store.delete()
                print("All existing stores deleted.")
    except:
        print("Could not check stores in database.")

def generate_install_url():
    """Generate a fresh installation URL."""
    shop = input("\nEnter your Shopify store domain (e.g., 'your-store.myshopify.com'): ")
    
    # Normalize shop URL
    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"
    
    # Check if store is accessible
    print(f"\nChecking if {shop} is accessible...")
    try:
        response = requests.get(f"https://{shop}", timeout=10)
        if response.status_code == 200:
            print(f"✅ Store {shop} is accessible")
        else:
            print(f"⚠️ Store returned status code {response.status_code} - installation may fail")
    except Exception as e:
        print(f"⚠️ Error checking store: {str(e)} - installation may fail")
    
    # Build installation URL with proper components
    api_key = settings.SHOPIFY_CLIENT_ID
    scopes = settings.SHOPIFY_API_SCOPES
    redirect_uri = "https://cloud-549585597.onetsolutions.network/auth/callback/"
    
    # Construct the install URL
    install_url = f"https://{shop}/admin/oauth/authorize?client_id={api_key}&scope={scopes}&redirect_uri={urllib.parse.quote(redirect_uri)}"
    
    print("\n============ FRESH INSTALLATION URL ============")
    print(f"Please visit this URL to install the app:\n")
    print(install_url)
    print("\nAfter installation, visit your app dashboard at:")
    print(f"{settings.APP_URL}/dashboard/")

def main():
    """Main function to verify credentials and generate installation URL."""
    print("StockMaster App Credentials Verifier")
    print("====================================")
    
    # Check credentials
    if not check_credentials():
        print("\n❌ Credentials check failed. Please check your .env file or settings.")
        return
    
    # Check redirect URIs
    check_allowed_redirect_uris()
    
    # Check active stores
    check_active_stores()
    
    # Generate installation URL
    generate_install_url()
    
    print("\n✅ Verification complete!")

if __name__ == "__main__":
    main() 