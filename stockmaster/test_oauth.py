#!/usr/bin/env python
"""
Test script to manually go through the Shopify OAuth flow.
This will guide you through the process of authorizing the app and obtaining a valid token.
"""
import os
import sys
import django
import logging
import requests
import json
import secrets
import webbrowser
from urllib.parse import urlencode
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

# Import Django settings
from django.conf import settings
from apps.accounts.models import ShopifyStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Default shop domain
SHOP_DOMAIN = 'devdevkira.myshopify.com'
# The port our callback server will listen on
CALLBACK_PORT = 3456
# Flag to indicate when we've received the OAuth callback
callback_received = False
# Code from the callback
auth_code = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global callback_received, auth_code
        
        # Parse query parameters
        from urllib.parse import urlparse, parse_qs
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        # Get the authorization code
        if 'code' in params:
            auth_code = params['code'][0]
            logger.info(f"Received authorization code: {auth_code}")
            
            # Exchange the code for an access token
            shop = SHOP_DOMAIN
            access_token = exchange_code_for_token(shop, auth_code)
            
            if access_token:
                logger.info(f"Successfully obtained access token: {access_token[:5]}...{access_token[-5:]}")
                
                # Update the store in the database
                try:
                    store, created = ShopifyStore.objects.update_or_create(
                        shop_url=shop,
                        defaults={
                            'access_token': access_token,
                            'is_active': True
                        }
                    )
                    logger.info(f"{'Created' if created else 'Updated'} store {shop} with new access token")
                except Exception as e:
                    logger.error(f"Error updating store: {str(e)}")
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                <html><body>
                <h1>Authorization Successful</h1>
                <p>You have successfully authorized the app. You can close this window and return to the terminal.</p>
                </body></html>
                """)
            else:
                # Send error response
                self.send_response(500)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                <html><body>
                <h1>Authorization Failed</h1>
                <p>Failed to exchange the authorization code for an access token. Please try again.</p>
                </body></html>
                """)
        else:
            # Send error response
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
            <html><body>
            <h1>Missing Code</h1>
            <p>The authorization code was not provided. Please try again.</p>
            </body></html>
            """)
        
        # Signal that we've received the callback
        callback_received = True

def exchange_code_for_token(shop, code):
    """Exchange the authorization code for a permanent access token."""
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

def start_callback_server():
    """Start a local server to handle the OAuth callback."""
    server = HTTPServer(('localhost', CALLBACK_PORT), OAuthCallbackHandler)
    
    # Run the server in a separate thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    logger.info(f"Started callback server on port {CALLBACK_PORT}")
    
    return server

def main():
    """Main function to run the OAuth flow test."""
    logger.info("=== Shopify OAuth Flow Test ===")
    
    # Check if we already have a valid token
    try:
        store = ShopifyStore.objects.get(shop_url=SHOP_DOMAIN)
        logger.info(f"Found existing store: {store.shop_url}")
        logger.info(f"Current access token: {store.access_token[:5]}...{store.access_token[-5:] if store.access_token else 'None'}")
    except ShopifyStore.DoesNotExist:
        logger.info(f"No existing store found for {SHOP_DOMAIN}")
    
    # Start the callback server
    server = start_callback_server()
    
    # Generate a random state parameter for security
    state = secrets.token_hex(16)
    
    # Build the authorization URL
    redirect_uri = f"http://localhost:{CALLBACK_PORT}/callback"
    scopes = settings.SHOPIFY_API_SCOPES
    
    query_params = {
        'client_id': settings.SHOPIFY_CLIENT_ID,
        'scope': scopes,
        'redirect_uri': redirect_uri,
        'state': state
    }
    auth_url = f"https://{SHOP_DOMAIN}/admin/oauth/authorize?{urlencode(query_params)}"
    
    logger.info(f"Opening browser to authorize app...")
    logger.info(f"Authorization URL: {auth_url}")
    
    # Open the browser to start the OAuth flow
    webbrowser.open(auth_url)
    
    logger.info("Waiting for callback...")
    
    # Wait for the callback to be received
    try:
        while not callback_received:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    finally:
        # Shutdown the server
        server.shutdown()
    
    logger.info("OAuth flow test completed")

if __name__ == "__main__":
    main() 