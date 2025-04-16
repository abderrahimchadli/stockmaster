from celery import shared_task
from django.utils import timezone
from django.conf import settings
import logging
import shopify

logger = logging.getLogger(__name__)

@shared_task
def sync_product(client, store, product_id):
    """
    Sync a product from Shopify and manage its inventory status.
    """
    # TODO: Implement this
    return {'status': 'not_implemented'}


@shared_task(bind=True, max_retries=3, default_retry_delay=60) # Retries on failure
def sync_store_data(self, store_id):
    """Celery task to sync products, variants, and inventory for a store."""
    # Import models here to avoid circular imports
    from apps.accounts.models import ShopifyStore
    from apps.inventory.models import Product, ProductVariant, InventoryLevel

    logger.info(f"Starting sync_store_data task for store ID: {store_id}")
    try:
        # Step 1: Get store info
        try:
            store = ShopifyStore.objects.get(id=store_id)
            logger.info(f"Store found: {store.shop_url}")
        except ShopifyStore.DoesNotExist:
            logger.error(f"Store with ID {store_id} not found for syncing.")
            return {'status': 'error', 'message': f"Store with ID {store_id} not found"}
        
        # Check if store has an access token
        if not store.access_token:
            logger.error(f"Store {store.shop_url} has no access token.")
            store.sync_status = 'failed'
            store.save(update_fields=['sync_status'])
            return {'status': 'error', 'message': f"Store {store.shop_url} has no access token"}

        # Step 2: Shopify API Client Setup
        try:
            logger.info(f"Activating Shopify session for {store.shop_url} with API version {settings.SHOPIFY_API_VERSION}")
            session = shopify.Session(store.shop_url, settings.SHOPIFY_API_VERSION, store.access_token)
            shopify.ShopifyResource.activate_session(session)
            logger.info(f"Shopify API session activated for {store.shop_url}")
        except Exception as e:
            logger.error(f"Failed to activate Shopify session for {store.shop_url}: {str(e)}", exc_info=True)
            store.sync_status = 'failed'
            store.save(update_fields=['sync_status'])
            # Retry the task if session activation fails
            raise self.retry(exc=e)

        # Step 3: Product Fetch
        try:
            all_products = []
            page = shopify.Product.find(limit=250) # Max limit
            all_products.extend(page)
            while page.has_next_page():
                page = page.next_page()
                all_products.extend(page)
            
            logger.info(f"Fetched {len(all_products)} products from Shopify for {store.shop_url}.")
        except Exception as e:
            logger.error(f"Error fetching products for {store.shop_url}: {str(e)}", exc_info=True)
            store.sync_status = 'failed'
            store.save(update_fields=['sync_status'])
            raise self.retry(exc=e)

        # Step 4: Process products
        try:
            synced_product_ids = set()
            for product_data in all_products:
                # Fixed field names to match the actual Product model
                product, created = Product.objects.update_or_create(
                    store=store,
                    shopify_id=product_data.id,
                    defaults={
                        'title': product_data.title,
                        'handle': product_data.handle,
                        'status': product_data.status,
                        'product_type': product_data.product_type,
                        'vendor': product_data.vendor,
                        # 'tags': product_data.tags,  # Field doesn't exist in model, removed
                        'published_at': product_data.published_at,
                        # 'last_synced_at': timezone.now()  # Changed to last_synced
                        'last_synced': timezone.now()
                    }
                )
                synced_product_ids.add(product.shopify_id)
                if created:
                    logger.debug(f"Created Product: {product.title} ({product.shopify_id})")
                else:
                    logger.debug(f"Updated Product: {product.title} ({product.shopify_id})")

                # --- Variant and Inventory Sync (per product) ---
                synced_variant_ids = set()
                for variant_data in product_data.variants:
                    # Only include fields that exist in our model
                    variant_defaults = {
                        'title': variant_data.title,
                        'price': variant_data.price,
                        'inventory_item_id': variant_data.inventory_item_id,
                    }
                    
                    # Only add optional fields if they exist and have values
                    if hasattr(variant_data, 'sku') and variant_data.sku:
                        variant_defaults['sku'] = variant_data.sku
                    
                    if hasattr(variant_data, 'barcode') and variant_data.barcode:
                        variant_defaults['barcode'] = variant_data.barcode
                    
                    if hasattr(variant_data, 'compare_at_price') and variant_data.compare_at_price:
                        variant_defaults['compare_at_price'] = variant_data.compare_at_price
                    
                    if hasattr(variant_data, 'position'):
                        variant_defaults['position'] = variant_data.position
                    
                    variant, v_created = ProductVariant.objects.update_or_create(
                        product=product,
                        shopify_id=variant_data.id,
                        defaults=variant_defaults
                    )
                    synced_variant_ids.add(variant.shopify_id)
                    if v_created:
                        logger.debug(f"  Created Variant: {variant.title or variant.shopify_id}")
                    
                    # --- Sync Inventory Levels (requires inventory scope) ---
                    try:
                        inventory_levels = shopify.InventoryLevel.find(
                            inventory_item_ids=variant_data.inventory_item_id
                        )
                        for level_data in inventory_levels:
                            # Need to get or create the InventoryLocation
                            from apps.inventory.models import InventoryLocation
                            location, _ = InventoryLocation.objects.get_or_create(
                                store=store,
                                shopify_id=level_data.location_id,
                                defaults={'name': f"Location {level_data.location_id}"}
                            )
                            
                            level, l_created = InventoryLevel.objects.update_or_create(
                                variant=variant,
                                location=location,  # Use the location object
                                defaults={
                                    'available': level_data.available or 0,
                                    'last_synced': timezone.now()  # Use last_synced not last_synced_at
                                }
                            )
                            if l_created:
                                 logger.debug(f"    Created InventoryLevel for Loc {level.location.shopify_id}")
                    except Exception as e:
                        logger.warning(f"Could not sync inventory level for variant {variant_data.id}: {e}. Check scopes?")
                
                # Ensure is_active field is set correctly for updated model
                ProductVariant.objects.filter(product=product).exclude(shopify_id__in=synced_variant_ids).update(
                    updated_at=timezone.now()
                )
                logger.debug(f"  Updated variants for product {product.shopify_id} not in sync list.")
            
            # Ensure is_active field is set correctly for updated model
            Product.objects.filter(store=store).exclude(shopify_id__in=synced_product_ids).update(
                updated_at=timezone.now()
            )
            logger.info(f"Updated products for store {store.id} not in sync list.")
        except Exception as e:
            logger.error(f"Error processing products for {store.shop_url}: {str(e)}", exc_info=True)
            store.sync_status = 'failed'
            store.save(update_fields=['sync_status'])
            raise self.retry(exc=e)

        # Step 5: Mark sync as successful
        store.last_sync_at = timezone.now()
        store.sync_status = 'success'
        store.save(update_fields=['last_sync_at', 'sync_status'])
        logger.info(f"Successfully completed data sync for store: {store.shop_url}")
        return {'status': 'success', 'message': f"Successfully synced store {store.shop_url}"}

    except Exception as e:
        logger.error(f"Unexpected error during store sync for ID {store_id}: {str(e)}", exc_info=True)
        # Optionally update store sync status to 'failed'
        try:
            store = ShopifyStore.objects.get(id=store_id)
            store.sync_status = 'failed'
            store.save(update_fields=['sync_status'])
        except Exception as inner_e:
            logger.error(f"Could not update store sync status: {str(inner_e)}")
        # Retry the task
        raise self.retry(exc=e)
    finally:
        # Deactivate session after use
        try:
            shopify.ShopifyResource.clear_session()
            logger.info(f"Shopify API session cleared")
        except Exception as e:
            logger.warning(f"Could not clear Shopify session: {e}") 