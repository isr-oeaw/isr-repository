from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import date, timedelta
import uuid

from .models import Project
from .forms import ProjectForm, ProjectTransferOwnershipForm, ProjectFilterForm
from .views import (
    ProjectListView, ProjectDetailView, ProjectCreateView, 
    ProjectUpdateView, ProjectDeleteView, ProjectTransferOwnershipView
)

User = get_user_model()


def _assign_editor_role(user):
    from user.models import Role

    user.role = Role.objects.get(name='Editor')
    user.save(update_fields=['role'])
    return user


class ProjectModelTests(TestCase):
    """Test cases for Project model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.collaborator = User.objects.create_user(
            username='collaborator',
            email='collaborator@example.com',
            password='testpass123'
        )
        
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
    
    def test_project_creation(self):
        """Test creating a basic project"""
        project = Project.objects.create(
            title='Test Project',
            description='This is a test project',
            abstract='Test abstract',
            owner=self.user,
            status='active',
            access_level='public'
        )
        
        self.assertEqual(project.title, 'Test Project')
        self.assertEqual(project.description, 'This is a test project')
        self.assertEqual(project.abstract, 'Test abstract')
        self.assertEqual(project.owner, self.user)
        self.assertEqual(project.status, 'active')
        self.assertEqual(project.access_level, 'public')
        self.assertIsNotNone(project.created_at)
        self.assertIsNotNone(project.updated_at)
    
    def test_project_str_representation(self):
        """Test the string representation of project"""
        project = Project.objects.create(
            title='Test Project',
            description='This is a test project',
            owner=self.user
        )
        
        self.assertEqual(str(project), 'Test Project')
    
    def test_project_status_choices(self):
        """Test all status choices are available"""
        statuses = ['planning', 'active', 'completed', 'on_hold', 'cancelled']
        
        for status in statuses:
            project = Project.objects.create(
                title=f'Test {status} project',
                description='Test description',
                owner=self.user,
                status=status
            )
            self.assertEqual(project.status, status)
    
    def test_project_access_level_choices(self):
        """Test all access level choices are available"""
        access_levels = ['public', 'restricted', 'private']
        
        for access_level in access_levels:
            project = Project.objects.create(
                title=f'Test {access_level} project',
                description='Test description',
                owner=self.user,
                access_level=access_level
            )
            self.assertEqual(project.access_level, access_level)
    
    def test_project_duration_days_property(self):
        """Test the duration_days property"""
        start_date = date.today()
        end_date = start_date + timedelta(days=30)
        
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user,
            start_date=start_date,
            end_date=end_date
        )
        
        self.assertEqual(project.duration_days, 30)
        
        # Test with no dates
        project_no_dates = Project.objects.create(
            title='Test Project No Dates',
            description='Test description',
            owner=self.user
        )
        
        self.assertIsNone(project_no_dates.duration_days)
    
    def test_project_is_active_property(self):
        """Test the is_active property"""
        active_project = Project.objects.create(
            title='Active Project',
            description='Test description',
            owner=self.user,
            status='active'
        )
        
        self.assertTrue(active_project.is_active)
        
        inactive_project = Project.objects.create(
            title='Inactive Project',
            description='Test description',
            owner=self.user,
            status='planning'
        )
        
        self.assertFalse(inactive_project.is_active)
    
    def test_project_is_completed_property(self):
        """Test the is_completed property"""
        completed_project = Project.objects.create(
            title='Completed Project',
            description='Test description',
            owner=self.user,
            status='completed'
        )
        
        self.assertTrue(completed_project.is_completed)
        
        active_project = Project.objects.create(
            title='Active Project',
            description='Test description',
            owner=self.user,
            status='active'
        )
        
        self.assertFalse(active_project.is_completed)
    
    def test_project_get_absolute_url(self):
        """Test the get_absolute_url method"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user
        )
        
        expected_url = reverse('projects:project_detail', kwargs={'pk': project.pk})
        self.assertEqual(project.get_absolute_url(), expected_url)
    
    def test_project_get_keywords_list(self):
        """Test the get_keywords_list method"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user,
            keywords='keyword1, keyword2, keyword3'
        )
        
        keywords = project.get_keywords_list()
        self.assertEqual(keywords, ['keyword1', 'keyword2', 'keyword3'])
        
        # Test with empty keywords
        project.keywords = ''
        project.save()
        keywords = project.get_keywords_list()
        self.assertEqual(keywords, [])
        
        # Test with whitespace
        project.keywords = ' keyword1 , keyword2 , keyword3 '
        project.save()
        keywords = project.get_keywords_list()
        self.assertEqual(keywords, ['keyword1', 'keyword2', 'keyword3'])
    
    def test_project_get_tags_list(self):
        """Test the get_tags_list method"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user,
            tags='tag1, tag2, tag3'
        )
        
        tags = project.get_tags_list()
        self.assertEqual(tags, ['tag1', 'tag2', 'tag3'])
        
        # Test with empty tags
        project.tags = ''
        project.save()
        tags = project.get_tags_list()
        self.assertEqual(tags, [])
        
        # Test with whitespace
        project.tags = ' tag1 , tag2 , tag3 '
        project.save()
        tags = project.get_tags_list()
        self.assertEqual(tags, ['tag1', 'tag2', 'tag3'])
    
    def test_project_is_accessible_by_owner(self):
        """Test project accessibility for owner"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user,
            access_level='private'
        )
        
        self.assertTrue(project.is_accessible_by(self.user))
    
    def test_project_is_accessible_by_collaborator(self):
        """Test project accessibility for collaborator"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user,
            access_level='private'
        )
        project.collaborators.add(self.collaborator)
        
        self.assertTrue(project.is_accessible_by(self.collaborator))
    
    def test_project_is_accessible_by_superuser(self):
        """Test project accessibility for superuser"""
        superuser = User.objects.create_superuser(
            username='superuser',
            email='super@example.com',
            password='testpass123'
        )
        
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user,
            access_level='private'
        )
        
        self.assertTrue(project.is_accessible_by(superuser))
    
    def test_project_is_accessible_by_public(self):
        """Test project accessibility for public projects"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user,
            access_level='public'
        )
        
        self.assertTrue(project.is_accessible_by(self.other_user))
    
    def test_project_is_accessible_by_restricted_with_permission(self):
        """Test project accessibility for restricted projects with permission"""
        # Create user with permission
        from django.contrib.auth.models import Permission
        permission = Permission.objects.get(codename='can_manage_projects')
        self.other_user.user_permissions.add(permission)
        
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user,
            access_level='restricted'
        )
        
        self.assertTrue(project.is_accessible_by(self.other_user))
    
    def test_project_is_accessible_by_restricted_without_permission(self):
        """Test project accessibility for restricted projects without permission"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user,
            access_level='restricted'
        )
        
        self.assertFalse(project.is_accessible_by(self.other_user))
    
    def test_project_is_accessible_by_private_other_user(self):
        """Test project accessibility for private projects by other users"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user,
            access_level='private'
        )
        
        self.assertFalse(project.is_accessible_by(self.other_user))
    
    def test_project_is_accessible_by_anonymous_user(self):
        """Test project accessibility for anonymous users"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user,
            access_level='public'
        )
        
        self.assertFalse(project.is_accessible_by(None))
    
    def test_project_ordering(self):
        """Test that projects are ordered by creation date (newest first)"""
        project1 = Project.objects.create(
            title='First Project',
            description='First description',
            owner=self.user
        )
        
        project2 = Project.objects.create(
            title='Second Project',
            description='Second description',
            owner=self.user
        )
        
        projects = list(Project.objects.all())
        self.assertEqual(projects[0], project2)  # Newer first
        self.assertEqual(projects[1], project1)  # Older second
    
    def test_project_collaborators_many_to_many(self):
        """Test the collaborators many-to-many relationship"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user
        )
        
        # Add collaborators
        project.collaborators.add(self.collaborator, self.other_user)
        
        self.assertEqual(project.collaborators.count(), 2)
        self.assertIn(self.collaborator, project.collaborators.all())
        self.assertIn(self.other_user, project.collaborators.all())
        
        # Remove one collaborator
        project.collaborators.remove(self.other_user)
        
        self.assertEqual(project.collaborators.count(), 1)
        self.assertIn(self.collaborator, project.collaborators.all())
        self.assertNotIn(self.other_user, project.collaborators.all())
    
    def test_project_meta_permissions(self):
        """Test that project model has correct permissions"""
        permissions = [perm[0] for perm in Project._meta.permissions]
        self.assertIn('can_manage_projects', permissions)
    
    def test_project_verbose_names(self):
        """Test that project model has correct verbose names"""
        self.assertEqual(Project._meta.verbose_name, 'Project')
        self.assertEqual(Project._meta.verbose_name_plural, 'Projects')


class ProjectFormTests(TestCase):
    """Test cases for Project forms"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.collaborator = User.objects.create_user(
            username='collaborator',
            email='collaborator@example.com',
            password='testpass123'
        )
    
    def test_project_form_valid_data(self):
        """Test ProjectForm with valid data"""
        form_data = {
            'title': 'Test Project',
            'description': 'This is a test project',
            'abstract': 'Test abstract',
            'status': 'active',
            'access_level': 'public',
            'keywords': 'test, project, research',
            'tags': 'research, data',
            'project_url': 'https://example.com/project',
            'funding_source': 'Test Foundation',
            'grant_number': 'GRANT-123',
            'collaborators': [self.collaborator.pk]
        }
        
        form = ProjectForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())
    
    def test_project_form_invalid_dates(self):
        """Test ProjectForm with invalid date range"""
        form_data = {
            'title': 'Test Project',
            'description': 'This is a test project',
            'start_date': date.today() + timedelta(days=30),
            'end_date': date.today(),
            'status': 'active',
            'access_level': 'public'
        }
        
        form = ProjectForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('End date must be after start date.', str(form.errors))
    
    def test_project_form_too_many_keywords(self):
        """Test ProjectForm with too many keywords"""
        keywords = ', '.join([f'keyword{i}' for i in range(21)])  # 21 keywords
        
        form_data = {
            'title': 'Test Project',
            'description': 'This is a test project',
            'keywords': keywords,
            'status': 'active',
            'access_level': 'public'
        }
        
        form = ProjectForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('Maximum 20 keywords allowed.', str(form.errors))
    
    def test_project_form_too_many_tags(self):
        """Test ProjectForm with too many tags"""
        tags = ', '.join([f'tag{i}' for i in range(16)])  # 16 tags
        
        form_data = {
            'title': 'Test Project',
            'description': 'This is a test project',
            'tags': tags,
            'status': 'active',
            'access_level': 'public'
        }
        
        form = ProjectForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('Maximum 15 tags allowed.', str(form.errors))
    
    def test_project_form_collaborators_excludes_owner(self):
        """Test that ProjectForm excludes owner from collaborators"""
        form = ProjectForm(user=self.user)
        collaborators_queryset = form.fields['collaborators'].queryset
        
        self.assertNotIn(self.user, collaborators_queryset)
        self.assertIn(self.collaborator, collaborators_queryset)
    
    def test_project_transfer_ownership_form_valid_data(self):
        """Test ProjectTransferOwnershipForm with valid data"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user
        )
        
        form_data = {
            'new_owner': self.collaborator.pk,
            'confirm_transfer': True
        }
        
        form = ProjectTransferOwnershipForm(
            data=form_data,
            current_user=self.user,
            project=project
        )
        self.assertTrue(form.is_valid())
    
    def test_project_transfer_ownership_form_no_confirmation(self):
        """Test ProjectTransferOwnershipForm without confirmation"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user
        )
        
        form_data = {
            'new_owner': self.collaborator.pk,
            'confirm_transfer': False
        }
        
        form = ProjectTransferOwnershipForm(
            data=form_data,
            current_user=self.user,
            project=project
        )
        self.assertFalse(form.is_valid())
    
    def test_project_transfer_ownership_form_excludes_current_owner(self):
        """Test that ProjectTransferOwnershipForm excludes current owner"""
        project = Project.objects.create(
            title='Test Project',
            description='Test description',
            owner=self.user
        )
        
        form = ProjectTransferOwnershipForm(
            current_user=self.user,
            project=project
        )
        new_owner_queryset = form.fields['new_owner'].queryset
        
        self.assertNotIn(self.user, new_owner_queryset)
        self.assertIn(self.collaborator, new_owner_queryset)
    
    def test_project_filter_form_valid_data(self):
        """Test ProjectFilterForm with valid data"""
        form_data = {
            'search': 'test project',
            'status': 'active'
        }
        
        form = ProjectFilterForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_project_filter_form_empty_data(self):
        """Test ProjectFilterForm with empty data"""
        form = ProjectFilterForm(data={})
        self.assertTrue(form.is_valid())


class ProjectViewTests(TestCase):
    """Test cases for Project views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = _assign_editor_role(User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        ))
        
        self.collaborator = User.objects.create_user(
            username='collaborator',
            email='collaborator@example.com',
            password='testpass123'
        )
        
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        self.project = Project.objects.create(
            title='Test Project',
            description='This is a test project',
            owner=self.user,
            status='active',
            access_level='public'
        )
    
    def test_project_list_view_requires_login(self):
        """Test that project list view requires login"""
        response = self.client.get(reverse('projects:project_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_project_list_view_authenticated_user(self):
        """Test project list view for authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('projects:project_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_list.html')
        self.assertIn('projects', response.context)
    
    def test_project_list_view_shows_accessible_projects(self):
        """Test that project list view shows only accessible projects"""
        # Create projects with different access levels
        private_project = Project.objects.create(
            title='Private Project',
            description='Private project',
            owner=self.user,
            access_level='private'
        )
        
        public_project = Project.objects.create(
            title='Public Project',
            description='Public project',
            owner=self.other_user,
            access_level='public'
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('projects:project_list'))
        
        projects = response.context['projects']
        project_titles = [p.title for p in projects]
        
        # Should see own private project and public project
        self.assertIn('Private Project', project_titles)
        self.assertIn('Public Project', project_titles)
        self.assertIn('Test Project', project_titles)
    
    def test_project_list_view_search_filter(self):
        """Test project list view with search filter"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('projects:project_list'), {'search': 'Test'})
        
        self.assertEqual(response.status_code, 200)
        projects = response.context['projects']
        self.assertIn(self.project, projects)
    
    def test_project_list_view_status_filter(self):
        """Test project list view with status filter"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('projects:project_list'), {'status': 'active'})
        
        self.assertEqual(response.status_code, 200)
        projects = response.context['projects']
        self.assertIn(self.project, projects)
    
    def test_project_detail_view_requires_login(self):
        """Test that project detail view requires login"""
        response = self.client.get(reverse('projects:project_detail', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_project_detail_view_accessible_project(self):
        """Test project detail view for accessible project"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('projects:project_detail', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_detail.html')
        self.assertEqual(response.context['project'], self.project)
    
    def test_project_detail_view_inaccessible_project(self):
        """Test project detail view for inaccessible project"""
        private_project = Project.objects.create(
            title='Private Project',
            description='Private project',
            owner=self.other_user,
            access_level='private'
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('projects:project_detail', kwargs={'pk': private_project.pk}))
        self.assertEqual(response.status_code, 404)
    
    def test_project_create_view_requires_login(self):
        """Test that project create view requires login"""
        response = self.client.get(reverse('projects:project_create'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_project_create_view_authenticated_user(self):
        """Test project create view for authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('projects:project_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_form.html')
    
    def test_project_create_view_post_valid_data(self):
        """Test creating project with valid data"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'title': 'New Test Project',
            'description': 'This is a new test project',
            'abstract': 'New test abstract',
            'status': 'planning',
            'access_level': 'private',
            'keywords': 'test, new, project',
            'tags': 'research, data'
        }
        
        response = self.client.post(reverse('projects:project_create'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that project was created
        project = Project.objects.get(title='New Test Project')
        self.assertEqual(project.description, 'This is a new test project')
        self.assertEqual(project.owner, self.user)
    
    def test_project_update_view_requires_login(self):
        """Test that project update view requires login"""
        response = self.client.get(reverse('projects:project_edit', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_project_update_view_owner_access(self):
        """Test project update view for project owner"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('projects:project_edit', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_form.html')
    
    def test_project_update_view_non_owner_access(self):
        """Test project update view for non-owner"""
        self.client.login(username='otheruser', password='testpass123')
        response = self.client.get(reverse('projects:project_edit', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 404)  # Not found (filtered out by queryset)
    
    def test_project_update_view_post_valid_data(self):
        """Test updating project with valid data"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'title': 'Updated Test Project',
            'description': 'This project has been updated',
            'abstract': 'Updated abstract',
            'status': 'active',
            'access_level': 'public',
            'keywords': 'updated, test, project',
            'tags': 'research, updated'
        }
        
        response = self.client.post(reverse('projects:project_edit', kwargs={'pk': self.project.pk}), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that project was updated
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, 'Updated Test Project')
        self.assertEqual(self.project.description, 'This project has been updated')
    
    def test_project_delete_view_requires_login(self):
        """Test that project delete view requires login"""
        response = self.client.get(reverse('projects:project_delete', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_project_delete_view_owner_access(self):
        """Test project delete view for project owner"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('projects:project_delete', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_confirm_delete.html')
    
    def test_project_delete_view_non_owner_access(self):
        """Test project delete view for non-owner"""
        self.client.login(username='otheruser', password='testpass123')
        response = self.client.get(reverse('projects:project_delete', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 404)  # Not found (filtered out by queryset)
    
    def test_project_delete_view_post(self):
        """Test deleting project"""
        self.client.login(username='testuser', password='testpass123')
        
        project_pk = self.project.pk
        response = self.client.post(reverse('projects:project_delete', kwargs={'pk': project_pk}))
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that project was deleted
        self.assertFalse(Project.objects.filter(pk=project_pk).exists())
    
    def test_project_transfer_ownership_view_requires_login(self):
        """Test that project transfer ownership view requires login"""
        response = self.client.get(reverse('projects:project_transfer_ownership', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_project_transfer_ownership_view_owner_access(self):
        """Test project transfer ownership view for project owner"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('projects:project_transfer_ownership', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_transfer_ownership.html')
    
    def test_project_transfer_ownership_view_non_owner_access(self):
        """Test project transfer ownership view for non-owner"""
        self.client.login(username='otheruser', password='testpass123')
        response = self.client.get(reverse('projects:project_transfer_ownership', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 404)  # Not found (filtered out by queryset)
    
    def test_project_transfer_ownership_view_post_valid_data(self):
        """Test transferring project ownership with valid data"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'new_owner': self.collaborator.pk,
            'confirm_transfer': True
        }
        
        response = self.client.post(reverse('projects:project_transfer_ownership', kwargs={'pk': self.project.pk}), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check that ownership was transferred
        self.project.refresh_from_db()
        self.assertEqual(self.project.owner, self.collaborator)
        self.assertIn(self.user, self.project.collaborators.all())


class ProjectIntegrationTests(TestCase):
    """Integration tests for project workflows"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = _assign_editor_role(User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        ))
        
        self.collaborator = User.objects.create_user(
            username='collaborator',
            email='collaborator@example.com',
            password='testpass123'
        )
    
    def test_complete_project_lifecycle(self):
        """Test complete project lifecycle from creation to completion"""
        self.client.login(username='testuser', password='testpass123')
        
        # 1. Create project
        create_data = {
            'title': 'Lifecycle Test Project',
            'description': 'A project to test the complete lifecycle',
            'abstract': 'Testing lifecycle',
            'status': 'planning',
            'access_level': 'private',
            'keywords': 'test, lifecycle',
            'tags': 'testing'
        }
        
        response = self.client.post(reverse('projects:project_create'), create_data)
        self.assertEqual(response.status_code, 302)
        
        project = Project.objects.get(title='Lifecycle Test Project')
        self.assertEqual(project.status, 'planning')
        self.assertEqual(project.owner, self.user)
        
        # 2. Update project to active
        update_data = {
            'title': 'Lifecycle Test Project',
            'description': 'A project to test the complete lifecycle',
            'abstract': 'Testing lifecycle',
            'status': 'active',
            'access_level': 'private',
            'keywords': 'test, lifecycle',
            'tags': 'testing'
        }
        
        response = self.client.post(reverse('projects:project_edit', kwargs={'pk': project.pk}), update_data)
        self.assertEqual(response.status_code, 302)
        
        project.refresh_from_db()
        self.assertEqual(project.status, 'active')
        self.assertTrue(project.is_active)
        
        # 3. Add collaborator
        collaborator_data = {
            'title': 'Lifecycle Test Project',
            'description': 'A project to test the complete lifecycle',
            'abstract': 'Testing lifecycle',
            'status': 'active',
            'access_level': 'private',
            'keywords': 'test, lifecycle',
            'tags': 'testing',
            'collaborators': [self.collaborator.pk]
        }
        
        response = self.client.post(reverse('projects:project_edit', kwargs={'pk': project.pk}), collaborator_data)
        self.assertEqual(response.status_code, 302)
        
        project.refresh_from_db()
        self.assertIn(self.collaborator, project.collaborators.all())
        
        # 4. Complete project
        complete_data = {
            'title': 'Lifecycle Test Project',
            'description': 'A project to test the complete lifecycle',
            'abstract': 'Testing lifecycle',
            'status': 'completed',
            'access_level': 'private',
            'keywords': 'test, lifecycle',
            'tags': 'testing',
            'collaborators': [self.collaborator.pk]
        }
        
        response = self.client.post(reverse('projects:project_edit', kwargs={'pk': project.pk}), complete_data)
        self.assertEqual(response.status_code, 302)
        
        project.refresh_from_db()
        self.assertEqual(project.status, 'completed')
        self.assertTrue(project.is_completed)
    
    def test_project_collaboration_workflow(self):
        """Test project collaboration workflow"""
        # Create project as owner
        self.client.login(username='testuser', password='testpass123')
        
        project = Project.objects.create(
            title='Collaboration Test Project',
            description='A project for testing collaboration',
            owner=self.user,
            status='active',
            access_level='private'
        )
        
        # Add collaborator
        project.collaborators.add(self.collaborator)
        
        # Collaborator can view project
        self.client.login(username='collaborator', password='testpass123')
        response = self.client.get(reverse('projects:project_detail', kwargs={'pk': project.pk}))
        self.assertEqual(response.status_code, 200)
        
        # Collaborator can edit project (collaborators have edit access)
        response = self.client.get(reverse('projects:project_edit', kwargs={'pk': project.pk}))
        self.assertEqual(response.status_code, 200)
        
        # Transfer ownership to collaborator
        self.client.login(username='testuser', password='testpass123')
        transfer_data = {
            'new_owner': self.collaborator.pk,
            'confirm_transfer': True
        }
        
        response = self.client.post(reverse('projects:project_transfer_ownership', kwargs={'pk': project.pk}), transfer_data)
        self.assertEqual(response.status_code, 302)
        
        project.refresh_from_db()
        self.assertEqual(project.owner, self.collaborator)
        self.assertIn(self.user, project.collaborators.all())
        
        # Now collaborator can edit project
        self.client.login(username='collaborator', password='testpass123')
        response = self.client.get(reverse('projects:project_edit', kwargs={'pk': project.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_project_access_control_workflow(self):
        """Test project access control workflow"""
        # Create private project
        self.client.login(username='testuser', password='testpass123')
        
        private_project = Project.objects.create(
            title='Private Test Project',
            description='A private project',
            owner=self.user,
            access_level='private'
        )
        
        # Create public project
        public_project = Project.objects.create(
            title='Public Test Project',
            description='A public project',
            owner=self.user,
            access_level='public'
        )
        
        # Create restricted project
        restricted_project = Project.objects.create(
            title='Restricted Test Project',
            description='A restricted project',
            owner=self.user,
            access_level='restricted'
        )
        
        # Test access as different users
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        self.client.login(username='otheruser', password='testpass123')
        
        # Can access public project
        response = self.client.get(reverse('projects:project_detail', kwargs={'pk': public_project.pk}))
        self.assertEqual(response.status_code, 200)
        
        # Cannot access private project
        response = self.client.get(reverse('projects:project_detail', kwargs={'pk': private_project.pk}))
        self.assertEqual(response.status_code, 404)
        
        # Cannot access restricted project without permission
        response = self.client.get(reverse('projects:project_detail', kwargs={'pk': restricted_project.pk}))
        self.assertEqual(response.status_code, 404)
        
        # Add permission and test again
        from django.contrib.auth.models import Permission
        permission = Permission.objects.get(codename='can_manage_projects')
        other_user.user_permissions.add(permission)
        
        response = self.client.get(reverse('projects:project_detail', kwargs={'pk': restricted_project.pk}))
        self.assertEqual(response.status_code, 200)
    
    def test_project_search_and_filter_workflow(self):
        """Test project search and filtering workflow"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create projects with different characteristics
        Project.objects.create(
            title='Machine Learning Research',
            description='Research on machine learning algorithms',
            owner=self.user,
            status='active',
            keywords='machine learning, AI, research',
            tags='research, AI'
        )
        
        Project.objects.create(
            title='Data Analysis Project',
            description='Analysis of customer data',
            owner=self.user,
            status='completed',
            keywords='data analysis, statistics',
            tags='analysis, data'
        )
        
        Project.objects.create(
            title='Web Development',
            description='Building a web application',
            owner=self.user,
            status='planning',
            keywords='web development, programming',
            tags='development, web'
        )
        
        # Test search functionality
        response = self.client.get(reverse('projects:project_list'), {'search': 'machine learning'})
        self.assertEqual(response.status_code, 200)
        projects = response.context['projects']
        self.assertTrue(any('Machine Learning' in p.title for p in projects))
        
        # Test status filter
        response = self.client.get(reverse('projects:project_list'), {'status': 'active'})
        self.assertEqual(response.status_code, 200)
        projects = response.context['projects']
        self.assertTrue(any(p.status == 'active' for p in projects))
        
        # Test combined search and filter
        response = self.client.get(reverse('projects:project_list'), {
            'search': 'data',
            'status': 'completed'
        })
        self.assertEqual(response.status_code, 200)
        projects = response.context['projects']
        self.assertTrue(any('Data Analysis' in p.title and p.status == 'completed' for p in projects))


class ExternalPartnerTests(TestCase):
    """Tests for External Partner role, scoped access, and project invites."""

    def setUp(self):
        from user.models import Role
        from datasets.models import Dataset, DatasetCategory, Publisher

        self.client = Client()

        self.partner_role = Role.objects.get(name='External Partner')
        self.admin_role = Role.objects.get(name='Administrator')

        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='testpass123',
            is_approved=True,
        )
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='testpass123',
            role=self.admin_role,
            is_approved=True,
        )
        self.partner = User.objects.create_user(
            username='partner',
            email='partner@example.com',
            password='testpass123',
            role=self.partner_role,
            is_approved=True,
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123',
            is_approved=True,
        )

        self.assigned_project = Project.objects.create(
            title='Assigned Project',
            description='Partner has access',
            owner=self.owner,
            access_level='private',
        )
        self.assigned_project.collaborators.add(self.partner)

        self.public_project = Project.objects.create(
            title='Public Project',
            description='Visible to everyone except partners',
            owner=self.owner,
            access_level='public',
        )

        self.category = DatasetCategory.objects.create(
            name='Partner Category',
            description='Test category',
            color='#007bff',
            is_active=True,
        )
        self.publisher = Publisher.objects.create(
            name='Partner Publisher',
            description='Test publisher',
            is_active=True,
        )
        self.assigned_dataset = Dataset.objects.create(
            title='Assigned Dataset',
            description='Linked to assigned project',
            owner=self.owner,
            category=self.category,
            publisher=self.publisher,
            status='published',
        )
        self.assigned_dataset.projects.add(self.assigned_project)

        self.other_dataset = Dataset.objects.create(
            title='Other Dataset',
            description='Not linked to partner project',
            owner=self.owner,
            category=self.category,
            publisher=self.publisher,
            status='published',
        )

    def test_external_partner_role_helpers(self):
        """External Partner role is detected only for that role."""
        self.assertTrue(self.partner.is_external_partner)
        self.assertFalse(self.owner.is_external_partner)
        self.assertFalse(self.admin_user.is_external_partner)

    def test_partner_assigned_projects_and_datasets(self):
        """Partner helpers return only assigned projects and their datasets."""
        self.assertEqual(self.partner.assigned_projects().count(), 1)
        self.assertIn(self.assigned_project, self.partner.assigned_projects())
        self.assertEqual(self.partner.assigned_datasets().count(), 1)
        self.assertIn(self.assigned_dataset, self.partner.assigned_datasets())

    def test_partner_cannot_access_unassigned_project(self):
        """Partner gets 404 for projects they are not assigned to."""
        self.client.login(username='partner', password='testpass123')
        response = self.client.get(
            reverse('projects:project_detail', kwargs={'pk': self.public_project.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_partner_can_access_assigned_project(self):
        """Partner can view a project they collaborate on."""
        self.client.login(username='partner', password='testpass123')
        response = self.client.get(
            reverse('projects:project_detail', kwargs={'pk': self.assigned_project.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Assigned Project')

    def test_partner_project_list_omits_unassigned_public_projects(self):
        """Partner project list excludes public projects they are not on."""
        self.client.login(username='partner', password='testpass123')
        response = self.client.get(reverse('projects:project_list'))
        self.assertEqual(response.status_code, 200)
        project_titles = [p.title for p in response.context['projects']]
        self.assertIn('Assigned Project', project_titles)
        self.assertNotIn('Public Project', project_titles)

    def test_partner_public_project_not_accessible_via_model(self):
        """External partners do not get public catalog access."""
        self.assertFalse(self.public_project.is_accessible_by(self.partner))

    def test_partner_cannot_access_unassigned_dataset(self):
        """Partner gets 404 for datasets outside assigned projects."""
        self.client.login(username='partner', password='testpass123')
        response = self.client.get(
            reverse('datasets:dataset_detail', kwargs={'pk': self.other_dataset.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_partner_can_access_assigned_project_dataset(self):
        """Partner can view datasets linked to assigned projects."""
        self.client.login(username='partner', password='testpass123')
        response = self.client.get(
            reverse('datasets:dataset_detail', kwargs={'pk': self.assigned_dataset.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Assigned Dataset')

    def test_owner_can_invite_new_partner(self):
        """Invite creates External Partner, adds collaborator, and sends login email."""
        from django.core import mail

        self.client.login(username='owner', password='testpass123')
        response = self.client.post(
            reverse('projects:project_invite_partner', kwargs={'pk': self.assigned_project.pk}),
            {
                'email': 'newpartner@example.com',
                'first_name': 'New',
                'last_name': 'Partner',
            },
        )
        self.assertEqual(response.status_code, 302)

        invited = User.objects.get(email='newpartner@example.com')
        self.assertTrue(invited.is_external_partner)
        self.assertTrue(invited.is_approved)
        self.assertIn(invited, self.assigned_project.collaborators.all())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/user/login/', mail.outbox[0].body)

    def test_invite_existing_user_only_adds_collaborator(self):
        """Inviting an existing user does not change their role."""
        from django.core import mail

        self.client.login(username='owner', password='testpass123')
        response = self.client.post(
            reverse('projects:project_invite_partner', kwargs={'pk': self.assigned_project.pk}),
            {'email': self.other_user.email},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.other_user, self.assigned_project.collaborators.all())
        self.other_user.refresh_from_db()
        self.assertIsNone(self.other_user.role)
        self.assertEqual(len(mail.outbox), 0)

    def test_non_owner_cannot_invite_partner(self):
        """Users without invite permission cannot invite partners."""
        self.client.login(username='other', password='testpass123')
        response = self.client.post(
            reverse('projects:project_invite_partner', kwargs={'pk': self.assigned_project.pk}),
            {'email': 'blocked@example.com'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(email='blocked@example.com').exists())

    def test_administrator_can_invite_partner(self):
        """Administrators can invite partners to any project."""
        self.client.login(username='adminuser', password='testpass123')
        response = self.client.post(
            reverse('projects:project_invite_partner', kwargs={'pk': self.public_project.pk}),
            {'email': 'admin-invited@example.com'},
        )
        self.assertEqual(response.status_code, 302)
        invited = User.objects.get(email='admin-invited@example.com')
        self.assertIn(invited, self.public_project.collaborators.all())
