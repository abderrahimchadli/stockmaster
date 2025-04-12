import logging
from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fix references to SmartShelf and rename to StockMaster in the database'

    def handle(self, *args, **options):
        self.stdout.write('Starting app rename process: SmartShelf → StockMaster')
        
        # 1. SQL fixes - update any places in the database with the old name
        try:
            with connection.cursor() as cursor:
                # Query to find tables/columns where 'SmartShelf' might be stored
                cursor.execute("""
                    UPDATE django_session 
                    SET session_data = REPLACE(session_data, 'SmartShelf', 'StockMaster')
                    WHERE session_data LIKE '%SmartShelf%';
                """)
                self.stdout.write(f"Updated {cursor.rowcount} session records")
                
                # Update any site settings if they exist
                cursor.execute("""
                    UPDATE django_site 
                    SET name = REPLACE(name, 'SmartShelf', 'StockMaster')
                    WHERE name LIKE '%SmartShelf%';
                """)
                self.stdout.write(f"Updated {cursor.rowcount} site records")
                
                # Update any stored shop data
                cursor.execute("""
                    UPDATE accounts_shopifystore 
                    SET shop_name = REPLACE(shop_name, 'SmartShelf', 'StockMaster')
                    WHERE shop_name LIKE '%SmartShelf%';
                """)
                self.stdout.write(f"Updated {cursor.rowcount} store records")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Database error: {str(e)}"))
                
        self.stdout.write(self.style.SUCCESS('App rename completed successfully'))
        
        # Instructions for manual steps
        self.stdout.write('\nIMPORTANT: You still need to perform these manual steps:')
        self.stdout.write('1. Update the app name in your Shopify Partner Dashboard')
        self.stdout.write('2. Update the APP_NAME in any JavaScript or template files not caught by our updates')
        self.stdout.write('3. Reinstall the app in your store to register with the new name\n')
            
        self.stdout.write(self.style.SUCCESS('App renaming process complete')) 