import os
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from auditlog.registry import auditlog
from auditlog.models import AuditlogHistoryField

User = get_user_model()


def dataset_version_upload_path(instance, filename):
    """
    Custom upload path for dataset version files.
    Includes dataset ID in the filename to avoid conflicts.
    Format: datasets/versions/YYYY/MM/DD/dataset_{id}_version_{version}_{filename}
    """
    # Get the current date for directory structure
    now = timezone.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')
    day = now.strftime('%d')
    
    # Get file extension
    _, ext = os.path.splitext(filename)
    
    # Create filename with dataset ID and version number
    safe_filename = f"dataset_{instance.dataset.id}_version_{instance.version_number}_{filename}"
    
    # Return the full path
    return f'datasets/versions/{year}/{month}/{day}/{safe_filename}'


def dataset_version_attachment_upload_path(instance, filename):
    """
    Upload path for additional files associated with a dataset version.
    Mirrors the main dataset version upload path but uses the DatasetVersionFile instance.
    """
    now = timezone.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')
    day = now.strftime('%d')
    
    dataset_id = instance.version.dataset.id
    version_number = instance.version.version_number
    
    safe_filename = f"dataset_{dataset_id}_version_{version_number}_{filename}"
    
    # Return the full path
    return f'datasets/versions/{year}/{month}/{day}/{safe_filename}'


def dataset_analysis_upload_path(instance, filename):
    """
    Custom upload path for dataset analysis/dataviz files.
    Format: datasets/analysis/YYYY/MM/DD/dataset_{id}_{filename}
    """
    now = timezone.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')
    day = now.strftime('%d')
    
    dataset_id = instance.dataset.id
    
    safe_filename = f"dataset_{dataset_id}_{filename}"
    
    return f'datasets/analysis/{year}/{month}/{day}/{safe_filename}'


class Publisher(models.Model):
    """Model for dataset publishers"""
    name = models.CharField(
        max_length=200, 
        unique=True,
        verbose_name=_('Name'),
        help_text=_('Name of the publisher (e.g., University of Vienna, Research Institute)')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Optional description of the publisher')
    )
    website = models.URLField(
        blank=True,
        verbose_name=_('Website'),
        help_text=_('Official website of the publisher')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Active'),
        help_text=_('Whether this publisher is active and available for selection')
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_('Default'),
        help_text=_('Whether this is the default publisher for new datasets')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Publisher')
        verbose_name_plural = _('Publishers')
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure only one default publisher
        if self.is_default:
            Publisher.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class DatasetCategory(models.Model):
    """Category model for organizing datasets"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff', help_text='Hex color code')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Dataset Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Dataset(models.Model):
    """Main dataset model"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
        ('private', 'Private'),
    ]
    
    ACCESS_LEVEL_CHOICES = [
        ('public', 'Public'),
        ('restricted', 'Restricted'),
        ('private', 'Private'),
    ]

    # Primary key as UUID
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_('ID'),
        help_text=_('Unique identifier for the dataset')
    )
    
    history = AuditlogHistoryField()
    
    # Basic information
    title = models.CharField(max_length=200)
    description = models.TextField()
    abstract = models.TextField(blank=True, help_text='Short summary of the dataset')
    
    # Metadata
    category = models.ForeignKey(
        DatasetCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='datasets'
    )
    tags = models.CharField(max_length=500, blank=True, help_text='Comma-separated tags')
    
    # Access and permissions
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='public')
    is_featured = models.BooleanField(default=False)
    
    # Ownership and attribution
    owner = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='owned_datasets'
    )
    contributors = models.ManyToManyField(
        User, 
        blank=True, 
        related_name='contributed_datasets',
        help_text='Users who contributed to this dataset'
    )
    
    # Related datasets
    related_datasets = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='related_to',
        help_text='Other datasets that are related to this one'
    )
    
    # Project association
    projects = models.ManyToManyField(
        'projects.Project',
        blank=True,
        related_name='datasets',
        verbose_name=_("Projects"),
        help_text=_("The research projects this dataset is associated with")
    )
    
    # License and citation
    license = models.CharField(max_length=100, blank=True)
    citation = models.TextField(blank=True, help_text='How to cite this dataset')
    doi = models.CharField(max_length=100, blank=True, help_text='Digital Object Identifier')
    
    # Publishing information
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='datasets',
        verbose_name=_('Publisher'),
        help_text=_('The organization or institution that published this dataset')
    )
    uri_ref = models.URLField(
        blank=True, 
        help_text='URI reference for the dataset (e.g., persistent identifier, institutional URL)'
    )
    
    
    # Statistics
    download_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'access_level']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Set published_at when status changes to published
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_file_size_display(self):
        """Return human-readable file size"""
        if self.file_size == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = self.file_size
        
        while size >= 1024 and i < len(size_names) - 1:
            size /= 1024
            i += 1
        
        return f"{size:.1f} {size_names[i]}"

    def get_tags_list(self):
        """Return tags as a list"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

    def is_accessible_by(self, user):
        """Check if user can access this dataset"""
        if self.access_level == 'public':
            return True
        elif self.access_level == 'restricted':
            return user and user.is_authenticated
        elif self.access_level == 'private':
            return user and (user == self.owner or user.is_superuser)
        return False

    def get_available_formats(self):
        """Get list of available data formats from dataset versions"""
        import os
        formats = set()
        
        for version in self.versions.all():
            if version.file:
                # Get file extension
                _, ext = os.path.splitext(version.file.name)
                if ext:
                    # Remove the dot and convert to uppercase
                    format_name = ext[1:].upper()
                    formats.add(format_name)
            # Include additional uploaded files
            if hasattr(version, 'files'):
                for attachment in version.files.all():
                    _, ext = os.path.splitext(attachment.file.name)
                    if ext:
                        format_name = ext[1:].upper()
                        formats.add(format_name)
            if version.file_url:
                # For external URLs, try to extract format from URL
                url_lower = version.file_url.lower()
                supported_extensions = [
                    '.csv', '.json', '.xlsx', '.xls', '.txt', '.zip', '.tar.gz', '.gpkg',
                    '.shp', '.shx', '.dbf', '.prj', '.sbn', '.sbx', '.shp.xml', '.cpg',
                    '.geojson', '.kml', '.kmz', '.tif', '.tiff', '.jpg', '.jpeg', '.png', '.img',
                    '.gdb', '.mdb', '.lyr', '.lyrx', '.mpk', '.mpkx', '.qgs', '.qgz', '.qml',
                    '.sqlite', '.sql', '.sav', '.zsav', '.por', '.dta', '.rds', '.pdf'
                ]
                if any(ext in url_lower for ext in supported_extensions):
                    for ext in supported_extensions:
                        if ext in url_lower:
                            format_name = ext[1:].upper()
                            if ext == '.tar.gz':
                                format_name = 'TAR.GZ'
                            elif ext == '.shp.xml':
                                format_name = 'SHP.XML'
                            formats.add(format_name)
                            break
        
        return sorted(list(formats))


class DatasetVersion(models.Model):
    """Version control for datasets"""
    dataset = models.ForeignKey(
        Dataset, 
        on_delete=models.CASCADE, 
        related_name='versions'
    )
    version_number = models.CharField(max_length=20)
    description = models.TextField(blank=True, help_text='Changes in this version')
    file = models.FileField(upload_to=dataset_version_upload_path, blank=True, null=True)
    file_size = models.BigIntegerField(default=0)
    file_url = models.URLField(blank=True, help_text='External URL to the file')
    file_url_description = models.TextField(blank=True, help_text='Description of the external file location')
    file_size_text = models.CharField(max_length=100, blank=True, help_text='Human-readable file size (e.g., "2.5 MB", "1.2 GB")')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=False)

    temporal_start = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Temporal coverage start'),
        help_text=_('Start of the time period covered by this version'),
    )
    temporal_end = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Temporal coverage end'),
        help_text=_('End of the time period covered by this version'),
    )
    spatial_coverage = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Spatial coverage'),
        help_text=_('Geographic area covered (e.g. Germany, NUTS-2)'),
    )
    unit_of_analysis = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Unit of analysis'),
        help_text=_('e.g. person, household, country-year'),
    )
    observation_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Number of observations'),
    )

    class Meta:
        ordering = ['-created_at']
        unique_together = ['dataset', 'version_number']

    def __str__(self):
        return f"{self.dataset.title} v{self.version_number}"
    
    def get_file_size_display(self):
        """Return human-readable file size"""
        if self.file_size_text:
            return self.file_size_text
        attachments_manager = getattr(self, 'files', None)
        if attachments_manager and attachments_manager.exists():
            attachments = list(attachments_manager.all())
            total_size = self.file_size or sum(f.file_size for f in attachments)
            size_names = ["B", "KB", "MB", "GB", "TB"]
            i = 0
            size = total_size
            
            while size >= 1024 and i < len(size_names) - 1:
                size /= 1024
                i += 1
            
            human_size = f"{size:.1f} {size_names[i]}"
            count = len(attachments)
            return f"{count} file{'s' if count != 1 else ''}, {human_size}"
        elif self.file_size > 0:
            size_names = ["B", "KB", "MB", "GB", "TB"]
            i = 0
            size = self.file_size
            
            while size >= 1024 and i < len(size_names) - 1:
                size /= 1024
                i += 1
            
            return f"{size:.1f} {size_names[i]}"
        return "Unknown size"
    
    def has_file(self):
        """Check if version has either uploaded file, external URL, or URL description"""
        if self.file:
            return True
        if hasattr(self, 'files') and self.files.exists():
            return True
        return bool(self.file_url or self.file_url_description)

    def get_temporal_coverage_display(self):
        """Human-readable temporal coverage for this version."""
        if self.temporal_start and self.temporal_end:
            return f'{self.temporal_start.isoformat()} – {self.temporal_end.isoformat()}'
        if self.temporal_start:
            return _('From %(date)s') % {'date': self.temporal_start.isoformat()}
        if self.temporal_end:
            return _('Until %(date)s') % {'date': self.temporal_end.isoformat()}
        return ''

    def has_data_description(self):
        """True if this version has any data-description metadata."""
        if any([
            self.temporal_start,
            self.temporal_end,
            self.spatial_coverage.strip(),
            self.unit_of_analysis.strip(),
            self.observation_count is not None,
        ]):
            return True
        return self.columns.exists()


class DatasetVersionColumn(models.Model):
    """Column/variable dictionary for a dataset version."""

    DATA_TYPE_CHOICES = [
        ('text', _('Text')),
        ('integer', _('Integer')),
        ('decimal', _('Decimal')),
        ('date', _('Date')),
        ('boolean', _('Boolean')),
        ('categorical', _('Categorical')),
    ]

    version = models.ForeignKey(
        DatasetVersion,
        on_delete=models.CASCADE,
        related_name='columns',
    )
    position = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=255, verbose_name=_('Name'))
    label = models.CharField(max_length=255, blank=True, verbose_name=_('Label'))
    data_type = models.CharField(
        max_length=20,
        choices=DATA_TYPE_CHOICES,
        default='text',
        verbose_name=_('Data type'),
    )
    description = models.TextField(blank=True, verbose_name=_('Description'))

    class Meta:
        ordering = ['position', 'id']
        verbose_name = _('Dataset version column')
        verbose_name_plural = _('Dataset version columns')

    def __str__(self):
        return self.name


class DatasetVersionFile(models.Model):
    """Individual files associated with a dataset version."""
    version = models.ForeignKey(
        DatasetVersion,
        on_delete=models.CASCADE,
        related_name='files'
    )
    file = models.FileField(upload_to=dataset_version_attachment_upload_path)
    file_size = models.BigIntegerField(default=0)
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at', 'id']

    def __str__(self):
        display_name = self.display_name
        return f"{self.version.dataset.title} v{self.version.version_number} - {display_name}"

    @property
    def display_name(self):
        if self.original_name:
            return self.original_name
        return os.path.basename(self.file.name)


class DatasetDownload(models.Model):
    """Track dataset downloads"""
    dataset = models.ForeignKey(
        Dataset, 
        on_delete=models.CASCADE, 
        related_name='downloads'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-downloaded_at']
        indexes = [
            models.Index(fields=['dataset', 'downloaded_at']),
            models.Index(fields=['user', 'downloaded_at']),
        ]

    def __str__(self):
        user_info = self.user.username if self.user else 'Anonymous'
        return f"{self.dataset.title} - {user_info}"


class Comment(models.Model):
    """Comment model for datasets"""
    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Dataset')
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dataset_comments',
        verbose_name=_('Author')
    )
    content = models.TextField(
        verbose_name=_('Comment'),
        help_text=_('Your comment about this dataset')
    )
    is_approved = models.BooleanField(
        default=True,
        verbose_name=_('Approved'),
        help_text=_('Whether this comment is approved and visible to others')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at')
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')

    def __str__(self):
        return f"Comment by {self.author.username} on {self.dataset.title}"

    def can_edit(self, user):
        """Check if user can edit this comment"""
        return user == self.author or user.is_staff or user.is_superuser

    def can_delete(self, user):
        """Check if user can delete this comment"""
        return user == self.author or user.is_staff or user.is_superuser


class DatasetAnalysis(models.Model):
    """Model for storing analysis/dataviz files related to a dataset"""
    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name='analyses',
        verbose_name=_('Dataset')
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_('Title'),
        help_text=_('Title or name of this analysis/visualization')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Optional description of the analysis or visualization')
    )
    file = models.FileField(
        upload_to=dataset_analysis_upload_path,
        verbose_name=_('File'),
        help_text=_('Upload your analysis or visualization file')
    )
    file_size = models.BigIntegerField(default=0)
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dataset_analyses',
        verbose_name=_('Uploaded by')
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = _('Dataset Analysis')
        verbose_name_plural = _('Dataset Analyses')
        indexes = [
            models.Index(fields=['dataset', 'uploaded_at']),
            models.Index(fields=['uploaded_by', 'uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.dataset.title} - {self.title}"
    
    @property
    def display_name(self):
        if self.original_name:
            return self.original_name
        return os.path.basename(self.file.name)
    
    def get_file_size_display(self):
        """Return human-readable file size"""
        if self.file_size == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = self.file_size
        
        while size >= 1024 and i < len(size_names) - 1:
            size /= 1024
            i += 1
        
        return f"{size:.1f} {size_names[i]}"
    
    def can_delete(self, user):
        """Check if user can delete this analysis"""
        return (
            user == self.uploaded_by or
            user == self.dataset.owner or
            user.is_staff or
            user.is_superuser
        )


# Register models for audit logging
auditlog.register(Publisher)
auditlog.register(Dataset)
auditlog.register(DatasetCategory)
auditlog.register(DatasetVersion)
auditlog.register(DatasetVersionColumn)
auditlog.register(DatasetVersionFile)
auditlog.register(Comment)
auditlog.register(DatasetDownload)
auditlog.register(DatasetAnalysis)