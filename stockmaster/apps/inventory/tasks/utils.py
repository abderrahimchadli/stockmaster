from datetime import datetime
import logging

logger = logging.getLogger(__name__)

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


def parse_shopify_datetime(datetime_str):
    """Parse a Shopify datetime string into a Python datetime object."""
    if not datetime_str:
        return None
    
    try:
        # Shopify datetime format: 2023-01-01T12:00:00-00:00
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


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
import logging

logger = logging.getLogger(__name__)

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


def parse_shopify_datetime(datetime_str):
    """Parse a Shopify datetime string into a Python datetime object."""
    if not datetime_str:
        return None
    
    try:
        # Shopify datetime format: 2023-01-01T12:00:00-00:00
        return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


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