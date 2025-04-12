from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class ShopifyStore(models.Model):
    """Model to store Shopify store information and credentials."""
    
    shop_url = models.CharField(max_length=255, unique=True, help_text="The myshopify.com domain of the store")
    shop_name = models.CharField(max_length=255, blank=True, null=True, help_text="The name of the store")
    shop_email = models.EmailField(blank=True, null=True, help_text="The email of the store owner")
    access_token = models.CharField(max_length=255, blank=True, null=True, help_text="The OAuth access token")
    scope = models.TextField(blank=True, null=True, help_text="The scopes granted to the app")
    is_active = models.BooleanField(default=True, help_text="Whether the store is active")
    setup_complete = models.BooleanField(default=False, help_text="Whether the store setup is complete")
    
    # Sync status
    sync_status = models.CharField(max_length=50, default='pending', choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ], help_text="Current sync status")
    last_sync_at = models.DateTimeField(blank=True, null=True, help_text="When the store was last synced")
    
    # Store owner (if a user is created)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='shopify_stores')
    
    # Plan and billing information
    plan = models.CharField(max_length=50, default='free', 
                            help_text="The subscription plan for the store")
    trial_ends_at = models.DateTimeField(blank=True, null=True, 
                                        help_text="When the trial period ends")
    subscription_id = models.CharField(max_length=255, blank=True, null=True, 
                                      help_text="The ID of the subscription in Shopify Billing")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_access = models.DateTimeField(default=timezone.now, 
                                      help_text="The last time the store accessed the app")
    
    class Meta:
        verbose_name = "Shopify Store"
        verbose_name_plural = "Shopify Stores"
        indexes = [
            models.Index(fields=['shop_url']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.shop_url
    
    @property
    def is_trial(self):
        """Check if the store is in trial period."""
        if not self.trial_ends_at:
            return False
        return self.trial_ends_at > timezone.now()
    
    @property
    def trial_days_left(self):
        """Get the number of days left in the trial."""
        if not self.is_trial:
            return 0
        delta = self.trial_ends_at - timezone.now()
        return max(0, delta.days)
    
    def update_last_access(self):
        """Update the last access timestamp."""
        self.last_access = timezone.now()
        self.save(update_fields=['last_access'])


class ShopifyWebhook(models.Model):
    """Model to track registered webhooks for a store."""
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='webhooks')
    webhook_id = models.CharField(max_length=255, help_text="The ID of the webhook in Shopify")
    topic = models.CharField(max_length=100, help_text="The webhook topic")
    address = models.URLField(help_text="The webhook callback URL")
    format = models.CharField(max_length=20, default='json', help_text="The format of the webhook")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Shopify Webhook"
        verbose_name_plural = "Shopify Webhooks"
        unique_together = ('store', 'webhook_id')
    
    def __str__(self):
        return f"{self.store.shop_url} - {self.topic}" 