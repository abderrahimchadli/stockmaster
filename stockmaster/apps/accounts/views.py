import secrets
import datetime
from django.shortcuts import render, redirect
from django.views import View
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import logging
import requests
import json
import hmac
import hashlib
import base64
import os
import time
import urllib.parse

from .models import ShopifyStore, ShopifyWebhook
from core.shopify.client import ShopifyClient
from core.utils.logger import logger
from apps.inventory.tasks import sync_store_data

logger = logging.getLogger(__name__)


def install_app(request):
    """
    Initiates the Shopify OAuth process with a simple redirect.
    """
    shop = request.GET.get('shop')  # e.g. my-store.myshopify.com
    if not shop:
        return render(request, 'accounts/login.html')
    
    # Normalize shop URL
    if not shop.endswith('.myshopify.com'):
        shop = f"{shop}.myshopify.com"
    
    # Generate a state parameter to prevent CSRF
    state = secrets.token_hex(16)
    request.session['shopify_auth_state'] = state
    request.session['shopify_shop'] = shop
    
    # Build redirection URL with proper components
    api_key = settings.SHOPIFY_CLIENT_ID
    scopes = settings.SHOPIFY_API_SCOPES
    
    # IMPORTANT: Use the exact callback URL registered in Shopify (with trailing slash)
    redirect_uri = "https://cloud-549585597.onetsolutions.network/auth/callback/"
    
    # Construct the install URL with URLEncoded redirect URI
    install_url = f"https://{shop}/admin/oauth/authorize?client_id={api_key}&scope={scopes}&redirect_uri={urllib.parse.quote(redirect_uri)}&state={state}"
    
    # Log the URL for debugging
    logger.info(f"Redirecting to Shopify OAuth URL: {install_url}")
    
    return redirect(install_url)


@csrf_exempt
def auth_callback(request):
    """
    Handle the OAuth callback from Shopify.
    """
    # Get parameters from request
    code = request.GET.get('code')
    shop = request.GET.get('shop')
    state = request.GET.get('state')
    hmac = request.GET.get('hmac')
    
    logger.info(f"[Callback] Received - Shop: {shop}, State: {state}, Code: {bool(code)}, HMAC: {bool(hmac)}")
    
    # 1. Validate state
    stored_state = request.session.get('shopify_auth_state')
    if not state or state != stored_state:
        logger.error(f"[Callback] State mismatch: Expected {stored_state}, Got {state}")
        return render(request, 'accounts/error.html', {'error': 'Invalid state parameter'})
    logger.info("[Callback] State validation successful.")
    
    # 2. Verify HMAC
    if not hmac_is_valid(request.GET):
        logger.error(f"[Callback] HMAC verification failed.")
        return render(request, 'accounts/error.html', {'error': 'HMAC verification failed'})
    logger.info("[Callback] HMAC verification successful.")

    # 3. Exchange code for access token
    access_token = exchange_code_for_token(shop, code)
    if not access_token:
        logger.error(f"[Callback] Failed to exchange code for access token for shop: {shop}")
        return render(request, 'accounts/error.html', {'error': 'Failed to get access token'})
    logger.info(f"[Callback] Successfully obtained access token for shop: {shop} (Token: {access_token[:5]}...{access_token[-5:]})")

    # 4. Get shop details (Optional but good)
    shop_details = get_shop_details(shop, access_token)
    shop_name = shop_details.get('name', shop) if shop_details else shop
    shop_email = shop_details.get('email') if shop_details else None
    logger.info(f"[Callback] Shop details - Name: {shop_name}, Email: {shop_email}")

    # 5. Save or Update Store Information in Database
    store = None
    try:
        store, created = ShopifyStore.objects.update_or_create(
            shop_url=shop,
            defaults={
                'access_token': access_token,
                'shop_name': shop_name,
                'shop_email': shop_email,
                'is_active': True, # Ensure it's active
                'scopes': settings.SHOPIFY_API_SCOPES,
                'last_access': timezone.now(),
                'installed_at': timezone.now() if created else F('installed_at'),
                'trial_ends_at': timezone.now() + datetime.timedelta(days=settings.TRIAL_DAYS) if created else None,
                'sync_status': 'pending' # Set initial sync status
            }
        )
        if store and store.id:
            logger.info(f"[Callback][DB Save SUCCESS] {'Created' if created else 'Updated'} ShopifyStore record. ID: {store.id}, Shop: {store.shop_url}, Active: {store.is_active}, Token Saved: {bool(store.access_token)}")
        else:
            logger.error("[Callback][DB Save FAILED] update_or_create finished but store object or ID is invalid.")
            # Optionally raise an exception here or return error

    except Exception as e:
        logger.error(f"[Callback][DB Save EXCEPTION] Error saving store {shop} to database: {str(e)}", exc_info=True)
        return render(request, 'accounts/error.html', {'error': 'Error processing store information in database.'})

    # Ensure we have a valid store object after saving
    if not store or not store.id:
        logger.error("[Callback] Store object is invalid after DB save attempt. Cannot proceed.")
        return render(request, 'accounts/error.html', {'error': 'Failed to properly save store information.'})

    # 6. Store necessary info in session for app usage
    request.session['shop'] = store.shop_url
    request.session['store_id'] = store.id
    request.session.pop('shopify_auth_state', None) # Clean up state
    request.session.pop('shopify_shop', None)
    logger.info(f"[Callback] Session updated for store ID: {store.id}")

    # 7. Setup Webhooks
    try:
        client = ShopifyClient(shop, access_token)
        setup_webhooks(client, store)
        logger.info(f"[Callback] Webhook setup completed for store ID: {store.id}")
    except Exception as e:
        logger.error(f"[Callback] Error setting up webhooks for store {store.id}: {str(e)}", exc_info=True)
        # Don't fail the whole callback for webhook setup issues

    # 8. Trigger Initial Data Sync (Async)
    try:
        sync_store_data.delay(store.id)
        store.sync_status = 'pending'
        store.save(update_fields=['sync_status'])
        logger.info(f"[Callback] Triggered background sync task for store ID: {store.id}")
    except Exception as e:
        logger.error(f"[Callback] Error triggering background sync for store {store.id}: {str(e)}", exc_info=True)

    # 9. Redirect to app in Shopify Admin
    admin_url = f"https://{shop}/admin/apps/{settings.SHOPIFY_CLIENT_ID}"
    logger.info(f"[Callback] Redirecting to app main page: {admin_url}")
    return redirect(admin_url)

# Add the missing AuthCallbackView class
class AuthCallbackView(View):
    """
    Class-based view for handling the OAuth callback from Shopify.
    This is a wrapper around the auth_callback function for use in urls.py.
    """
    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
        
    def get(self, request):
        """Handle GET requests for the OAuth callback"""
        return auth_callback(request)
        
    def post(self, request):
        """Handle POST requests for the OAuth callback (shouldn't happen but just in case)"""
        return auth_callback(request)

# --- Helper Functions (Refactored & Added) ---

def hmac_is_valid(query_params):
    """Verify the HMAC signature from Shopify using manual calculation."""
    hmac_value = query_params.get('hmac')
    if not hmac_value:
        logger.warning("[HMAC] No HMAC value found in query parameters.")
        return False # Or raise error, depending on strictness needed

    # Create a dictionary of parameters excluding hmac
    params_copy = query_params.copy()
    params_copy.pop('hmac', None)
    
    # Sort the parameters and create the message string
    sorted_params = sorted(params_copy.items())
    message = '&'.join([f"{key}={value}" for key, value in sorted_params])
    
    # Calculate the HMAC
    try:
        digest = hmac.new(
            settings.SHOPIFY_CLIENT_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        is_valid = hmac.compare_digest(digest, hmac_value)
        if not is_valid:
            logger.warning(f"[HMAC] Mismatch. Computed: {digest}, Received: {hmac_value}")
        return is_valid
    except Exception as e:
        logger.error(f"[HMAC] Error during HMAC calculation: {str(e)}", exc_info=True)
        return False

def exchange_code_for_token(shop, code):
    """Exchange authorization code for permanent access token"""
    access_token_url = f"https://{shop}/admin/oauth/access_token"
    payload = {
        "client_id": settings.SHOPIFY_CLIENT_ID,
        "client_secret": settings.SHOPIFY_CLIENT_SECRET,
        "code": code
    }
    try:
        response = requests.post(access_token_url, json=payload, timeout=15)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        access_token = data.get('access_token')
        if not access_token:
            logger.error(f"[Token Exchange] Access token not found in response: {data}")
            return None
        return access_token
    except requests.exceptions.RequestException as e:
        logger.error(f"[Token Exchange] Error: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"[Token Exchange] Response Body: {e.response.text}")
        return None

def get_shop_details(shop, access_token):
    """Fetch shop details (name, email) using the Admin API."""
    client = ShopifyClient(shop, access_token)
    try:
        # Use REST endpoint for simplicity here
        response = client._request('GET', '/shop.json')
        if response and 'shop' in response:
            return response['shop']
        else:
            logger.warning(f"[Shop Details] Could not fetch shop details. Response: {response}")
            return None
    except Exception as e:
        logger.error(f"[Shop Details] Error fetching details: {str(e)}")
        return None

def setup_webhooks(client, store):
    """Set up essential webhooks (e.g., app/uninstalled)."""
    required_webhooks = {
        'app/uninstalled': f"{settings.APP_URL}/webhooks/app_uninstalled/",
        # Add other essential webhooks here if needed
        # 'products/update': f"{settings.APP_URL}/webhooks/products_update/",
    }
    
    try:
        existing_webhooks = client.get_webhooks()
        existing_topics = []
        if existing_webhooks and 'webhooks' in existing_webhooks:
            existing_topics = [wh['topic'] for wh in existing_webhooks['webhooks']]
        
        for topic, address in required_webhooks.items():
            if topic not in existing_topics:
                logger.info(f"[Webhooks] Creating webhook for topic: {topic}")
                response = client.create_webhook(topic, address)
                if response and 'webhook' in response:
                    # Save webhook details (optional but good practice)
                    ShopifyWebhook.objects.update_or_create(
                        store=store,
                        topic=topic,
                        defaults={
                            'webhook_id': response['webhook']['id'],
                            'address': address
                        }
                    )
                    logger.info(f"[Webhooks] Successfully created webhook for {topic}")
                else:
                    logger.error(f"[Webhooks] Failed to create webhook for {topic}. Response: {response}")
            else:
                logger.info(f"[Webhooks] Webhook for topic {topic} already exists.")
        
    except Exception as e:
        logger.error(f"[Webhooks] Error during setup: {str(e)}", exc_info=True)
        # Don't necessarily fail the whole callback for this

class LogoutView(View):
    """
    Log out the current shop.
    """
    def get(self, request):
        # Clear the shop from session
        if 'shop' in request.session:
            del request.session['shop']
        
        # Clear any other session data
        request.session.flush()
        
        # Redirect to login page
        return redirect('accounts:login')


def landing_page(request):
    """
    Landing page for the app - entry point for installation
    """
    shop = request.GET.get('shop')
    if not shop:
        # Show generic landing page if no shop parameter
        return render(request, 'accounts/landing.html')
    
    # Check if this is a valid Shopify shop
    if not shop.endswith('.myshopify.com'):
        return HttpResponse("Invalid shop parameter", status=400)
    
    # Start OAuth process for Shopify
    api_key = settings.SHOPIFY_CLIENT_ID
    scopes = settings.SHOPIFY_API_SCOPES
    redirect_uri = f"{settings.APP_URL}/auth/callback/"
    state = create_nonce()
    
    # Store the state in session for validation
    request.session['shopify_auth_state'] = state
    request.session['shopify_shop'] = shop
    
    # Construct authorization URL
    auth_url = f"https://{shop}/admin/oauth/authorize?client_id={api_key}&scope={scopes}&redirect_uri={redirect_uri}&state={state}"
    
    return redirect(auth_url)

@csrf_exempt
def callback(request):
    """
    OAuth callback from Shopify - handles token exchange and triggers initial sync.
    """
    # Get parameters from request
    shop = request.GET.get('shop')
    code = request.GET.get('code')
    state = request.GET.get('state')
    
    logger.info(f"Received callback for shop: {shop}, state: {state}")
    
    # Validate state to prevent CSRF
    stored_state = request.session.get('shopify_auth_state')
    stored_shop = request.session.get('shopify_shop')
    
    if not state or state != stored_state or not shop or shop != stored_shop:
        logger.warning(f"Invalid state or shop mismatch during callback. State: {state} vs {stored_state}, Shop: {shop} vs {stored_shop}")
        return HttpResponse("Invalid request: State mismatch.", status=400)
    
    logger.info("State validation successful.")
    
    # Exchange code for access token
    access_token = exchange_code_for_token(shop, code)
    if not access_token:
        logger.error(f"Failed to exchange code for access token for shop: {shop}")
        return HttpResponse("Failed to get access token", status=400)
    
    logger.info(f"Successfully obtained access token for shop: {shop}")
    
    # Get shop details
    shop_details = get_shop_details(shop, access_token)
    if not shop_details:
        logger.error(f"Failed to get shop details for shop: {shop} after obtaining token.")
        # Decide if this is fatal - maybe proceed without details?
        # return HttpResponse("Failed to get shop details", status=400)
        shop_name = shop # Fallback name
    else:
        shop_name = shop_details.get('name', shop)
        logger.info(f"Successfully retrieved shop details for: {shop_name}")
    
    # --- Save or Update Store Information ---
    try:
        store, created = ShopifyStore.objects.update_or_create(
            shop_url=shop,
            defaults={
                'access_token': access_token,
                'shop_name': shop_name,
                'email': shop_details.get('email') if shop_details else None,
                'is_active': True, # Mark as active upon successful auth
                'installed_at': timezone.now() if created else F('installed_at'), # Keep original install date
                'scopes': settings.SHOPIFY_API_SCOPES # Store the requested scopes
                # Add other fields from shop_details if needed
            }
        )
        logger.info(f"{'Created' if created else 'Updated'} ShopifyStore record for {shop}")

        # Store necessary info in session for app usage
        request.session['shop'] = store.shop_url
        request.session['store_id'] = store.id
        request.session.pop('shopify_auth_state', None) # Clean up state
        request.session.pop('shopify_shop', None)
        request.session.pop('shopify_access_token', None) # Token is in DB now
        
        # --- Trigger Initial Data Sync --- 
        # Use .delay() to run the task asynchronously
        logger.info(f"Triggering initial data sync task for store ID: {store.id}")
        sync_store_data.delay(store.id)
        # Optionally update store status
        store.sync_status = 'pending'
        store.save(update_fields=['sync_status'])
        # --- End Sync Trigger ---
        
        # --- User Association (Optional but Recommended) ---
        # If you have a logged-in user concept separate from the store owner,
        # associate the store with the user here.
        # if request.user.is_authenticated:
        #     store.user = request.user 
        #     store.save()
        # else:
        #     # Maybe create a user based on shop details?
        #     pass 
        # --- End User Association ---

    except Exception as e:
        logger.error(f"Error saving store or triggering sync for {shop}: {str(e)}", exc_info=True)
        return HttpResponse("Error processing store information.", status=500)
    
    # Redirect to app in Shopify Admin
    app_url = f"https://{shop}/admin/apps/{settings.SHOPIFY_CLIENT_ID}"
    logger.info(f"Redirecting to app main page: {app_url}")
    return redirect(app_url)

def create_nonce():
    """Generate a random nonce for OAuth state"""
    return base64.b64encode(os.urandom(16)).decode('utf-8')

@login_required
def index(request):
    """
    Dashboard view (requires login)
    """
    return redirect('dashboard:index')

class LoginView(View):
    """
    View to start the Shopify OAuth flow.
    """
    def get(self, request):
        # If shop isn't provided, show login form
        shop = request.GET.get('shop')
        if not shop:
            return render(request, 'accounts/login.html')
        
        # Normalize shop URL
        if not shop.endswith('.myshopify.com'):
            shop = f"{shop}.myshopify.com"
        
        # Check if we already have a token for this shop
        try:
            store = ShopifyStore.objects.get(shop_url=shop, is_active=True)
            if store.access_token:
                # Store exists and has a token, update session
                request.session['shop'] = shop
                store.update_last_access()
                return redirect('dashboard:index')
        except ShopifyStore.DoesNotExist:
            # Store doesn't exist, will create during callback
            pass
        
        # Generate a state parameter to prevent CSRF
        state = secrets.token_hex(16)
        request.session['state'] = state
        
        # Build the redirect URL
        redirect_uri = request.build_absolute_uri(reverse('accounts:callback'))
        
        # Generate the install URL
        install_url = ShopifyClient.get_install_url(shop, redirect_uri, state)
        
        # Redirect to Shopify for authorization
        return HttpResponseRedirect(install_url)

"""
Closing any potentially unclosed docstring
""" 
