/**
 * Shopify App Bridge Initialization
 */

(function() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAppBridge);
    } else {
        initAppBridge();
    }

    function initAppBridge() {
        try {
            // Check if App Bridge is available
            if (typeof window['app-bridge'] === 'undefined') {
                console.warn('App Bridge not loaded');
                return;
            }
            
            // Get shop from URL (common in Shopify admin)
            const urlParams = new URLSearchParams(window.location.search);
            const shop = urlParams.get('shop');
            
            if (!shop) {
                console.warn('No shop parameter found in URL');
                return;
            }
            
            // Get API key from meta tag
            const apiKeyMeta = document.querySelector('meta[name="shopify-api-key"]');
            if (!apiKeyMeta) {
                console.error('No Shopify API key meta tag found');
                return;
            }
            
            const apiKey = apiKeyMeta.getAttribute('content');
            
            // Initialize App Bridge
            const AppBridge = window['app-bridge'];
            const createApp = AppBridge.default;
            const app = createApp({
                apiKey: apiKey,
                shopOrigin: shop,
                forceRedirect: false
            });
            
            // Save app instance globally
            window.shopifyApp = app;
            
            // Setup App Bridge utilities
            setupAppBridgeUtils(app);
            
            console.log('App Bridge initialized for shop:', shop);
        } catch (error) {
            console.error('Failed to initialize App Bridge:', error);
        }
    }
    
    function setupAppBridgeUtils(app) {
        // Set up App Bridge utilities if available
        if (window['app-bridge-utils']) {
            const AppBridgeUtils = window['app-bridge-utils'];
            
            // Initialize utilities
            const actions = window['app-bridge'].actions;
            window.shopifyActions = {
                Redirect: actions.Redirect.create(app),
                Toast: actions.Toast.create(app),
                Loading: actions.Loading.create(app),
                Modal: actions.Modal.create(app),
                TitleBar: actions.TitleBar.create(app)
            };
            
            // If on login page, set up shopify login flow
            setupLoginFlow();
        }
    }
    
    function setupLoginFlow() {
        // Check if we're on the login page
        const loginForm = document.getElementById('loginForm');
        if (!loginForm) return;
        
        const shopInput = document.getElementById('shop');
        if (!shopInput) return;
        
        // Add shop from URL if available
        const urlParams = new URLSearchParams(window.location.search);
        const shopParam = urlParams.get('shop');
        if (shopParam) {
            shopInput.value = shopParam;
        }
        
        // For embedded apps, handle auth differently
        loginForm.addEventListener('submit', function(e) {
            // Only if we're in an iframe
            if (window !== window.parent && window.shopifyActions && window.shopifyActions.Redirect) {
                e.preventDefault();
                
                // Get the shop from the form
                const shopValue = shopInput.value;
                
                // Make sure it's a myshopify.com domain
                let shopUrl = shopValue;
                if (!shopUrl.includes('myshopify.com')) {
                    shopUrl = `${shopUrl}.myshopify.com`;
                }
                
                // Redirect to auth endpoint
                const authUrl = `${window.location.origin}/accounts/login/?shop=${shopUrl}`;
                window.shopifyActions.Redirect.dispatch(
                    window['app-bridge'].actions.Redirect.Action.REMOTE, 
                    authUrl
                );
            }
            // Otherwise regular form submission works
        });
    }
})(); 