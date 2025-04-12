from django.db import models
from django.utils import timezone
from apps.accounts.models import ShopifyStore
from apps.inventory.models import Product


class Rule(models.Model):
    """Model for business rules to handle out-of-stock products."""
    
    TRIGGER_CHOICES = (
        ('out_of_stock', 'Out of Stock'),
        ('low_stock', 'Low Stock'),
        ('back_in_stock', 'Back in Stock'),
    )
    
    ACTION_CHOICES = (
        ('hide_product', 'Hide Product'),
        ('show_product', 'Show Product'),
        ('move_to_collection', 'Move to Collection'),
        ('reorder_collection', 'Reorder in Collection'),
        ('tag_product', 'Tag Product'),
        ('notify', 'Send Notification'),
    )
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='rules')
    name = models.CharField(max_length=255, help_text="Rule name")
    description = models.TextField(blank=True, null=True, help_text="Rule description")
    
    # When the rule is triggered
    trigger_type = models.CharField(max_length=50, choices=TRIGGER_CHOICES, help_text="When the rule is triggered")
    threshold = models.IntegerField(default=0, help_text="Threshold value for triggering the rule (e.g., 0 for out of stock)")
    
    # What action to take
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES, help_text="The action to take")
    
    # Optional delay before action
    delay_minutes = models.IntegerField(default=0, help_text="Delay in minutes before applying the action")
    
    # Optional restoration after specific time
    auto_restore = models.BooleanField(default=False, help_text="Whether to automatically restore the product")
    restore_after_days = models.IntegerField(default=0, help_text="Days after which to restore the product")
    
    # Rule conditions - can be expanded with JSONField for more complex conditions
    product_type_filter = models.CharField(max_length=255, blank=True, null=True, help_text="Apply only to specific product types")
    vendor_filter = models.CharField(max_length=255, blank=True, null=True, help_text="Apply only to specific vendors")
    tag_filter = models.CharField(max_length=255, blank=True, null=True, help_text="Apply only to products with specific tags")
    collection_filter = models.CharField(max_length=255, blank=True, null=True, help_text="Apply only to products in specific collections")
    
    # Rule status
    is_active = models.BooleanField(default=True, help_text="Whether the rule is active")
    priority = models.IntegerField(default=0, help_text="Rule priority (higher number = higher priority)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Rule"
        verbose_name_plural = "Rules"
        ordering = ['-priority', 'name']
        indexes = [
            models.Index(fields=['store', 'is_active']),
            models.Index(fields=['store', 'trigger_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.store.shop_url})"


class RuleApplication(models.Model):
    """Model to track when rules are applied to products."""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('applied', 'Applied'),
        ('reversed', 'Reversed'),
        ('failed', 'Failed'),
    )
    
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE, related_name='applications')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='rule_applications')
    
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending', help_text="Current status of the rule application")
    
    triggered_at = models.DateTimeField(default=timezone.now, help_text="When the rule was triggered")
    scheduled_for = models.DateTimeField(blank=True, null=True, help_text="When the action is scheduled to be applied")
    applied_at = models.DateTimeField(blank=True, null=True, help_text="When the action was actually applied")
    restore_scheduled_for = models.DateTimeField(blank=True, null=True, help_text="When the product is scheduled to be restored")
    
    notes = models.TextField(blank=True, null=True, help_text="Additional information about the rule application")
    
    class Meta:
        verbose_name = "Rule Application"
        verbose_name_plural = "Rule Applications"
        ordering = ['-triggered_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['scheduled_for']),
            models.Index(fields=['restore_scheduled_for']),
        ]
    
    def __str__(self):
        return f"{self.rule.name} applied to {self.product.title}"
    
    @property
    def is_scheduled(self):
        """Check if the rule application is scheduled but not yet applied."""
        return (
            self.status == 'pending' and 
            self.scheduled_for is not None and 
            self.scheduled_for > timezone.now()
        )
    
    @property
    def is_restoration_scheduled(self):
        """Check if the product restoration is scheduled."""
        return (
            self.status == 'applied' and 
            self.restore_scheduled_for is not None and 
            self.restore_scheduled_for > timezone.now()
        ) 