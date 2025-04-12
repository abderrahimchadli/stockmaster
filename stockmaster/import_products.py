#!/usr/bin/env python
"""
Script to import test products into the application database.
This will create sample data so the app shows proper information on the dashboard.
"""
import os
import sys
import django
import logging
from datetime import datetime

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

# Import models after Django setup
from django.conf import settings
from apps.accounts.models import ShopifyStore
from apps.inventory.models import Product, ProductVariant, InventoryLevel, InventoryLocation
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

def ensure_inventory_location(store):
    """Make sure there is at least one inventory location available."""
    # Check if location already exists
    location, created = InventoryLocation.objects.get_or_create(
        store=store,
        location_id=1,
        defaults={
            'name': 'Primary Location',
            'address': '123 Test St',
            'city': 'Test City',
            'zip': '12345',
            'country': 'US',
            'is_active': True
        }
    )
    
    if created:
        logger.info(f"Created inventory location: {location.name}")
    else:
        logger.info(f"Using existing location: {location.name}")
    
    return location

def create_test_products(store, count=10):
    """Create sample products in the database."""
    logger.info(f"Creating {count} test products for store: {store.shop_url}")
    
    # Ensure we have a location for inventory
    location = ensure_inventory_location(store)
    
    products_created = 0
    
    # Create products
    for i in range(1, count+1):
        product_id = 1000000 + i
        
        # Check if product already exists
        if Product.objects.filter(store=store, shopify_id=product_id).exists():
            logger.info(f"Product {product_id} already exists, skipping")
            continue
        
        # Create product
        product = Product.objects.create(
            store=store,
            shopify_id=product_id,
            title=f"Test Product {i}",
            handle=f"test-product-{i}",
            product_type="Test",
            vendor="Test Vendor",
            status="active",
            published_at=timezone.now(),
            is_visible=True,
            last_synced=timezone.now()
        )
        
        logger.info(f"Created product: {product.title} (ID: {product.id})")
        
        # Create variant
        variant_id = 2000000 + i
        variant = ProductVariant.objects.create(
            product=product,
            shopify_id=variant_id,
            title="Default",
            sku=f"TEST-{i}",
            barcode=f"123456789{i}",
            price=10.99 + i,
            compare_at_price=19.99 + i,
            position=1,
            inventory_item_id=3000000 + i
        )
        
        logger.info(f"Created variant: {variant.title} for product {product.title}")
        
        # Create inventory level
        inventory = 10 if i % 3 != 0 else 0  # Make every 3rd product out of stock
        
        inventory_level = InventoryLevel.objects.create(
            variant=variant,
            location_id=location.id,
            available=inventory,
            updated_at=timezone.now()
        )
        
        logger.info(f"Created inventory level for {product.title}: {inventory} units")
        
        products_created += 1
    
    logger.info(f"Successfully created {products_created} test products")
    return products_created

def main():
    """Main function to run the import process."""
    logger.info("Starting product import process")
    
    # Get all active stores
    stores = ShopifyStore.objects.filter(is_active=True)
    logger.info(f"Found {stores.count()} active stores")
    
    if not stores.exists():
        logger.warning("No active stores found. Creating a test store...")
        
        # Create a test store
        store = ShopifyStore.objects.create(
            shop_url='devdevkira.myshopify.com',
            shop_name='Dev Dev Kira Store',
            access_token='sample_token_for_test_data_only',
            is_active=True
        )
        
        logger.info(f"Created test store: {store.shop_url} (ID: {store.id})")
        stores = [store]
    
    # Import products for each store
    for store in stores:
        # Check if store already has products
        existing_products = Product.objects.filter(store=store).count()
        
        if existing_products > 0:
            logger.info(f"Store {store.shop_url} already has {existing_products} products")
            
            # Ask if user wants to add more products
            response = input("Do you want to add more test products? (y/n): ")
            
            if response.lower() != 'y':
                logger.info("Skipping product import for this store")
                continue
        
        # Create test products
        created = create_test_products(store, count=15)
        logger.info(f"Added {created} test products to store {store.shop_url}")

if __name__ == "__main__":
    start_time = datetime.now()
    logger.info(f"Script started at: {start_time}")
    
    main()
    
    end_time = datetime.now()
    duration = end_time - start_time
    logger.info(f"Script completed at: {end_time}")
    logger.info(f"Total duration: {duration}") 