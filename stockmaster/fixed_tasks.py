"""
Tasks for inventory management.
"""
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging
from django.conf import settings
import shopify

from core.utils.logger import logger
from core.shopify.client import ShopifyClient

logger = logging.getLogger(__name__)
logger.info("Loading inventory tasks module")

# This file is maintained for backward compatibility
# All task implementations have been moved to the tasks package

# Re-export all tasks
from apps.inventory.tasks.sync_tasks import sync_store_data, sync_product
from apps.inventory.tasks.inventory_tasks import process_inventory_update
from apps.inventory.tasks.rule_tasks import apply_rule, check_scheduled_rules, restore_product
from apps.inventory.tasks.utils import get_variant_by_id, parse_shopify_datetime, rule_matches_product

# Re-export functions used by other modules
from apps.inventory.tasks.rule_tasks import process_out_of_stock_rules, schedule_rule_application

# ======== Utility Functions ========

def get_variant_by_id(client, variant_id):
    """Get a variant from Shopify by its ID."""
    query = """
    query getVariant($id: ID!) {
        productVariant(id: $id) {
            id
            product {
                id
            }
        }
    }
    """
    
    gid = f"gid://shopify/ProductVariant/{variant_id}"
    
    result = client.graphql(query, {'id': gid})
    
    if result and 'data' in result and 'productVariant' in result['data'] and result['data']['productVariant']:
        variant = result['data']['productVariant']
        product_gid = variant['product']['id']
        product_id = product_gid.split('/')[-1]
        return {'product_id': int(product_id)}
    
    return None


def parse_shopify_datetime(datetime_str):
    """Parse a Shopify datetime string into a Python datetime object."""
    if not datetime_str:
        return None
    
    try:
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


def rule_matches_product(rule, product):
    """Check if a rule matches a product based on rule filters."""
    if rule.product_type_filter and rule.product_type_filter != product.product_type:
        return False
    
    if rule.vendor_filter and rule.vendor_filter != product.vendor:
        return False
    
    return True

# ======== Task Functions ========

@shared_task
def process_inventory_update(shop_domain, product_id=None, variant_id=None):
    """Process inventory update when a webhook is received."""
    from apps.accounts.models import ShopifyStore
    
    logger.info(f"Processing inventory update for {shop_domain}, product: {product_id}, variant: {variant_id}")
    
    try:
        # Get the store
        store = ShopifyStore.objects.get(shop_url=shop_domain, is_active=True)
        
        # Setup client
        client = ShopifyClient(store)
        
        # If variant ID is provided but product ID is not, look up the product ID
        if variant_id and not product_id:
            variant_info = get_variant_by_id(client, variant_id)
            if variant_info and 'product_id' in variant_info:
                product_id = variant_info['product_id']
                logger.info(f"Found product ID {product_id} for variant {variant_id}")
            else:
                logger.warning(f"Could not find product for variant {variant_id}")
                return {'error': f"Could not find product for variant {variant_id}"}
        
        # Process product update
        if product_id:
            result = sync_product(client, store, product_id)
            return result
        else:
            logger.error(f"No product ID provided and could not be determined")
            return {'error': "No product ID provided and could not be determined"}
            
    except ShopifyStore.DoesNotExist:
        logger.error(f"Store {shop_domain} not found or not active")
        return {'error': f"Store {shop_domain} not found or not active"}
    except Exception as e:
        logger.exception(f"Error processing inventory update: {str(e)}")
        return {'error': str(e)}


@shared_task
def sync_product(client, store, product_id):
    """Sync a product from Shopify and manage its inventory status."""
    # TODO: Implement this
    return {'status': 'not_implemented'}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_store_data(self, store_id):
    """Celery task to sync products, variants, and inventory for a store."""
    from apps.accounts.models import ShopifyStore
    from apps.inventory.models import Product, ProductVariant, InventoryLevel, InventoryLocation

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
            raise self.retry(exc=e)

        # Step 3: Product Fetch
        try:
            all_products = []
            page = shopify.Product.find(limit=250)
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
                        'published_at': product_data.published_at,
                        'last_synced': timezone.now()  # Use the correct field name that exists in the model
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
                    defaults = {
                        'title': variant_data.title,
                        'price': variant_data.price,
                        'inventory_item_id': variant_data.inventory_item_id,
                    }
                    
                    # Only add sku if it exists to avoid empty string issues
                    if hasattr(variant_data, 'sku') and variant_data.sku:
                        defaults['sku'] = variant_data.sku
                        
                    variant, v_created = ProductVariant.objects.update_or_create(
                        product=product,
                        shopify_id=variant_data.id,
                        defaults=defaults
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
                            location, _ = InventoryLocation.objects.get_or_create(
                                store=store,
                                shopify_id=level_data.location_id,
                                defaults={'name': f"Location {level_data.location_id}"}
                            )
                            
                            level, l_created = InventoryLevel.objects.update_or_create(
                                variant=variant,
                                location=location,
                                defaults={
                                    'available': level_data.available or 0,
                                    'last_synced': timezone.now()  # Using correct field name
                                }
                            )
                            if l_created:
                                logger.debug(f"    Created InventoryLevel for Loc {level.location.shopify_id}")
                    except Exception as e:
                        logger.warning(f"Could not sync inventory level for variant {variant_data.id}: {e}. Check scopes?")
                
                # Update variants not in sync list
                ProductVariant.objects.filter(product=product).exclude(shopify_id__in=synced_variant_ids).update(
                    updated_at=timezone.now()
                )
                logger.debug(f"  Updated variants for product {product.shopify_id} not in sync list.")
            
            # Update products not in sync list
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
        try:
            store = ShopifyStore.objects.get(id=store_id)
            store.sync_status = 'failed'
            store.save(update_fields=['sync_status'])
        except Exception as inner_e:
            logger.error(f"Could not update store sync status: {str(inner_e)}")
        raise self.retry(exc=e)
    finally:
        try:
            shopify.ShopifyResource.clear_session()
            logger.info(f"Shopify API session cleared")
        except Exception as e:
            logger.warning(f"Could not clear Shopify session: {e}") 

# ======== Rule Functions ========

def process_out_of_stock_rules(store, product):
    """Process rules for an out-of-stock product."""
    from apps.rules.models import Rule
    
    logger.info(f"Processing out-of-stock rules for product {product.id} in store {store.id}")
    
    rules = Rule.objects.filter(
        store=store,
        is_active=True,
        trigger_type='out_of_stock'
    ).order_by('priority')
    
    for rule in rules:
        if rule_matches_product(rule, product):
            logger.info(f"Rule {rule.id} matches product {product.id}")
            schedule_rule_application(rule, product)


def schedule_rule_application(rule, product):
    """Schedule a rule application."""
    from apps.rules.models import RuleApplication
    
    existing = RuleApplication.objects.filter(
        rule=rule,
        product=product,
        status='pending'
    ).exists()
    
    if existing:
        logger.info(f"Rule {rule.id} already scheduled for product {product.id}")
        return
    
    apply_at = timezone.now()
    if rule.delay_minutes > 0:
        apply_at = apply_at + timezone.timedelta(minutes=rule.delay_minutes)
    
    application = RuleApplication.objects.create(
        rule=rule,
        product=product,
        status='pending',
        scheduled_at=apply_at
    )
    
    logger.info(f"Scheduled rule {rule.id} for product {product.id} at {apply_at}")
    
    if rule.delay_minutes <= 0:
        apply_rule.delay(application.id)


@shared_task
def apply_rule(rule_application_id):
    """Apply a rule to a product."""
    from apps.rules.models import RuleApplication
    from apps.notifications.tasks import send_rule_applied_notification
    
    logger.info(f"Applying rule application {rule_application_id}")
    
    try:
        with transaction.atomic():
            application = RuleApplication.objects.select_related('rule', 'product').get(id=rule_application_id)
            
            if application.status != 'pending':
                logger.info(f"Rule application {rule_application_id} is not pending, status: {application.status}")
                return {'status': 'skipped', 'reason': f"Status is {application.status}"}
            
            rule = application.rule
            product = application.product
            
            if rule.action_type == 'hide_product':
                product.is_visible = False
                product.hidden_at = timezone.now()
                product.save(update_fields=['is_visible', 'hidden_at'])
                logger.info(f"Product {product.id} hidden by rule {rule.id}")
            
            elif rule.action_type == 'schedule_return':
                return_at = timezone.now() + timezone.timedelta(days=rule.return_days)
                
                product.is_visible = False
                product.hidden_at = timezone.now()
                product.scheduled_return = return_at
                product.save(update_fields=['is_visible', 'hidden_at', 'scheduled_return'])
                logger.info(f"Product {product.id} hidden by rule {rule.id}, scheduled return at {return_at}")
                
                restore_product.apply_async(
                    args=[application.id],
                    eta=return_at
                )
            
            application.status = 'applied'
            application.applied_at = timezone.now()
            application.save(update_fields=['status', 'applied_at'])
            
            from apps.inventory.models import InventoryLog
            InventoryLog.objects.create(
                store=product.store,
                product=product,
                action='rule',
                previous_status='visible' if product.is_visible else 'hidden',
                new_status='hidden',
                notes=f"Rule '{rule.name}' applied"
            )
            
            if rule.send_notification:
                send_rule_applied_notification.delay(application.id)
            
            return {
                'status': 'success',
                'rule_id': rule.id,
                'product_id': product.id,
                'action': rule.action_type
            }
    
    except RuleApplication.DoesNotExist:
        logger.error(f"Rule application {rule_application_id} not found")
        return {'status': 'error', 'message': f"Rule application {rule_application_id} not found"}
    except Exception as e:
        logger.exception(f"Error applying rule: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def check_scheduled_rules():
    """Check for scheduled rules that need to be applied."""
    from apps.rules.models import RuleApplication
    
    logger.info("Checking for scheduled rules to apply")
    
    now = timezone.now()
    
    applications = RuleApplication.objects.filter(
        status='pending',
        scheduled_at__lte=now
    )
    
    if not applications.exists():
        logger.info("No scheduled rules to apply")
        return {'status': 'success', 'count': 0}
    
    logger.info(f"Found {applications.count()} scheduled rules to apply")
    
    count = 0
    for application in applications:
        apply_rule.delay(application.id)
        count += 1
    
    return {'status': 'success', 'count': count}


@shared_task
def restore_product(rule_application_id):
    """Restore a product after a rule has been applied."""
    from apps.rules.models import RuleApplication
    
    logger.info(f"Restoring product for rule application {rule_application_id}")
    
    try:
        with transaction.atomic():
            application = RuleApplication.objects.select_related('rule', 'product').get(id=rule_application_id)
            
            if application.status != 'applied':
                logger.info(f"Rule application {rule_application_id} was not applied, status: {application.status}")
                return {'status': 'skipped', 'reason': f"Status is {application.status}"}
            
            product = application.product
            
            product.is_visible = True
            product.hidden_at = None
            product.scheduled_return = None
            product.save(update_fields=['is_visible', 'hidden_at', 'scheduled_return'])
            
            from apps.inventory.models import InventoryLog
            InventoryLog.objects.create(
                store=product.store,
                product=product,
                action='schedule',
                previous_status='hidden',
                new_status='visible',
                notes=f"Product restored after rule '{application.rule.name}'"
            )
            
            application.status = 'restored'
            application.restored_at = timezone.now()
            application.save(update_fields=['status', 'restored_at'])
            
            logger.info(f"Product {product.id} restored after rule {application.rule.id}")
            
            return {
                'status': 'success',
                'rule_id': application.rule.id,
                'product_id': product.id
            }
    
    except RuleApplication.DoesNotExist:
        logger.error(f"Rule application {rule_application_id} not found")
        return {'status': 'error', 'message': f"Rule application {rule_application_id} not found"}
    except Exception as e:
        logger.exception(f"Error restoring product: {str(e)}")
        return {'status': 'error', 'message': str(e)}

__all__ = [
    'sync_store_data',
    'sync_product',
    'process_inventory_update',
    'apply_rule',
    'check_scheduled_rules',
    'restore_product',
    'get_variant_by_id',
    'parse_shopify_datetime',
    'rule_matches_product',
    'process_out_of_stock_rules',
    'schedule_rule_application',
] 