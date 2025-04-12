#!/usr/bin/env python
"""
Script to find and activate a specific Shopify store in the database.
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

def activate_store_by_id(store_id):
    """Finds a store by ID and sets it to active."""
    try:
        store = ShopifyStore.objects.get(id=store_id)
        logger.info(f"Found store: {store.shop_url} (ID: {store.id})")
        if not store.is_active:
            store.is_active = True
            store.save(update_fields=['is_active'])
            logger.info(f"Store {store.id} activated successfully.")
        else:
            logger.info(f"Store {store.id} is already active.")
        return True
    except ShopifyStore.DoesNotExist:
        logger.error(f"Store with ID {store_id} not found.")
        return False
    except Exception as e:
        logger.error(f"Error activating store {store_id}: {str(e)}")
        return False

if __name__ == "__main__":
    store_id_to_activate = 1 # Assuming the correct store is ID 1
    print(f"Attempting to activate store with ID: {store_id_to_activate}")
    if activate_store_by_id(store_id_to_activate):
        print("Activation process finished.")
    else:
        print("Activation failed.") 