from django.test import TestCase, override_settings, Client
from django.core import mail
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict
from unittest.mock import patch, MagicMock
from datetime import timedelta
from tempfile import TemporaryDirectory
import uuid

from .models import (
    Dataset,
    DatasetVersion,
    DatasetVersionFile,
    Comment,
    Publisher,
    DatasetCategory,
    DatasetDownload,
    DatasetAnalysis,
)
from .views import (
    send_comment_notification_email,
    send_dataset_update_notification_email,
    send_new_version_notification_email,
    DatasetListView, DatasetDetailView, DatasetCreateView, 
    DatasetUpdateView, DatasetDeleteView, DatasetVersionCreateView,
    add_comment, edit_comment, delete_comment, dataset_download,
    assign_dataset_to_project,
    upload_dataset_analysis, delete_dataset_analysis, download_dataset_analysis,
)
from .forms import (
    DatasetForm, DatasetVersionForm, CommentForm, CommentEditForm,
    DatasetProjectAssignmentForm, DatasetAnalysisForm,
)

User = get_user_model()


class NotificationEmailTests(TestCase):
    """Test cases for email notification functions"""
    
    def setUp(self):
        """Set up test data"""
        # Create test users
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@test.com',
            password='testpass123',
            notify_comments=True,
            notify_dataset_updates=True,
            notify_new_versions=True
        )
        
        self.commenter = User.objects.create_user(
            username='commenter',
            email='commenter@test.com',
            password='testpass123'
        )
        
        self.other_user = User.objects.create_user(
            username='other_user',
            email='other@test.com',
            password='testpass123',
            notify_dataset_updates=True,
            notify_new_versions=True
        )
        
        # Create test publisher
        self.publisher = Publisher.objects.create(
            name='Test Publisher',
            description='Test publisher for notifications'
        )
        
        # Create test dataset
        self.dataset = Dataset.objects.create(
            title='Test Dataset',
            description='Test dataset for notifications',
            abstract='Test abstract',
            owner=self.owner,
            publisher=self.publisher,
            status='published',
            access_level='public'
        )
        
        # Create test dataset version
        self.version = DatasetVersion.objects.create(
            dataset=self.dataset,
            version_number='1.0',
            description='Initial version',
            created_by=self.owner
        )
        
        # Create test comment
        self.comment = Comment.objects.create(
            dataset=self.dataset,
            author=self.commenter,
            content='Test comment for notifications'
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='noreply@test.com',
        SITE_NAME='Test Site',
        SITE_URL='http://test.com'
    )
    def test_send_comment_notification_email_success(self):
        """Test successful comment notification email sending"""
        # Clear any existing emails
        mail.outbox = []
        
        # Send notification
        send_comment_notification_email(self.comment)
        
        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.owner.email])
        self.assertEqual(email.from_email, 'noreply@test.com')
        self.assertIn('New comment on your dataset: Test Dataset', email.subject)
        self.assertIn('Test comment for notifications', email.body)
        self.assertIn('Test Site', email.body)

    def test_send_comment_notification_email_disabled(self):
        """Test that comment notification is not sent when disabled"""
        # Disable comment notifications for owner
        self.owner.notify_comments = False
        self.owner.save()
        
        # Clear any existing emails
        mail.outbox = []
        
        # Send notification
        send_comment_notification_email(self.comment)
        
        # Check that no email was sent
        self.assertEqual(len(mail.outbox), 0)


    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='noreply@test.com',
        SITE_NAME='Test Site',
        SITE_URL='http://test.com'
    )
    def test_send_dataset_update_notification_email_success(self):
        """Test successful dataset update notification email sending"""
        # Clear any existing emails
        mail.outbox = []
        
        # Send notification
        send_dataset_update_notification_email(self.dataset)
        
        # Check that emails were sent to users with notifications enabled
        self.assertEqual(len(mail.outbox), 2)  # owner and other_user
        
        # Check email content
        for email in mail.outbox:
            self.assertEqual(email.from_email, 'noreply@test.com')
            self.assertIn('Dataset updated: Test Dataset', email.subject)
            self.assertIn('Test Dataset', email.body)
            self.assertIn('Test Site', email.body)

    def test_send_dataset_update_notification_email_no_users(self):
        """Test that no emails are sent when no users have notifications enabled"""
        # Disable notifications for all users
        User.objects.filter(notify_dataset_updates=True).update(notify_dataset_updates=False)
        
        # Clear any existing emails
        mail.outbox = []
        
        # Send notification
        send_dataset_update_notification_email(self.dataset)
        
        # Check that no emails were sent
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='noreply@test.com',
        SITE_NAME='Test Site',
        SITE_URL='http://test.com'
    )
    def test_send_new_version_notification_email_success(self):
        """Test successful new version notification email sending"""
        # Clear any existing emails
        mail.outbox = []
        
        # Send notification
        send_new_version_notification_email(self.dataset, self.version)
        
        # Check that emails were sent to users with notifications enabled
        self.assertEqual(len(mail.outbox), 2)  # owner and other_user
        
        # Check email content
        for email in mail.outbox:
            self.assertEqual(email.from_email, 'noreply@test.com')
            self.assertIn('New version available: Test Dataset v1.0', email.subject)
            self.assertIn('Test Dataset', email.body)
            self.assertIn('1.0', email.body)
            self.assertIn('Test Site', email.body)

    def test_send_new_version_notification_email_no_users(self):
        """Test that no emails are sent when no users have notifications enabled"""
        # Disable notifications for all users
        User.objects.filter(notify_new_versions=True).update(notify_new_versions=False)
        
        # Clear any existing emails
        mail.outbox = []
        
        # Send notification
        send_new_version_notification_email(self.dataset, self.version)
        
        # Check that no emails were sent
        self.assertEqual(len(mail.outbox), 0)

    @patch('django.core.mail.send_mail')
    def test_send_comment_notification_email_exception_handling(self, mock_send_mail):
        """Test exception handling in comment notification email"""
        # Make send_mail raise an exception
        mock_send_mail.side_effect = Exception('SMTP Error')
        
        # Clear any existing emails
        mail.outbox = []
        
        # Send notification (should not raise exception)
        with self.assertRaises(Exception):
            send_comment_notification_email(self.comment)
        
        # Check that send_mail was called
        mock_send_mail.assert_called_once()

    @patch('django.core.mail.send_mail')
    def test_send_dataset_update_notification_email_exception_handling(self, mock_send_mail):
        """Test exception handling in dataset update notification email"""
        # Make send_mail raise an exception
        mock_send_mail.side_effect = Exception('SMTP Error')
        
        # Clear any existing emails
        mail.outbox = []
        
        # Send notification (should not raise exception)
        try:
            send_dataset_update_notification_email(self.dataset)
        except Exception as e:
            self.fail(f"send_dataset_update_notification_email raised an exception: {e}")
        
        # Check that send_mail was called for each user
        self.assertEqual(mock_send_mail.call_count, 2)  # owner and other_user

    def test_notification_email_templates_exist(self):
        """Test that all required email templates exist"""
        from django.template.loader import get_template
        
        # Test comment notification templates
        comment_html_template = get_template('datasets/email/comment_notification.html')
        comment_txt_template = get_template('datasets/email/comment_notification.txt')
        self.assertIsNotNone(comment_html_template)
        self.assertIsNotNone(comment_txt_template)
        
        # Test dataset update notification templates
        update_html_template = get_template('datasets/email/dataset_update_notification.html')
        update_txt_template = get_template('datasets/email/dataset_update_notification.txt')
        self.assertIsNotNone(update_html_template)
        self.assertIsNotNone(update_txt_template)
        
        # Test new version notification templates
        version_html_template = get_template('datasets/email/new_version_notification.html')
        version_txt_template = get_template('datasets/email/new_version_notification.txt')
        self.assertIsNotNone(version_html_template)
        self.assertIsNotNone(version_txt_template)


class DatasetVersionFormTests(TestCase):
    """Tests for the dataset version form multi-file capabilities."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='formuser',
            email='formuser@example.com',
            password='testpass123'
        )
        self.dataset = Dataset.objects.create(
            title='Form Dataset',
            description='Dataset for form tests',
            owner=self.user
        )

    def test_form_accepts_multiple_file_uploads(self):
        """Ensure the form validates when multiple files are uploaded."""
        file_one = SimpleUploadedFile('data1.csv', b'col1,col2\n1,2\n')
        file_two = SimpleUploadedFile('data2.csv', b'col1,col2\n3,4\n')

        form = DatasetVersionForm(
            data={
                'version_number': '1.0',
                'description': 'Initial release',
                'input_method': 'upload',
                'file_url': '',
                'file_url_description': '',
                'file_size_text': '',
            },
            files=MultiValueDict({'files': [file_one, file_two]}),
            dataset=self.dataset,
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(len(form.cleaned_data['uploaded_files']), 2)
        expected_size = file_one.size + file_two.size
        self.assertEqual(form.cleaned_data['uploaded_files_total_size'], expected_size)

    def test_form_rejects_files_for_url_method(self):
        """Ensure uploaded files are not allowed when using the URL method."""
        uploaded_file = SimpleUploadedFile('data.csv', b'data')

        form = DatasetVersionForm(
            data={
                'version_number': '1.0',
                'description': 'External data',
                'input_method': 'url',
                'file_url': 'https://example.com/data.csv',
                'file_url_description': 'External storage',
                'file_size_text': '10 MB',
            },
            files=MultiValueDict({'files': [uploaded_file]}),
            dataset=self.dataset,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Please do not upload files when using the external URL method.', form.non_field_errors())

    def test_form_rejects_oversized_file_upload(self):
        """Ensure files larger than MAX_DATASET_UPLOAD_SIZE are rejected."""
        from unittest.mock import patch
        from django.conf import settings

        oversized_file = SimpleUploadedFile('large.csv', b'data')
        oversized_file.size = settings.MAX_DATASET_UPLOAD_SIZE + 1

        form = DatasetVersionForm(
            data={
                'version_number': '1.0',
                'description': 'Too large',
                'input_method': 'upload',
                'file_url': '',
                'file_url_description': '',
                'file_size_text': '',
            },
            files=MultiValueDict({'files': [oversized_file]}),
            dataset=self.dataset,
        )

        with patch.object(settings, 'MAX_DATASET_UPLOAD_SIZE', 1024):
            self.assertFalse(form.is_valid())
            self.assertIn('files', form.errors)

    def test_form_rejects_oversized_total_upload(self):
        """Ensure total upload size over MAX_DATASET_UPLOAD_SIZE is rejected."""
        from unittest.mock import patch
        from django.conf import settings

        file_one = SimpleUploadedFile('part1.csv', b'data')
        file_two = SimpleUploadedFile('part2.csv', b'data')
        file_one.size = 600
        file_two.size = 600

        form = DatasetVersionForm(
            data={
                'version_number': '1.0',
                'description': 'Total too large',
                'input_method': 'upload',
                'file_url': '',
                'file_url_description': '',
                'file_size_text': '',
            },
            files=MultiValueDict({'files': [file_one, file_two]}),
            dataset=self.dataset,
        )

        with patch.object(settings, 'MAX_DATASET_UPLOAD_SIZE', 1000):
            self.assertFalse(form.is_valid())
            self.assertIn('files', form.errors)
            self.assertIn('Total upload size', form.errors['files'][0])

    def test_form_accepts_supported_file_formats(self):
        """Test that the form accepts all supported file formats including .dta and .rds"""
        # All supported file formats
        supported_formats = [
            ('data.csv', 'text/csv'),
            ('data.json', 'application/json'),
            ('data.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('data.xls', 'application/vnd.ms-excel'),
            ('data.txt', 'text/plain'),
            ('data.zip', 'application/zip'),
            ('data.tar.gz', 'application/gzip'),
            ('data.gpkg', 'application/geopackage+sqlite3'),
            ('data.sav', 'application/x-spss-sav'),
            ('data.zsav', 'application/x-spss-sav'),
            ('data.por', 'application/x-spss-por'),
            ('data.dta', 'application/x-stata'),
            ('data.rds', 'application/octet-stream'),
            ('data.shp', 'application/octet-stream'),
            ('data.geojson', 'application/geo+json'),
            ('data.kml', 'application/vnd.google-earth.kml+xml'),
            ('data.kmz', 'application/vnd.google-earth.kmz'),
            ('data.tif', 'image/tiff'),
            ('data.png', 'image/png'),
            ('data.sqlite', 'application/x-sqlite3'),
            ('data.sql', 'application/sql'),
            ('data.pdf', 'application/pdf'),
        ]
        
        for filename, content_type in supported_formats:
            with self.subTest(filename=filename):
                test_file = SimpleUploadedFile(
                    filename,
                    b'test file content',
                    content_type=content_type
                )
                
                form = DatasetVersionForm(
                    data={
                        'version_number': '1.0',
                        'description': f'Test upload for {filename}',
                        'input_method': 'upload',
                        'file_url': '',
                        'file_url_description': '',
                        'file_size_text': '',
                    },
                    files=MultiValueDict({'files': [test_file]}),
                    dataset=self.dataset,
                )
                
                # Form should be valid for all supported formats
                self.assertTrue(
                    form.is_valid(),
                    f"Form should accept {filename} but got errors: {form.errors}"
                )
                
                # Verify the file was processed
                if form.is_valid():
                    self.assertIn('uploaded_files', form.cleaned_data)
                    self.assertEqual(len(form.cleaned_data['uploaded_files']), 1)
                    self.assertEqual(
                        form.cleaned_data['uploaded_files'][0].name,
                        filename
                    )

    def test_form_widget_accept_attribute_includes_all_formats(self):
        """Test that the file input widget's accept attribute includes all supported formats"""
        form = DatasetVersionForm(dataset=self.dataset)
        files_widget = form.fields['files'].widget
        
        # Get the accept attribute value
        accept_attr = files_widget.attrs.get('accept', '')
        
        # Check that all key formats are included
        required_formats = [
            '.csv', '.json', '.xlsx', '.xls', '.txt', '.zip',
            '.sav', '.zsav', '.por', '.dta', '.rds',  # Statistical formats
            '.gpkg', '.shp', '.geojson', '.kml', '.kmz',  # Geospatial formats
            '.tif', '.png', '.sqlite', '.sql', '.pdf'  # Other formats
        ]
        
        for format_ext in required_formats:
            with self.subTest(format=format_ext):
                self.assertIn(
                    format_ext,
                    accept_attr,
                    f"Accept attribute should include {format_ext}. Current value: {accept_attr}"
                )

    def test_form_accepts_new_statistical_formats(self):
        """Specifically test that the newly added .dta and .rds formats are accepted"""
        # Test Stata .dta format
        stata_file = SimpleUploadedFile(
            'dataset.dta',
            b'Stata binary data content',
            content_type='application/x-stata'
        )
        
        form_dta = DatasetVersionForm(
            data={
                'version_number': '1.0',
                'description': 'Stata dataset',
                'input_method': 'upload',
                'file_url': '',
                'file_url_description': '',
                'file_size_text': '',
            },
            files=MultiValueDict({'files': [stata_file]}),
            dataset=self.dataset,
        )
        
        self.assertTrue(
            form_dta.is_valid(),
            f"Form should accept .dta files but got errors: {form_dta.errors}"
        )
        
        # Test R .rds format
        r_file = SimpleUploadedFile(
            'dataset.rds',
            b'R serialized data content',
            content_type='application/octet-stream'
        )
        
        form_rds = DatasetVersionForm(
            data={
                'version_number': '1.0',
                'description': 'R dataset',
                'input_method': 'upload',
                'file_url': '',
                'file_url_description': '',
                'file_size_text': '',
            },
            files=MultiValueDict({'files': [r_file]}),
            dataset=self.dataset,
        )
        
        self.assertTrue(
            form_rds.is_valid(),
            f"Form should accept .rds files but got errors: {form_rds.errors}"
        )
        
        # Verify both files are in the accept attribute
        form = DatasetVersionForm(dataset=self.dataset)
        accept_attr = form.fields['files'].widget.attrs.get('accept', '')
        self.assertIn('.dta', accept_attr, '.dta should be in accept attribute')
        self.assertIn('.rds', accept_attr, '.rds should be in accept attribute')


class DatasetModelTests(TestCase):
    """Test cases for Dataset model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.publisher = Publisher.objects.create(
            name='Test Publisher',
            description='Test publisher description'
        )
        
        self.category = DatasetCategory.objects.create(
            name='Test Category',
            description='Test category description',
            color='#007bff'
        )
    
    def test_dataset_creation(self):
        """Test creating a basic dataset"""
        dataset = Dataset.objects.create(
            title='Test Dataset',
            description='This is a test dataset',
            abstract='Test abstract',
            owner=self.user,
            publisher=self.publisher,
            category=self.category,
            status='published',
            access_level='public'
        )
        
        self.assertEqual(dataset.title, 'Test Dataset')
        self.assertEqual(dataset.description, 'This is a test dataset')
        self.assertEqual(dataset.owner, self.user)
        self.assertEqual(dataset.publisher, self.publisher)
        self.assertEqual(dataset.category, self.category)
        self.assertEqual(dataset.status, 'published')
        self.assertEqual(dataset.access_level, 'public')
        self.assertIsNotNone(dataset.id)  # UUID field
        self.assertIsNotNone(dataset.created_at)
        self.assertIsNotNone(dataset.updated_at)
    
    def test_dataset_str_representation(self):
        """Test the string representation of dataset"""
        dataset = Dataset.objects.create(
            title='Test Dataset',
            description='This is a test dataset',
            owner=self.user
        )
        
        self.assertEqual(str(dataset), 'Test Dataset')
    
    def test_dataset_status_choices(self):
        """Test all status choices are available"""
        statuses = ['draft', 'published', 'archived', 'private']
        
        for status in statuses:
            dataset = Dataset.objects.create(
                title=f'Test {status} dataset',
                description='Test description',
                owner=self.user,
                status=status
            )
            self.assertEqual(dataset.status, status)
    
    def test_dataset_access_level_choices(self):
        """Test all access level choices are available"""
        access_levels = ['public', 'restricted', 'private']
        
        for access_level in access_levels:
            dataset = Dataset.objects.create(
                title=f'Test {access_level} dataset',
                description='Test description',
                owner=self.user,
                access_level=access_level
            )
            self.assertEqual(dataset.access_level, access_level)
    
    def test_dataset_published_at_auto_set(self):
        """Test that published_at is set when status changes to published"""
        dataset = Dataset.objects.create(
            title='Test Dataset',
            description='Test description',
            owner=self.user,
            status='draft'
        )
        
        self.assertIsNone(dataset.published_at)
        
        # Change status to published
        dataset.status = 'published'
        dataset.save()
        
        self.assertIsNotNone(dataset.published_at)
        self.assertAlmostEqual(
            dataset.published_at.timestamp(),
            timezone.now().timestamp(),
            delta=1
        )
    
    def test_dataset_get_tags_list(self):
        """Test the get_tags_list method"""
        dataset = Dataset.objects.create(
            title='Test Dataset',
            description='Test description',
            owner=self.user,
            tags='tag1, tag2, tag3'
        )
        
        tags = dataset.get_tags_list()
        self.assertEqual(tags, ['tag1', 'tag2', 'tag3'])
        
        # Test with empty tags
        dataset.tags = ''
        dataset.save()
        tags = dataset.get_tags_list()
        self.assertEqual(tags, [])
        
        # Test with whitespace
        dataset.tags = ' tag1 , tag2 , tag3 '
        dataset.save()
        tags = dataset.get_tags_list()
        self.assertEqual(tags, ['tag1', 'tag2', 'tag3'])
    
    def test_dataset_is_accessible_by_public(self):
        """Test dataset accessibility for public datasets"""
        dataset = Dataset.objects.create(
            title='Public Dataset',
            description='Test description',
            owner=self.user,
            access_level='public'
        )
        
        # Should be accessible by anyone
        self.assertTrue(dataset.is_accessible_by(None))  # Anonymous user
        self.assertTrue(dataset.is_accessible_by(self.user))
        
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123'
        )
        self.assertTrue(dataset.is_accessible_by(other_user))
    
    def test_dataset_is_accessible_by_restricted(self):
        """Test dataset accessibility for restricted datasets"""
        dataset = Dataset.objects.create(
            title='Restricted Dataset',
            description='Test description',
            owner=self.user,
            access_level='restricted'
        )
        
        # Should only be accessible by authenticated users
        self.assertFalse(dataset.is_accessible_by(None))  # Anonymous user
        self.assertTrue(dataset.is_accessible_by(self.user))
        
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123'
        )
        self.assertTrue(dataset.is_accessible_by(other_user))
    
    def test_dataset_is_accessible_by_private(self):
        """Test dataset accessibility for private datasets"""
        dataset = Dataset.objects.create(
            title='Private Dataset',
            description='Test description',
            owner=self.user,
            access_level='private'
        )
        
        # Should only be accessible by owner or superuser
        self.assertFalse(dataset.is_accessible_by(None))  # Anonymous user
        
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123'
        )
        self.assertFalse(dataset.is_accessible_by(other_user))
        
        self.assertTrue(dataset.is_accessible_by(self.user))  # Owner
        
        # Superuser should have access
        superuser = User.objects.create_superuser(
            username='superuser',
            email='super@example.com',
            password='testpass123'
        )
        self.assertTrue(dataset.is_accessible_by(superuser))
    
    def test_dataset_get_available_formats(self):
        """Test getting available formats from dataset versions"""
        dataset = Dataset.objects.create(
            title='Test Dataset',
            description='Test description',
            owner=self.user
        )
        
        # Create versions with different file types
        version1 = DatasetVersion.objects.create(
            dataset=dataset,
            version_number='1.0',
            description='Version 1',
            created_by=self.user,
            file_url='http://example.com/data.csv'
        )
        
        version2 = DatasetVersion.objects.create(
            dataset=dataset,
            version_number='2.0',
            description='Version 2',
            created_by=self.user,
            file_url='http://example.com/data.json'
        )
        
        version3 = DatasetVersion.objects.create(
            dataset=dataset,
            version_number='3.0',
            description='Version 3',
            created_by=self.user,
            file_url='http://example.com/data.xlsx'
        )
        
        formats = dataset.get_available_formats()
        self.assertIn('CSV', formats)
        self.assertIn('JSON', formats)
        self.assertIn('XLSX', formats)
    
    def test_dataset_get_available_formats_from_attachments(self):
        """Test that attachment file extensions are included in available formats."""
        dataset = Dataset.objects.create(
            title='Attachment Dataset',
            description='Dataset description',
            owner=self.user
        )

        version = DatasetVersion.objects.create(
            dataset=dataset,
            version_number='1.0',
            description='Version with attachments',
            created_by=self.user,
            is_current=True
        )

        DatasetVersionFile.objects.create(
            version=version,
            file=SimpleUploadedFile('attachment.csv', b'col1,col2'),
            file_size=12,
            original_name='attachment.csv'
        )
        DatasetVersionFile.objects.create(
            version=version,
            file=SimpleUploadedFile('attachment.geojson', b'{}'),
            file_size=2,
            original_name='attachment.geojson'
        )

        formats = dataset.get_available_formats()
        self.assertIn('CSV', formats)
        self.assertIn('GEOJSON', formats)
    
    def test_dataset_ordering(self):
        """Test that datasets are ordered by creation date (newest first)"""
        dataset1 = Dataset.objects.create(
            title='First Dataset',
            description='First description',
            owner=self.user
        )
        
        dataset2 = Dataset.objects.create(
            title='Second Dataset',
            description='Second description',
            owner=self.user
        )
        
        datasets = list(Dataset.objects.all())
        self.assertEqual(datasets[0], dataset2)  # Newer first
        self.assertEqual(datasets[1], dataset1)  # Older second


class DatasetVersionModelTests(TestCase):
    """Test cases for DatasetVersion model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.dataset = Dataset.objects.create(
            title='Test Dataset',
            description='Test description',
            owner=self.user
        )
    
    def test_dataset_version_creation(self):
        """Test creating a dataset version"""
        version = DatasetVersion.objects.create(
            dataset=self.dataset,
            version_number='1.0',
            description='Initial version',
            created_by=self.user
        )
        
        self.assertEqual(version.dataset, self.dataset)
        self.assertEqual(version.version_number, '1.0')
        self.assertEqual(version.description, 'Initial version')
        self.assertEqual(version.created_by, self.user)
        self.assertFalse(version.is_current)
        self.assertEqual(version.file_size, 0)
        self.assertIsNotNone(version.created_at)
    
    def test_dataset_version_str_representation(self):
        """Test the string representation of dataset version"""
        version = DatasetVersion.objects.create(
            dataset=self.dataset,
            version_number='1.0',
            description='Initial version',
            created_by=self.user
        )
        
        expected_str = 'Test Dataset v1.0'
        self.assertEqual(str(version), expected_str)
    
    def test_dataset_version_unique_together(self):
        """Test that dataset and version_number combination is unique"""
        # Test that the unique constraint is defined in the model
        self.assertIn(('dataset', 'version_number'), DatasetVersion._meta.unique_together)
        
        # Test that we can create versions with different version numbers
        version1 = DatasetVersion.objects.create(
            dataset=self.dataset,
            version_number='1.0',
            description='Initial version',
            created_by=self.user
        )
        
        version2 = DatasetVersion.objects.create(
            dataset=self.dataset,
            version_number='2.0',
            description='Second version',
            created_by=self.user
        )
        
        self.assertEqual(version1.version_number, '1.0')
        self.assertEqual(version2.version_number, '2.0')
    
    def test_dataset_version_get_file_size_display(self):
        """Test the get_file_size_display method"""
        version = DatasetVersion.objects.create(
            dataset=self.dataset,
            version_number='1.0',
            description='Initial version',
            created_by=self.user,
            file_size=1024
        )
        
        # Test with file_size_text
        version.file_size_text = '1.5 MB'
        version.save()
        self.assertEqual(version.get_file_size_display(), '1.5 MB')
        
        # Test with file_size only
        version.file_size_text = ''
        version.file_size = 2048
        version.save()
        self.assertEqual(version.get_file_size_display(), '2.0 KB')
        
        # Test with no size information
        version.file_size = 0
        version.save()
        self.assertEqual(version.get_file_size_display(), 'Unknown size')
        
        # Test with uploaded attachments
        version.file = None
        version.save()
        attachment_one = DatasetVersionFile.objects.create(
            version=version,
            file=SimpleUploadedFile('attachment1.csv', b'data1'),
            file_size=5,
            original_name='attachment1.csv'
        )
        version.file_size = attachment_one.file_size
        version.save(update_fields=['file_size'])
        self.assertEqual(version.get_file_size_display(), '1 file, 5.0 B')

        attachment_two = DatasetVersionFile.objects.create(
            version=version,
            file=SimpleUploadedFile('attachment2.csv', b'data234'),
            file_size=7,
            original_name='attachment2.csv'
        )
        version.file_size = attachment_one.file_size + attachment_two.file_size
        version.save(update_fields=['file_size'])
        self.assertEqual(version.get_file_size_display(), '2 files, 12.0 B')
    
    def test_dataset_version_has_file(self):
        """Test the has_file method"""
        version = DatasetVersion.objects.create(
            dataset=self.dataset,
            version_number='1.0',
            description='Initial version',
            created_by=self.user
        )
        
        # No file initially
        self.assertFalse(version.has_file())
        
        # With file URL
        version.file_url = 'http://example.com/data.csv'
        version.save()
        self.assertTrue(version.has_file())
        
        # With file URL description
        version.file_url = ''
        version.file_url_description = 'Data available at external location'
        version.save()
        self.assertTrue(version.has_file())
        
        # With uploaded file (mocked)
        version.file_url_description = ''
        version.file = SimpleUploadedFile('test.csv', b'content')
        version.save()
        self.assertTrue(version.has_file())
        
        # With uploaded attachments
        version.file = None
        version.save()
        DatasetVersionFile.objects.create(
            version=version,
            file=SimpleUploadedFile('attachment.csv', b'data'),
            file_size=4,
            original_name='attachment.csv'
        )
        self.assertTrue(version.has_file())


class PublisherModelTests(TestCase):
    """Test cases for Publisher model"""
    
    def test_publisher_creation(self):
        """Test creating a publisher"""
        publisher = Publisher.objects.create(
            name='Test Publisher',
            description='Test publisher description',
            website='https://example.com',
            is_active=True
        )
        
        self.assertEqual(publisher.name, 'Test Publisher')
        self.assertEqual(publisher.description, 'Test publisher description')
        self.assertEqual(publisher.website, 'https://example.com')
        self.assertTrue(publisher.is_active)
        self.assertFalse(publisher.is_default)
        self.assertIsNotNone(publisher.created_at)
        self.assertIsNotNone(publisher.updated_at)
    
    def test_publisher_str_representation(self):
        """Test the string representation of publisher"""
        publisher = Publisher.objects.create(
            name='Test Publisher',
            description='Test description'
        )
        
        self.assertEqual(str(publisher), 'Test Publisher')
    
    def test_publisher_unique_name(self):
        """Test that publisher names are unique"""
        Publisher.objects.create(
            name='Test Publisher',
            description='Test description'
        )
        
        # Creating another publisher with same name should fail
        with self.assertRaises(Exception):
            Publisher.objects.create(
                name='Test Publisher',
                description='Another description'
            )
    
    def test_publisher_default_constraint(self):
        """Test that only one publisher can be default"""
        publisher1 = Publisher.objects.create(
            name='Publisher 1',
            description='First publisher',
            is_default=True
        )
        
        publisher2 = Publisher.objects.create(
            name='Publisher 2',
            description='Second publisher',
            is_default=True
        )
        
        # Refresh from database
        publisher1.refresh_from_db()
        publisher2.refresh_from_db()
        
        # Only the last one should be default
        self.assertFalse(publisher1.is_default)
        self.assertTrue(publisher2.is_default)


class DatasetCategoryModelTests(TestCase):
    """Test cases for DatasetCategory model"""
    
    def test_dataset_category_creation(self):
        """Test creating a dataset category"""
        category = DatasetCategory.objects.create(
            name='Test Category',
            description='Test category description',
            color='#007bff',
            is_active=True
        )
        
        self.assertEqual(category.name, 'Test Category')
        self.assertEqual(category.description, 'Test category description')
        self.assertEqual(category.color, '#007bff')
        self.assertTrue(category.is_active)
        self.assertIsNotNone(category.created_at)
        self.assertIsNotNone(category.updated_at)
    
    def test_dataset_category_str_representation(self):
        """Test the string representation of dataset category"""
        category = DatasetCategory.objects.create(
            name='Test Category',
            description='Test description'
        )
        
        self.assertEqual(str(category), 'Test Category')
    
    def test_dataset_category_unique_name(self):
        """Test that category names are unique"""
        DatasetCategory.objects.create(
            name='Test Category',
            description='Test description'
        )
        
        # Creating another category with same name should fail
        with self.assertRaises(Exception):
            DatasetCategory.objects.create(
                name='Test Category',
                description='Another description'
            )


class CommentModelTests(TestCase):
    """Test cases for Comment model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        self.dataset = Dataset.objects.create(
            title='Test Dataset',
            description='Test description',
            owner=self.user
        )
    
    def test_comment_creation(self):
        """Test creating a comment"""
        comment = Comment.objects.create(
            dataset=self.dataset,
            author=self.user,
            content='This is a test comment'
        )
        
        self.assertEqual(comment.dataset, self.dataset)
        self.assertEqual(comment.author, self.user)
        self.assertEqual(comment.content, 'This is a test comment')
        self.assertTrue(comment.is_approved)
        self.assertIsNotNone(comment.created_at)
        self.assertIsNotNone(comment.updated_at)
    
    def test_comment_str_representation(self):
        """Test the string representation of comment"""
        comment = Comment.objects.create(
            dataset=self.dataset,
            author=self.user,
            content='Test comment'
        )
        
        expected_str = f'Comment by {self.user.username} on {self.dataset.title}'
        self.assertEqual(str(comment), expected_str)
    
    def test_comment_can_edit_author(self):
        """Test that comment author can edit their comment"""
        comment = Comment.objects.create(
            dataset=self.dataset,
            author=self.user,
            content='Test comment'
        )
        
        self.assertTrue(comment.can_edit(self.user))
    
    def test_comment_can_edit_staff_user(self):
        """Test that staff users can edit any comment"""
        staff_user = User.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )
        
        comment = Comment.objects.create(
            dataset=self.dataset,
            author=self.other_user,
            content='Test comment'
        )
        
        self.assertTrue(comment.can_edit(staff_user))  # Staff user
    
    def test_comment_can_edit_other_user(self):
        """Test that other users cannot edit comments"""
        comment = Comment.objects.create(
            dataset=self.dataset,
            author=self.user,
            content='Test comment'
        )
        
        self.assertFalse(comment.can_edit(self.other_user))
    
    def test_comment_can_edit_superuser(self):
        """Test that superusers can edit any comment"""
        superuser = User.objects.create_superuser(
            username='superuser',
            email='super@example.com',
            password='testpass123'
        )
        
        comment = Comment.objects.create(
            dataset=self.dataset,
            author=self.user,
            content='Test comment'
        )
        
        self.assertTrue(comment.can_edit(superuser))


class DatasetDownloadModelTests(TestCase):
    """Test cases for DatasetDownload model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.dataset = Dataset.objects.create(
            title='Test Dataset',
            description='Test description',
            owner=self.user
        )
    
    def test_dataset_download_creation(self):
        """Test creating a dataset download record"""
        download = DatasetDownload.objects.create(
            dataset=self.dataset,
            user=self.user,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        self.assertEqual(download.dataset, self.dataset)
        self.assertEqual(download.user, self.user)
        self.assertEqual(download.ip_address, '192.168.1.1')
        self.assertEqual(download.user_agent, 'Mozilla/5.0')
        self.assertIsNotNone(download.downloaded_at)
    
    def test_dataset_download_anonymous(self):
        """Test creating a dataset download record for anonymous user"""
        download = DatasetDownload.objects.create(
            dataset=self.dataset,
            user=None,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        self.assertEqual(download.dataset, self.dataset)
        self.assertIsNone(download.user)
        self.assertEqual(download.ip_address, '192.168.1.1')
    
    def test_dataset_download_str_representation(self):
        """Test the string representation of dataset download"""
        download = DatasetDownload.objects.create(
            dataset=self.dataset,
            user=self.user,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        expected_str = f'{self.dataset.title} - {self.user.username}'
        self.assertEqual(str(download), expected_str)
        
        # Test anonymous user
        download.user = None
        download.save()
        expected_str = f'{self.dataset.title} - Anonymous'
        self.assertEqual(str(download), expected_str)


class DatasetDownloadViewTests(TestCase):
    """Test cases for the dataset download view handling attachments."""

    def setUp(self):
        self.temp_media = TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)
        self.override_media = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)

        self.owner = User.objects.create_user(
            username='dataset_owner',
            email='owner@example.com',
            password='testpass123'
        )
        self.downloader = User.objects.create_user(
            username='downloader',
            email='downloader@example.com',
            password='testpass123'
        )
        self.dataset = Dataset.objects.create(
            title='Downloadable Dataset',
            description='Contains multiple attachments',
            owner=self.owner
        )
        self.version = DatasetVersion.objects.create(
            dataset=self.dataset,
            version_number='1.0',
            description='Initial release',
            created_by=self.owner,
            is_current=True
        )

        file_one = SimpleUploadedFile('first.csv', b'col1,col2\n1,2\n')
        file_two = SimpleUploadedFile('second.csv', b'col1,col2\n3,4\n')

        self.attachment_one = DatasetVersionFile.objects.create(
            version=self.version,
            file=file_one,
            file_size=file_one.size,
            original_name='first.csv'
        )
        self.attachment_two = DatasetVersionFile.objects.create(
            version=self.version,
            file=file_two,
            file_size=file_two.size,
            original_name='second.csv'
        )

        self.version.file_size = self.attachment_one.file_size + self.attachment_two.file_size
        self.version.save(update_fields=['file_size'])

        self.client = Client()
        self.client.force_login(self.downloader)

    def test_download_defaults_to_first_attachment(self):
        """Downloading without specifying a file returns the first attachment."""
        url = reverse('datasets:dataset_download', args=[self.dataset.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.attachment_one.display_name, response.get('Content-Disposition', ''))

        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.download_count, 1)
        self.assertEqual(DatasetDownload.objects.count(), 1)

    def test_download_specific_attachment(self):
        """Downloading with file query parameter returns the requested attachment."""
        url = reverse('datasets:dataset_download', args=[self.dataset.pk])
        response = self.client.get(url, {'version': self.version.id, 'file': self.attachment_two.id})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.attachment_two.display_name, response.get('Content-Disposition', ''))

        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.download_count, 1)
        self.assertEqual(DatasetDownload.objects.count(), 1)

class DatasetDeleteViewTests(TestCase):
    """Test cases for DatasetDeleteView - superuser only deletion"""
    
    def setUp(self):
        """Set up test data"""
        # Create regular user
        self.regular_user = User.objects.create_user(
            username='regularuser',
            email='regular@example.com',
            password='testpass123'
        )
        
        # Create staff user (not superuser)
        self.staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )
        
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='superuser',
            email='super@example.com',
            password='testpass123'
        )
        
        # Create a publisher and category for datasets
        self.publisher = Publisher.objects.create(
            name='Test Publisher',
            description='Test publisher description'
        )
        
        self.category = DatasetCategory.objects.create(
            name='Test Category',
            description='Test category description'
        )
        
        # Create datasets owned by regular user
        self.dataset1 = Dataset.objects.create(
            title='Test Dataset 1',
            description='Test description 1',
            owner=self.regular_user,
            publisher=self.publisher,
            category=self.category,
            status='published'
        )
        
        self.dataset2 = Dataset.objects.create(
            title='Test Dataset 2',
            description='Test description 2',
            owner=self.regular_user,
            publisher=self.publisher,
            status='draft'
        )
        
        # Create dataset version for dataset1
        self.version = DatasetVersion.objects.create(
            dataset=self.dataset1,
            version_number='1.0',
            description='Initial version',
            created_by=self.regular_user
        )
        
        # Create download record for dataset1
        self.download = DatasetDownload.objects.create(
            dataset=self.dataset1,
            user=self.regular_user,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )
        
        # Create comment for dataset1
        self.comment = Comment.objects.create(
            dataset=self.dataset1,
            author=self.regular_user,
            content='Test comment'
        )
        
        self.client = Client()
    
    def test_superuser_can_access_delete_page(self):
        """Test that superuser can access the delete confirmation page"""
        self.client.login(username='superuser', password='testpass123')
        url = reverse('datasets:dataset_delete', kwargs={'pk': self.dataset1.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'datasets/dataset_confirm_delete.html')
        self.assertContains(response, 'Delete Dataset')
        self.assertContains(response, self.dataset1.title)
    
    def test_superuser_can_delete_dataset(self):
        """Test that superuser can successfully delete a dataset"""
        self.client.login(username='superuser', password='testpass123')
        url = reverse('datasets:dataset_delete', kwargs={'pk': self.dataset1.pk})
        
        # Verify dataset exists before deletion
        self.assertTrue(Dataset.objects.filter(pk=self.dataset1.pk).exists())
        
        # Delete the dataset
        response = self.client.post(url, follow=True)
        
        # Check that dataset was deleted
        self.assertFalse(Dataset.objects.filter(pk=self.dataset1.pk).exists())
        
        # Check redirect to dataset list
        self.assertRedirects(response, reverse('datasets:dataset_list'))
        
        # Check success message
        flash_messages = list(get_messages(response.wsgi_request))
        if flash_messages:
            self.assertTrue(any('Dataset deleted successfully!' in str(message) for message in flash_messages))
    
    def test_superuser_can_delete_dataset_with_related_objects(self):
        """Test that superuser can delete a dataset and related objects are cascaded"""
        self.client.login(username='superuser', password='testpass123')
        url = reverse('datasets:dataset_delete', kwargs={'pk': self.dataset1.pk})
        
        dataset_id = self.dataset1.pk
        version_id = self.version.pk
        download_id = self.download.pk
        comment_id = self.comment.pk
        
        # Verify related objects exist
        self.assertTrue(DatasetVersion.objects.filter(pk=version_id).exists())
        self.assertTrue(DatasetDownload.objects.filter(pk=download_id).exists())
        self.assertTrue(Comment.objects.filter(pk=comment_id).exists())
        
        # Delete the dataset
        response = self.client.post(url, follow=True)
        
        # Check that dataset was deleted
        self.assertFalse(Dataset.objects.filter(pk=dataset_id).exists())
        
        # Related objects should also be deleted (CASCADE)
        self.assertFalse(DatasetVersion.objects.filter(pk=version_id).exists())
        self.assertFalse(DatasetDownload.objects.filter(pk=download_id).exists())
        self.assertFalse(Comment.objects.filter(pk=comment_id).exists())
    
    def test_regular_user_cannot_access_delete_page(self):
        """Test that regular user cannot access the delete confirmation page"""
        self.client.login(username='regularuser', password='testpass123')
        url = reverse('datasets:dataset_delete', kwargs={'pk': self.dataset1.pk})
        response = self.client.get(url, follow=True)
        
        # Should redirect with error message
        redirect_url = reverse('datasets:dataset_detail', kwargs={'pk': self.dataset1.pk})
        self.assertIn((redirect_url, 302), response.redirect_chain)
        
        flash_messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Access denied. Only superusers can delete datasets.' in str(message) for message in flash_messages))
    
    def test_regular_user_cannot_delete_own_dataset(self):
        """Test that even dataset owners cannot delete their own datasets (only superusers can)"""
        self.client.login(username='regularuser', password='testpass123')
        url = reverse('datasets:dataset_delete', kwargs={'pk': self.dataset1.pk})
        
        # Try to delete (even though user owns the dataset)
        response = self.client.post(url, follow=True)
        redirect_url = reverse('datasets:dataset_detail', kwargs={'pk': self.dataset1.pk})
        self.assertIn((redirect_url, 302), response.redirect_chain)
        
        # Dataset should still exist
        self.assertTrue(Dataset.objects.filter(pk=self.dataset1.pk).exists())
        
        # Check error message
        flash_messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Access denied. Only superusers can delete datasets.' in str(message) for message in flash_messages))
    
    def test_staff_user_cannot_delete_dataset(self):
        """Test that staff users (non-superuser) cannot delete datasets"""
        self.client.login(username='staffuser', password='testpass123')
        url = reverse('datasets:dataset_delete', kwargs={'pk': self.dataset1.pk})
        response = self.client.get(url, follow=True)
        
        redirect_url = reverse('datasets:dataset_detail', kwargs={'pk': self.dataset1.pk})
        self.assertIn((redirect_url, 302), response.redirect_chain)
        self.assertTrue(Dataset.objects.filter(pk=self.dataset1.pk).exists())
        
        flash_messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Access denied. Only superusers can delete datasets.' in str(message) for message in flash_messages))
    
    def test_unauthenticated_user_cannot_delete_dataset(self):
        """Test that unauthenticated users cannot delete datasets"""
        url = reverse('datasets:dataset_delete', kwargs={'pk': self.dataset1.pk})
        response = self.client.get(url)
        
        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
        
        # Dataset should still exist
        self.assertTrue(Dataset.objects.filter(pk=self.dataset1.pk).exists())
    
    def test_superuser_can_delete_multiple_datasets(self):
        """Test that superuser can delete multiple datasets"""
        self.client.login(username='superuser', password='testpass123')
        
        # Delete first dataset
        url1 = reverse('datasets:dataset_delete', kwargs={'pk': self.dataset1.pk})
        response1 = self.client.post(url1, follow=True)
        self.assertFalse(Dataset.objects.filter(pk=self.dataset1.pk).exists())
        
        # Delete second dataset
        url2 = reverse('datasets:dataset_delete', kwargs={'pk': self.dataset2.pk})
        response2 = self.client.post(url2, follow=True)
        self.assertFalse(Dataset.objects.filter(pk=self.dataset2.pk).exists())
        
        # Both should be deleted
        self.assertEqual(Dataset.objects.count(), 0)
    
    def test_delete_nonexistent_dataset_returns_404(self):
        """Test that deleting a non-existent dataset returns 404"""
        self.client.login(username='superuser', password='testpass123')
        fake_uuid = uuid.uuid4()
        url = reverse('datasets:dataset_delete', kwargs={'pk': fake_uuid})
        with self.assertLogs('django.request', level='WARNING') as log_capture:
            response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)
        self.assertTrue(any('Not Found' in entry for entry in log_capture.output))


class DatasetAnalysisModelTests(TestCase):
    """Test cases for DatasetAnalysis model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.dataset = Dataset.objects.create(
            title='Test Dataset',
            description='Test description',
            owner=self.user
        )
        
        self.test_file = SimpleUploadedFile(
            'test_analysis.pdf',
            b'PDF content here',
            content_type='application/pdf'
        )
    
    def test_dataset_analysis_creation(self):
        """Test creating a DatasetAnalysis instance"""
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Test Analysis',
            description='Test description',
            file=self.test_file,
            file_size=self.test_file.size,
            original_name='test_analysis.pdf',
            uploaded_by=self.user
        )
        
        self.assertEqual(analysis.dataset, self.dataset)
        self.assertEqual(analysis.title, 'Test Analysis')
        self.assertEqual(analysis.description, 'Test description')
        self.assertEqual(analysis.uploaded_by, self.user)
        self.assertEqual(analysis.file_size, self.test_file.size)
        self.assertEqual(analysis.original_name, 'test_analysis.pdf')
    
    def test_dataset_analysis_str_representation(self):
        """Test string representation of DatasetAnalysis"""
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='My Analysis',
            file=self.test_file,
            file_size=self.test_file.size,
            uploaded_by=self.user
        )
        
        expected_str = f"{self.dataset.title} - My Analysis"
        self.assertEqual(str(analysis), expected_str)
    
    def test_display_name_with_original_name(self):
        """Test display_name property when original_name is set"""
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Test Analysis',
            file=self.test_file,
            file_size=self.test_file.size,
            original_name='my_original_file.pdf',
            uploaded_by=self.user
        )
        
        self.assertEqual(analysis.display_name, 'my_original_file.pdf')
    
    def test_display_name_without_original_name(self):
        """Test display_name property when original_name is not set"""
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Test Analysis',
            file=self.test_file,
            file_size=self.test_file.size,
            uploaded_by=self.user
        )
        
        # Should extract filename from file.name
        self.assertIn('test_analysis.pdf', analysis.display_name)
    
    def test_get_file_size_display_bytes(self):
        """Test file size display for bytes"""
        small_file = SimpleUploadedFile('small.txt', b'x' * 512)
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Small Analysis',
            file=small_file,
            file_size=512,
            uploaded_by=self.user
        )
        
        self.assertEqual(analysis.get_file_size_display(), '512.0 B')
    
    def test_get_file_size_display_kb(self):
        """Test file size display for kilobytes"""
        kb_file = SimpleUploadedFile('kb_file.txt', b'x' * 2048)
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='KB Analysis',
            file=kb_file,
            file_size=2048,
            uploaded_by=self.user
        )
        
        self.assertEqual(analysis.get_file_size_display(), '2.0 KB')
    
    def test_get_file_size_display_mb(self):
        """Test file size display for megabytes"""
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='MB Analysis',
            file=self.test_file,
            file_size=2 * 1024 * 1024,  # 2 MB
            uploaded_by=self.user
        )
        
        self.assertEqual(analysis.get_file_size_display(), '2.0 MB')
    
    def test_get_file_size_display_zero(self):
        """Test file size display for zero bytes"""
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Zero Analysis',
            file=self.test_file,
            file_size=0,
            uploaded_by=self.user
        )
        
        self.assertEqual(analysis.get_file_size_display(), '0 B')
    
    def test_can_delete_by_uploader(self):
        """Test that uploader can delete their own analysis"""
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Test Analysis',
            file=self.test_file,
            file_size=self.test_file.size,
            uploaded_by=self.user
        )
        
        self.assertTrue(analysis.can_delete(self.user))
    
    def test_can_delete_by_dataset_owner(self):
        """Test that dataset owner can delete any analysis"""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Test Analysis',
            file=self.test_file,
            file_size=self.test_file.size,
            uploaded_by=other_user
        )
        
        # Dataset owner should be able to delete
        self.assertTrue(analysis.can_delete(self.user))
    
    def test_can_delete_by_staff(self):
        """Test that staff users can delete analyses"""
        staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )
        
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Test Analysis',
            file=self.test_file,
            file_size=self.test_file.size,
            uploaded_by=self.user
        )
        
        self.assertTrue(analysis.can_delete(staff_user))
    
    def test_can_delete_by_superuser(self):
        """Test that superusers can delete analyses"""
        superuser = User.objects.create_superuser(
            username='superuser',
            email='super@example.com',
            password='testpass123'
        )
        
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Test Analysis',
            file=self.test_file,
            file_size=self.test_file.size,
            uploaded_by=self.user
        )
        
        self.assertTrue(analysis.can_delete(superuser))
    
    def test_can_delete_by_unauthorized_user(self):
        """Test that unauthorized users cannot delete analyses"""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Test Analysis',
            file=self.test_file,
            file_size=self.test_file.size,
            uploaded_by=self.user
        )
        
        self.assertFalse(analysis.can_delete(other_user))
    
    def test_dataset_analysis_ordering(self):
        """Test that analyses are ordered by uploaded_at descending"""
        file1 = SimpleUploadedFile('file1.pdf', b'content1')
        file2 = SimpleUploadedFile('file2.pdf', b'content2')
        
        analysis1 = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='First Analysis',
            file=file1,
            file_size=file1.size,
            uploaded_by=self.user
        )
        
        # Add a small delay to ensure different timestamps
        import time
        time.sleep(0.01)
        
        analysis2 = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Second Analysis',
            file=file2,
            file_size=file2.size,
            uploaded_by=self.user
        )
        
        analyses = list(DatasetAnalysis.objects.all())
        # Most recent should be first
        self.assertEqual(analyses[0], analysis2)
        self.assertEqual(analyses[1], analysis1)


class DatasetAnalysisFormTests(TestCase):
    """Test cases for DatasetAnalysisForm"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.dataset = Dataset.objects.create(
            title='Test Dataset',
            description='Test description',
            owner=self.user
        )
    
    def test_form_valid_with_all_fields(self):
        """Test form validation with all required fields"""
        pdf_file = SimpleUploadedFile(
            'analysis.pdf',
            b'PDF content',
            content_type='application/pdf'
        )
        
        form = DatasetAnalysisForm(
            data={
                'title': 'Test Analysis',
                'description': 'Test description'
            },
            files={'file': pdf_file},
            dataset=self.dataset,
            user=self.user
        )
        
        self.assertTrue(form.is_valid())
    
    def test_form_valid_without_description(self):
        """Test form validation without optional description"""
        pdf_file = SimpleUploadedFile(
            'analysis.pdf',
            b'PDF content',
            content_type='application/pdf'
        )
        
        form = DatasetAnalysisForm(
            data={'title': 'Test Analysis'},
            files={'file': pdf_file},
            dataset=self.dataset,
            user=self.user
        )
        
        self.assertTrue(form.is_valid())
    
    def test_form_invalid_without_title(self):
        """Test form validation fails without title"""
        pdf_file = SimpleUploadedFile(
            'analysis.pdf',
            b'PDF content',
            content_type='application/pdf'
        )
        
        form = DatasetAnalysisForm(
            data={'description': 'Test description'},
            files={'file': pdf_file},
            dataset=self.dataset,
            user=self.user
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_form_invalid_without_file(self):
        """Test form validation fails without file"""
        form = DatasetAnalysisForm(
            data={
                'title': 'Test Analysis',
                'description': 'Test description'
            },
            dataset=self.dataset,
            user=self.user
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)
    
    def test_form_invalid_file_too_large(self):
        """Test form validation fails with file exceeding 100MB"""
        large_file = SimpleUploadedFile(
            'large_file.pdf',
            b'x' * (101 * 1024 * 1024),  # 101 MB
            content_type='application/pdf'
        )
        
        form = DatasetAnalysisForm(
            data={'title': 'Test Analysis'},
            files={'file': large_file},
            dataset=self.dataset,
            user=self.user
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)
    
    def test_form_invalid_file_type(self):
        """Test form validation fails with unsupported file type"""
        invalid_file = SimpleUploadedFile(
            'analysis.exe',
            b'executable content',
            content_type='application/x-msdownload'
        )
        
        form = DatasetAnalysisForm(
            data={'title': 'Test Analysis'},
            files={'file': invalid_file},
            dataset=self.dataset,
            user=self.user
        )
        
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)
    
    def test_form_valid_file_types(self):
        """Test form accepts all supported file types"""
        supported_files = [
            ('analysis.pdf', 'application/pdf'),
            ('visualization.html', 'text/html'),
            ('chart.png', 'image/png'),
            ('data.csv', 'text/csv'),
            ('notebook.ipynb', 'application/json'),
            ('script.py', 'text/x-python'),
            ('script.r', 'text/x-r'),
            ('data.json', 'application/json'),
        ]
        
        for filename, content_type in supported_files:
            test_file = SimpleUploadedFile(
                filename,
                b'test content',
                content_type=content_type
            )
            
            form = DatasetAnalysisForm(
                data={'title': 'Test Analysis'},
                files={'file': test_file},
                dataset=self.dataset,
                user=self.user
            )
            
            # File extension validation happens in clean_file
            # We check the file extension, not content_type
            if filename.endswith(('.pdf', '.html', '.png', '.csv', '.ipynb', '.py', '.r', '.json')):
                # These should be valid based on extension
                self.assertTrue(form.is_valid() or 'file' in form.errors and 'not allowed' not in str(form.errors['file']))
    
    def test_form_save(self):
        """Test form save creates DatasetAnalysis instance"""
        pdf_file = SimpleUploadedFile(
            'analysis.pdf',
            b'PDF content',
            content_type='application/pdf'
        )
        
        form = DatasetAnalysisForm(
            data={
                'title': 'Test Analysis',
                'description': 'Test description'
            },
            files={'file': pdf_file},
            dataset=self.dataset,
            user=self.user
        )
        
        self.assertTrue(form.is_valid())
        analysis = form.save()
        
        self.assertIsNotNone(analysis.pk)
        self.assertEqual(analysis.dataset, self.dataset)
        self.assertEqual(analysis.uploaded_by, self.user)
        self.assertEqual(analysis.title, 'Test Analysis')
        self.assertEqual(analysis.description, 'Test description')
        self.assertEqual(analysis.file_size, pdf_file.size)
        self.assertEqual(analysis.original_name, 'analysis.pdf')


class DatasetAnalysisViewTests(TestCase):
    """Test cases for DatasetAnalysis views"""
    
    def setUp(self):
        """Set up test data"""
        self.temp_media = TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)
        self.override_media = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.override_media.enable()
        self.addCleanup(self.override_media.disable)
        
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='testpass123'
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        self.dataset = Dataset.objects.create(
            title='Test Dataset',
            description='Test description',
            owner=self.owner
        )
        
        self.test_file = SimpleUploadedFile(
            'test_analysis.pdf',
            b'PDF content here',
            content_type='application/pdf'
        )
        
        self.analysis = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Test Analysis',
            description='Test description',
            file=self.test_file,
            file_size=self.test_file.size,
            original_name='test_analysis.pdf',
            uploaded_by=self.user
        )
        
        self.client = Client()
    
    def test_upload_analysis_requires_login(self):
        """Test that uploading analysis requires authentication"""
        url = reverse('datasets:upload_analysis', args=[self.dataset.pk])
        pdf_file = SimpleUploadedFile('new_analysis.pdf', b'content')
        
        response = self.client.post(url, {
            'title': 'New Analysis',
            'file': pdf_file
        })
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/user/login/', response.url)
    
    def test_upload_analysis_authenticated(self):
        """Test uploading analysis as authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:upload_analysis', args=[self.dataset.pk])
        pdf_file = SimpleUploadedFile('new_analysis.pdf', b'new content')
        
        response = self.client.post(url, {
            'title': 'New Analysis',
            'description': 'New description',
            'file': pdf_file
        })
        
        # Should redirect to dataset detail
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('datasets:dataset_detail', args=[self.dataset.pk]))
        
        # Check that analysis was created
        self.assertTrue(DatasetAnalysis.objects.filter(title='New Analysis').exists())
        
        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('uploaded successfully' in str(msg) for msg in messages))
    
    def test_upload_analysis_invalid_form(self):
        """Test uploading analysis with invalid form data"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:upload_analysis', args=[self.dataset.pk])
        
        # Missing required file
        response = self.client.post(url, {
            'title': 'New Analysis'
        })
        
        # Should redirect to dataset detail with error message
        self.assertEqual(response.status_code, 302)
        
        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('correct the errors' in str(msg).lower() for msg in messages))
    
    def test_delete_analysis_requires_login(self):
        """Test that deleting analysis requires authentication"""
        url = reverse('datasets:delete_analysis', args=[self.dataset.pk, self.analysis.pk])
        
        response = self.client.post(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/user/login/', response.url)
    
    def test_delete_analysis_by_uploader(self):
        """Test deleting analysis by uploader"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:delete_analysis', args=[self.dataset.pk, self.analysis.pk])
        
        response = self.client.post(url)
        
        # Should redirect to dataset detail
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('datasets:dataset_detail', args=[self.dataset.pk]))
        
        # Check that analysis was deleted
        self.assertFalse(DatasetAnalysis.objects.filter(pk=self.analysis.pk).exists())
        
        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('deleted successfully' in str(msg) for msg in messages))
    
    def test_delete_analysis_by_dataset_owner(self):
        """Test deleting analysis by dataset owner"""
        self.client.login(username='owner', password='testpass123')
        url = reverse('datasets:delete_analysis', args=[self.dataset.pk, self.analysis.pk])
        
        response = self.client.post(url)
        
        # Should redirect to dataset detail
        self.assertEqual(response.status_code, 302)
        
        # Check that analysis was deleted
        self.assertFalse(DatasetAnalysis.objects.filter(pk=self.analysis.pk).exists())
    
    def test_delete_analysis_by_unauthorized_user(self):
        """Test that unauthorized user cannot delete analysis"""
        self.client.login(username='otheruser', password='testpass123')
        url = reverse('datasets:delete_analysis', args=[self.dataset.pk, self.analysis.pk])
        
        response = self.client.post(url)
        
        # Should redirect to dataset detail
        self.assertEqual(response.status_code, 302)
        
        # Check that analysis was NOT deleted
        self.assertTrue(DatasetAnalysis.objects.filter(pk=self.analysis.pk).exists())
        
        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('permission' in str(msg).lower() for msg in messages))
    
    def test_delete_analysis_get_request(self):
        """Test that GET request to delete redirects without deleting"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:delete_analysis', args=[self.dataset.pk, self.analysis.pk])
        
        response = self.client.get(url)
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Analysis should still exist
        self.assertTrue(DatasetAnalysis.objects.filter(pk=self.analysis.pk).exists())
    
    def test_download_analysis_requires_login(self):
        """Test that downloading analysis requires authentication"""
        url = reverse('datasets:download_analysis', args=[self.dataset.pk, self.analysis.pk])
        
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/user/login/', response.url)
    
    def test_download_analysis_authenticated(self):
        """Test downloading analysis as authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:download_analysis', args=[self.dataset.pk, self.analysis.pk])
        
        response = self.client.get(url)
        
        # Should return file response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response.get('Content-Disposition', ''))
        self.assertIn('test_analysis.pdf', response.get('Content-Disposition', ''))
    
    def test_download_nonexistent_analysis(self):
        """Test downloading non-existent analysis returns 404"""
        self.client.login(username='testuser', password='testpass123')
        fake_id = 99999
        url = reverse('datasets:download_analysis', args=[self.dataset.pk, fake_id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)
    
    def test_dataset_detail_includes_analyses(self):
        """Test that dataset detail view includes analyses in context"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:dataset_detail', args=[self.dataset.pk])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('analyses', response.context)
        self.assertIn('analysis_form', response.context)
        self.assertIn(self.analysis, response.context['analyses'])
    
    def test_analysis_form_hidden_by_default(self):
        """Test that the analysis upload form is hidden by default in the template"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:dataset_detail', args=[self.dataset.pk])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check that the form container exists and has the d-none class (hidden by default)
        response_content = response.content.decode('utf-8')
        # Check that the form div contains both the ID and d-none class together
        self.assertIn('id="analysis-upload-form"', response_content)
        # Use regex to find the form div tag and verify it has d-none class
        # The attributes can be in any order
        import re
        form_pattern = r'<div[^>]*id="analysis-upload-form"[^>]*>'
        form_match = re.search(form_pattern, response_content)
        self.assertIsNotNone(form_match, "Form div with id='analysis-upload-form' should exist")
        form_tag = form_match.group(0)
        # Check that d-none is in the class attribute
        self.assertIn('d-none', form_tag, f"Form div should have 'd-none' class. Found: {form_tag}")
    
    def test_add_analysis_button_present_for_authenticated_users(self):
        """Test that the 'Add Analysis' button is present for authenticated users"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:dataset_detail', args=[self.dataset.pk])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check that the toggle button is present
        self.assertContains(response, 'id="toggle-analysis-form-btn"')
        self.assertContains(response, 'Add Analysis')
        self.assertContains(response, 'bi-plus-circle')  # Bootstrap icon
        self.assertContains(response, 'data-text-show')
        self.assertContains(response, 'data-text-hide')
    
    def test_add_analysis_button_not_present_for_anonymous_users(self):
        """Test that anonymous users are redirected to login (dataset detail requires auth)"""
        url = reverse('datasets:dataset_detail', args=[self.dataset.pk])
        
        response = self.client.get(url)
        
        # Should redirect to login since DatasetDetailView requires authentication
        self.assertEqual(response.status_code, 302)
        self.assertIn('/user/login/', response.url)
    
    def test_toggle_analysis_form_javascript_present(self):
        """Test that the JavaScript toggle function is present in the template"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:dataset_detail', args=[self.dataset.pk])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check that the JavaScript function is present
        self.assertContains(response, 'function toggleAnalysisForm()')
        self.assertContains(response, 'analysis-upload-form')
        self.assertContains(response, 'toggle-analysis-form-btn')
        self.assertContains(response, 'scrollIntoView')
    
    def test_analysis_form_has_correct_structure(self):
        """Test that the analysis form has the correct HTML structure"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:dataset_detail', args=[self.dataset.pk])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check form structure
        self.assertContains(response, 'Upload Analysis or Visualization')
        self.assertContains(response, 'name="title"')
        self.assertContains(response, 'name="description"')
        self.assertContains(response, 'name="file"')
        self.assertContains(response, 'enctype="multipart/form-data"')
        # Check cancel button
        self.assertContains(response, 'Cancel')
        self.assertContains(response, 'onclick="toggleAnalysisForm()"')
    
    def test_analysis_form_action_url_correct(self):
        """Test that the form action points to the correct upload URL"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:dataset_detail', args=[self.dataset.pk])
        upload_url = reverse('datasets:upload_analysis', args=[self.dataset.pk])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Check that the form action is correct
        self.assertContains(response, f'action="{upload_url}"')
    
    def test_can_upload_analysis_context_variable(self):
        """Test that can_upload_analysis context variable is set correctly"""
        # For authenticated user
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:dataset_detail', args=[self.dataset.pk])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('can_upload_analysis', response.context)
        self.assertTrue(response.context['can_upload_analysis'])
    
    def test_analysis_section_title_present(self):
        """Test that the Data Visualization & Analysis section title is present"""
        self.client.login(username='testuser', password='testpass123')
        url = reverse('datasets:dataset_detail', args=[self.dataset.pk])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Data Visualization & Analysis')
        # Check that analyses count badge is present
        if self.dataset.analyses.exists():
            self.assertContains(response, 'badge bg-secondary')
    
    def test_multiple_analyses_displayed(self):
        """Test that multiple analyses are displayed correctly"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create additional analyses
        file2 = SimpleUploadedFile('analysis2.pdf', b'content2')
        analysis2 = DatasetAnalysis.objects.create(
            dataset=self.dataset,
            title='Second Analysis',
            file=file2,
            file_size=file2.size,
            uploaded_by=self.user
        )
        
        url = reverse('datasets:dataset_detail', args=[self.dataset.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('analyses', response.context)
        analyses = response.context['analyses']
        self.assertEqual(analyses.count(), 2)
        self.assertIn(self.analysis, analyses)
        self.assertIn(analysis2, analyses)
        
        # Check that both are displayed in template
        self.assertContains(response, 'Test Analysis')
        self.assertContains(response, 'Second Analysis')
