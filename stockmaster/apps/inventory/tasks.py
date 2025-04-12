from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging
from django.conf import settings

from core.utils.logger import logger
from core.shopify.client import ShopifyClient
from apps.accounts.models import ShopifyStore
from apps.inventory.models import Product, ProductVariant, InventoryLevel, InventoryLog
from apps.rules.models import Rule
import shopify # Using the official shopify library directly for now

logger = logging.getLogger(__name__)

@shared_task
def process_inventory_update(shop_domain, product_id=None, variant_id=None):
    """
    Process inventory update when a webhook is received.
    
    Args:
        shop_domain (str): The Shopify store domain
        product_id (int, optional): The Shopify product ID
        variant_id (int, optional): The Shopify variant ID
        
    Returns:
        dict: Summary of operations performed
    """
    logger.info(f"Processing inventory update for {shop_domain}, product: {product_id}, variant: {variant_id}")
    
    try:
        # Get the store
        store = ShopifyStore.objects.get(shop_url=shop_domain, is_active=True)
        
        # Create Shopify client
        client = ShopifyClient(store.shop_url, store.access_token)
        
        # If we have a product ID, sync that product
        if product_id:
            return sync_product(client, store, product_id)
            
        # If we have a variant ID, find the associated product and sync it
        elif variant_id:
            # Query Shopify for the variant information
            variant_data = get_variant_by_id(client, variant_id)
            if variant_data and 'product_id' in variant_data:
                return sync_product(client, store, variant_data['product_id'])
            else:
                logger.error(f"Could not find product for variant {variant_id}")
                return {'error': f"Could not find product for variant {variant_id}"}
        
        else:
            logger.error("Neither product_id nor variant_id provided")
            return {'error': "Neither product_id nor variant_id provided"}
            
    except ShopifyStore.DoesNotExist:
        logger.error(f"Store not found for domain {shop_domain}")
        return {'error': f"Store not found for domain {shop_domain}"}
        
    except Exception as e:
        logger.exception(f"Error processing inventory update: {str(e)}")
        return {'error': str(e)}


def get_variant_by_id(client, variant_id):
    """
    Get a variant from Shopify by its ID.
    
    Args:
        client (ShopifyClient): The Shopify client
        variant_id (int): The variant ID
        
    Returns:
        dict: The variant data or None if not found
    """
    # Use GraphQL to efficiently query variant data
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
    
    # Format the ID for GraphQL
    gid = f"gid://shopify/ProductVariant/{variant_id}"
    
    result = client.graphql(query, {'id': gid})
    
    if result and 'data' in result and 'productVariant' in result['data'] and result['data']['productVariant']:
        variant = result['data']['productVariant']
        product_gid = variant['product']['id']
        # Extract the numeric ID from the GID
        product_id = product_gid.split('/')[-1]
        return {'product_id': int(product_id)}
    
    return None


@shared_task
def sync_product(client, store, product_id):
    """
    Sync a product from Shopify and manage its inventory status.
    
    Args:
        client (ShopifyClient): The Shopify client
        store (ShopifyStore): The store object
        product_id (int): The Shopify product ID
        
    Returns:
        dict: Summary of operations performed
    """
    logger.info(f"Syncing product {product_id} for store {store.shop_url}")
    
    try:
        # Get the product data from Shopify
        response = client.get_product(product_id)
        
        if not response or 'product' not in response:
            logger.error(f"Could not fetch product {product_id}")
            return {'error': f"Could not fetch product {product_id}"}
        
        product_data = response['product']
        
        with transaction.atomic():
            # Create or update the product
            product, product_created = Product.objects.update_or_create(
                store=store,
                shopify_id=product_id,
                defaults={
                    'title': product_data.get('title', ''),
                    'handle': product_data.get('handle', ''),
                    'product_type': product_data.get('product_type', ''),
                    'vendor': product_data.get('vendor', ''),
                    'status': product_data.get('status', 'active'),
                    'published_at': parse_shopify_datetime(product_data.get('published_at')),
                    'last_synced': timezone.now(),
                }
            )
            
            # Process each variant
            variant_ids = []
            inventory_item_ids = []
            
            for variant_data in product_data.get('variants', []):
                variant_id = variant_data.get('id')
                inventory_item_id = variant_data.get('inventory_item_id')
                
                if variant_id and inventory_item_id:
                    variant_ids.append(variant_id)
                    inventory_item_ids.append(inventory_item_id)
                    
                    # Create or update the variant
                    variant, variant_created = ProductVariant.objects.update_or_create(
                        product=product,
                        shopify_id=variant_id,
                        defaults={
                            'title': variant_data.get('title', ''),
                            'sku': variant_data.get('sku', ''),
                            'barcode': variant_data.get('barcode', ''),
                            'price': variant_data.get('price', 0),
                            'compare_at_price': variant_data.get('compare_at_price'),
                            'position': variant_data.get('position', 1),
                            'inventory_item_id': inventory_item_id,
                        }
                    )
            
            # Fetch inventory levels for all variants
            if inventory_item_ids:
                inventory_response = client.get_inventory_levels(inventory_item_ids=inventory_item_ids)
                
                if inventory_response and 'inventory_levels' in inventory_response:
                    for level_data in inventory_response['inventory_levels']:
                        inventory_item_id = level_data.get('inventory_item_id')
                        location_id = level_data.get('location_id')
                        available = level_data.get('available', 0)
                        
                        if inventory_item_id and location_id is not None:
                            # Get or create the location
                            location, _ = store.inventory_locations.get_or_create(
                                shopify_id=location_id,
                                defaults={'name': f"Location {location_id}"}
                            )
                            
                            # Find the variant for this inventory item
                            variant = ProductVariant.objects.filter(
                                product=product,
                                inventory_item_id=inventory_item_id
                            ).first()
                            
                            if variant:
                                # Update or create inventory level
                                inv_level, created = InventoryLevel.objects.update_or_create(
                                    variant=variant,
                                    location=location,
                                    defaults={
                                        'available': available,
                                        'last_synced': timezone.now(),
                                    }
                                )
                                
                                # Create inventory log
                                if not created:
                                    # Only log if there's a change in available quantity
                                    if inv_level.available != available:
                                        InventoryLog.objects.create(
                                            store=store,
                                            product=product,
                                            variant=variant,
                                            location=location,
                                            action='sync',
                                            previous_value=inv_level.available,
                                            new_value=available,
                                        )
            
            # Check if product is out of stock across all locations
            total_inventory = sum(
                InventoryLevel.objects.filter(
                    variant__product=product
                ).values_list('available', flat=True)
            )
            
            # Apply rules if needed
            if total_inventory <= 0:
                # Product is out of stock, check for rules to apply
                process_out_of_stock_rules(store, product)
            
            return {
                'success': True,
                'product_id': product_id,
                'total_inventory': total_inventory,
                'is_out_of_stock': total_inventory <= 0,
            }
                
    except Exception as e:
        logger.exception(f"Error syncing product {product_id}: {str(e)}")
        return {'error': str(e)}


def parse_shopify_datetime(datetime_str):
    """Parse a Shopify datetime string into a Python datetime object."""
    if not datetime_str:
        return None
    
    try:
        # Shopify datetime format: 2023-01-01T12:00:00-00:00
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


def process_out_of_stock_rules(store, product):
    """
    Process rules for an out-of-stock product.
    
    Args:
        store (ShopifyStore): The store object
        product (Product): The product that is out of stock
    """
    # Find active rules for out-of-stock products
    rules = Rule.objects.filter(
        store=store,
        is_active=True,
        trigger_type='out_of_stock'
    ).order_by('-priority')
    
    for rule in rules:
        # Check if the rule matches the product
        if rule_matches_product(rule, product):
            # Schedule rule application
            schedule_rule_application(rule, product)


def rule_matches_product(rule, product):
    """
    Check if a rule matches a product based on rule filters.
    
    Args:
        rule (Rule): The rule to check
        product (Product): The product to check against
        
    Returns:
        bool: True if the rule matches the product, False otherwise
    """
    # Check product type filter
    if rule.product_type_filter and rule.product_type_filter != product.product_type:
        return False
    
    # Check vendor filter
    if rule.vendor_filter and rule.vendor_filter != product.vendor:
        return False
    
    # TODO: Implement tag and collection filters when those are available
    
    return True


def schedule_rule_application(rule, product):
    """
    Schedule a rule application.
    
    Args:
        rule (Rule): The rule to apply
        product (Product): The product to apply the rule to
    """
    from apps.rules.models import RuleApplication
    
    # Calculate the scheduled time
    if rule.delay_minutes > 0:
        scheduled_for = timezone.now() + timedelta(minutes=rule.delay_minutes)
    else:
        scheduled_for = timezone.now()
    
    # Calculate restoration time if applicable
    restore_scheduled_for = None
    if rule.auto_restore and rule.restore_after_days > 0:
        restore_scheduled_for = scheduled_for + timedelta(days=rule.restore_after_days)
    
    # Create or update rule application
    rule_app, created = RuleApplication.objects.update_or_create(
        rule=rule,
        product=product,
        status='pending',
        defaults={
            'triggered_at': timezone.now(),
            'scheduled_for': scheduled_for,
            'restore_scheduled_for': restore_scheduled_for,
        }
    )
    
    if created:
        logger.info(f"Scheduled rule '{rule.name}' for product '{product.title}' at {scheduled_for}")
    else:
        logger.info(f"Updated scheduled rule '{rule.name}' for product '{product.title}' to {scheduled_for}")
    
    # If no delay, apply the rule immediately
    if rule.delay_minutes == 0:
        apply_rule.delay(rule_app.id)
    

@shared_task
def apply_rule(rule_application_id):
    """
    Apply a rule to a product.
    
    Args:
        rule_application_id (int): The ID of the rule application to process
        
    Returns:
        dict: Summary of operations performed
    """
    from apps.rules.models import RuleApplication
    
    try:
        rule_app = RuleApplication.objects.select_related('rule', 'product').get(id=rule_application_id)
        
        # Check if the rule has already been applied
        if rule_app.status != 'pending':
            return {'status': 'skipped', 'reason': f"Rule already in status: {rule_app.status}"}
        
        # Check if it's time to apply the rule
        if rule_app.scheduled_for and rule_app.scheduled_for > timezone.now():
            return {'status': 'deferred', 'scheduled_for': rule_app.scheduled_for}
        
        rule = rule_app.rule
        product = rule_app.product
        store = rule.store
        
        # Create Shopify client
        client = ShopifyClient(store.shop_url, store.access_token)
        
        # Apply the action based on rule type
        if rule.action_type == 'hide_product':
            # Hide the product
            product_data = {
                'product': {
                    'id': product.shopify_id,
                    'status': 'draft'  # Change to draft to hide from storefront
                }
            }
            
            response = client.update_product(product.shopify_id, product_data)
            
            if response and 'product' in response:
                # Update the product status
                old_status = product.status
                product.status = 'draft'
                product.is_visible = False
                product.hidden_at = timezone.now()
                product.save()
                
                # Create log entry
                InventoryLog.objects.create(
                    store=store,
                    product=product,
                    action='hide',
                    previous_status=old_status,
                    new_status='draft',
                    notes=f"Hidden by rule: {rule.name}"
                )
                
                # Update rule application status
                rule_app.status = 'applied'
                rule_app.applied_at = timezone.now()
                rule_app.save()
                
                logger.info(f"Applied rule '{rule.name}' to hide product '{product.title}'")
                
                # Schedule notifications
                from apps.notifications.tasks import send_rule_applied_notification
                send_rule_applied_notification.delay(store.id, rule.id, product.id)
                
                return {'status': 'success', 'action': 'hide_product'}
            else:
                # Mark as failed
                rule_app.status = 'failed'
                rule_app.notes = "Failed to update product in Shopify"
                rule_app.save()
                
                logger.error(f"Failed to apply rule '{rule.name}' to product '{product.title}'")
                return {'status': 'error', 'message': "Failed to update product in Shopify"}
                
        # Implement other action types here
        # ...
        
        else:
            rule_app.status = 'failed'
            rule_app.notes = f"Unsupported action type: {rule.action_type}"
            rule_app.save()
            
            logger.error(f"Unsupported action type '{rule.action_type}' for rule '{rule.name}'")
            return {'status': 'error', 'message': f"Unsupported action type: {rule.action_type}"}
            
    except RuleApplication.DoesNotExist:
        logger.error(f"Rule application with ID {rule_application_id} not found")
        return {'status': 'error', 'message': f"Rule application with ID {rule_application_id} not found"}
        
    except Exception as e:
        logger.exception(f"Error applying rule: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def check_scheduled_rules():
    """
    Check for scheduled rules that need to be applied.
    
    Returns:
        dict: Summary of operations performed
    """
    from apps.rules.models import RuleApplication
    
    now = timezone.now()
    
    # Find pending rule applications that are scheduled for now or earlier
    pending_applications = RuleApplication.objects.filter(
        status='pending',
        scheduled_for__lte=now
    )
    
    count = 0
    for app in pending_applications:
        apply_rule.delay(app.id)
        count += 1
    
    # Find applied rule applications that need to be restored
    restore_applications = RuleApplication.objects.filter(
        status='applied',
        restore_scheduled_for__lte=now
    )
    
    restore_count = 0
    for app in restore_applications:
        restore_product.delay(app.id)
        restore_count += 1
    
    return {
        'applied_count': count,
        'restored_count': restore_count,
        'timestamp': now.isoformat()
    }


@shared_task
def restore_product(rule_application_id):
    """
    Restore a product after a rule has been applied.
    
    Args:
        rule_application_id (int): The ID of the rule application to process
        
    Returns:
        dict: Summary of operations performed
    """
    from apps.rules.models import RuleApplication
    
    try:
        rule_app = RuleApplication.objects.select_related('rule', 'product').get(id=rule_application_id)
        
        # Check if the rule has already been reversed
        if rule_app.status == 'reversed':
            return {'status': 'skipped', 'reason': "Rule already reversed"}
        
        # Check if the rule has been applied
        if rule_app.status != 'applied':
            return {'status': 'skipped', 'reason': f"Rule not in applied status: {rule_app.status}"}
        
        rule = rule_app.rule
        product = rule_app.product
        store = rule.store
        
        # Create Shopify client
        client = ShopifyClient(store.shop_url, store.access_token)
        
        # Reverse the action based on rule type
        if rule.action_type == 'hide_product':
            # Show the product
            product_data = {
                'product': {
                    'id': product.shopify_id,
                    'status': 'active'  # Change back to active
                }
            }
            
            response = client.update_product(product.shopify_id, product_data)
            
            if response and 'product' in response:
                # Update the product status
                old_status = product.status
                product.status = 'active'
                product.is_visible = True
                product.save()
                
                # Create log entry
                InventoryLog.objects.create(
                    store=store,
                    product=product,
                    action='show',
                    previous_status=old_status,
                    new_status='active',
                    notes=f"Restored by rule: {rule.name}"
                )
                
                # Update rule application status
                rule_app.status = 'reversed'
                rule_app.save()
                
                logger.info(f"Reversed rule '{rule.name}' to show product '{product.title}'")
                return {'status': 'success', 'action': 'show_product'}
            else:
                logger.error(f"Failed to reverse rule '{rule.name}' for product '{product.title}'")
                return {'status': 'error', 'message': "Failed to update product in Shopify"}
                
        # Implement other action types here
        # ...
        
        else:
            logger.error(f"Unsupported action type '{rule.action_type}' for rule '{rule.name}'")
            return {'status': 'error', 'message': f"Unsupported action type: {rule.action_type}"}
            
    except RuleApplication.DoesNotExist:
        logger.error(f"Rule application with ID {rule_application_id} not found")
        return {'status': 'error', 'message': f"Rule application with ID {rule_application_id} not found"}
        
    except Exception as e:
        logger.exception(f"Error restoring product: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60) # Retries on failure
def sync_store_data(self, store_id):
    """Celery task to sync products, variants, and inventory for a store."""
    try:
        store = ShopifyStore.objects.get(id=store_id)
        logger.info(f"Starting data sync for store: {store.shop_url}")

        # --- Shopify API Client Setup ---
        # Adjust this based on how you initialize your Shopify API connection
        try:
            session = shopify.Session(store.shop_url, settings.SHOPIFY_API_VERSION, store.access_token)
            shopify.ShopifyResource.activate_session(session)
            logger.info(f"Shopify API session activated for {store.shop_url}")
        except Exception as e:
            logger.error(f"Failed to activate Shopify session for {store.shop_url}: {e}")
            # Retry the task if session activation fails
            raise self.retry(exc=e)
        # --- End Shopify API Client Setup ---

        # --- Product Sync ---
        all_products = []
        page = shopify.Product.find(limit=250) # Max limit
        all_products.extend(page)
        while page.has_next_page():
            page = page.next_page()
            all_products.extend(page)
        
        logger.info(f"Fetched {len(all_products)} products from Shopify for {store.shop_url}.")

        synced_product_ids = set()
        for product_data in all_products:
            product, created = Product.objects.update_or_create(
                store=store,
                shopify_product_id=product_data.id,
                defaults={
                    'title': product_data.title,
                    'handle': product_data.handle,
                    'status': product_data.status,
                    'product_type': product_data.product_type,
                    'vendor': product_data.vendor,
                    'tags': product_data.tags,
                    'published_at': product_data.published_at,
                    # Assuming is_visible is managed by your app logic, not directly synced?
                    # 'is_visible': True, 
                    'last_synced_at': timezone.now()
                }
            )
            synced_product_ids.add(product.shopify_product_id)
            if created:
                logger.debug(f"Created Product: {product.title} ({product.shopify_product_id})")
            else:
                logger.debug(f"Updated Product: {product.title} ({product.shopify_product_id})")

            # --- Variant and Inventory Sync (per product) ---
            synced_variant_ids = set()
            for variant_data in product_data.variants:
                variant, v_created = ProductVariant.objects.update_or_create(
                    product=product,
                    shopify_variant_id=variant_data.id,
                    defaults={
                        'title': variant_data.title,
                        'sku': variant_data.sku,
                        'price': variant_data.price,
                        'inventory_quantity': variant_data.inventory_quantity, # Often stale, use InventoryLevel
                        'inventory_management': variant_data.inventory_management,
                        'inventory_policy': variant_data.inventory_policy,
                        'last_synced_at': timezone.now()
                    }
                )
                synced_variant_ids.add(variant.shopify_variant_id)
                if v_created:
                    logger.debug(f"  Created Variant: {variant.title or variant.shopify_variant_id}")
                
                # --- Sync Inventory Levels (requires inventory scope) ---
                try:
                    inventory_levels = shopify.InventoryLevel.find(
                        inventory_item_ids=variant_data.inventory_item_id
                    )
                    for level_data in inventory_levels:
                        level, l_created = InventoryLevel.objects.update_or_create(
                            variant=variant,
                            shopify_location_id=level_data.location_id,
                            defaults={
                                'available': level_data.available or 0,
                                'last_synced_at': timezone.now()
                            }
                        )
                        if l_created:
                             logger.debug(f"    Created InventoryLevel for Loc {level.shopify_location_id}")
                except Exception as e:
                    logger.warning(f"Could not sync inventory level for variant {variant_data.id}: {e}. Check scopes?")
            
            # Deactivate variants not found in the latest sync for this product
            ProductVariant.objects.filter(product=product).exclude(shopify_variant_id__in=synced_variant_ids).update(is_active=False, last_synced_at=timezone.now())
            logger.debug(f"  Deactivated variants for product {product.shopify_product_id} not in sync list.")
        
        # Deactivate products not found in the latest sync for this store
        Product.objects.filter(store=store).exclude(shopify_product_id__in=synced_product_ids).update(is_active=False, last_synced_at=timezone.now())
        logger.info(f"Deactivated products for store {store.id} not in sync list.")
        
        store.last_sync_at = timezone.now()
        store.sync_status = 'success'
        store.save(update_fields=['last_sync_at', 'sync_status'])
        logger.info(f"Successfully completed data sync for store: {store.shop_url}")

    except ShopifyStore.DoesNotExist:
        logger.error(f"Store with ID {store_id} not found for syncing.")
    except Exception as e:
        logger.error(f"Error during store sync for ID {store_id}: {str(e)}", exc_info=True)
        # Optionally update store sync status to 'failed'
        try:
            store = ShopifyStore.objects.get(id=store_id)
            store.sync_status = 'failed'
            store.save(update_fields=['sync_status'])
        except ShopifyStore.DoesNotExist:
            pass # Store doesn't exist, nothing to update
        # Retry the task
        raise self.retry(exc=e)
    finally:
        # Deactivate session after use
        try:
            shopify.ShopifyResource.clear_session()
            logger.info(f"Shopify API session cleared for {store.shop_url}")
        except Exception as e:
            logger.warning(f"Could not clear Shopify session: {e}") 