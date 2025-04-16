#!/usr/bin/env python
"""
Debug script for syncing Shopify data.
Run with `docker-compose exec web python debug_sync.py`
"""
import os
import sys
import django
import logging

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

# Import models and libraries
from django.conf import settings
from django.utils import timezone
import shopify
from apps.accounts.models import ShopifyStore
from apps.inventory.models import Product, ProductVariant, InventoryLevel, InventoryLocation

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to debug Shopify sync."""
    # Get active store
    try:
        store = ShopifyStore.objects.get(is_active=True)
        logger.info(f"Found store: {store.shop_url}")
        logger.info(f"Store sync status: {store.sync_status}")
        logger.info(f"Store last sync: {store.last_sync_at}")
    except ShopifyStore.DoesNotExist:
        logger.error("No active store found")
        return
    
    # Check if store has access token
    if not store.access_token:
        logger.error(f"Store {store.shop_url} has no access token")
        return
    
    # Setup Shopify session
    try:
        logger.info(f"Activating Shopify session for {store.shop_url}")
        session = shopify.Session(store.shop_url, settings.SHOPIFY_API_VERSION, store.access_token)
        shopify.ShopifyResource.activate_session(session)
        logger.info("Shopify session activated successfully")
    except Exception as e:
        logger.error(f"Failed to activate Shopify session: {e}")
        return
    
    try:
        # Fetch products from Shopify
        logger.info("Fetching products from Shopify...")
        products = shopify.Product.find(limit=5)
        logger.info(f"Found {len(products)} products in Shopify")
        
        # Process each product
        for product_data in products:
            logger.info(f"Processing product: {product_data.title} (ID: {product_data.id})")
            
            # Update or create product in database
            product, created = Product.objects.update_or_create(
                store=store,
                shopify_id=product_data.id,
                defaults={
                    'title': product_data.title,
                    'handle': product_data.handle,
                    'status': product_data.status,
                    'product_type': getattr(product_data, 'product_type', ''),
                    'vendor': getattr(product_data, 'vendor', ''),
                    'published_at': getattr(product_data, 'published_at', None),
                    'last_synced': timezone.now()
                }
            )
            logger.info(f"{'Created' if created else 'Updated'} product in database: {product.title}")
            
            # Process variants
            logger.info(f"Processing {len(product_data.variants)} variants...")
            for variant_data in product_data.variants:
                logger.info(f"  Variant: {variant_data.title} (ID: {variant_data.id})")
                
                # Update or create variant
                defaults = {
                    'title': variant_data.title,
                    'price': variant_data.price,
                    'inventory_item_id': variant_data.inventory_item_id,
                }
                
                if hasattr(variant_data, 'sku') and variant_data.sku:
                    defaults['sku'] = variant_data.sku
                
                variant, v_created = ProductVariant.objects.update_or_create(
                    product=product,
                    shopify_id=variant_data.id,
                    defaults=defaults
                )
                logger.info(f"  {'Created' if v_created else 'Updated'} variant in database: {variant.title}")
                
                # Process inventory levels
                try:
                    logger.info(f"  Fetching inventory levels for inventory item ID: {variant_data.inventory_item_id}")
                    inventory_levels = shopify.InventoryLevel.find(
                        inventory_item_ids=variant_data.inventory_item_id
                    )
                    logger.info(f"  Found {len(inventory_levels)} inventory levels")
                    
                    for level_data in inventory_levels:
                        logger.info(f"    Location ID: {level_data.location_id}, Available: {level_data.available}")
                        
                        # Create or update location
                        location, l_created = InventoryLocation.objects.get_or_create(
                            store=store,
                            shopify_id=level_data.location_id,
                            defaults={'name': f"Location {level_data.location_id}"}
                        )
                        logger.info(f"    {'Created' if l_created else 'Using existing'} location: {location.name}")
                        
                        # Create or update inventory level
                        inv_level, il_created = InventoryLevel.objects.update_or_create(
                            variant=variant,
                            location=location,
                            defaults={
                                'available': level_data.available or 0,
                                'last_synced': timezone.now()
                            }
                        )
                        logger.info(f"    {'Created' if il_created else 'Updated'} inventory level: {inv_level.available} units available")
                except Exception as e:
                    logger.error(f"  Error syncing inventory levels: {type(e).__name__}: {e}")
                    if hasattr(e, 'response') and e.response:
                        logger.error(f"  Response: {e.response.code} - {e.response.body}")
        
        # Update store sync status
        store.sync_status = 'success'
        store.last_sync_at = timezone.now()
        store.save(update_fields=['sync_status', 'last_sync_at'])
        logger.info(f"Updated store sync status to 'success'")
        
        # Print summary
        product_count = Product.objects.filter(store=store).count()
        variant_count = ProductVariant.objects.filter(product__store=store).count()
        inventory_count = InventoryLevel.objects.filter(variant__product__store=store).count()
        logger.info(f"Sync summary - Products: {product_count}, Variants: {variant_count}, Inventory Levels: {inventory_count}")
        
    except Exception as e:
        logger.error(f"Error during sync: {type(e).__name__}: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response: {e.response.code} - {e.response.body}")
        store.sync_status = 'failed'
        store.save(update_fields=['sync_status'])
    finally:
        # Clean up
        try:
            shopify.ShopifyResource.clear_session()
            logger.info("Shopify session cleared")
        except Exception as e:
            logger.warning(f"Could not clear Shopify session: {e}")

if __name__ == "__main__":
    main() 