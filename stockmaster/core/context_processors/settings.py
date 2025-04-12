from django.conf import settings

def settings_context(request):
    """
    Context processor that adds Django settings to the template context
    """
    return {
        'settings': settings
    } 