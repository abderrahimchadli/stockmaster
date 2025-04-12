import json
from django.http import HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from core.shopify.client import ShopifyClient
from core.utils.logger import logger
from apps.inventory.tasks import process_inventory_update
from apps.accounts.models import ShopifyStore


@method_decorator(csrf_exempt, name='dispatch')
class ShopifyWebhookView(View):
    """Base class for all Shopify webhook handlers."""
    
    def verify_webhook(self, request):
        """Verify that the webhook came from Shopify."""
        hmac_header = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256')
        if not hmac_header:
            logger.warning("Missing HMAC header in webhook request")
            return False
        
        data = request.body
        return ShopifyClient.verify_webhook(data, hmac_header)
    
    def post(self, request, *args, **kwargs):
        """Handle webhook POST request."""
        if not self.verify_webhook(request):
            logger.warning("Webhook verification failed")
            return HttpResponse(status=401)
        
        shop_domain = request.META.get('HTTP_X_SHOPIFY_SHOP_DOMAIN')
        if not shop_domain:
            logger.warning("Missing shop domain in webhook request")
            return HttpResponse(status=400)
        
        try:
            data = json.loads(request.body)
            self.process_webhook(shop_domain, data)
            return HttpResponse(status=200)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook request")
            return HttpResponse(status=400)
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return HttpResponse(status=500)
    
    def process_webhook(self, shop_domain, data):
        """Process the webhook data. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement process_webhook")


class ProductUpdateWebhook(ShopifyWebhookView):
    """Handler for product update webhooks."""
    
    def process_webhook(self, shop_domain, data):
        """Process a product update webhook."""
        product_id = data.get('id')
        logger.info(f"Product update webhook received for product {product_id} from {shop_domain}")
        
        # Check if product is out of stock
        variants = data.get('variants', [])
        for variant in variants:
            inventory_quantity = variant.get('inventory_quantity', 0)
            if inventory_quantity <= 0:
                # Schedule inventory update processing
                process_inventory_update.delay(shop_domain, product_id, variant.get('id'))


class InventoryLevelUpdateWebhook(ShopifyWebhookView):
    """Handler for inventory level update webhooks."""
    
    def process_webhook(self, shop_domain, data):
        """Process an inventory level update webhook."""
        inventory_item_id = data.get('inventory_item_id')
        available = data.get('available')
        logger.info(f"Inventory update webhook received for item {inventory_item_id} from {shop_domain}, available: {available}")
        
        # If inventory is zero or below, handle out-of-stock scenario
        if available is not None and available <= 0:
            # Find associated product
            try:
                store = ShopifyStore.objects.get(shop_url=shop_domain)
                # Create a client to get product information
                client = ShopifyClient(store.shop_url, store.access_token)
                
                # Get inventory item to find associated variant and product
                inventory_item = client.get_inventory_item(inventory_item_id)
                if inventory_item and 'inventory_item' in inventory_item:
                    variant_id = inventory_item['inventory_item'].get('variant_id')
                    if variant_id:
                        # Schedule inventory update processing
                        process_inventory_update.delay(shop_domain, None, variant_id)
            except ShopifyStore.DoesNotExist:
                logger.error(f"Store not found for domain {shop_domain}")
            except Exception as e:
                logger.error(f"Error processing inventory update: {str(e)}")


class AppUninstalledWebhook(ShopifyWebhookView):
    """Handler for app uninstalled webhooks."""
    
    def process_webhook(self, shop_domain, data):
        """Process an app uninstalled webhook."""
        logger.info(f"App uninstalled webhook received from {shop_domain}")
        
        # Clean up shop data when app is uninstalled
        try:
            store = ShopifyStore.objects.get(shop_url=shop_domain)
            store.is_active = False
            store.access_token = None  # Clear token for security
            store.save()
            logger.info(f"Marked store {shop_domain} as inactive due to uninstallation")
        except ShopifyStore.DoesNotExist:
            logger.warning(f"Store not found for domain {shop_domain} during uninstallation")
        except Exception as e:
            logger.error(f"Error handling app uninstallation: {str(e)}") 