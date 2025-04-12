from django.db import models
from django.utils import timezone
from apps.accounts.models import ShopifyStore
from apps.inventory.models import Product


class DailySummary(models.Model):
    """Model to store daily inventory statistics for analytics."""
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='daily_summaries')
    date = models.DateField(help_text="The date of the summary")
    
    total_products = models.IntegerField(default=0, help_text="Total number of products")
    out_of_stock_products = models.IntegerField(default=0, help_text="Number of out-of-stock products")
    low_stock_products = models.IntegerField(default=0, help_text="Number of low-stock products")
    hidden_products = models.IntegerField(default=0, help_text="Number of hidden products")
    
    rules_applied = models.IntegerField(default=0, help_text="Number of rules applied")
    notifications_sent = models.IntegerField(default=0, help_text="Number of notifications sent")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Daily Summary"
        verbose_name_plural = "Daily Summaries"
        unique_together = ('store', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['store', 'date']),
        ]
    
    def __str__(self):
        return f"Summary for {self.store.shop_url} on {self.date}"


class ProductAnalytics(models.Model):
    """Model to track product analytics and history."""
    
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='analytics')
    
    # Inventory history
    out_of_stock_count = models.IntegerField(default=0, help_text="Number of times the product has been out of stock")
    total_days_out_of_stock = models.IntegerField(default=0, help_text="Total days the product has been out of stock")
    last_out_of_stock_at = models.DateTimeField(blank=True, null=True, help_text="When the product was last out of stock")
    
    # Visibility history
    times_hidden = models.IntegerField(default=0, help_text="Number of times the product has been hidden")
    total_days_hidden = models.IntegerField(default=0, help_text="Total days the product has been hidden")
    last_hidden_at = models.DateTimeField(blank=True, null=True, help_text="When the product was last hidden")
    
    # Rule application history
    rule_applications_count = models.IntegerField(default=0, help_text="Number of rule applications to this product")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Product Analytics"
        verbose_name_plural = "Product Analytics"
        indexes = [
            models.Index(fields=['out_of_stock_count']),
            models.Index(fields=['times_hidden']),
        ]
    
    def __str__(self):
        return f"Analytics for {self.product.title}"


class StockPrediction(models.Model):
    """Model to store stock level predictions for products."""
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_predictions')
    
    predicted_out_of_stock_date = models.DateTimeField(blank=True, null=True, help_text="Predicted date when the product will be out of stock")
    confidence_score = models.FloatField(default=0.0, help_text="Confidence score for the prediction (0-1)")
    
    # Data used for prediction
    days_of_data = models.IntegerField(default=0, help_text="Number of days of data used for prediction")
    average_sales_per_day = models.FloatField(default=0.0, help_text="Average sales per day based on historical data")
    current_stock_level = models.IntegerField(default=0, help_text="Current stock level when the prediction was made")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Stock Prediction"
        verbose_name_plural = "Stock Predictions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'created_at']),
            models.Index(fields=['predicted_out_of_stock_date']),
        ]
    
    def __str__(self):
        if self.predicted_out_of_stock_date:
            return f"Prediction for {self.product.title}: Out of stock on {self.predicted_out_of_stock_date.strftime('%Y-%m-%d')}"
        return f"Prediction for {self.product.title}: No prediction"
    
    @property
    def days_until_out_of_stock(self):
        """Calculate days until the product is predicted to be out of stock."""
        if not self.predicted_out_of_stock_date:
            return None
        
        delta = self.predicted_out_of_stock_date - timezone.now()
        return max(0, delta.days) 