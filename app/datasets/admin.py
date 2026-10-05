from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Dataset,
    DatasetCategory,
    DatasetVersion,
    DatasetVersionColumn,
    DatasetDownload,
    Comment,
    Publisher,
)


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ['name', 'website_display', 'dataset_count', 'is_active', 'is_default', 'created_at']
    list_filter = ['is_active', 'is_default', 'created_at']
    search_fields = ['name', 'description', 'website']
    list_editable = ['is_active', 'is_default']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'website')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_default')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def website_display(self, obj):
        if obj.website:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.website, obj.website)
        return '-'
    website_display.short_description = 'Website'
    
    def dataset_count(self, obj):
        return obj.datasets.count()
    dataset_count.short_description = 'Datasets'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('datasets')


@admin.register(DatasetCategory)
class DatasetCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color_display', 'dataset_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
    ordering = ['name']

    def color_display(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px;">{}</span>',
            obj.color,
            obj.color
        )
    color_display.short_description = 'Color'

    def dataset_count(self, obj):
        return obj.datasets.count()
    dataset_count.short_description = 'Datasets'


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'owner', 'category', 'projects_display', 'status', 'access_level', 
        'download_count', 'view_count', 'is_featured', 'created_at'
    ]
    list_filter = [
        'status', 'access_level', 'category', 'projects', 'is_featured', 
        'created_at'
    ]
    search_fields = ['title', 'description', 'abstract', 'tags', 'keywords', 'projects__title']
    list_editable = ['status', 'access_level', 'is_featured']
    readonly_fields = ['download_count', 'view_count', 'created_at', 'updated_at', 'published_at']
    filter_horizontal = ['contributors', 'related_datasets', 'projects']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'abstract', 'category', 'tags', 'keywords')
        }),
        ('Access & Status', {
            'fields': ('status', 'access_level', 'is_featured')
        }),
        ('Ownership & Attribution', {
            'fields': ('owner', 'contributors', 'related_datasets', 'projects', 'license', 'citation', 'doi')
        }),
        ('Publishing Information', {
            'fields': ('publisher', 'uri_ref')
        }),
        ('Statistics', {
            'fields': ('download_count', 'view_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner', 'category').prefetch_related('contributors', 'projects')
    
    def projects_display(self, obj):
        """Display projects as a comma-separated list"""
        projects = obj.projects.all()
        if projects:
            return ', '.join([p.title for p in projects])
        return '-'
    projects_display.short_description = 'Projects'


class DatasetVersionColumnInline(admin.TabularInline):
    model = DatasetVersionColumn
    extra = 1
    fields = ['position', 'name', 'label', 'data_type', 'description']
    ordering = ['position', 'id']


@admin.register(DatasetVersion)
class DatasetVersionAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'version_number', 'created_by', 'file_size_display', 'is_current', 'created_at']
    list_filter = ['is_current', 'created_at']
    search_fields = ['dataset__title', 'version_number', 'description']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    inlines = [DatasetVersionColumnInline]
    fieldsets = (
        (None, {
            'fields': (
                'dataset',
                'version_number',
                'description',
                'is_current',
                'created_by',
            ),
        }),
        ('Data description', {
            'fields': (
                'temporal_start',
                'temporal_end',
                'spatial_coverage',
                'unit_of_analysis',
                'observation_count',
            ),
        }),
        ('Files', {
            'fields': (
                'file',
                'file_size',
                'file_size_text',
                'file_url',
                'file_url_description',
            ),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
        }),
    )

    def file_size_display(self, obj):
        if obj.file_size == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = obj.file_size
        
        while size >= 1024 and i < len(size_names) - 1:
            size /= 1024
            i += 1
        
        return f"{size:.1f} {size_names[i]}"
    file_size_display.short_description = 'File Size'


@admin.register(DatasetDownload)
class DatasetDownloadAdmin(admin.ModelAdmin):
    list_display = ['dataset', 'user', 'ip_address', 'downloaded_at']
    list_filter = ['downloaded_at']
    search_fields = ['dataset__title', 'user__username', 'ip_address']
    readonly_fields = ['downloaded_at']
    ordering = ['-downloaded_at']
    date_hierarchy = 'downloaded_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('dataset', 'user')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'dataset', 'content_preview', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'created_at', 'updated_at']
    search_fields = ['content', 'author__username', 'author__email', 'dataset__title']
    list_editable = ['is_approved']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Comment Information', {
            'fields': ('dataset', 'author', 'content', 'is_approved')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content Preview'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author', 'dataset')