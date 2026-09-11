import re

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from django.urls import reverse_lazy
from django.http import Http404
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from user.access import EXTERNAL_PARTNER_ROLE, user_can_invite_project_partner
from user.email_utils import send_account_invite_email
from user.models import Role

from .models import Project
from .forms import ProjectForm, ProjectFilterForm, ProjectTransferOwnershipForm, ProjectPartnerInviteForm

User = get_user_model()


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
            'Access denied. Only Editors and Administrators can create projects.'
        )
        return redirect('projects:project_list')


class ProjectListView(LoginRequiredMixin, ListView):
    """List all projects accessible to the user"""
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Project.objects.select_related('owner').prefetch_related('collaborators')
        
        # Apply access control
        if not self.request.user.is_superuser:
            if self.request.user.is_external_partner:
                queryset = queryset.filter(
                    Q(owner=self.request.user) |
                    Q(collaborators=self.request.user)
                ).distinct()
            else:
                queryset = queryset.filter(
                    Q(owner=self.request.user) |
                    Q(collaborators=self.request.user) |
                    Q(access_level='public')
                ).distinct()
        
        # Apply filters
        search = self.request.GET.get('search')
        status = self.request.GET.get('status')
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(abstract__icontains=search) |
                Q(keywords__icontains=search) |
                Q(tags__icontains=search)
            )
        
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ProjectFilterForm(self.request.GET)
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_status'] = self.request.GET.get('status', '')
        return context


class ProjectDetailView(LoginRequiredMixin, DetailView):
    """View individual project details"""
    model = Project
    template_name = 'projects/project_detail.html'
    context_object_name = 'project'
    
    def get_queryset(self):
        return Project.objects.select_related('owner').prefetch_related(
            'collaborators', 'datasets__owner', 'datasets__versions'
        )
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        
        # Check access permissions
        if not obj.is_accessible_by(self.request.user):
            raise Http404("Project not found or access denied")
        
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        
        context['can_edit'] = (
            self.request.user == project.owner or
            self.request.user in project.collaborators.all() or
            self.request.user.is_superuser
        )
        
        context['is_collaborator'] = (
            self.request.user in project.collaborators.all()
        )

        context['can_invite_partner'] = user_can_invite_project_partner(
            self.request.user, project
        )
        context['partner_invite_form'] = ProjectPartnerInviteForm()
        
        return context


def _username_from_email(email):
    local = email.split('@')[0]
    base = re.sub(r'[^a-zA-Z0-9._-]', '', local)[:30] or 'partner'
    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        username = f'{base}{suffix}'
        suffix += 1
    return username


def _ensure_verified_email_address(user):
    from allauth.account.models import EmailAddress

    email_address, created = EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={'verified': True, 'primary': True},
    )
    if not created:
        email_address.verified = True
        email_address.primary = True
        email_address.save(update_fields=['verified', 'primary'])


@login_required
@require_POST
def invite_project_partner(request, pk):
    """Invite an external partner by email and add them as a project collaborator."""
    project = get_object_or_404(Project, pk=pk)

    if not user_can_invite_project_partner(request.user, project):
        messages.error(
            request,
            _('You do not have permission to invite partners to this project.'),
        )
        return redirect('projects:project_detail', pk=pk)

    form = ProjectPartnerInviteForm(request.POST)
    if not form.is_valid():
        messages.error(request, _('Please enter a valid email address.'))
        return redirect('projects:project_detail', pk=pk)

    email = form.cleaned_data['email'].strip().lower()
    first_name = form.cleaned_data.get('first_name', '').strip()
    last_name = form.cleaned_data.get('last_name', '').strip()

    existing_user = User.objects.filter(email__iexact=email).first()
    if existing_user:
        project.collaborators.add(existing_user)
        messages.success(
            request,
            _('%(email)s has been added as a project collaborator.') % {'email': email},
        )
        return redirect('projects:project_detail', pk=pk)

    try:
        partner_role = Role.objects.get(name=EXTERNAL_PARTNER_ROLE, is_active=True)
    except Role.DoesNotExist:
        messages.error(
            request,
            _('External Partner role is not configured. Please contact an administrator.'),
        )
        return redirect('projects:project_detail', pk=pk)

    partner = User(
        username=_username_from_email(email),
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=partner_role,
        is_approved=True,
    )
    partner.set_unusable_password()
    partner.save()
    _ensure_verified_email_address(partner)
    project.collaborators.add(partner)

    email_sent = send_account_invite_email(partner, request=request, project=project)
    if email_sent:
        messages.success(
            request,
            _('Partner invitation sent to %(email)s.') % {'email': email},
        )
    else:
        messages.warning(
            request,
            _('Partner account created for %(email)s, but the invitation email could not be sent.') % {
                'email': email,
            },
        )

    return redirect('projects:project_detail', pk=pk)


class ProjectCreateView(LoginRequiredMixin, EditorOrAdministratorMixin, CreateView):
    """Create a new project"""
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Project "{self.object.title}" has been created successfully.'
        )
        return response
    
    def get_success_url(self):
        return reverse_lazy('projects:project_detail', kwargs={'pk': self.object.pk})


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing project"""
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_form.html'
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return Project.objects.all()
        return Project.objects.filter(
            Q(owner=self.request.user) |
            Q(collaborators=self.request.user)
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Project "{self.object.title}" has been updated successfully.'
        )
        return response
    
    def get_success_url(self):
        return reverse_lazy('projects:project_detail', kwargs={'pk': self.object.pk})


class ProjectDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a project"""
    model = Project
    template_name = 'projects/project_confirm_delete.html'
    success_url = reverse_lazy('projects:project_list')
    
    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)
    
    def delete(self, request, *args, **kwargs):
        project = self.get_object()
        project_title = project.title
        response = super().delete(request, *args, **kwargs)
        messages.success(
            request,
            f'Project "{project_title}" has been deleted successfully.'
        )
        return response


class ProjectTransferOwnershipView(LoginRequiredMixin, UpdateView):
    """Transfer project ownership to another user"""
    model = Project
    form_class = ProjectTransferOwnershipForm
    template_name = 'projects/project_transfer_ownership.html'
    
    def get_queryset(self):
        # Only project owners can transfer ownership
        return Project.objects.filter(owner=self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Remove instance since this form doesn't need it
        kwargs.pop('instance', None)
        kwargs['current_user'] = self.request.user
        kwargs['project'] = self.get_object()
        return kwargs
    
    def form_valid(self, form):
        project = self.get_object()
        new_owner = form.cleaned_data['new_owner']
        current_owner = self.request.user
        
        # Store original owner for message
        original_owner_name = current_owner.get_full_name() or current_owner.username
        new_owner_name = new_owner.get_full_name() or new_owner.username
        
        # Transfer ownership
        project.owner = new_owner
        
        # Add current owner as a collaborator if not already one
        if current_owner not in project.collaborators.all():
            project.collaborators.add(current_owner)
        
        # Remove new owner from collaborators if they were one
        if new_owner in project.collaborators.all():
            project.collaborators.remove(new_owner)
        
        project.save()
        
        # Send success message
        messages.success(
            self.request,
            f'Project ownership has been successfully transferred from {original_owner_name} to {new_owner_name}. '
            f'You are now a collaborator on this project.'
        )
        
        return redirect('projects:project_detail', pk=project.pk)
    
    def get_success_url(self):
        return reverse_lazy('projects:project_detail', kwargs={'pk': self.object.pk})

