#!/usr/bin/env python
"""
Script to generate a clean Shopify app installation URL.
This will help reset the OAuth flow and get a fresh access token.
"""
import os
import sys
import django
import urllib.parse

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

# Import settings
from django.conf import settings

def generate_clean_install_url():
    """Generate a clean app installation URL."""
    print("\nStockMaster App Installation URL Generator")
    print("=======================================")
    
    # Use a default store domain instead of prompting for input
    # You can change this to your actual store
    shop = "test-store.myshopify.com"
    
    print(f"Using store domain: {shop}")
    
    # Build installation URL with proper components
    api_key = settings.SHOPIFY_CLIENT_ID
    scopes = settings.SHOPIFY_API_SCOPES
    
    # Use the exact URL that's registered in Shopify app settings (with trailing slash)
    redirect_uri = "https://cloud-549585597.onetsolutions.network/auth/callback/"
    
    # Construct the install URL
    install_url = f"https://{shop}/admin/oauth/authorize?client_id={api_key}&scope={scopes}&redirect_uri={urllib.parse.quote(redirect_uri)}"
    
    print("\n============ INSTALLATION URL ============")
    print(f"Please visit this URL to install the app:\n")
    print(install_url)
    print("\nThis will initiate a fresh OAuth flow and set up a new access token.")
    print("After installation, the app should be able to access your store's data.")

if __name__ == "__main__":
    generate_clean_install_url() 