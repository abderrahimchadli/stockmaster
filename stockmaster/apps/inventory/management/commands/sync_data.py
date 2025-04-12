from django.core.management.base import BaseCommand
from apps.accounts.models import ShopifyStore
from apps.inventory.tasks import sync_store_data
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync data from Shopify stores'

    def add_arguments(self, parser):
        parser.add_argument(
            '--store',
            type=str,
            help='Store URL (e.g., mystore.myshopify.com)',
        )

    def handle(self, *args, **options):
        store_url = options.get('store')
        
        if store_url:
            # Sync specific store
            try:
                store = ShopifyStore.objects.get(shop_url=store_url, is_active=True)
                self.stdout.write(f"Found store {store.shop_url} (ID: {store.id})")
                self.stdout.write(f"Starting sync for {store.shop_url}...")
                
                # Run the sync task directly (not as a background task)
                sync_store_data(store.id)
                
                self.stdout.write(self.style.SUCCESS(f"Successfully synced data for {store.shop_url}"))
            except ShopifyStore.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Store not found: {store_url}"))
        else:
            # Sync all active stores
            stores = ShopifyStore.objects.filter(is_active=True)
            self.stdout.write(f"Found {stores.count()} active stores")
            
            # Print the list of stores
            for store in stores:
                self.stdout.write(f"- {store.shop_url} (ID: {store.id})")
            
            if stores.exists():
                self.stdout.write("Starting sync for all stores...")
                for store in stores:
                    try:
                        self.stdout.write(f"Syncing {store.shop_url}...")
                        sync_store_data(store.id)
                        self.stdout.write(self.style.SUCCESS(f"Successfully synced data for {store.shop_url}"))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error syncing {store.shop_url}: {str(e)}"))
            else:
                self.stdout.write(self.style.WARNING("No active stores found")) 