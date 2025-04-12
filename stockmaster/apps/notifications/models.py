from django.db import models
from django.utils import timezone
from apps.accounts.models import ShopifyStore


class NotificationChannel(models.Model):
    """Model for notification channels (email, Slack, etc.)."""
    
    CHANNEL_CHOICES = (
        ('email', 'Email'),
        ('slack', 'Slack'),
        ('webhook', 'Webhook'),
        ('in_app', 'In-App Notification'),
    )
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='notification_channels')
    channel_type = models.CharField(max_length=50, choices=CHANNEL_CHOICES, help_text="Type of notification channel")
    name = models.CharField(max_length=255, help_text="Channel name")
    
    # Configuration depends on channel type
    email_recipients = models.TextField(blank=True, null=True, help_text="Comma-separated list of email recipients")
    slack_webhook_url = models.URLField(blank=True, null=True, help_text="Slack webhook URL")
    webhook_url = models.URLField(blank=True, null=True, help_text="Webhook URL for custom integrations")
    webhook_secret = models.CharField(max_length=255, blank=True, null=True, help_text="Secret key for webhook security")
    
    is_active = models.BooleanField(default=True, help_text="Whether the channel is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Notification Channel"
        verbose_name_plural = "Notification Channels"
        unique_together = ('store', 'name')
    
    def __str__(self):
        return f"{self.name} ({self.get_channel_type_display()})"


class NotificationPreference(models.Model):
    """Model for notification preferences to determine what events to notify about."""
    
    EVENT_CHOICES = (
        ('out_of_stock', 'Product Out of Stock'),
        ('low_stock', 'Product Low Stock'),
        ('back_in_stock', 'Product Back in Stock'),
        ('rule_applied', 'Rule Applied'),
        ('rule_reversed', 'Rule Reversed'),
        ('error', 'System Error'),
    )
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='notification_preferences')
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE, related_name='preferences')
    event_type = models.CharField(max_length=50, choices=EVENT_CHOICES, help_text="Type of event to notify about")
    
    # Optional filters
    product_type_filter = models.CharField(max_length=255, blank=True, null=True, help_text="Notify only for specific product types")
    vendor_filter = models.CharField(max_length=255, blank=True, null=True, help_text="Notify only for specific vendors")
    tag_filter = models.CharField(max_length=255, blank=True, null=True, help_text="Notify only for products with specific tags")
    
    is_active = models.BooleanField(default=True, help_text="Whether the preference is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"
        unique_together = ('store', 'channel', 'event_type')
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.channel.name}"


class Notification(models.Model):
    """Model to track notifications sent."""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('read', 'Read'),
    )
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='notifications')
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE, related_name='notifications')
    event_type = models.CharField(max_length=50, help_text="Type of event that triggered the notification")
    
    title = models.CharField(max_length=255, help_text="Notification title")
    message = models.TextField(help_text="Notification message")
    
    # Optional link to related objects - using generic foreign key pattern
    object_type = models.CharField(max_length=50, blank=True, null=True, help_text="Type of related object")
    object_id = models.CharField(max_length=50, blank=True, null=True, help_text="ID of related object")
    
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending', help_text="Current status of the notification")
    error_message = models.TextField(blank=True, null=True, help_text="Error message if sending failed")
    
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True, help_text="When the notification was sent")
    read_at = models.DateTimeField(blank=True, null=True, help_text="When the notification was read")
    
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['store', 'status']),
            models.Index(fields=['store', 'event_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.created_at.strftime('%Y-%m-%d %H:%M:%S')})"
    
    def mark_as_sent(self):
        """Mark the notification as sent."""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_as_failed(self, error_message):
        """Mark the notification as failed with an error message."""
        self.status = 'failed'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message'])
    
    def mark_as_read(self):
        """Mark the notification as read."""
        self.status = 'read'
        self.read_at = timezone.now()
        self.save(update_fields=['status', 'read_at']) 