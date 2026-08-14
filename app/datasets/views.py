from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.contrib import messages
from django.http import HttpResponse, Http404, FileResponse, JsonResponse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from pathlib import Path

from .models import (
    Dataset,
    DatasetCategory,
    DatasetVersion,
    DatasetVersionFile,
    DatasetDownload,
    Comment,
    Publisher,
    DatasetAnalysis,
)
from .forms import DatasetForm, DatasetFilterForm, DatasetVersionForm, DatasetCategoryForm, DatasetCategoryFilterForm, CommentForm, CommentEditForm, PublisherForm, PublisherFilterForm, DatasetProjectAssignmentForm, DatasetAnalysisForm
from .chunk_uploads import append_chunk, remove_chunk_upload


def user_can_manage_dataset_versions(user, dataset):
    """Return True if the user may add versions to the dataset."""
    return (
        user == dataset.owner
        or user in dataset.contributors.all()
        or user.is_superuser
    )


@login_required
def upload_dataset_version_chunk(request, dataset_pk):
    """Append one chunk to a staged dataset version upload."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required.'}, status=405)

    dataset = get_object_or_404(Dataset, pk=dataset_pk)
    if not user_can_manage_dataset_versions(request.user, dataset):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    upload_id = request.POST.get('upload_id')
    file_index = request.POST.get('file_index')
    chunk_index = request.POST.get('chunk_index')
    total_chunks = request.POST.get('total_chunks')
    filename = request.POST.get('filename')
    chunk_file = request.FILES.get('file')

    if not all([
        upload_id,
        file_index is not None,
        chunk_index is not None,
        total_chunks,
        filename,
        chunk_file,
    ]):
        return JsonResponse({'success': False, 'error': 'Missing required fields.'}, status=400)

    try:
        result = append_chunk(
            request.user,
            upload_id,
            file_index,
            chunk_index,
            total_chunks,
            filename,
            chunk_file,
        )
        return JsonResponse({'success': True, **result})
    except ValueError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)


class AdministratorOnlyMixin(UserPassesTestMixin):
    """Mixin to restrict access to users with Administrator role only"""
    
    def test_func(self):
        """Check if user has Administrator role"""
        user = self.request.user
        if not user.is_authenticated:
            return False
        
        # Superusers are always allowed
        if user.is_superuser:
            return True
        
        # Check if user has Administrator role
        if user.role and user.role.name == 'Administrator' and user.role.is_active:
            return True
        
        return False
    
    def handle_no_permission(self):
        """Handle access denied - redirect with error message"""
        messages.error(
            self.request, 
            'Access denied. Only Administrators can manage dataset categories.'
        )
        return redirect('datasets:category_list')


class EditorOrAdministratorMixin(UserPassesTestMixin):
    """Mixin to restrict access to users with Editor or Administrator role"""
    
    def test_func(self):
        """Check if user has Editor or Administrator role"""
        user = self.request.user
        if not user.is_authenticated:
            return False
        
        # Superusers are always allowed
        if user.is_superuser:
            return True
        
        # Check if user has Editor or Administrator role
        if user.role and user.role.is_active:
            if user.role.name in ['Editor', 'Administrator']:
                return True
        
        return False
    
    def handle_no_permission(self):
        """Handle access denied - redirect with error message"""
        messages.error(
            self.request, 
            'Access denied. Only Editors and Administrators can create datasets.'
        )
        return redirect('datasets:dataset_list')


class DatasetListView(LoginRequiredMixin, ListView):
    """List all datasets (requires authentication)"""
    model = Dataset
    template_name = 'datasets/dataset_list.html'
    context_object_name = 'datasets'
    paginate_by = 12

    def get_queryset(self):
        # All authenticated users can see all datasets regardless of status
        queryset = Dataset.objects.all().select_related('owner', 'category').prefetch_related('contributors', 'versions', 'versions__files')
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category__name=category)
        
        # Filter by search query
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(abstract__icontains=search) |
                Q(keywords__icontains=search) |
                Q(tags__icontains=search)
            )
        
        # Filter by tags
        tags = self.request.GET.get('tags')
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',')]
            for tag in tag_list:
                queryset = queryset.filter(tags__icontains=tag)
        
        # Order by featured first, then by creation date
        return queryset.order_by('-is_featured', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = DatasetCategory.objects.filter(is_active=True)
        
        # Featured datasets - superusers see all featured datasets
        if self.request.user and self.request.user.is_authenticated and self.request.user.is_superuser:
            featured_queryset = Dataset.objects.filter(
                is_featured=True
            ).select_related('owner', 'category').prefetch_related('versions', 'versions__files')
        else:
            # Featured datasets including user's private datasets
            featured_queryset = Dataset.objects.filter(
                is_featured=True,
                access_level__in=['public', 'restricted']
            ).select_related('owner', 'category').prefetch_related('versions', 'versions__files')
            
            # Add user's private featured datasets
            if self.request.user and self.request.user.is_authenticated:
                user_private_featured = Dataset.objects.filter(
                    owner=self.request.user,
                    is_featured=True,
                    access_level='private'
                ).select_related('owner', 'category').prefetch_related('versions', 'versions__files')
                
                featured_queryset = featured_queryset.union(user_private_featured)
        
        context['featured_datasets'] = featured_queryset[:6]
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_tags'] = self.request.GET.get('tags', '')
        return context


class DatasetDetailView(LoginRequiredMixin, DetailView):
    """View individual dataset details (requires authentication)"""
    model = Dataset
    template_name = 'datasets/dataset_detail.html'
    context_object_name = 'dataset'

    def get_queryset(self):
        # All authenticated users can see all datasets regardless of status
        return Dataset.objects.select_related('owner', 'category', 'publisher').prefetch_related(
            'contributors', 'versions', 'versions__files', 'related_datasets', 'comments__author', 'projects'
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        
        # Increment view count for authenticated users
        obj.view_count += 1
        obj.save(update_fields=['view_count'])
        
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dataset = self.get_object()
        
        # Add related datasets to context (from model relationship)
        context['related_datasets'] = dataset.related_datasets.all().select_related('owner', 'category')[:8]
        
        context['can_edit'] = (
            self.request.user == dataset.owner or 
            self.request.user.is_superuser
        )
        context['can_download'] = True  # All authenticated users can download
        context['can_assign_project'] = (
            self.request.user == dataset.owner or 
            self.request.user.is_superuser
        )
        
        # Add comments to context
        context['comments'] = dataset.comments.filter(is_approved=True).select_related('author')
        context['comment_form'] = CommentForm(user=self.request.user, dataset=dataset)
        
        # Add analyses to context
        context['analyses'] = dataset.analyses.all().select_related('uploaded_by').order_by('-uploaded_at')
        context['analysis_form'] = DatasetAnalysisForm(dataset=dataset, user=self.request.user)
        context['can_upload_analysis'] = self.request.user.is_authenticated
        
        return context


class DatasetCreateView(LoginRequiredMixin, EditorOrAdministratorMixin, CreateView):
    """Create a new dataset (Editors and Administrators only)"""
    model = Dataset
    form_class = DatasetForm
    template_name = 'datasets/dataset_form.html'

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, 'Dataset created successfully!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('datasets:dataset_detail', kwargs={'pk': self.object.pk})


class DatasetUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing dataset"""
    model = Dataset
    form_class = DatasetForm
    template_name = 'datasets/dataset_form.html'

    def get_queryset(self):
        # Allow owners, contributors, and staff/superusers to edit
        if self.request.user.is_staff or self.request.user.is_superuser:
            return Dataset.objects.all()
        return Dataset.objects.filter(
            Q(owner=self.request.user) | 
            Q(contributors=self.request.user)
        ).distinct()

    def form_valid(self, form):
        # Send notification about dataset update
        send_dataset_update_notification_email(self.object)
        messages.success(self.request, 'Dataset updated successfully!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('datasets:dataset_detail', kwargs={'pk': self.object.pk})


class DatasetDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete a dataset (superusers only)"""
    model = Dataset
    template_name = 'datasets/dataset_confirm_delete.html'
    success_url = reverse_lazy('datasets:dataset_list')

    def test_func(self):
        """Check if user is a superuser"""
        return self.request.user.is_superuser
    
    def handle_no_permission(self):
        """Handle access denied - redirect with error message"""
        if not self.request.user.is_authenticated:
            return redirect_to_login(self.request.get_full_path())
        messages.error(
            self.request, 
            'Access denied. Only superusers can delete datasets.'
        )
        # Try to redirect to the dataset detail page if we have the pk
        pk = self.kwargs.get('pk')
        if pk:
            return redirect('datasets:dataset_detail', pk=pk)
        return redirect('datasets:dataset_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Dataset deleted successfully!')
        return super().delete(request, *args, **kwargs)


def dataset_download(request, pk):
    """Handle dataset downloads (requires authentication via session or API key)"""
    dataset = get_object_or_404(Dataset, pk=pk)
    
    # Authenticate user - either via session login or API key
    if not request.user.is_authenticated:
        # Try API key authentication
        from user.authentication import APIKeyBackend
        backend = APIKeyBackend()
        user = backend.authenticate(request)
        if user:
            # Set the authenticated user
            request.user = user
        else:
            # No valid authentication found
            if request.headers.get('Accept', '').startswith('application/json'):
                # API request - return JSON error
                from django.http import JsonResponse
                return JsonResponse({
                    'error': 'Authentication required. Please provide a valid API key via Authorization header or api_key parameter.'
                }, status=401)
            else:
                # Web request - redirect to login
                return redirect_to_login(request.get_full_path())
    
    # All authenticated users can download all datasets regardless of status
    
    version_id = request.GET.get('version')
    version = None

    if version_id:
        try:
            version = dataset.versions.get(id=version_id)
        except DatasetVersion.DoesNotExist:
            messages.error(request, 'Requested dataset version was not found.')
            return redirect('datasets:dataset_detail', pk=pk)
    else:
        version = dataset.versions.filter(is_current=True).first()

    if not version:
        messages.error(request, 'No version available for download.')
        return redirect('datasets:dataset_detail', pk=pk)
    
    # Determine which file (if any) should be served
    file_id = request.GET.get('file')
    attachment = None

    if file_id:
        attachment = version.files.filter(id=file_id).first()
        if not attachment:
            messages.error(request, 'Requested file was not found for this dataset version.')
            return redirect('datasets:dataset_detail', pk=pk)
    else:
        attachment = version.files.order_by('uploaded_at', 'id').first()
    
    storage_file = None
    download_filename = None
    redirect_url = None
    
    if attachment:
        storage_file = attachment.file
        download_filename = attachment.display_name
    elif version.file:
        storage_file = version.file
        download_filename = Path(version.file.name).name
    elif version.file_url:
        redirect_url = version.file_url
    else:
        messages.error(request, 'No file available for download.')
        return redirect('datasets:dataset_detail', pk=pk)
    
    # Record download
    DatasetDownload.objects.create(
        dataset=dataset,
        user=request.user if request.user.is_authenticated else None,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # Increment download count
    dataset.download_count += 1
    dataset.save(update_fields=['download_count'])
    
    # Serve file or redirect to URL
    if storage_file:
        file_handle = storage_file.open('rb')
        response = FileResponse(file_handle, as_attachment=True, filename=download_filename)
        return response
    else:
        return redirect(redirect_url)


@login_required
def dataset_statistics(request):
    """Display dataset statistics (requires authentication)"""
    # All authenticated users can see statistics for all published datasets
    # Superusers can see statistics for all datasets including drafts
    # All authenticated users can see all datasets regardless of status
    dataset_filter = Q()
    
    stats = {
        'total_datasets': Dataset.objects.filter(dataset_filter).count(),
        'total_categories': DatasetCategory.objects.filter(is_active=True).count(),
        'total_downloads': DatasetDownload.objects.count(),
        'total_contributors': Dataset.objects.filter(dataset_filter).values('owner').distinct().count(),
        'recent_datasets': Dataset.objects.filter(dataset_filter).order_by('-created_at')[:5],
        'most_downloaded': Dataset.objects.filter(dataset_filter).order_by('-download_count')[:5],
        'categories_with_counts': DatasetCategory.objects.filter(
            is_active=True
        ).annotate(
            dataset_count=Count('datasets')
        ).order_by('-dataset_count'),
    }
    
    return render(request, 'datasets/statistics.html', {'stats': stats})


class DatasetVersionCreateView(LoginRequiredMixin, CreateView):
    """Create a new version for a dataset"""
    model = DatasetVersion
    form_class = DatasetVersionForm
    template_name = 'datasets/dataset_version_form.html'

    def dispatch(self, request, *args, **kwargs):
        # Get the dataset and check permissions
        self.dataset = get_object_or_404(Dataset, pk=kwargs['dataset_pk'])
        
        # Check if user can add versions (owner, contributor, or superuser)
        if not (request.user == self.dataset.owner or 
                request.user in self.dataset.contributors.all() or 
                request.user.is_superuser):
            messages.error(request, 'You do not have permission to add versions to this dataset.')
            return redirect('datasets:dataset_detail', pk=self.dataset.pk)
        
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['dataset'] = self.dataset
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        import logging
        logger = logging.getLogger('django')
        
        try:
            input_method = form.cleaned_data.get('input_method')
            uploaded_files = form.cleaned_data.get('uploaded_files', [])
            total_upload_size = form.cleaned_data.get('uploaded_files_total_size', 0)
            upload_id = form.cleaned_data.get('upload_id')

            logger.info(f'Creating dataset version for dataset {self.dataset.pk}, user: {self.request.user.username}, '
                       f'method: {input_method}, files: {len(uploaded_files)}, total_size: {total_upload_size}')

            with transaction.atomic():
                # Set previous versions to not current
                DatasetVersion.objects.filter(dataset=self.dataset).update(is_current=False)

                self.object = form.save(commit=False)
                self.object.dataset = self.dataset
                self.object.created_by = self.request.user
                self.object.is_current = True  # New version becomes current

                # Ensure legacy single-file fields are cleared for upload flow
                self.object.file = None

                if input_method == 'upload':
                    self.object.file_url = ''
                    self.object.file_url_description = ''
                    self.object.file_size_text = ''
                    self.object.file_size = total_upload_size
                else:
                    # For external URLs, rely on provided metadata but keep computed size at zero
                    self.object.file_size = 0

                self.object.save()
                logger.info(f'Dataset version {self.object.version_number} (ID: {self.object.pk}) created successfully')

                # Persist uploaded files as separate attachments
                if input_method == 'upload':
                    for idx, upload in enumerate(uploaded_files):
                        try:
                            DatasetVersionFile.objects.create(
                                version=self.object,
                                file=upload,
                                file_size=upload.size,
                                original_name=upload.name,
                            )
                            logger.debug(f'File {idx+1}/{len(uploaded_files)} uploaded: {upload.name} ({upload.size} bytes)')
                        except Exception as e:
                            logger.error(f'Error saving file {upload.name}: {str(e)}', exc_info=True)
                            raise

            if upload_id:
                remove_chunk_upload(self.request.user.pk, upload_id)

            # Send notification about new version
            try:
                send_new_version_notification_email(self.dataset, self.object)
            except Exception as e:
                logger.warning(f'Failed to send notification email: {str(e)}', exc_info=True)
                # Don't fail the entire operation if email fails

            messages.success(self.request, f'Version {self.object.version_number} created successfully!')
            
            # Handle AJAX requests
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({
                    'success': True,
                    'redirect_url': self.get_success_url()
                })
            
            return redirect(self.get_success_url())
        except Exception as e:
            logger.error(f'Error creating dataset version: {str(e)}', exc_info=True)
            
            # Handle AJAX requests with error
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                from django.conf import settings
                import traceback
                error_details = str(e)
                if hasattr(e, '__traceback__'):
                    error_details += f"\n\nTraceback:\n{traceback.format_exc()}"
                return JsonResponse({
                    'success': False,
                    'error': f'An error occurred while creating the version: {str(e)}',
                    'error_details': error_details if settings.DEBUG else None
                }, status=500)
            
            messages.error(self.request, f'An error occurred while creating the version: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        import logging
        logger = logging.getLogger('django')
        
        # Log form errors
        error_messages = []
        for field, errors in form.errors.items():
            for error in errors:
                error_msg = f'Form error - {field}: {error}'
                error_messages.append(error_msg)
                logger.warning(error_msg)
        
        # Log non-field errors
        for error in form.non_field_errors():
            error_msg = f'Form error (non-field): {error}'
            error_messages.append(error_msg)
            logger.warning(error_msg)
        
        messages.error(self.request, 'Please correct the errors below.')
        
        # Handle AJAX requests
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            from django.conf import settings
            
            # Format errors for JSON response
            formatted_errors = {}
            for field, errors in form.errors.items():
                formatted_errors[field] = errors
            
            return JsonResponse({
                'success': False,
                'error': 'Form validation failed. Please check the errors below.',
                'errors': formatted_errors,
                'non_field_errors': form.non_field_errors(),
                'error_messages': error_messages,
                'error_details': '\n'.join(error_messages) if settings.DEBUG else None
            }, status=400)
        
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('datasets:dataset_detail', kwargs={'pk': self.dataset.pk})

    def get_context_data(self, **kwargs):
        from django.conf import settings

        context = super().get_context_data(**kwargs)
        context['dataset'] = self.dataset
        context['max_dataset_upload_size'] = settings.MAX_DATASET_UPLOAD_SIZE
        context['chunk_upload_url'] = reverse(
            'datasets:dataset_version_upload_chunk',
            kwargs={'dataset_pk': self.dataset.pk},
        )
        return context


# Category Views
class DatasetCategoryListView(LoginRequiredMixin, ListView):
    """List all dataset categories"""
    model = DatasetCategory
    template_name = 'datasets/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def get_queryset(self):
        queryset = DatasetCategory.objects.all()
        
        # Apply filters
        search = self.request.GET.get('search')
        is_active = self.request.GET.get('is_active')
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(description__icontains=search)
            )
        
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)
        
        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = DatasetCategoryFilterForm(self.request.GET)
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_status'] = self.request.GET.get('is_active', '')
        return context


class DatasetCategoryCreateView(LoginRequiredMixin, AdministratorOnlyMixin, CreateView):
    """Create a new dataset category (Administrators only)"""
    model = DatasetCategory
    form_class = DatasetCategoryForm
    template_name = 'datasets/category_form.html'

    def get_success_url(self):
        return reverse('datasets:category_list')

    def form_valid(self, form):
        messages.success(self.request, f'Category "{form.instance.name}" created successfully!')
        return super().form_valid(form)


class DatasetCategoryUpdateView(LoginRequiredMixin, AdministratorOnlyMixin, UpdateView):
    """Update an existing dataset category (Administrators only)"""
    model = DatasetCategory
    form_class = DatasetCategoryForm
    template_name = 'datasets/category_form.html'

    def get_success_url(self):
        return reverse('datasets:category_list')

    def form_valid(self, form):
        messages.success(self.request, f'Category "{form.instance.name}" updated successfully!')
        return super().form_valid(form)


class DatasetCategoryDeleteView(LoginRequiredMixin, AdministratorOnlyMixin, DeleteView):
    """Delete a dataset category (Administrators only)"""
    model = DatasetCategory
    template_name = 'datasets/category_confirm_delete.html'
    success_url = reverse_lazy('datasets:category_list')

    def delete(self, request, *args, **kwargs):
        category = self.get_object()
        messages.success(request, f'Category "{category.name}" deleted successfully!')
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.get_object()
        
        # Check if category is used by any datasets
        dataset_count = Dataset.objects.filter(category=category).count()
        context['dataset_count'] = dataset_count
        context['can_delete'] = dataset_count == 0
        
        return context


# Comment Views
@login_required
def add_comment(request, dataset_id):
    """Add a comment to a dataset"""
    dataset = get_object_or_404(Dataset, id=dataset_id)
    
    if request.method == 'POST':
        form = CommentForm(request.POST, user=request.user, dataset=dataset)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.dataset = dataset
            comment.author = request.user
            comment.save()
            
            # Send email notification to dataset owner if enabled
            if dataset.owner.notify_comments and dataset.owner != request.user:
                send_comment_notification_email(comment)
            
            messages.success(request, 'Your comment has been added successfully.')
            return redirect('datasets:dataset_detail', pk=dataset.id)
    else:
        form = CommentForm(user=request.user, dataset=dataset)
    
    return render(request, 'datasets/dataset_detail.html', {
        'dataset': dataset,
        'comment_form': form
    })


@login_required
def edit_comment(request, comment_id):
    """Edit a comment"""
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Check if user can edit this comment
    if not comment.can_edit(request.user):
        messages.error(request, 'You do not have permission to edit this comment.')
        return redirect('datasets:dataset_detail', pk=comment.dataset.id)
    
    if request.method == 'POST':
        form = CommentEditForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your comment has been updated successfully.')
            return redirect('datasets:dataset_detail', pk=comment.dataset.id)
    else:
        form = CommentEditForm(instance=comment)
    
    return render(request, 'datasets/comment_edit.html', {
        'form': form,
        'comment': comment,
        'dataset': comment.dataset
    })


@login_required
def delete_comment(request, comment_id):
    """Delete a comment"""
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Check if user can delete this comment
    if not comment.can_delete(request.user):
        messages.error(request, 'You do not have permission to delete this comment.')
        return redirect('datasets:dataset_detail', pk=comment.dataset.id)
    
    dataset_id = comment.dataset.id
    comment.delete()
    messages.success(request, 'Your comment has been deleted successfully.')
    return redirect('datasets:dataset_detail', pk=dataset_id)


def send_comment_notification_email(comment):
    """Send email notification to dataset owner about new comment"""
    import logging
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    
    logger = logging.getLogger('datasets.email')
    
    dataset = comment.dataset
    owner = dataset.owner
    
    logger.info(f"Comment notification email requested for dataset '{dataset.title}' (ID: {dataset.id})")
    logger.info(f"Dataset owner: {owner.username} ({owner.email})")
    logger.info(f"Comment author: {comment.author.username}")
    
    # Check if owner wants to receive comment notifications
    if not owner.notify_comments:
        logger.info(f"Comment notifications disabled for user {owner.username}, skipping email")
        return
    
    logger.info(f"Comment notifications enabled for user {owner.username}, proceeding with email")
    
    # Prepare email context
    context = {
        'owner': owner,
        'comment': comment,
        'dataset': dataset,
        'commenter': comment.author,
        'site_name': getattr(settings, 'SITE_NAME', 'ISR Datasets'),
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    }
    
    # Render email templates
    subject = f'New comment on your dataset: {dataset.title}'
    html_message = render_to_string('datasets/email/comment_notification.html', context)
    plain_message = render_to_string('datasets/email/comment_notification.txt', context)
    
    logger.info(f"Email templates rendered successfully")
    logger.info(f"Subject: {subject}")
    logger.info(f"Plain message length: {len(plain_message)} chars")
    logger.info(f"HTML message length: {len(html_message)} chars")
    
    try:
        logger.info(f"Attempting to send comment notification email to {owner.email}")
        result = send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            fail_silently=False,
        )
        logger.info(f"Comment notification email sent successfully to {owner.email}")
        return result
    except Exception as e:
        logger.error(f"Failed to send comment notification email to {owner.email}: {str(e)}")
        logger.error(f"Email backend: {settings.EMAIL_BACKEND}")
        logger.error(f"SMTP settings: host={getattr(settings, 'EMAIL_HOST', 'N/A')}, port={getattr(settings, 'EMAIL_PORT', 'N/A')}")
        raise


def send_dataset_update_notification_email(dataset):
    """Send email notification to users following this dataset about updates"""
    import logging
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    from user.models import CustomUser
    
    logger = logging.getLogger('datasets.email')
    
    logger.info(f"Dataset update notification email requested for dataset '{dataset.title}' (ID: {dataset.id})")
    
    # Get users who want to receive dataset update notifications
    # For now, we'll notify all users who have this preference enabled
    # In a more advanced system, you might have a "following" relationship
    users_to_notify = CustomUser.objects.filter(
        notify_dataset_updates=True,
        is_active=True
    ).exclude(email='')
    
    logger.info(f"Found {users_to_notify.count()} users with dataset update notifications enabled")
    
    if not users_to_notify.exists():
        logger.info("No users to notify for dataset updates, skipping email")
        return
    
    # Prepare email context
    context = {
        'dataset': dataset,
        'site_name': getattr(settings, 'SITE_NAME', 'ISR Datasets'),
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    }
    
    # Render email templates
    subject = f'Dataset updated: {dataset.title}'
    html_message = render_to_string('datasets/email/dataset_update_notification.html', context)
    plain_message = render_to_string('datasets/email/dataset_update_notification.txt', context)
    
    logger.info(f"Email templates rendered successfully")
    logger.info(f"Subject: {subject}")
    logger.info(f"Plain message length: {len(plain_message)} chars")
    logger.info(f"HTML message length: {len(html_message)} chars")
    
    # Send emails to all users
    success_count = 0
    failure_count = 0
    
    for user in users_to_notify:
        try:
            logger.info(f"Attempting to send dataset update notification email to {user.email}")
            context['user'] = user
            result = send_mail(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"Dataset update notification email sent successfully to {user.email}")
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send dataset update notification email to {user.email}: {str(e)}")
            failure_count += 1
    
    logger.info(f"Dataset update notification email summary: {success_count} sent, {failure_count} failed")


def send_new_version_notification_email(dataset, version):
    """Send email notification to users following this dataset about new versions"""
    import logging
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    from user.models import CustomUser
    
    logger = logging.getLogger('datasets.email')
    
    logger.info(f"New version notification email requested for dataset '{dataset.title}' (ID: {dataset.id})")
    logger.info(f"Version: {version.version_number}")
    
    # Get users who want to receive new version notifications
    users_to_notify = CustomUser.objects.filter(
        notify_new_versions=True,
        is_active=True
    ).exclude(email='')
    
    logger.info(f"Found {users_to_notify.count()} users with new version notifications enabled")
    
    if not users_to_notify.exists():
        logger.info("No users to notify for new versions, skipping email")
        return
    
    # Prepare email context
    context = {
        'dataset': dataset,
        'version': version,
        'site_name': getattr(settings, 'SITE_NAME', 'ISR Datasets'),
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    }
    
    # Render email templates
    subject = f'New version available: {dataset.title} v{version.version_number}'
    html_message = render_to_string('datasets/email/new_version_notification.html', context)
    plain_message = render_to_string('datasets/email/new_version_notification.txt', context)
    
    logger.info(f"Email templates rendered successfully")
    logger.info(f"Subject: {subject}")
    logger.info(f"Plain message length: {len(plain_message)} chars")
    logger.info(f"HTML message length: {len(html_message)} chars")
    
    # Send emails to all users
    success_count = 0
    failure_count = 0
    
    for user in users_to_notify:
        try:
            logger.info(f"Attempting to send new version notification email to {user.email}")
            context['user'] = user
            result = send_mail(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"New version notification email sent successfully to {user.email}")
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send new version notification email to {user.email}: {str(e)}")
            failure_count += 1
    
    logger.info(f"New version notification email summary: {success_count} sent, {failure_count} failed")


# Publisher Views
class PublisherListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """List all publishers"""
    model = Publisher
    context_object_name = 'publishers'
    template_name = 'datasets/publisher_list.html'
    paginate_by = 20

    def test_func(self):
        # Allow access only if user is superuser
        return self.request.user.is_superuser

    def get_queryset(self):
        queryset = Publisher.objects.all().order_by('name')
        
        # Filter by search query
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Filter by active status
        is_active_filter = self.request.GET.get('is_active', '')
        if is_active_filter == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active_filter == 'false':
            queryset = queryset.filter(is_active=False)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['is_active_filter'] = self.request.GET.get('is_active', '')
        return context


class PublisherCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create a new publisher"""
    model = Publisher
    form_class = PublisherForm
    template_name = 'datasets/publisher_form.html'
    success_url = reverse_lazy('datasets:publisher_list')

    def test_func(self):
        # Allow access only if user is superuser
        return self.request.user.is_superuser

    def form_valid(self, form):
        messages.success(self.request, 'Publishing authority created successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class PublisherUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update an existing publisher"""
    model = Publisher
    form_class = PublisherForm
    template_name = 'datasets/publisher_form.html'
    success_url = reverse_lazy('datasets:publisher_list')

    def test_func(self):
        # Allow access only if user is superuser
        return self.request.user.is_superuser

    def form_valid(self, form):
        messages.success(self.request, 'Publishing authority updated successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class PublisherDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete a publisher"""
    model = Publisher
    template_name = 'datasets/publisher_confirm_delete.html'
    success_url = reverse_lazy('datasets:publisher_list')

    def test_func(self):
        # Allow access only if user is superuser
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        publishing_authority = self.get_object()
        
        # Check if publishing authority is used by any datasets
        dataset_count = Dataset.objects.filter(publishing_authority=publishing_authority).count()
        context['dataset_count'] = dataset_count
        context['can_delete'] = dataset_count == 0
        
        return context

    def delete(self, request, *args, **kwargs):
        publishing_authority = self.get_object()
        dataset_count = Dataset.objects.filter(publishing_authority=publishing_authority).count()
        
        if dataset_count > 0:
            messages.error(
                request, 
                f'Cannot delete "{publishing_authority.name}" because it is used by {dataset_count} dataset(s).'
            )
            return redirect('datasets:publishing_authority_list')
        
        messages.success(request, f'Publishing authority "{publishing_authority.name}" deleted successfully.')
        return super().delete(request, *args, **kwargs)


@login_required
def assign_dataset_to_project(request, pk):
    """Assign a dataset to projects (requires authentication)"""
    dataset = get_object_or_404(Dataset, pk=pk)
    
    # Check permissions - user must be dataset owner or superuser
    if not (request.user == dataset.owner or request.user.is_superuser):
        messages.error(request, 'You do not have permission to assign this dataset to projects.')
        return redirect('datasets:dataset_detail', pk=pk)
    
    if request.method == 'POST':
        form = DatasetProjectAssignmentForm(request.POST, user=request.user, dataset=dataset)
        if form.is_valid():
            selected_projects = form.cleaned_data['projects']
            
            # Update the dataset's projects
            dataset.projects.set(selected_projects)
            
            if selected_projects:
                project_names = [p.title for p in selected_projects]
                messages.success(request, f'Dataset "{dataset.title}" has been assigned to projects: {", ".join(project_names)}.')
            else:
                messages.success(request, f'Dataset "{dataset.title}" has been removed from all projects.')
            
            return redirect('datasets:dataset_detail', pk=pk)
    else:
        form = DatasetProjectAssignmentForm(user=request.user, dataset=dataset)
    
    return render(request, 'datasets/assign_to_project.html', {
        'form': form,
        'dataset': dataset
    })


@login_required
def upload_dataset_analysis(request, pk):
    """Upload an analysis/dataviz file for a dataset"""
    dataset = get_object_or_404(Dataset, pk=pk)
    
    if request.method == 'POST':
        form = DatasetAnalysisForm(request.POST, request.FILES, dataset=dataset, user=request.user)
        if form.is_valid():
            analysis = form.save()
            messages.success(request, f'Analysis "{analysis.title}" uploaded successfully!')
            return redirect('datasets:dataset_detail', pk=pk)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DatasetAnalysisForm(dataset=dataset, user=request.user)
    
    # If it's not a POST request, redirect to dataset detail
    return redirect('datasets:dataset_detail', pk=pk)


@login_required
def delete_dataset_analysis(request, pk, analysis_id):
    """Delete an analysis file"""
    dataset = get_object_or_404(Dataset, pk=pk)
    analysis = get_object_or_404(DatasetAnalysis, pk=analysis_id, dataset=dataset)
    
    # Check permissions
    if not analysis.can_delete(request.user):
        messages.error(request, 'You do not have permission to delete this analysis.')
        return redirect('datasets:dataset_detail', pk=pk)
    
    if request.method == 'POST':
        title = analysis.title
        analysis.file.delete()  # Delete the file from storage
        analysis.delete()
        messages.success(request, f'Analysis "{title}" deleted successfully!')
        return redirect('datasets:dataset_detail', pk=pk)
    
    # If it's not a POST request, redirect to dataset detail
    return redirect('datasets:dataset_detail', pk=pk)


@login_required
def download_dataset_analysis(request, pk, analysis_id):
    """Download an analysis file"""
    dataset = get_object_or_404(Dataset, pk=pk)
    analysis = get_object_or_404(DatasetAnalysis, pk=analysis_id, dataset=dataset)
    
    # All authenticated users can download analyses
    from django.http import FileResponse
    from pathlib import Path
    
    if analysis.file:
        file_handle = analysis.file.open('rb')
        download_filename = analysis.display_name
        response = FileResponse(file_handle, as_attachment=True, filename=download_filename)
        return response
    else:
        messages.error(request, 'Analysis file not found.')
        return redirect('datasets:dataset_detail', pk=pk)