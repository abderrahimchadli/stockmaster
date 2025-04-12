#!/usr/bin/env python
"""
Script to generate a Shopify app installation URL for reinstalling the app.
This will help reset the OAuth flow and get a fresh access token.
"""
import os
import sys
import django
import urllib.parse
from dotenv import load_dotenv

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

# Import settings
from django.conf import settings

# Load environment variables
load_dotenv()

def generate_install_url():
    """Generate the app installation URL."""
    shop = input("Enter your Shopify store domain (e.g., 'your-store.myshopify.com'): ")
    
    # Normalize shop URL
    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"
    
    # Build installation URL with proper components
    api_key = settings.SHOPIFY_CLIENT_ID
    scopes = settings.SHOPIFY_API_SCOPES
    
    # Use the exact URL that's registered in Shopify app settings (with trailing slash)
    redirect_uri = "https://cloud-549585597.onetsolutions.network/auth/callback/"
    
    # Construct the install URL
    install_url = f"https://{shop}/admin/oauth/authorize?client_id={api_key}&scope={scopes}&redirect_uri={urllib.parse.quote(redirect_uri)}"
    
    print("\n============ REINSTALLATION URL ============")
    print(f"Please visit this URL to reinstall the app:\n")
    print(install_url)
    print("\nThis will initiate a fresh OAuth flow and set up a new access token.")
    print("After reinstallation, the app should be able to access your store's data.")

if __name__ == "__main__":
    print("StockMaster App Reinstallation Helper")
    print("=====================================")
    generate_install_url() 