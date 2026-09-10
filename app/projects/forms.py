from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from .models import Project

User = get_user_model()


class ProjectForm(forms.ModelForm):
    """Form for creating and editing projects"""
    
    class Meta:
        model = Project
        fields = [
            'title', 'description', 'abstract', 'start_date', 'end_date',
            'status', 'access_level', 'keywords', 'tags', 'project_url',
            'funding_source', 'grant_number', 'collaborators'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter project title')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Describe the project objectives and scope...')
            }),
            'abstract': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Brief summary of the project...')
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'access_level': forms.Select(attrs={
                'class': 'form-select'
            }),
            'keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter keywords separated by commas')
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter tags separated by commas')
            }),
            'project_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': _('https://example.com/project')
            }),
            'funding_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Funding organization name')
            }),
            'grant_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Grant or contract number')
            }),
            'collaborators': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'size': 5
            })
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Configure collaborators queryset to exclude the current user
        if user and user.is_authenticated:
            self.fields['collaborators'].queryset = User.objects.exclude(pk=user.pk)
        
        # Add help text for fields
        self.fields['title'].help_text = _('A descriptive title for the project')
        self.fields['description'].help_text = _('Detailed description of project objectives and scope')
        self.fields['abstract'].help_text = _('Brief summary for quick understanding')
        self.fields['start_date'].help_text = _('When the project starts')
        self.fields['end_date'].help_text = _('When the project is expected to end')
        self.fields['status'].help_text = _('Current status of the project')
        self.fields['access_level'].help_text = _('Who can view this project')
        self.fields['keywords'].help_text = _('Comma-separated keywords for searching')
        self.fields['tags'].help_text = _('Comma-separated tags for categorization')
        self.fields['project_url'].help_text = _('External URL to project website or repository')
        self.fields['funding_source'].help_text = _('Organization funding this project')
        self.fields['grant_number'].help_text = _('Grant or contract identifier')
        self.fields['collaborators'].help_text = _('Users who can collaborate on this project')
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError(_('End date must be after start date.'))
        
        return cleaned_data
    
    def clean_keywords(self):
        keywords = self.cleaned_data.get('keywords', '')
        if keywords:
            # Remove extra spaces and validate
            keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
            if len(keyword_list) > 20:
                raise forms.ValidationError(_('Maximum 20 keywords allowed.'))
        return keywords
    
    def clean_tags(self):
        tags = self.cleaned_data.get('tags', '')
        if tags:
            # Remove extra spaces and validate
            tag_list = [t.strip() for t in tags.split(',') if t.strip()]
            if len(tag_list) > 15:
                raise forms.ValidationError(_('Maximum 15 tags allowed.'))
        return tags


class ProjectTransferOwnershipForm(forms.Form):
    """Form for transferring project ownership"""
    
    new_owner = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label=_('New Owner'),
        help_text=_('Select the user who will become the new owner of this project')
    )
    
    confirm_transfer = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label=_('I confirm that I want to transfer ownership'),
        help_text=_('This action cannot be undone. You will become a collaborator instead of the owner.')
    )
    
    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        
        if current_user and project:
            # Exclude current owner and include current collaborators
            excluded_users = [current_user.pk]
            if project.owner:
                excluded_users.append(project.owner.pk)
            
            # Get all users except current owner and current user
            queryset = User.objects.exclude(pk__in=excluded_users).order_by('username')
            self.fields['new_owner'].queryset = queryset
            
            # Add current collaborators to the top of the list
            if project.collaborators.exists():
                collaborator_ids = list(project.collaborators.values_list('pk', flat=True))
                # Reorder queryset to show collaborators first
                collaborators = User.objects.filter(pk__in=collaborator_ids).order_by('username')
                other_users = queryset.exclude(pk__in=collaborator_ids)
                # Combine and set as queryset
                from django.db.models import QuerySet
                combined_queryset = QuerySet(model=User)
                combined_queryset._result_cache = list(collaborators) + list(other_users)
                self.fields['new_owner'].queryset = combined_queryset
    
    def clean_new_owner(self):
        new_owner = self.cleaned_data.get('new_owner')
        if not new_owner:
            raise forms.ValidationError(_('Please select a new owner for the project.'))
        return new_owner


class ProjectFilterForm(forms.Form):
    """Form for filtering projects"""
    
    STATUS_CHOICES = [('', _('All Statuses'))] + Project.STATUS_CHOICES
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search projects...')
        }),
        label=_('Search')
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label=_('Status')
    )


class ProjectPartnerInviteForm(forms.Form):
    """Invite an external partner to collaborate on a project."""

    email = forms.EmailField(
        label=_('Email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _('partner@example.com'),
        }),
    )
    first_name = forms.CharField(
        label=_('First name'),
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    last_name = forms.CharField(
        label=_('Last name'),
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
