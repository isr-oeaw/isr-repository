from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.utils import user_pk_to_url_str

from .tokens import magic_login_token

User = get_user_model()


def build_magic_login_url(user, request=None):
    """Build a signed magic-login URL for the given user."""
    token = magic_login_token.make_token(user)
    uid = user_pk_to_url_str(user)
    path = reverse('user-magic-login', kwargs={'uidb36': uid, 'token': token})
    if request is not None:
        return request.build_absolute_uri(path)
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    return f'{site_url}{path}'


class AccountAdapter(DefaultAccountAdapter):
    """Extend allauth emails with magic-login links for login-code messages."""

    def send_mail(self, template_prefix, email, context):
        if template_prefix == 'account/email/login_code':
            user = context.get('user')
            if user is None:
                user = User.objects.filter(email__iexact=email).first()
            if user is not None:
                context['magic_login_url'] = build_magic_login_url(user, self.request)
                context.setdefault('site_name', getattr(settings, 'SITE_NAME', 'ISR Datasets'))
        return super().send_mail(template_prefix, email, context)
