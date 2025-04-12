#!/usr/bin/env python
"""
Script to check and display active Shopify stores in the database.
"""
import os
import sys
import django
import logging

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

# Import models
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

def display_active_stores():
    """Finds and displays details of all active stores."""
    try:
        active_stores = ShopifyStore.objects.filter(is_active=True)
        count = active_stores.count()
        logger.info(f"Found {count} active store(s).")
        
        print("\n--- Active Store Details ---")
        if count > 0:
            for store in active_stores:
                token_display = f"{store.access_token[:5]}...{store.access_token[-5:]}" if store.access_token else "None"
                print(f"- ID: {store.id}")
                print(f"  Shop URL: {store.shop_url}")
                print(f"  Shop Name: {store.shop_name}")
                print(f"  Is Active: {store.is_active}")
                print(f"  Token: {token_display}")
                print(f"  Sync Status: {store.sync_status}")
                print(f"  Created: {store.created_at}")
                print(f"  Updated: {store.updated_at}")
        else:
            print("No active stores found in the database.")
        print("--------------------------")
        return True
        
    except Exception as e:
        logger.error(f"Error reading stores from database: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    print("Checking database for active stores...")
    display_active_stores() 