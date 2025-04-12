#!/usr/bin/env python
"""
Script to check if a Shopify store is accessible.
This will help troubleshoot the "shop is currently unavailable" error.
"""
import os
import sys
import requests
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def check_store_availability(shop_domain):
    """
    Check if a Shopify store is available.
    
    Args:
        shop_domain: Shopify store domain (e.g., 'example.myshopify.com')
    """
    if not shop_domain.endswith('.myshopify.com'):
        shop_domain = f"{shop_domain}.myshopify.com"
    
    logger.info(f"Checking availability for: {shop_domain}")
    
    # Check the store's homepage
    try:
        response = requests.get(f"https://{shop_domain}", timeout=10)
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("✅ Store is accessible")
            return True
        elif response.status_code == 401:
            logger.error("❌ Store requires password authentication (might be in development/password mode)")
            return False
        elif response.status_code == 404:
            logger.error("❌ Store not found")
            return False
        elif response.status_code == 503:
            logger.error("❌ Store is currently unavailable/suspended")
            return False
        else:
            logger.error(f"❌ Unexpected status code: {response.status_code}")
            return False
    
    except requests.RequestException as e:
        logger.error(f"❌ Error connecting to store: {str(e)}")
        return False

def main():
    """Main function to check store availability."""
    print("Shopify Store Availability Checker")
    print("==================================")
    
    # Get store domain from user input
    shop_domain = input("Enter your Shopify store domain (e.g., 'your-store.myshopify.com'): ")
    
    # Check availability
    check_store_availability(shop_domain)
    
    print("\nTroubleshooting steps if store is unavailable:")
    print("1. Make sure your store is not in development mode or password-protected")
    print("2. Verify your store has not been suspended")
    print("3. Check that you're using the correct store domain")
    print("4. Ensure your developer account has proper access to the store")
    print("5. If you're using a development store, make sure it's properly set up")

if __name__ == "__main__":
    main() 