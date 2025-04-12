#!/usr/bin/env python
"""
Standalone script to run the data sync process manually.
This bypasses Celery and directly executes the sync logic.
"""
import os
import sys
import django
import logging
import requests
import json
from datetime import datetime

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

# Import models after Django setup
from django.conf import settings
from apps.accounts.models import ShopifyStore
from apps.inventory.models import Product, ProductVariant
from django.utils import timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def fetch_products(store):
    """Fetch products directly using requests instead of shopify library."""
    logger.info(f"Attempting fetch for store ID: {store.id}, Shop URL: {store.shop_url}")
    
    # *** TEMPORARY DEBUGGING: Log the full token ***
    full_token = store.access_token if store.access_token else 'NONE'
    logger.info(f"Using FULL Access Token: {full_token}") 
    # ************************************************
    
    headers = {
        'X-Shopify-Access-Token': store.access_token,
        'Content-Type': 'application/json'
    }
    
    url = f"https://{store.shop_url}/admin/api/{settings.SHOPIFY_API_VERSION}/products.json?limit=250"
    
    logger.info(f"Fetching products from URL: {url}")
    # logger.info(f"Using access token: {store.access_token[:5]}...{store.access_token[-5:] if store.access_token else 'None'}") # Commented out brief log
    logger.info(f"Store ID: {store.id}, Created: {store.created_at}, Updated: {store.updated_at}")
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Error response: {response.text}")
            
            # If token is invalid, provide clear guidance on how to fix
            if response.status_code == 401:
                logger.error("Invalid access token. Please reinstall the app by visiting:")
                logger.error(f"https://{store.shop_url}/admin/oauth/authorize?client_id={settings.SHOPIFY_CLIENT_ID}&scope={settings.SHOPIFY_API_SCOPES}&redirect_uri=https://cloud-549585597.onetsolutions.network/auth/callback/")
        
        response.raise_for_status()
        
        products = response.json().get('products', [])
        logger.info(f"Successfully fetched {len(products)} products")
        
        # Log some product details if any were found
        if products:
            example = products[0]
            logger.info(f"Example product: ID={example.get('id')}, Title={example.get('title')}")
        
        return products
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching products: {str(e)}")
        return []

def sync_store(store):
    """Manually sync store data."""
    logger.info(f"Starting data sync for store: {store.shop_url}")
    
    # Mark sync as in progress
    store.sync_status = 'in_progress'
    store.save(update_fields=['sync_status'])
    
    try:
        # Fetch products
        products_data = fetch_products(store)
        logger.info(f"Fetched {len(products_data)} products from Shopify")
        
        # Process products
        synced_product_ids = set()
        for product_data in products_data:
            # Create or update product
            product_id = product_data.get('id')
            product, created = Product.objects.update_or_create(
                store=store,
                shopify_id=product_id,
                defaults={
                    'title': product_data.get('title', ''),
                    'handle': product_data.get('handle', ''),
                    'product_type': product_data.get('product_type', ''),
                    'vendor': product_data.get('vendor', ''),
                    'status': product_data.get('status', 'active'),
                    'published_at': product_data.get('published_at'),
                    'is_visible': True,
                    'last_synced': timezone.now()
                }
            )
            synced_product_ids.add(product_id)
            logger.info(f"{'Created' if created else 'Updated'} product: {product.title}")
            
            # Process variants
            variants_data = product_data.get('variants', [])
            synced_variant_ids = set()
            
            for variant_data in variants_data:
                variant_id = variant_data.get('id')
                variant, v_created = ProductVariant.objects.update_or_create(
                    product=product,
                    shopify_id=variant_id,
                    defaults={
                        'title': variant_data.get('title', ''),
                        'sku': variant_data.get('sku', ''),
                        'barcode': variant_data.get('barcode', ''),
                        'price': variant_data.get('price', 0),
                        'compare_at_price': variant_data.get('compare_at_price'),
                        'position': variant_data.get('position', 1),
                        'inventory_item_id': variant_data.get('inventory_item_id'),
                    }
                )
                synced_variant_ids.add(variant_id)
                logger.info(f"{'Created' if v_created else 'Updated'} variant: {variant.title}")
        
        # Update the sync status
        store.sync_status = 'success'
        store.last_sync_at = timezone.now()
        store.save(update_fields=['sync_status', 'last_sync_at'])
        
        logger.info(f"Successfully synced {len(synced_product_ids)} products for store: {store.shop_url}")
        return True
    except Exception as e:
        logger.error(f"Error syncing store {store.shop_url}: {str(e)}")
        store.sync_status = 'failed'
        store.save(update_fields=['sync_status'])
        return False

def main():
    """Main function to run the sync process."""
    start_time = datetime.now()
    logger.info(f"Script started at: {start_time}")
    logger.info("Starting manual data sync process")
    
    # Get all active stores
    stores = ShopifyStore.objects.filter(is_active=True)
    logger.info(f"Found {stores.count()} active stores")
    
    if not stores.exists():
        logger.warning("No active stores found. Please ensure the app is installed correctly via OAuth.")
        return # Exit if no active stores are found
    
    # Run sync for each store
    success_count = 0
    total_stores = stores.count()
    for store in stores:
        logger.info(f"Starting sync for store: {store.shop_url} (ID: {store.id})")
        if sync_store(store):
            success_count += 1
    
    end_time = datetime.now()
    duration = end_time - start_time
    logger.info(f"Manual data sync process completed. Successfully synced {success_count}/{total_stores} stores.")
    logger.info(f"Script completed at: {end_time}")
    logger.info(f"Total duration: {duration}")

# Add this at the end to call the main function when script is run
if __name__ == "__main__":
    main() 