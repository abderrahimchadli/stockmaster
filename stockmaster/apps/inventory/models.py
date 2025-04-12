from django.db import models
from django.utils import timezone
from apps.accounts.models import ShopifyStore


class Product(models.Model):
    """Model to store Shopify product information."""
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='products')
    shopify_id = models.BigIntegerField(help_text="Shopify product ID")
    title = models.CharField(max_length=255, help_text="Product title")
    handle = models.CharField(max_length=255, help_text="Product handle/slug")
    product_type = models.CharField(max_length=255, blank=True, null=True, help_text="Product type")
    vendor = models.CharField(max_length=255, blank=True, null=True, help_text="Product vendor")
    status = models.CharField(max_length=50, default='active', help_text="Product status (active, draft, archived)")
    published_at = models.DateTimeField(blank=True, null=True, help_text="When the product was published")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced = models.DateTimeField(default=timezone.now, help_text="When the product was last synced from Shopify")
    
    # Fields to track product visibility
    is_visible = models.BooleanField(default=True, help_text="Whether the product is visible on the storefront")
    hidden_at = models.DateTimeField(blank=True, null=True, help_text="When the product was hidden")
    scheduled_return = models.DateTimeField(blank=True, null=True, help_text="When the product is scheduled to be visible again")
    
    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        unique_together = ('store', 'shopify_id')
        indexes = [
            models.Index(fields=['store', 'shopify_id']),
            models.Index(fields=['store', 'handle']),
            models.Index(fields=['store', 'is_visible']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.store.shop_url})"
    
    @property
    def shopify_admin_url(self):
        """Get the Shopify admin URL for this product."""
        return f"https://{self.store.shop_url}/admin/products/{self.shopify_id}"
    
    @property
    def shopify_storefront_url(self):
        """Get the Shopify storefront URL for this product."""
        return f"https://{self.store.shop_url}/products/{self.handle}"


class ProductVariant(models.Model):
    """Model to store product variant information."""
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    shopify_id = models.BigIntegerField(help_text="Shopify variant ID")
    title = models.CharField(max_length=255, help_text="Variant title")
    sku = models.CharField(max_length=255, blank=True, null=True, help_text="Stock keeping unit")
    barcode = models.CharField(max_length=255, blank=True, null=True, help_text="Barcode or UPC")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Variant price")
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Compare at price")
    position = models.IntegerField(default=1, help_text="Variant position")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Link to inventory item ID in Shopify
    inventory_item_id = models.BigIntegerField(help_text="Shopify inventory item ID")
    
    class Meta:
        verbose_name = "Product Variant"
        verbose_name_plural = "Product Variants"
        unique_together = ('product', 'shopify_id')
        indexes = [
            models.Index(fields=['shopify_id']),
            models.Index(fields=['inventory_item_id']),
        ]
    
    def __str__(self):
        return f"{self.product.title} - {self.title}"


class InventoryLocation(models.Model):
    """Model to store Shopify inventory location information."""
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='inventory_locations')
    shopify_id = models.BigIntegerField(help_text="Shopify location ID")
    name = models.CharField(max_length=255, help_text="Location name")
    is_active = models.BooleanField(default=True, help_text="Whether the location is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Inventory Location"
        verbose_name_plural = "Inventory Locations"
        unique_together = ('store', 'shopify_id')
    
    def __str__(self):
        return f"{self.name} ({self.store.shop_url})"


class InventoryLevel(models.Model):
    """Model to store inventory levels for product variants at specific locations."""
    
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='inventory_levels')
    location = models.ForeignKey(InventoryLocation, on_delete=models.CASCADE, related_name='inventory_levels')
    available = models.IntegerField(default=0, help_text="Available quantity")
    updated_at = models.DateTimeField(auto_now=True)
    last_synced = models.DateTimeField(default=timezone.now, help_text="When the inventory was last synced from Shopify")
    
    class Meta:
        verbose_name = "Inventory Level"
        verbose_name_plural = "Inventory Levels"
        unique_together = ('variant', 'location')
        indexes = [
            models.Index(fields=['variant', 'location']),
            models.Index(fields=['available']),
        ]
    
    def __str__(self):
        return f"{self.variant} at {self.location.name}: {self.available}"


class InventoryLog(models.Model):
    """Model to track inventory changes for audit purposes."""
    
    ACTION_CHOICES = (
        ('sync', 'Synced from Shopify'),
        ('hide', 'Product Hidden'),
        ('show', 'Product Shown'),
        ('schedule', 'Visibility Scheduled'),
        ('rule', 'Rule Applied'),
        ('manual', 'Manual Update'),
    )
    
    store = models.ForeignKey(ShopifyStore, on_delete=models.CASCADE, related_name='inventory_logs')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_logs', null=True, blank=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='inventory_logs', null=True, blank=True)
    location = models.ForeignKey(InventoryLocation, on_delete=models.CASCADE, related_name='inventory_logs', null=True, blank=True)
    
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, help_text="The type of action performed")
    previous_value = models.IntegerField(null=True, blank=True, help_text="Previous inventory quantity")
    new_value = models.IntegerField(null=True, blank=True, help_text="New inventory quantity")
    previous_status = models.CharField(max_length=50, null=True, blank=True, help_text="Previous product status")
    new_status = models.CharField(max_length=50, null=True, blank=True, help_text="New product status")
    
    notes = models.TextField(blank=True, null=True, help_text="Additional information about the change")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Inventory Log"
        verbose_name_plural = "Inventory Logs"
        indexes = [
            models.Index(fields=['store', 'created_at']),
            models.Index(fields=['product', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.action} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}" 