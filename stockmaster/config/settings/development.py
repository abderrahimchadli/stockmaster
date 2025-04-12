from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*', 'localhost', '127.0.0.1', DOMAIN]

# CORS settings
CORS_ALLOW_ALL_ORIGINS = True

# Enable debug toolbar for development
INSTALLED_APPS += [
    'debug_toolbar',
]

MIDDLEWARE += [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
]

# For Django Debug Toolbar
INTERNAL_IPS = [
    '127.0.0.1',
]

# Simplified email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable secure SSL redirect in development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Set CSRF_TRUSTED_ORIGINS for development
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    f'https://{DOMAIN}',
    'https://admin.shopify.com'
]

# SameSite cookie setting for development
SESSION_COOKIE_SAMESITE = 'None'

# Optional - configure logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'stockmaster': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
} 