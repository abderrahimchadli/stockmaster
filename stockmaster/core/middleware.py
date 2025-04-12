class ShopifyAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Add Shopify App Bridge headers
        response['X-Frame-Options'] = 'ALLOW-FROM https://*.myshopify.com'
        response['Content-Security-Policy'] = (
            "default-src 'self' https://*.myshopify.com https://cdn.shopify.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.myshopify.com https://cdn.shopify.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com https://argus.shopifycloud.com; "
            "style-src 'self' 'unsafe-inline' https://*.myshopify.com https://cdn.shopify.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://*.myshopify.com https://cdn.shopify.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com; "
            "connect-src 'self' https://*.myshopify.com https://cdn.shopify.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com https://argus.shopifycloud.com wss://argus.shopifycloud.com; "
            "frame-ancestors https://*.myshopify.com; "
            "frame-src https://*.myshopify.com; "
            "worker-src 'self' blob:; "
            "child-src 'self' blob:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self' https://*.myshopify.com; "
            "upgrade-insecure-requests;"
        )
        response['X-Content-Type-Options'] = 'nosniff'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        response['Cross-Origin-Embedder-Policy'] = 'require-corp'
        response['Cross-Origin-Resource-Policy'] = 'same-site'
        
        # Add sandbox attribute to iframe
        if 'X-Frame-Options' in response:
            response['X-Frame-Options'] = 'ALLOW-FROM https://*.myshopify.com'
            response['X-Frame-Options'] += '; sandbox allow-scripts allow-same-origin allow-forms allow-popups allow-modals'
        
        return response 