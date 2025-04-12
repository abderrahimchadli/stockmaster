import json
import requests
from urllib.parse import urlencode
import hmac
import hashlib
import base64
import time
from django.conf import settings
from core.utils.logger import logger

class ShopifyClient:
    """
    Client for interacting with the Shopify API.
    Handles authentication, API calls, and webhook verification.
    """
    
    @staticmethod
    def get_install_url(shop, redirect_uri, state=None):
        """
        Generate the Shopify app installation URL for OAuth flow.
        
        Args:
            shop (str): The shop's myshopify domain
            redirect_uri (str): The redirect URI after authentication
            state (str, optional): A randomly generated state parameter for security
            
        Returns:
            str: The Shopify authorization URL
        """
        scopes = settings.SHOPIFY_API_SCOPES
        client_id = settings.SHOPIFY_CLIENT_ID
        
        query_params = {
            'client_id': client_id,
            'scope': scopes,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
        }
        
        if state:
            query_params['state'] = state
        
        return f"https://{shop}/admin/oauth/authorize?{urlencode(query_params)}"
    
    @staticmethod
    def get_access_token(shop, code):
        """
        Exchange authorization code for permanent access token.
        
        Args:
            shop (str): The shop's myshopify domain
            code (str): The authorization code from Shopify
            
        Returns:
            str: The permanent access token or None if an error occurs
        """
        url = f"https://{shop}/admin/oauth/access_token"
        payload = {
            'client_id': settings.SHOPIFY_CLIENT_ID,
            'client_secret': settings.SHOPIFY_CLIENT_SECRET,
            'code': code
        }
        
        try:
            response = requests.post(url, json=payload)
            response_data = response.json()
            
            if 'access_token' in response_data:
                return response_data['access_token']
            else:
                logger.error(f"Error getting access token: {response_data}")
                return None
                
        except Exception as e:
            logger.error(f"Exception getting access token: {str(e)}")
            return None
    
    @staticmethod
    def verify_webhook(data, hmac_header):
        """
        Verify webhook request from Shopify using HMAC validation.
        
        Args:
            data (bytes): Raw request body data
            hmac_header (str): X-Shopify-Hmac-SHA256 header value
            
        Returns:
            bool: True if the webhook is valid, False otherwise
        """
        digest = hmac.new(
            settings.SHOPIFY_CLIENT_SECRET.encode('utf-8'),
            data,
            hashlib.sha256
        ).digest()
        
        computed_hmac = base64.b64encode(digest).decode('utf-8')
        return hmac.compare_digest(computed_hmac, hmac_header)
    
    def __init__(self, shop_url, access_token):
        """
        Initialize the Shopify client with shop URL and access token.
        
        Args:
            shop_url (str): The shop's myshopify domain
            access_token (str): The shop's access token
        """
        self.shop_url = shop_url
        self.access_token = access_token
        self.base_url = f"https://{shop_url}/admin/api/2024-01"  # Use latest stable API version
    
    def _request(self, method, endpoint, data=None, params=None):
        """
        Make a request to the Shopify API.
        
        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE)
            endpoint (str): API endpoint
            data (dict, optional): Request body for POST/PUT requests
            params (dict, optional): Query parameters
            
        Returns:
            dict: Response data or None if an error occurs
        """
        headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, headers=headers, data=json.dumps(data), params=params)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, data=json.dumps(data), params=params)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                logger.warning(f"Rate limited. Retrying after {retry_after} seconds")
                time.sleep(retry_after)
                return self._request(method, endpoint, data, params)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {str(e)}")
            return None
    
    # Inventory related methods
    def get_products(self, params=None):
        """Get products from the shop"""
        return self._request('GET', '/products.json', params=params)
    
    def get_product(self, product_id):
        """Get a specific product"""
        return self._request('GET', f'/products/{product_id}.json')
    
    def update_product(self, product_id, data):
        """Update a product"""
        return self._request('PUT', f'/products/{product_id}.json', data=data)
    
    def get_inventory_levels(self, location_id=None, inventory_item_ids=None):
        """Get inventory levels"""
        params = {}
        if location_id:
            params['location_id'] = location_id
        if inventory_item_ids:
            params['inventory_item_ids'] = ','.join(map(str, inventory_item_ids))
        
        return self._request('GET', '/inventory_levels.json', params=params)
    
    def get_inventory_item(self, inventory_item_id):
        """Get a specific inventory item"""
        return self._request('GET', f'/inventory_items/{inventory_item_id}.json')
    
    def update_inventory_item(self, inventory_item_id, data):
        """Update an inventory item"""
        return self._request('PUT', f'/inventory_items/{inventory_item_id}.json', data=data)
    
    def adjust_inventory_level(self, location_id, inventory_item_id, available_adjustment):
        """Adjust inventory level"""
        data = {
            'location_id': location_id,
            'inventory_item_id': inventory_item_id,
            'available_adjustment': available_adjustment
        }
        return self._request('POST', '/inventory_levels/adjust.json', data=data)
    
    # Webhook management methods
    def create_webhook(self, topic, address):
        """Create a webhook subscription"""
        data = {
            'webhook': {
                'topic': topic,
                'address': address,
                'format': 'json'
            }
        }
        return self._request('POST', '/webhooks.json', data=data)
    
    def get_webhooks(self):
        """Get all webhooks"""
        return self._request('GET', '/webhooks.json')
    
    def delete_webhook(self, webhook_id):
        """Delete a webhook"""
        return self._request('DELETE', f'/webhooks/{webhook_id}.json')
    
    # GraphQL API method
    def graphql(self, query, variables=None):
        """Execute a GraphQL query"""
        url = f"https://{self.shop_url}/admin/api/2024-01/graphql.json"
        headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        
        payload = {'query': query}
        if variables:
            payload['variables'] = variables
            
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GraphQL request error: {str(e)}")
            return None 