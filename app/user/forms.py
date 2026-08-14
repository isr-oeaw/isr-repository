from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, SetPasswordForm
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Role, APIKey

CustomUser = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    role = forms.ModelChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        empty_label="No role assigned"
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role')
    
    def __init__(self, *args, **kwargs):
        self.created_by_admin = kwargs.pop('created_by_admin', False)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        user = super().save(commit=False)
        # If created by an admin, auto-approve the user
        if self.created_by_admin:
            user.is_approved = True
        if commit:
            user.save()
        return user


class CustomUserEditForm(UserChangeForm):
    role = forms.ModelChoiceField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
        empty_label="No role assigned"
    )
    
    is_staff = forms.BooleanField(
        required=False,
        label=_('Staff'),
        help_text=_('Designates whether the user can log into the admin site.')
    )
    
    is_superuser = forms.BooleanField(
        required=False,
        label=_('Superuser'),
        help_text=_('Designates that this user has all permissions without explicitly assigning them.')
    )
    
    is_approved = forms.BooleanField(
        required=False,
        label=_('Approved'),
        help_text=_('Whether this user has been approved by an administrator')
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_superuser', 'is_approved')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to form fields
        for field_name, field in self.fields.items():
            if field_name == 'role':
                field.widget.attrs.update({'class': 'form-select'})
            elif field_name in ['is_staff', 'is_superuser']:
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            # Check if username is already taken by another user
            existing_user = CustomUser.objects.filter(username=username).exclude(pk=self.instance.pk)
            if existing_user.exists():
                raise forms.ValidationError(_('A user with this username already exists.'))
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if email is already taken by another user
            existing_user = CustomUser.objects.filter(email=email).exclude(pk=self.instance.pk)
            if existing_user.exists():
                raise forms.ValidationError(_('A user with this email address already exists.'))
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        is_superuser = cleaned_data.get('is_superuser')
        is_staff = cleaned_data.get('is_staff')
        
        # If user is being made a superuser, they should also be staff
        if is_superuser and not is_staff:
            cleaned_data['is_staff'] = True
            # Add a non-field error to inform the user
            self.add_error('is_staff', _('Superusers must also be staff members. This has been automatically set.'))
        
        return cleaned_data


class UserProfileForm(forms.ModelForm):
    """Form for user profile information"""
    
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].label = _('First Name')
        self.fields['last_name'].label = _('Last Name')


class UserSettingsForm(forms.ModelForm):
    """Form for user account settings including language preference and notifications"""
    
    class Meta:
        model = CustomUser
        fields = ['language', 'notify_dataset_updates', 'notify_new_versions', 'notify_comments']
        widgets = {
            'language': forms.Select(attrs={
                'class': 'form-select'
            }),
            'notify_dataset_updates': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notify_new_versions': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notify_comments': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['language'].label = _('Interface Language')
        self.fields['language'].help_text = _('Choose your preferred language for the interface')
        self.fields['notify_dataset_updates'].label = _('Dataset Updates')
        self.fields['notify_dataset_updates'].help_text = _('Receive email notifications when datasets you follow are updated')
        self.fields['notify_new_versions'].label = _('New Versions')
        self.fields['notify_new_versions'].help_text = _('Receive email notifications when new versions of datasets you follow are published')
        self.fields['notify_comments'].label = _('Comments')
        self.fields['notify_comments'].help_text = _('Receive email notifications for comments on your datasets')


class UserNotificationForm(forms.ModelForm):
    """Form for user notification preferences only"""
    
    class Meta:
        model = CustomUser
        fields = ['notify_dataset_updates', 'notify_new_versions', 'notify_comments']
        widgets = {
            'notify_dataset_updates': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notify_new_versions': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notify_comments': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notify_dataset_updates'].label = _('Dataset Updates')
        self.fields['notify_dataset_updates'].help_text = _('Receive email notifications when datasets you follow are updated')
        self.fields['notify_new_versions'].label = _('New Versions')
        self.fields['notify_new_versions'].help_text = _('Receive email notifications when new versions of datasets you follow are published')
        self.fields['notify_comments'].label = _('Comments')
        self.fields['notify_comments'].help_text = _('Receive email notifications for comments on your datasets')


class DataExportForm(forms.Form):
    """Form for requesting data export"""
    
    EXPORT_FORMATS = [
        ('json', _('JSON')),
        ('csv', _('CSV')),
        ('xml', _('XML')),
    ]
    
    format = forms.ChoiceField(
        choices=EXPORT_FORMATS,
        initial='json',
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label=_('Export Format'),
        help_text=_('Choose the format for your data export')
    )
    
    include_datasets = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_('Include Datasets'),
        help_text=_('Include your datasets in the export')
    )
    
    include_projects = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_('Include Projects'),
        help_text=_('Include your projects in the export')
    )
    
    include_activity = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_('Include Activity Log'),
        help_text=_('Include your activity and download history')
    )


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['name', 'description', 'permissions']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'permissions': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Enter permissions as JSON array, e.g.: ["user.view", "user.edit", "user.delete"]'}),
        }

    def clean_permissions(self):
        permissions = self.cleaned_data.get('permissions')
        if isinstance(permissions, str):
            import json
            try:
                permissions = json.loads(permissions)
            except json.JSONDecodeError:
                raise forms.ValidationError("Invalid JSON format for permissions")
        
        if not isinstance(permissions, dict):
            permissions = {'permissions': permissions if isinstance(permissions, list) else []}
        
        return permissions


class RoleFilterForm(forms.Form):
    """Form for filtering roles in the role list view"""
    name = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'Search by name'}))
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('True', 'Active'), ('False', 'Inactive')],
        required=False,
        initial=''
    )


class APIKeyCreateForm(forms.Form):
    """Form for creating a new API key"""
    name = forms.CharField(
        max_length=100,
        required=True,
        label=_('Name'),
        help_text=_('A descriptive name for this API key (e.g., "My Script", "Production API")'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('e.g., My Script, Production API')
        })
    )
    expires_at = forms.DateTimeField(
        required=False,
        label=_('Expiration Date (Optional)'),
        help_text=_('Optional: Set an expiration date for this API key. Leave empty for no expiration.'),
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    def clean_expires_at(self):
        """Validate that expiration date is in the future"""
        expires_at = self.cleaned_data.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise forms.ValidationError(_('Expiration date must be in the future.'))
        return expires_at


class APIKeyRevokeForm(forms.Form):
    """Form for revoking an API key"""
    api_key_id = forms.IntegerField(
        required=True,
        widget=forms.HiddenInput()
    )
    confirm = forms.BooleanField(
        required=True,
        label=_('I understand that this action cannot be undone'),
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )


class AdminSetPasswordForm(SetPasswordForm):
    """Allow administrators to set a new password for another user."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})