import secrets
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from auditlog.registry import auditlog
from auditlog.models import AuditlogHistoryField

from .access import EXTERNAL_PARTNER_ROLE


class Role(models.Model):
    """Role model for role-based access control"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_permissions(self):
        """Get list of permissions for this role"""
        if isinstance(self.permissions, list):
            return self.permissions
        elif isinstance(self.permissions, dict):
            return self.permissions.get('permissions', [])
        return []

    def has_permission(self, permission):
        """Check if role has specific permission"""
        return permission in self.get_permissions()


class CustomUser(AbstractUser):
    history = AuditlogHistoryField()
    
    # Add role field
    role = models.ForeignKey(
        Role, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='users'
    )
    
    # Language preference
    language = models.CharField(
        max_length=10,
        choices=[
            ('en', _('English')),
            ('de', _('German')),
        ],
        default='en',
        verbose_name=_('Language'),
        help_text=_('Preferred language for the interface')
    )
    
    # Notification preferences
    email_notifications = models.BooleanField(
        default=False,
        verbose_name=_('Email Notifications'),
        help_text=_('Receive email notifications for comments on your datasets')
    )
    
    # Dataset notification preferences
    notify_dataset_updates = models.BooleanField(
        default=False,
        verbose_name=_('Dataset Updates'),
        help_text=_('Receive email notifications when datasets you follow are updated')
    )
    
    notify_new_versions = models.BooleanField(
        default=False,
        verbose_name=_('New Versions'),
        help_text=_('Receive email notifications when new versions of datasets you follow are published')
    )
    
    notify_comments = models.BooleanField(
        default=False,
        verbose_name=_('Comments'),
        help_text=_('Receive email notifications for comments on your datasets')
    )
    
    # User approval system
    is_approved = models.BooleanField(
        default=False,
        verbose_name=_('Approved'),
        help_text=_('Whether this user has been approved by an administrator')
    )
    
    # First login tracking for help section
    first_login_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('First Login Date'),
        help_text=_('Date of the user\'s first login')
    )
    
    # Add related_name to avoid field clashes
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user',
    )

    class Meta:
        ordering = ['username']

    def __str__(self):
        return f"{self.username} ({self.email})"

    def has_role_permission(self, permission):
        """Check if user has permission through their role"""
        if self.role and self.role.is_active:
            return self.role.has_permission(permission)
        return False

    def get_all_permissions(self):
        """Get all permissions for the user (Django + role-based)"""
        permissions = set()
        
        # Django permissions
        permissions.update(self.get_group_permissions())
        permissions.update(self.get_user_permissions())
        
        # Role-based permissions
        if self.role and self.role.is_active:
            permissions.update(self.role.get_permissions())
        
        return permissions

    def has_any_permission(self, permissions):
        """Check if user has any of the given permissions"""
        user_permissions = self.get_all_permissions()
        return any(perm in user_permissions for perm in permissions)

    def is_group_admin_of(self, group):
        """Check if user is a group admin of a specific group"""
        return group.has_group_admin(self)

    def get_group_admin_groups(self):
        """Get all groups where the user is a group admin"""
        from group.models import Group
        return Group.objects.filter(
            members__user=self,
            members__role='admin',
            members__is_active=True
        )

    def is_group_admin_anywhere(self):
        """Check if user is a group admin of any group"""
        return self.get_group_admin_groups().exists()

    def is_email_verified(self):
        """Check if the user's email is verified"""
        try:
            from allauth.account.models import EmailAddress
            email_address = EmailAddress.objects.get(user=self, email=self.email)
            return email_address.verified
        except (ImportError, EmailAddress.DoesNotExist):
            # If allauth is not available or no EmailAddress record exists,
            # assume email is verified (for backwards compatibility)
            return True

    @property
    def is_external_partner(self):
        """Return True when the user has the External Partner role."""
        return bool(
            self.role
            and self.role.is_active
            and self.role.name == EXTERNAL_PARTNER_ROLE
        )

    def assigned_projects(self):
        """Projects the user owns or collaborates on."""
        from projects.models import Project

        return Project.objects.filter(
            Q(owner=self) | Q(collaborators=self)
        ).distinct()

    def assigned_datasets(self):
        """Datasets linked to projects the user is assigned to."""
        from datasets.models import Dataset

        return Dataset.objects.filter(
            projects__in=self.assigned_projects()
        ).distinct()


class APIKey(models.Model):
    """API Key model for user authentication"""
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name=_('User'),
        help_text=_('The user who owns this API key')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('Name'),
        help_text=_('A descriptive name for this API key (e.g., "My Script", "Production API")')
    )
    key = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_('API Key'),
        help_text=_('The API key value (shown only once when created)')
    )
    prefix = models.CharField(
        max_length=8,
        verbose_name=_('Key Prefix'),
        help_text=_('First 8 characters of the key for identification')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Whether this API key is active and can be used')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
        help_text=_('When this API key was created')
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Used At'),
        help_text=_('When this API key was last used')
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Expires At'),
        help_text=_('Optional expiration date for this API key')
    )

    class Meta:
        verbose_name = _('API Key')
        verbose_name_plural = _('API Keys')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.prefix}...)" if self.prefix else f"{self.name}"

    @classmethod
    def generate_key(cls, user, name, expires_at=None):
        """Generate a new API key for a user"""
        # Generate a secure random key (64 characters)
        key = secrets.token_urlsafe(48)  # Generates ~64 character URL-safe string
        prefix = key[:8]
        
        api_key = cls.objects.create(
            user=user,
            name=name,
            key=key,
            prefix=prefix,
            expires_at=expires_at
        )
        return api_key

    def is_expired(self):
        """Check if the API key has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    def is_valid(self):
        """Check if the API key is valid (active and not expired)"""
        return self.is_active and not self.is_expired()

    def update_last_used(self):
        """Update the last used timestamp"""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])

    def revoke(self):
        """Revoke the API key"""
        self.is_active = False
        self.save(update_fields=['is_active'])


# Register models for audit logging
auditlog.register(CustomUser)
auditlog.register(Role)
auditlog.register(APIKey)