import logging
import jwt
import traceback
from django.contrib.auth import authenticate, login
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger(__name__)

class JWTAuthenticationMiddleware(MiddlewareMixin):
    """
    Primary middleware for authenticating users with Shopify JWT tokens.
    
    This middleware:
    1. Extracts JWT tokens from various sources (headers, query params)
    2. Authenticates users with Django's auth system
    3. Maintains session state for subsequent requests
    4. Handles token storage for AJAX requests
    """
    
    def process_request(self, request):
        """
        Early pre-processing of the request to ensure user attribute exists.
        This is a safety measure in case the middleware runs before Django's AuthenticationMiddleware.
        """
        try:
            # Check if JWT token exists and store it for later use
            jwt_token = self._extract_jwt_token(request)
            if jwt_token:
                # Store the token in the request object for later use
                request._jwt_token = jwt_token
                
            # DO NOT try to access request.user here, as it might not be set yet
            return None  # Continue processing
        except Exception as e:
            # Log the error but don't crash the request
            logger.error(f"[JWTAuthMiddleware] Error in process_request: {str(e)}")
            logger.error(traceback.format_exc())
            return None  # Continue processing
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Process the view after Django's AuthenticationMiddleware has set up the user.
        This ensures request.user is available.
        """
        try:
            # Skip if user is already authenticated
            if hasattr(request, 'user') and request.user.is_authenticated:
                # Even if authenticated, ensure we have the shop in session
                self._ensure_shop_in_session(request)
                return None  # Continue to the view
            
            # If user attribute is not set, log a warning but don't crash
            if not hasattr(request, 'user'):
                logger.warning("[JWTAuthMiddleware] request.user not available in process_view")
                return None  # Continue to the view
            
            # Get JWT token (either from request._jwt_token or extract it again)
            jwt_token = getattr(request, '_jwt_token', None) or self._extract_jwt_token(request)
            
            if not jwt_token:
                # No token found, can't authenticate
                logger.debug("[JWTAuthMiddleware] No JWT token found in request")
                return None  # Continue to the view
            
            # Try to authenticate with the token
            user = authenticate(request=request, token=jwt_token)
            
            if user:
                # User authenticated, log them in with Django's auth system
                login(request, user)
                logger.debug(f"[JWTAuthMiddleware] User '{user.username}' authenticated successfully")
                
                # Store token and shop info in session
                self._store_token_data(request, jwt_token, user.username)
            else:
                logger.warning("[JWTAuthMiddleware] JWT token authentication failed")
                
            return None  # Continue to the view
        except Exception as e:
            # Log the error but don't crash the request
            logger.error(f"[JWTAuthMiddleware] Error in process_view: {str(e)}")
            logger.error(traceback.format_exc())
            return None  # Continue to the view
    
    def _extract_jwt_token(self, request):
        """
        Extract JWT token from multiple possible sources in priority order:
        1. Authorization header
        2. id_token query parameter
        3. Session storage
        """
        try:
            # 1. Check Authorization header (best practice)
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                logger.debug("[JWTAuthMiddleware] Found JWT token in Authorization header")
                return auth_header.split(' ')[1]
            
            # 2. Check for id_token in request params (Shopify standard)
            id_token = request.GET.get('id_token')
            if id_token:
                logger.debug("[JWTAuthMiddleware] Found JWT token in id_token parameter")
                return id_token
            
            # 3. Check for token in session
            if hasattr(request, 'session'):
                session_token = request.session.get('shopify_jwt_token')
                if session_token:
                    logger.debug("[JWTAuthMiddleware] Found JWT token in session")
                    return session_token
            
            # No token found
            return None
        except Exception as e:
            logger.error(f"[JWTAuthMiddleware] Error extracting JWT token: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def _store_token_data(self, request, token, shop):
        """
        Store token and shop data in session for future requests.
        This ensures consistent authentication state across requests.
        """
        try:
            # Make sure we have a session
            if not hasattr(request, 'session'):
                logger.warning("[JWTAuthMiddleware] No session available to store token data")
                return
                
            # Store the token in session
            request.session['shopify_jwt_token'] = token
            
            # Store shop domains for compatibility with the rest of the app
            request.session['shop'] = shop
            request.session['shopify_shop'] = shop
            
            try:
                # Extract token data without verification for additional info
                unverified_payload = jwt.decode(token, options={"verify_signature": False})
                
                # Store token expiry if available
                if 'exp' in unverified_payload:
                    request.session['token_expiry'] = unverified_payload['exp']
            except Exception as e:
                logger.warning(f"[JWTAuthMiddleware] Error decoding token payload: {str(e)}")
                
            # Save the session to ensure persistence
            try:
                request.session.save()
            except Exception as e:
                logger.warning(f"[JWTAuthMiddleware] Error saving session: {str(e)}")
            
            logger.debug(f"[JWTAuthMiddleware] Stored JWT token and shop data in session: {shop}")
        except Exception as e:
            logger.error(f"[JWTAuthMiddleware] Error storing token data: {str(e)}")
            logger.error(traceback.format_exc())
            
    def _ensure_shop_in_session(self, request):
        """
        Ensure shop information is in session even if user is already authenticated.
        This helps with Shopify embedding and app navigation.
        """
        try:
            # If user is authenticated but shop isn't in session, add it
            if request.user.is_authenticated and hasattr(request, 'session'):
                if not request.session.get('shop'):
                    # Use username as shop (our auth backend sets username = shop_url)
                    shop = request.user.username
                    request.session['shop'] = shop
                    request.session['shopify_shop'] = shop
                    try:
                        request.session.save()
                    except Exception as e:
                        logger.warning(f"[JWTAuthMiddleware] Error saving session: {str(e)}")
                    logger.debug(f"[JWTAuthMiddleware] Added missing shop to session: {shop}")
        except Exception as e:
            logger.error(f"[JWTAuthMiddleware] Error ensuring shop in session: {str(e)}")
            logger.error(traceback.format_exc()) 