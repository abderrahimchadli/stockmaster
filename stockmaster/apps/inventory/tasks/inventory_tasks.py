from celery import shared_task
from django.utils import timezone
import logging

from core.shopify.client import ShopifyClient
from .utils import get_variant_by_id

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
            from .sync_tasks import sync_product
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
from django.utils import timezone
import logging

from core.shopify.client import ShopifyClient
from .utils import get_variant_by_id

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
            from .sync_tasks import sync_product
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