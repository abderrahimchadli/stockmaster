#!/usr/bin/env python
"""
Script to get a valid access token for the Shopify API.
This uses the API key and secret to request a token for the store.
"""
import os
import sys
import requests
import django
from dotenv import load_dotenv

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

# Import models
from apps.accounts.models import ShopifyStore
from django.conf import settings

# Load environment variables
load_dotenv()

def get_access_token(shop_url="devdevkira.myshopify.com"):
    """
    Get Shopify access token using password grant (private app credentials).
    """
    print("=" * 40)
    print("GETTING ACCESS TOKEN")
    print("=" * 40)
    print(f"Shop URL: {shop_url}")
    print(f"Client ID: {settings.SHOPIFY_CLIENT_ID}")
    
    # Only print first few characters of secret
    secret_preview = settings.SHOPIFY_CLIENT_SECRET[:4] + "..." + settings.SHOPIFY_CLIENT_SECRET[-4:]
    print(f"Client Secret: {secret_preview}")
    
    # Instructions for getting private app credentials
    print("\nTo get a valid access token:")
    print("1. Go to https://devdevkira.myshopify.com/admin/apps/private")
    print("2. Create a new private app")
    print("3. Grant the following permissions:")
    print("   - Read/Write access to Products")
    print("   - Read/Write access to Inventory")
    print("   - Read access to Orders")
    print("4. Copy the Admin API access token")
    
    # Update existing store record with the new token
    try:
        store = ShopifyStore.objects.get(shop_url=shop_url)
        print(f"\nFound existing store: {store.shop_url} (ID: {store.id})")
        
        # Update with a valid token obtained from private app
        token = input("\nEnter your private app Admin API access token: ")
        if token:
            store.access_token = token
            store.is_active = True
            store.save()
            print(f"Updated store with new access token!")
            return token
    except ShopifyStore.DoesNotExist:
        # Create a new store if needed
        shop_name = input("\nEnter shop name: ")
        token = input("Enter your private app Admin API access token: ")
        
        if token:
            store = ShopifyStore(
                shop_url=shop_url,
                shop_name=shop_name,
                access_token=token,
                is_active=True
            )
            store.save()
            print(f"Created new store with access token!")
            return token
    
    return None

if __name__ == "__main__":
    token = get_access_token()
    if token:
        print("\nSuccessfully set up access token!")
        print("You can now run the sync script to fetch your store data.")
    else:
        print("\nFailed to set up access token. Please try again.") 