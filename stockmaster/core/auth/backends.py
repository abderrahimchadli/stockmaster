import jwt
import logging
import traceback
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.backends import BaseBackend
from apps.accounts.models import ShopifyStore

logger = logging.getLogger(__name__)

class ShopifyJWTBackend(BaseBackend):
    """
    Custom authentication backend for Shopify JWT tokens.
    This allows us to authenticate users via the Shopify JWT token
    without requiring them to explicitly log in via Django's system.
    """
    
    def authenticate(self, request, token=None, **kwargs):
        """
        Authenticate a user based on the Shopify JWT token.
        """
        try:
            if not token:
                # Try to get the token from the request if not provided
                if request:
                    # Check Authorization header
                    auth_header = request.headers.get('Authorization')
                    if auth_header and auth_header.startswith('Bearer '):
                        token = auth_header.split(' ')[1]
                    else:
                        # Check for id_token in request params
                        token = request.GET.get('id_token')
                
                if not token:
                    # No token found
                    logger.debug("[ShopifyJWTBackend] No token found in request")
                    return None
            
            logger.debug(f"[ShopifyJWTBackend] Attempting to authenticate with token: {token[:10]}...")
            
            try:
                # Verify the token
                payload = jwt.decode(
                    token,
                    settings.SHOPIFY_CLIENT_SECRET,
                    algorithms=["HS256"],
                    audience=settings.SHOPIFY_CLIENT_ID,
                    options={"verify_exp": True, "verify_aud": True}
                )
                
                # Extract shop domain
                shop = payload.get('dest', '').replace('https://', '')
                if not shop:
                    logger.warning("[ShopifyJWTBackend] JWT token missing shop domain")
                    return None
                
                logger.debug(f"[ShopifyJWTBackend] JWT payload validated for shop: {shop}")
                
                # Find the store in our database
                try:
                    store = ShopifyStore.objects.get(shop_url=shop, is_active=True)
                    
                    # Get or create a Django user for this store
                    # We use the shop URL as the username since it's unique
                    # This allows us to have a proper Django user for auth
                    user, created = User.objects.get_or_create(
                        username=shop,
                        defaults={
                            'email': store.shop_email or f"{shop}@example.com",
                            'is_active': True,
                        }
                    )
                    
                    if created:
                        logger.info(f"[ShopifyJWTBackend] Created new user for store: {shop}")
                    
                    logger.debug(f"[ShopifyJWTBackend] Successfully authenticated user for shop: {shop}")
                    # Return the user for authentication
                    return user
                    
                except ShopifyStore.DoesNotExist:
                    logger.warning(f"[ShopifyJWTBackend] Store not found in database: {shop}")
                    return None
                except Exception as e:
                    logger.error(f"[ShopifyJWTBackend] Error looking up store: {str(e)}")
                    logger.error(traceback.format_exc())
                    return None
                    
            except jwt.ExpiredSignatureError as e:
                logger.warning(f"[ShopifyJWTBackend] JWT token expired: {str(e)}")
            except jwt.InvalidAudienceError as e:
                logger.warning(f"[ShopifyJWTBackend] JWT audience invalid: {str(e)}")
            except jwt.InvalidTokenError as e:
                logger.error(f"[ShopifyJWTBackend] Invalid JWT token: {str(e)}")
            except Exception as e:
                logger.error(f"[ShopifyJWTBackend] Error decoding JWT token: {str(e)}")
                logger.error(traceback.format_exc())
            
            return None
            
        except Exception as e:
            # Catch any unexpected exceptions to prevent 500 errors
            logger.error(f"[ShopifyJWTBackend] Unexpected authentication error: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    def get_user(self, user_id):
        """
        Get the user by ID.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning(f"[ShopifyJWTBackend] User {user_id} not found")
            return None
        except Exception as e:
            logger.error(f"[ShopifyJWTBackend] Error getting user {user_id}: {str(e)}")
            logger.error(traceback.format_exc())
            return None 