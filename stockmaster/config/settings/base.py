"""
Base settings to be imported by specific settings profiles.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-for-development-only')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'cloud-549585597.onetsolutions.network',
    '185.163.125.214',
    '172.25.0.5',
    '172.29.0.5',  # Docker container IP
]

# Add any additional hosts from environment variable
if os.getenv('ALLOWED_HOSTS'):
    ALLOWED_HOSTS.extend(os.getenv('ALLOWED_HOSTS', '').split(','))

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'django_celery_beat',
    'django_celery_results',
    'corsheaders',
]

LOCAL_APPS = [
    'apps.accounts.apps.AccountsConfig',
    'apps.dashboard.apps.DashboardConfig',
    'apps.inventory.apps.InventoryConfig',
    'apps.notifications.apps.NotificationsConfig',
    'apps.rules.apps.RulesConfig',
    'apps.analytics.apps.AnalyticsConfig',
    'core',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.auth.JWTAuthenticationMiddleware',  # Now AFTER Django's AuthenticationMiddleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.shopify_auth.ShopifyAuthMiddleware',
    'core.middleware.ajax.AjaxTemplateResponseMiddleware',  # Process TemplateResponse objects first
    'core.middleware.ajax.AjaxTemplateMiddleware',  # Fallback for other responses
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.static',
                'core.context_processors.settings.settings_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.getenv('DB_NAME', 'stockmaster'),
    }
}

# If using PostgreSQL, set additional required parameters
if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
    DATABASES['default'].update({
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    })

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Add this to make {{ STATIC_URL }} available in templates
TEMPLATE_CONTEXT_PROCESSORS = [
    'django.template.context_processors.static',
]

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configuration
CELERY_BROKER_URL = f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/0"
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Shopify Configuration
SHOPIFY_CLIENT_ID = os.getenv('SHOPIFY_CLIENT_ID')
SHOPIFY_CLIENT_SECRET = os.getenv('SHOPIFY_CLIENT_SECRET')
SHOPIFY_API_SCOPES = os.getenv('SHOPIFY_API_SCOPES', 'read_products,write_products,read_inventory,write_inventory')
SHOPIFY_API_VERSION = '2024-01'  # Use the latest stable API version
APP_URL = os.getenv('APP_URL', 'https://cloud-549585597.onetsolutions.network')
DOMAIN = os.getenv('DOMAIN', 'cloud-549585597.onetsolutions.network')

# Frame embedding settings for Shopify
X_FRAME_OPTIONS = 'ALLOW-FROM https://admin.shopify.com'  # Allow embedding in Shopify Admin
SECURE_CROSS_ORIGIN_OPENER_POLICY = None # Keep as None for broader compatibility initially
CSRF_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [
    'https://admin.shopify.com',
    'https://*.myshopify.com',
    'https://cloud-549585597.onetsolutions.network',
]

# CORS settings for Shopify embedded apps
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    'https://admin.shopify.com',
    'https://*.myshopify.com',
    'https://cloud-549585597.onetsolutions.network',
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']
CORS_ALLOW_HEADERS = [
    'X-Frame-Options',
    'Content-Type',
    'Authorization',
    'X-CSRFToken',
]

# Ensure no Content-Security-Policy header in Django
CSP_DEFAULT_SRC = None
CSP_FRAME_ANCESTORS = None

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
}

# Webhook settings
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.example.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'stockmaster@example.com')

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/stockmaster.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'stockmaster': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Authentication settings
AUTHENTICATION_BACKENDS = [
    'core.auth.ShopifyJWTBackend',  # Our custom Shopify JWT auth backend
    'django.contrib.auth.backends.ModelBackend',  # Django's default auth backend
]

# Login URL - where to redirect for login
LOGIN_URL = '/accounts/login/'

# The URL where requests are redirected after login when no specific next page is provided
LOGIN_REDIRECT_URL = '/'

# The URL where requests are redirected after logout
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Make sessions expire when the browser is closed
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Additional session settings for Shopify embedded apps
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400 * 7  # 1 week in seconds

# Application specific settings
TRIAL_DAYS = int(os.environ.get('TRIAL_DAYS', 14)) 