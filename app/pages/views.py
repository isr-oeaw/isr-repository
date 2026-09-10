import logging
import requests
import json
from datetime import datetime, timedelta

from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.conf import settings
from django.db.models import Count, Sum, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class HomePageView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['host'] = self.request.get_host()
        context['API_URL'] = settings.API_URL
        
        # Get real data from models
        try:
            from datasets.models import Dataset, DatasetVersion, DatasetCategory
            from user.models import CustomUser
            from projects.models import Project
            
            user = self.request.user
            is_partner = user.is_authenticated and user.is_external_partner
            assigned_datasets = user.assigned_datasets() if is_partner else None
            assigned_projects = user.assigned_projects() if is_partner else None

            # Get basic statistics
            if is_partner:
                total_datasets = assigned_datasets.filter(status='published').count()
                total_projects = assigned_projects.count()
            else:
                total_datasets = Dataset.objects.filter(status='published').count()
                total_projects = Project.objects.count()
            total_users = CustomUser.objects.filter(is_active=True).count()
            
            # Calculate total data volume (sum of all file sizes)
            if is_partner:
                total_data_volume = DatasetVersion.objects.filter(
                    dataset__in=assigned_datasets
                ).aggregate(total_size=Sum('file_size'))['total_size'] or 0
            else:
                total_data_volume = DatasetVersion.objects.aggregate(
                    total_size=Sum('file_size')
                )['total_size'] or 0
            
            # Convert bytes to human readable format
            if total_data_volume > 1024**4:  # TB
                data_volume_display = f"{total_data_volume / (1024**4):.1f}TB"
            elif total_data_volume > 1024**3:  # GB
                data_volume_display = f"{total_data_volume / (1024**3):.1f}GB"
            elif total_data_volume > 1024**2:  # MB
                data_volume_display = f"{total_data_volume / (1024**2):.1f}MB"
            else:
                data_volume_display = f"{total_data_volume / 1024:.1f}KB"
            
            # Get recent datasets (last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            if is_partner:
                recent_datasets = assigned_datasets.filter(
                    created_at__gte=thirty_days_ago,
                    status='published',
                ).select_related('owner', 'category').order_by('-created_at')[:5]
                popular_datasets = assigned_datasets.filter(
                    status='published',
                ).select_related('owner', 'category', 'publisher').order_by('-download_count')[:5]
                recent_versions = DatasetVersion.objects.filter(
                    created_at__gte=thirty_days_ago,
                    dataset__in=assigned_datasets,
                ).select_related('dataset', 'dataset__owner').order_by('-created_at')[:10]
                categories_with_counts = DatasetCategory.objects.filter(
                    datasets__in=assigned_datasets,
                    datasets__status='published',
                ).annotate(
                    dataset_count=Count('datasets', filter=Q(datasets__status='published'))
                ).filter(dataset_count__gt=0).order_by('-dataset_count')[:6]
            else:
                recent_datasets = Dataset.objects.filter(
                    created_at__gte=thirty_days_ago,
                    status='published',
                ).select_related('owner', 'category').order_by('-created_at')[:5]
                popular_datasets = Dataset.objects.filter(
                    status='published',
                ).select_related('owner', 'category', 'publisher').order_by('-download_count')[:5]
                recent_versions = DatasetVersion.objects.filter(
                    created_at__gte=thirty_days_ago,
                ).select_related('dataset', 'dataset__owner').order_by('-created_at')[:10]
                categories_with_counts = DatasetCategory.objects.annotate(
                    dataset_count=Count('datasets', filter=Q(datasets__status='published'))
                ).filter(dataset_count__gt=0).order_by('-dataset_count')[:6]
            
            # Get user's datasets if logged in
            user_datasets = []
            if user.is_authenticated:
                if is_partner:
                    user_datasets = assigned_datasets.select_related(
                        'category'
                    ).order_by('-created_at')[:5]
                else:
                    user_datasets = Dataset.objects.filter(
                        owner=user,
                    ).select_related('category').order_by('-created_at')[:5]
            
            # Get user's recent activity
            user_recent_activity = []
            if user.is_authenticated:
                if is_partner:
                    user_recent_activity = DatasetVersion.objects.filter(
                        dataset__in=assigned_datasets,
                    ).select_related('dataset').order_by('-created_at')[:5]
                else:
                    user_recent_activity = DatasetVersion.objects.filter(
                        dataset__owner=user,
                    ).select_related('dataset').order_by('-created_at')[:5]
            
            # System uptime (mock for now - could be real system monitoring)
            uptime_percentage = 99.9
            
            context.update({
                'total_datasets': total_datasets,
                'total_users': total_users,
                'total_projects': total_projects,
                'data_volume_display': data_volume_display,
                'uptime_percentage': uptime_percentage,
                'recent_datasets': recent_datasets,
                'popular_datasets': popular_datasets,
                'recent_versions': recent_versions,
                'categories_with_counts': categories_with_counts,
                'user_datasets': user_datasets,
                'user_recent_activity': user_recent_activity,
                'thirty_days_ago': thirty_days_ago,
            })
            
        except ImportError:
            # If models are not available, use mock data
            context.update({
                'total_datasets': 0,
                'total_users': 0,
                'total_projects': 0,
                'data_volume_display': '0KB',
                'uptime_percentage': 0,
                'recent_datasets': [],
                'popular_datasets': [],
                'recent_versions': [],
                'categories_with_counts': [],
                'user_datasets': [],
                'user_recent_activity': [],
                'thirty_days_ago': timezone.now() - timedelta(days=30),
            })
        
        # Check if help section should be shown (only for 7 days after first login)
        show_help_section = False
        if self.request.user.is_authenticated and self.request.user.first_login_date:
            days_since_first_login = (timezone.now() - self.request.user.first_login_date).days
            show_help_section = days_since_first_login <= 7
        
        context['show_help_section'] = show_help_section
        
        # Get active announcements
        try:
            from .models import Announcement
            active_announcements = Announcement.objects.filter(
                is_active=True
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gt=timezone.now())
            ).filter(
                valid_from__lte=timezone.now()
            ).select_related('created_by').order_by('-priority', '-created_at')
            
            context['active_announcements'] = active_announcements
        except ImportError:
            context['active_announcements'] = []
        
        # Add group membership data for the current user (keeping existing functionality)
        if self.request.user.is_authenticated:
            try:
                from group.models import GroupMember
                from local.models import Local, Council
                
                # Get user's group memberships
                group_memberships = GroupMember.objects.filter(
                    user=self.request.user,
                    is_active=True
                ).select_related(
                    'group',
                    'group__party',
                    'group__party__local'
                ).order_by('group__name')
                
                context['group_memberships'] = group_memberships
                
                # Get unique locals and councils from memberships
                locals_from_memberships = set()
                councils_from_memberships = set()
                
                for membership in group_memberships:
                    if membership.group.party and membership.group.party.local:
                        locals_from_memberships.add(membership.group.party.local)
                        if hasattr(membership.group.party.local, 'council') and membership.group.party.local.council:
                            councils_from_memberships.add(membership.group.party.local.council)
                
                context['locals_from_memberships'] = sorted(locals_from_memberships, key=lambda x: x.name)
                context['councils_from_memberships'] = sorted(councils_from_memberships, key=lambda x: x.name)
                
            except ImportError:
                # If models are not available, set empty lists
                context['group_memberships'] = []
                context['locals_from_memberships'] = []
                context['councils_from_memberships'] = []
        else:
            context['group_memberships'] = []
            context['locals_from_memberships'] = []
            context['councils_from_memberships'] = []
        
        return context


class DocumentationView(TemplateView):
    """Documentation page view"""
    template_name = "documentation.html"


class AnnouncementManagementView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    View for managing announcements - only accessible by administrators
    """
    template_name = 'pages/announcement_management.html'
    context_object_name = 'announcements'
    paginate_by = 20
    
    def test_func(self):
        """Only superusers and users with admin role permission can access"""
        return (
            self.request.user.is_superuser or
            self.request.user.has_role_permission('admin')
        )
    
    def get_queryset(self):
        """Get all announcements ordered by priority and creation date"""
        from .models import Announcement
        return Announcement.objects.select_related('created_by').order_by('-priority', '-created_at')
    
    @property
    def model(self):
        """Get the Announcement model"""
        from .models import Announcement
        return Announcement
    
    def get_context_data(self, **kwargs):
        """Add additional context data"""
        # Set up view attributes for proper context generation
        if not hasattr(self, 'kwargs'):
            self.kwargs = {}
        if not hasattr(self, 'object_list'):
            self.object_list = self.get_queryset()
        
        context = super().get_context_data(**kwargs)
        
        # Add statistics
        from .models import Announcement
        context['total_announcements'] = Announcement.objects.count()
        context['active_announcements'] = Announcement.objects.filter(is_active=True).count()
        context['expired_announcements'] = Announcement.objects.filter(
            valid_until__lt=timezone.now()
        ).count()
        context['future_announcements'] = Announcement.objects.filter(
            valid_from__gt=timezone.now()
        ).count()
        
        return context


class AnnouncementCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    View for creating new announcements
    """
    model = None  # Will be set in __init__
    template_name = 'pages/announcement_form.html'
    fields = ['title', 'message', 'priority', 'is_active', 'valid_from', 'valid_until']
    success_url = reverse_lazy('announcement-management')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Announcement
        self.model = Announcement
    
    def test_func(self):
        """Only superusers and users with admin role permission can access"""
        return (
            self.request.user.is_superuser or
            self.request.user.has_role_permission('admin')
        )
    
    def form_valid(self, form):
        """Set the created_by field to current user"""
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Announcement "{form.instance.title}" has been created successfully.')
        return super().form_valid(form)


class AnnouncementUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    View for updating existing announcements
    """
    model = None  # Will be set in __init__
    template_name = 'pages/announcement_form.html'
    fields = ['title', 'message', 'priority', 'is_active', 'valid_from', 'valid_until']
    success_url = reverse_lazy('announcement-management')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Announcement
        self.model = Announcement
    
    def test_func(self):
        """Only superusers and users with admin role permission can access"""
        return (
            self.request.user.is_superuser or
            self.request.user.has_role_permission('admin')
        )
    
    def form_valid(self, form):
        """Show success message"""
        messages.success(self.request, f'Announcement "{form.instance.title}" has been updated successfully.')
        return super().form_valid(form)


class AnnouncementDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    View for deleting announcements
    """
    model = None  # Will be set in __init__
    template_name = 'pages/announcement_confirm_delete.html'
    success_url = reverse_lazy('announcement-management')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Announcement
        self.model = Announcement
    
    def test_func(self):
        """Only superusers and users with admin role permission can access"""
        return (
            self.request.user.is_superuser or
            self.request.user.has_role_permission('admin')
        )
    
    def delete(self, request, *args, **kwargs):
        """Show success message"""
        announcement = self.get_object()
        messages.success(request, f'Announcement "{announcement.title}" has been deleted successfully.')
        return super().delete(request, *args, **kwargs)