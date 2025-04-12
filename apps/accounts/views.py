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

from .models import ShopifyStore, ShopifyWebhook
from core.shopify.client import ShopifyClient
from core.utils.logger import logger

logger = logging.getLogger(__name__)


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


class AuthCallbackView(View):
    """
    Handle the OAuth callback from Shopify.
    """
    def get(self, request):
        # Verify the state parameter to prevent CSRF
        state = request.GET.get('state')
        if state != request.session.get('state'):
            logger.error("State parameter mismatch")
            messages.error(request, "Invalid state parameter. Please try again.")
            return redirect('accounts:login')
        
        # Clear the state from session
        if 'state' in request.session:
            del request.session['state']
        
        # Get query parameters
        shop = request.GET.get('shop')
        code = request.GET.get('code')
        
        if not shop or not code:
            logger.error("Missing shop or code parameter")
            messages.error(request, "Missing required parameters. Please try again.")
            return redirect('accounts:login')
        
        # Exchange the code for an access token
        access_token = ShopifyClient.get_access_token(shop, code)
        
        if not access_token:
            logger.error(f"Failed to get access token for {shop}")
            messages.error(request, "Failed to authenticate with Shopify. Please try again.")
            return redirect('accounts:login')
        
        # Create or update the store
        store, created = ShopifyStore.objects.update_or_create(
            shop_url=shop,
            defaults={
                'access_token': access_token,
                'is_active': True,
                'last_access': timezone.now(),
            }
        )
        
        # If it's a new store, set up trial period
        if created:
            # Set 14-day trial period
            store.trial_ends_at = timezone.now() + datetime.timedelta(days=14)
            store.save()
            
            # Create a client instance to interact with the Shopify API
            client = ShopifyClient(shop, access_token)
            
            # Set up webhooks
            self._setup_webhooks(client, store)
            
            # Fetch and store shop details
            self._fetch_shop_details(client, store)
        
        # Store shop in session
        request.session['shop'] = shop
        
        # Redirect to the dashboard
        return redirect('dashboard:index')
    
    def _setup_webhooks(self, client, store):
        """
        Set up the required webhooks for the store.
        """
        try:
            # Define the webhook topics we need
            webhook_topics = [
                'products/update',
                'inventory_levels/update',
                'app/uninstalled',
            ]
            
            # Base URL for webhooks
            base_url = f"{settings.APP_URL}/webhooks"
            
            # Register each webhook
            for topic in webhook_topics:
                address = f"{base_url}/{topic.replace('/', '_')}"
                response = client.create_webhook(topic, address)
                
                if response and 'webhook' in response:
                    # Save the webhook details
                    ShopifyWebhook.objects.create(
                        store=store,
                        webhook_id=response['webhook']['id'],
                        topic=topic,
                        address=address,
                        format='json'
                    )
                    logger.info(f"Created webhook for {topic} for store {store.shop_url}")
                else:
                    logger.error(f"Failed to create webhook for {topic} for store {store.shop_url}")
        
        except Exception as e:
            logger.error(f"Error setting up webhooks: {str(e)}")
    
    def _fetch_shop_details(self, client, store):
        """
        Fetch and store shop details from the Shopify API.
        """
        try:
            # GraphQL query to get shop details
            query = """
            {
                shop {
                    name
                    email
                    myshopifyDomain
                }
            }
            """
            
            # Execute the query
            response = client.graphql(query)
            
            if response and 'data' in response and 'shop' in response['data']:
                shop_data = response['data']['shop']
                
                # Update the store with the retrieved details
                store.shop_name = shop_data.get('name')
                store.shop_email = shop_data.get('email')
                store.save()
                
                logger.info(f"Updated shop details for {store.shop_url}")
            else:
                logger.error(f"Failed to fetch shop details for {store.shop_url}")
        
        except Exception as e:
            logger.error(f"Error fetching shop details: {str(e)}")


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


class ShopifyAuthView(View):
    """
    View to handle Shopify App Bridge authentication.
    """
    def get(self, request):
        shop = request.GET.get('shop')
        if not shop:
            return HttpResponse("Missing shop parameter", status=400)
        
        # Make sure it's a valid Shopify domain
        if not shop.endswith('.myshopify.com'):
            shop = f"{shop}.myshopify.com"
        
        # Check if this shop is already installed
        try:
            store = ShopifyStore.objects.get(shop_url=shop, is_active=True)
            # Shop exists and is active, redirect to embedded app
            return redirect(f"https://{shop}/admin/apps/{settings.SHOPIFY_CLIENT_ID}")
        except ShopifyStore.DoesNotExist:
            # Shop doesn't exist, initiate OAuth flow
            pass
        
        # Generate a random state value to protect against CSRF
        state = secrets.token_hex(16)
        request.session['shopify_auth_state'] = state
        
        # Build the authorization URL
        scopes = settings.SHOPIFY_API_SCOPES
        redirect_uri = f"{settings.APP_URL}/auth/shopify/callback/"
        auth_url = f"https://{shop}/admin/oauth/authorize?client_id={settings.SHOPIFY_CLIENT_ID}&scope={scopes}&redirect_uri={redirect_uri}&state={state}"
        
        return redirect(auth_url)


class ShopifyCallbackView(View):
    """
    Handle callbacks from Shopify OAuth for App Bridge.
    """
    def get(self, request):
        # Verify all required params are present
        shop = request.GET.get('shop')
        code = request.GET.get('code')
        state = request.GET.get('state')
        hmac_value = request.GET.get('hmac')
        
        if not all([shop, code, state, hmac_value]):
            return HttpResponse("Missing required parameters", status=400)
        
        # Verify state to prevent CSRF attacks
        if state != request.session.get('shopify_auth_state'):
            return HttpResponse("Invalid state parameter", status=403)
        
        # Clear the state from session
        if 'shopify_auth_state' in request.session:
            del request.session['shopify_auth_state']
        
        # Verify the HMAC
        if not self._verify_hmac(request.GET, settings.SHOPIFY_CLIENT_SECRET):
            return HttpResponse("HMAC verification failed", status=403)
        
        # Exchange the code for an access token
        access_token = self._exchange_code_for_token(shop, code)
        if not access_token:
            return HttpResponse("Failed to get access token", status=500)
        
        # Save the store details
        store, created = ShopifyStore.objects.update_or_create(
            shop_url=shop,
            defaults={
                'access_token': access_token,
                'is_active': True,
                'last_access': timezone.now(),
                'trial_ends_at': timezone.now() + datetime.timedelta(days=14) if created else F('trial_ends_at')
            }
        )
        
        # Set up webhooks and fetch shop details
        if created:
            client = ShopifyClient(shop, access_token)
            # Set up webhooks
            try:
                self._setup_webhooks(client, store)
            except Exception as e:
                logger.error(f"Error setting up webhooks: {str(e)}")
            
            # Fetch shop details
            try:
                self._fetch_shop_details(client, store)
            except Exception as e:
                logger.error(f"Error fetching shop details: {str(e)}")
        
        # Redirect to the Shopify admin app page
        return redirect(f"https://{shop}/admin/apps/{settings.SHOPIFY_CLIENT_ID}")
    
    def _verify_hmac(self, params, secret):
        """Verify the HMAC signature from Shopify"""
        # Create a new dictionary of parameters excluding hmac
        params_copy = params.copy()
        hmac_value = params_copy.pop('hmac', '')
        
        # Sort the parameters and create the message
        sorted_params = sorted(params_copy.items())
        message = '&'.join([f"{key}={value}" for key, value in sorted_params])
        
        # Calculate the HMAC
        digest = hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(digest, hmac_value)
    
    def _exchange_code_for_token(self, shop, code):
        """Exchange authorization code for permanent access token"""
        try:
            data = {
                'client_id': settings.SHOPIFY_CLIENT_ID,
                'client_secret': settings.SHOPIFY_CLIENT_SECRET,
                'code': code
            }
            response = requests.post(f"https://{shop}/admin/oauth/access_token", data=data)
            if response.status_code == 200:
                return response.json().get('access_token')
            logger.error(f"Failed to get access token: {response.text}")
            return None
        except Exception as e:
            logger.error(f"Error exchanging code for token: {str(e)}")
            return None
    
    def _setup_webhooks(self, client, store):
        """Set up webhooks for the Shopify store"""
        # Define the webhook topics we need
        webhook_topics = [
            'products/update',
            'inventory_levels/update',
            'app/uninstalled',
        ]
        
        # Base URL for webhooks
        base_url = f"{settings.APP_URL}/webhooks"
        
        # Register each webhook
        for topic in webhook_topics:
            address = f"{base_url}/{topic.replace('/', '_')}"
            response = client.create_webhook(topic, address)
            
            if response and 'webhook' in response:
                # Save the webhook details
                ShopifyWebhook.objects.create(
                    store=store,
                    webhook_id=response['webhook']['id'],
                    topic=topic,
                    address=address,
                    format='json'
                )
                logger.info(f"Created webhook for {topic} for store {store.shop_url}")
            else:
                logger.error(f"Failed to create webhook for {topic} for store {store.shop_url}")
    
    def _fetch_shop_details(self, client, store):
        """Fetch details about the Shopify store"""
        try:
            response = client.get_shop()
            if response and 'shop' in response:
                shop_data = response['shop']
                store.shop_name = shop_data.get('name')
                store.shop_email = shop_data.get('email')
                store.save()
            else:
                logger.error(f"Failed to fetch shop details for {store.shop_url}")
        except Exception as e:
            logger.error(f"Error fetching shop details: {str(e)}")


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
    redirect_uri = f"{settings.APP_URL}/auth/callback"
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
    OAuth callback from Shopify
    """
    # Get parameters from request
    shop = request.GET.get('shop')
    code = request.GET.get('code')
    state = request.GET.get('state')
    
    # Validate state to prevent CSRF
    stored_state = request.session.get('shopify_auth_state')
    stored_shop = request.session.get('shopify_shop')
    
    if not state or state != stored_state or not shop or shop != stored_shop:
        return HttpResponse("Invalid request", status=400)
    
    # Exchange code for access token
    access_token = exchange_code_for_token(shop, code)
    if not access_token:
        return HttpResponse("Failed to get access token", status=400)
    
    # Store the token in session
    request.session['shopify_access_token'] = access_token
    
    # Get shop details and store in database
    shop_details = get_shop_details(shop, access_token)
    if not shop_details:
        return HttpResponse("Failed to get shop details", status=400)
    
    # Save shop details and token to database (simplified for now)
    
    # Redirect to app in Shopify Admin
    return redirect(f"https://{shop}/admin/apps/{settings.SHOPIFY_CLIENT_ID}")

def create_nonce():
    """Generate a random nonce for OAuth state"""
    return base64.b64encode(os.urandom(16)).decode('utf-8')

def exchange_code_for_token(shop, code):
    """Exchange authorization code for permanent access token"""
    try:
        data = {
            'client_id': settings.SHOPIFY_CLIENT_ID,
            'client_secret': settings.SHOPIFY_CLIENT_SECRET,
            'code': code
        }
        response = requests.post(f"https://{shop}/admin/oauth/access_token", data=data)
        if response.status_code == 200:
            return response.json().get('access_token')
        logger.error(f"Failed to get access token: {response.text}")
        return None
    except Exception as e:
        logger.error(f"Error exchanging code for token: {str(e)}")
        return None

def get_shop_details(shop, access_token):
    """Get shop details from Shopify"""
    try:
        headers = {
            'X-Shopify-Access-Token': access_token,
            'Content-Type': 'application/json'
        }
        response = requests.get(f"https://{shop}/admin/api/2023-10/shop.json", headers=headers)
        if response.status_code == 200:
            return response.json().get('shop')
        logger.error(f"Failed to get shop details: {response.text}")
        return None
    except Exception as e:
        logger.error(f"Error getting shop details: {str(e)}")
        return None

@login_required
def index(request):
    """
    Dashboard view (requires login)
    """
    return redirect('dashboard:index') 