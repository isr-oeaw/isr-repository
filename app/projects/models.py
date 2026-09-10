from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

User = get_user_model()


class Project(models.Model):
    """Model representing a research project that can use multiple datasets"""
    
    STATUS_CHOICES = [
        ('planning', _('Planning')),
        ('active', _('Active')),
        ('completed', _('Completed')),
        ('on_hold', _('On Hold')),
        ('cancelled', _('Cancelled')),
    ]
    
    ACCESS_LEVEL_CHOICES = [
        ('public', _('Public')),
        ('restricted', _('Restricted')),
        ('private', _('Private')),
    ]
    
    # Basic Information
    title = models.CharField(
        max_length=200,
        verbose_name=_("Project Title"),
        help_text=_("Name of the research project")
    )
    description = models.TextField(
        verbose_name=_("Description"),
        help_text=_("Detailed description of the project objectives and scope")
    )
    abstract = models.TextField(
        blank=True,
        verbose_name=_("Abstract"),
        help_text=_("Brief summary of the project")
    )
    
    # Project Details
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Start Date"),
        help_text=_("Project start date")
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("End Date"),
        help_text=_("Project end date")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planning',
        verbose_name=_("Status")
    )
    access_level = models.CharField(
        max_length=20,
        choices=ACCESS_LEVEL_CHOICES,
        default='private',
        verbose_name=_("Access Level")
    )
    
    # Ownership and Management
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='owned_projects',
        verbose_name=_("Project Owner"),
        help_text=_("User who owns and manages this project")
    )
    collaborators = models.ManyToManyField(
        User,
        blank=True,
        related_name='collaborated_projects',
        verbose_name=_("Collaborators"),
        help_text=_("Users who can collaborate on this project")
    )
    
    # Project Metadata
    keywords = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Keywords"),
        help_text=_("Comma-separated keywords for the project")
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Tags"),
        help_text=_("Comma-separated tags for categorization")
    )
    
    # External References
    project_url = models.URLField(
        blank=True,
        verbose_name=_("Project URL"),
        help_text=_("External URL to project website or repository")
    )
    funding_source = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Funding Source"),
        help_text=_("Organization or agency funding this project")
    )
    grant_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Grant Number"),
        help_text=_("Grant or contract number")
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")
        permissions = [
            ("can_manage_projects", "Can manage all projects"),
        ]
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.pk})
    
    @property
    def duration_days(self):
        """Calculate project duration in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return None
    
    @property
    def is_active(self):
        """Check if project is currently active"""
        return self.status == 'active'
    
    @property
    def is_completed(self):
        """Check if project is completed"""
        return self.status == 'completed'
    
    def is_accessible_by(self, user):
        """Check if user can access this project"""
        if not user or not user.is_authenticated:
            return False
        
        # Owner and collaborators always have access
        if user == self.owner or user in self.collaborators.all():
            return True
        
        # Superusers can access all projects
        if user.is_superuser:
            return True

        # External partners only see projects they are assigned to
        if user.is_external_partner:
            return False
        
        # Public projects are accessible to all authenticated users
        if self.access_level == 'public':
            return True
        
        # Restricted projects require specific permissions
        if self.access_level == 'restricted':
            return user.has_perm('projects.can_manage_projects')
        
        # Private projects are only accessible to owner and collaborators
        return False
    
    def get_keywords_list(self):
        """Return keywords as a list"""
        if self.keywords:
            return [keyword.strip() for keyword in self.keywords.split(',') if keyword.strip()]
        return []
    
    def get_tags_list(self):
        """Return tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []