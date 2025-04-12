# Signals for accounts app
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from core.utils.logger import logger
from .models import ShopifyStore

@receiver(post_save, sender=ShopifyStore)
def create_user_for_store(sender, instance, created, **kwargs):
    """
    Create a user account for the store owner if one doesn't exist.
    """
    if created and instance.shop_email and not instance.user:
        try:
            # Check if a user with this email already exists
            user = User.objects.filter(email=instance.shop_email).first()
            
            if not user:
                # Create a new user with the store's email
                username = instance.shop_url.split('.')[0]
                user = User.objects.create_user(
                    username=username,
                    email=instance.shop_email,
                    password=None  # No password needed, using Shopify auth
                )
                logger.info(f"Created user {username} for store {instance.shop_url}")
            
            # Associate the user with the store
            instance.user = user
            instance.save(update_fields=['user'])
            
        except Exception as e:
            logger.error(f"Error creating user for store {instance.shop_url}: {str(e)}") 