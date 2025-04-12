import re
import logging
import hmac
import hashlib
import base64
import jwt
from urllib.parse import parse_qs, urlencode
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseForbidden, JsonResponse
from django.contrib.auth import authenticate, login

logger = logging.getLogger(__name__)

class ShopifyAuthMiddleware:
    """
    Middleware to handle Shopify embedded app authentication and embedding concerns.
    This middleware:
    1. Allows public paths without authentication
    2. Handles initial OAuth flow (HMAC verification)
    3. Adds necessary headers for Shopify embedding
    
    Authentication is handled by JWTAuthenticationMiddleware, this middleware
    only handles Shopify-specific embedding concerns.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Public paths regex patterns
        self.public_paths = [
            re.compile(r'^/admin/.*'),
            re.compile(r'^/auth/.*'),
            re.compile(r'^/accounts/login/?$'),
            re.compile(r'^/accounts/callback/?$'),
            re.compile(r'^/auth/callback/?$'),
            re.compile(r'^/auth/shopify/callback/?$'),
            re.compile(r'^/shopify/callback/?$'),
            re.compile(r'^/webhooks/.*'),
            re.compile(r'^/static/.*'),
            re.compile(r'^/__debug__/.*'),
            re.compile(r'^/$'),                  # Allow root path
            re.compile(r'^/accounts/?$'),        # Allow accounts landing
            re.compile(r'^/accounts/landing/?$'), # Allow explicit landing page
            re.compile(r'^/api/.*'),             # Allow API access
            re.compile(r'^.*\.js$'),             # Allow JavaScript files
            re.compile(r'^.*\.css$'),            # Allow CSS files
            re.compile(r'^.*\.map$'),            # Allow source maps
            re.compile(r'^.*favicon\.ico$'),     # Allow favicon
            re.compile(r'^.*\.png$'),            # Allow image files
            re.compile(r'^.*\.jpg$'),            # Allow image files
            re.compile(r'^.*\.svg$'),            # Allow image files
            re.compile(r'^.*\.gif$'),            # Allow image files
        ]
    
    def __call__(self, request):
        """Main middleware handling."""
        # Store reference to the request
        self.request = request
        path = request.path
        
        # 1. Allow public paths without auth
        if self.is_public_path(path):
            logger.debug(f"[ShopifyAuthMiddleware] Path {path} is public, skipping auth")
            response = self.get_response(request)
            
            # Even for public paths, if embedded=1, we need to add headers
            if request.GET.get('embedded') == '1':
                shop = request.GET.get('shop')
                if shop:
                    response = self.add_shopify_headers(response, shop)
            
            return response

        # 2. Handle initial OAuth requests with HMAC
        # This is for the initial handshake when Shopify loads your app
        shop = request.GET.get('shop')
        hmac = request.GET.get('hmac')
        
        if shop and hmac:
            logger.debug(f"[ShopifyAuthMiddleware] HMAC check - Shop: {shop}, HMAC present: {bool(hmac)}")
            
            # If valid HMAC, let the request through to handle OAuth flow
            if self.verify_hmac_params(request.GET):
                logger.debug("[ShopifyAuthMiddleware] HMAC verification successful")
                response = self.get_response(request)
                response = self.add_shopify_headers(response, shop)
                return response
            else:
                logger.warning("[ShopifyAuthMiddleware] HMAC verification failed")
                return self.auth_failed(request, "Invalid HMAC signature")
        
        # 3. Normal authenticated request flow
        # Allow the request to proceed to other middleware/view
        response = self.get_response(request)
        
        # 4. Add Shopify embedding headers for embedded requests
        if request.GET.get('embedded') == '1':
            # If we have a shop in session or request, add headers
            shop = request.session.get('shop') or request.GET.get('shop')
            if shop:
                response = self.add_shopify_headers(response, shop)
        
        return response
    
    def is_public_path(self, path):
        """Check if the path is public and should bypass authentication."""
        for pattern in self.public_paths:
            if pattern.match(path):
                return True
        return False
    
    def verify_hmac_params(self, params):
        """Verify HMAC signature from query parameters."""
        params_copy = params.copy()
        hmac_value = params_copy.pop('hmac', None)
        
        # Extract the first value if hmac is a list
        if isinstance(hmac_value, list):
            hmac_value = hmac_value[0]

        if not hmac_value:
            logger.warning("HMAC missing from parameters during initial auth check.")
            return False

        # Remove parameters that should not be included in HMAC validation
        params_copy.pop('id_token', None)
        params_copy.pop('session', None)
        params_copy.pop('embedded', None)

        # Convert QueryDict to regular dict with single values
        param_dict = {}
        for key, value in params_copy.items():
            # Handle both single values and lists (use first item if list)
            if isinstance(value, list):
                param_dict[key] = value[0]
            else:
                param_dict[key] = value
            
            # Ensure all values are strings
            param_dict[key] = str(param_dict[key])

        # Create a string of key=value pairs sorted by key
        sorted_params = []
        for key in sorted(param_dict.keys()):
            sorted_params.append(f"{key}={param_dict[key]}")
        
        message = '&'.join(sorted_params)

        try:
            # Get client secret from settings
            client_secret = settings.SHOPIFY_CLIENT_SECRET
            
            digest = hmac.new(
                client_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            is_valid = hmac.compare_digest(digest, hmac_value)
            if not is_valid:
                logger.warning(f"HMAC mismatch. Calculated: {digest}, Received: {hmac_value}")
            return is_valid
        except Exception as e:
            logger.error(f"Error verifying param HMAC: {e}")
            return False
    
    def add_shopify_headers(self, response, shop):
        """Add required headers for Shopify embedding."""
        # Remove X-Frame-Options to allow embedding in Shopify admin
        if 'X-Frame-Options' in response:
            del response['X-Frame-Options']
            
        # Add Content-Security-Policy to allow framing only from Shopify
        response['Content-Security-Policy'] = "frame-ancestors https://*.myshopify.com https://admin.shopify.com;"
        
        return response
        
    def auth_failed(self, request, reason):
        """Handle authentication failure."""
        logger.warning(f"[ShopifyAuthMiddleware] Auth failed: {reason} for path: {request.path}")
        
        # Check if this is an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('ajax') == '1'
        is_embedded = request.GET.get('embedded') == '1'
        shop = request.GET.get('shop') or request.session.get('shop')
        
        # For AJAX requests, return a JSON response
        if is_ajax:
            return JsonResponse({
                "error": reason,
                "auth_required": True,
                "login_url": f"/accounts/login/?shop={shop}" if shop else "/accounts/login/"
            }, status=401)
        
        # For embedded requests, return minimal HTML
        if is_embedded:
            simple_html = f"""
            <!DOCTYPE html>
            <html>
            <head><title>Authentication Failed</title></head>
            <body>
                <h1>Authentication Required</h1>
                <p>{reason}. Please try refreshing the page or reinstalling the app.</p>
            </body>
            </html>
            """
            return HttpResponseForbidden(simple_html, content_type="text/html")
        
        # For regular requests, redirect to login
        login_url = f"/accounts/login/?shop={shop}" if shop else "/accounts/login/"
        return redirect(login_url) 