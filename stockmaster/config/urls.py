from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from apps.accounts.views import AuthCallbackView
from core.webhooks.views import AppUninstalledWebhook

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Application URLs
    path('', include('apps.dashboard.urls')),
    # Enable accounts URLs
    path('accounts/', include('apps.accounts.urls')),
    # Use 'auth_app' namespace to avoid collision
    path('auth/', include('apps.accounts.urls', namespace='auth_app')),
    # Add specific auth callback route that's whitelisted in Shopify
    path('auth/callback/', AuthCallbackView.as_view(), name='auth_callback'),
    # Enable previously disabled apps
    # path('api/', include('apps.api.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('rules/', include('apps.rules.urls')),
    path('notifications/', include('apps.notifications.urls')),
    
    # Webhooks
    path('webhooks/', include('core.webhooks.urls')),
    # Direct route for app uninstalled webhook
    path('webhooks/app_uninstalled', AppUninstalledWebhook.as_view(), name='app_uninstalled_webhook'),
    
    # Error pages
    path('404/', TemplateView.as_view(template_name='404.html'), name='404'),
    path('500/', TemplateView.as_view(template_name='500.html'), name='500'),
]

# Add static files handling
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # Enable debug toolbar in development
    urlpatterns.append(path('__debug__/', include('debug_toolbar.urls'))) 