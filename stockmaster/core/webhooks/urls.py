from django.urls import path
from .views import (
    ProductUpdateWebhook,
    InventoryLevelUpdateWebhook,
    AppUninstalledWebhook
)

app_name = 'webhooks'

urlpatterns = [
    path('products/update', ProductUpdateWebhook.as_view(), name='product_update'),
    path('inventory_levels/update', InventoryLevelUpdateWebhook.as_view(), name='inventory_level_update'),
    path('app/uninstalled', AppUninstalledWebhook.as_view(), name='app_uninstalled'),
] 