"""
Context processors for the main Django application.
"""
from django.conf import settings


def site_settings(request):
    """Context processor to provide site settings to all templates"""
    return {
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'ISR Repository'),
        'SITE_URL': getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/'),
    }




