from django.contrib.auth.tokens import PasswordResetTokenGenerator


class MagicLoginTokenGenerator(PasswordResetTokenGenerator):
    """One-time magic login links invalidated after login (last_login changes)."""

    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{user.last_login}{user.is_active}{timestamp}'


magic_login_token = MagicLoginTokenGenerator()
