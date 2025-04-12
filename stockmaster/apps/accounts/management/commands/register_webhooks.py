import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.accounts.models import ShopifyStore
from core.shopify.client import ShopifyClient

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Register required webhooks for all active stores'

    def handle(self, *args, **options):
        stores = ShopifyStore.objects.filter(is_active=True)
        
        if not stores.exists():
            self.stdout.write(self.style.WARNING('No active stores found'))
            return
        
        self.stdout.write(f'Registering webhooks for {stores.count()} stores')
        
        webhook_topics = [
            'app/uninstalled',
            'products/update',
            'inventory_levels/update'
        ]
        
        base_url = settings.APP_URL.rstrip('/')
        
        for store in stores:
            self.stdout.write(f'Processing store: {store.shop_url}')
            
            if not store.access_token:
                self.stdout.write(self.style.WARNING(f'Store {store.shop_url} has no access token. Skipping.'))
                continue
            
            client = ShopifyClient(store.shop_url, store.access_token)
            
            # First, get existing webhooks
            try:
                existing_webhooks = client.get_webhooks()
                if 'webhooks' in existing_webhooks:
                    existing_webhook_topics = [w['topic'] for w in existing_webhooks['webhooks']]
                else:
                    existing_webhook_topics = []
                
                self.stdout.write(f'Found {len(existing_webhook_topics)} existing webhooks')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error getting webhooks for {store.shop_url}: {str(e)}'))
                continue
            
            # Register required webhooks if they don't exist
            for topic in webhook_topics:
                if topic in existing_webhook_topics:
                    self.stdout.write(f'Webhook for {topic} already exists. Skipping.')
                    continue
                
                # Convert topic format: app/uninstalled -> app_uninstalled
                endpoint_name = topic.replace('/', '_')
                
                # Different webhook paths based on the topic
                if topic == 'app/uninstalled':
                    webhook_url = f'{base_url}/webhooks/{endpoint_name}'
                else:
                    # Use the standard webhook paths for other topics
                    webhook_url = f'{base_url}/webhooks/{topic.split("/")[0]}/{topic.split("/")[1]}'
                
                try:
                    response = client.create_webhook(topic, webhook_url)
                    if 'webhook' in response:
                        self.stdout.write(self.style.SUCCESS(f'Registered webhook for {topic} at {webhook_url}'))
                    else:
                        self.stdout.write(self.style.ERROR(f'Failed to register webhook for {topic}: {response}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error registering webhook for {topic}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS('Webhook registration completed')) 