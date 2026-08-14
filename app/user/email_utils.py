import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _

from allauth.account.adapter import get_adapter
from allauth.account.utils import user_pk_to_url_str

logger = logging.getLogger(__name__)


def build_password_set_url(user, request=None):
    """Build an allauth password-set URL for a newly invited user."""
    adapter = get_adapter()
    token = adapter.get_token_generator().make_token(user)
    uid = user_pk_to_url_str(user)
    path = reverse(
        'account_reset_password_from_key',
        kwargs={'uidb36': uid, 'key': token},
    )
    if request is not None:
        return request.build_absolute_uri(path)
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    return f'{site_url}{path}'


def send_account_invite_email(user, request=None):
    """Send a welcome email with login details and a link to set the password."""
    password_set_url = build_password_set_url(user, request=request)
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    site_name = getattr(settings, 'SITE_NAME', 'ISR Repository')
    login_url = f'{site_url}{reverse("account_login")}'

    context = {
        'user': user,
        'username': user.username,
        'email': user.email,
        'role_name': user.role.name if user.role else None,
        'site_name': site_name,
        'site_url': site_url,
        'login_url': login_url,
        'password_set_url': password_set_url,
    }

    subject = _('Your %(site_name)s account has been created') % {'site_name': site_name}
    html_message = render_to_string('user/email/account_invite_message.html', context)
    plain_message = render_to_string('user/email/account_invite_message.txt', context)

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info('Account invite email sent to %s', user.email)
        return True
    except Exception as exc:
        logger.error('Failed to send account invite email to %s: %s', user.email, exc, exc_info=True)
        return False
