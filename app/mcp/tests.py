import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from datasets.models import Dataset, DatasetCategory, Publisher
from projects.models import Project
from user.models import APIKey, Role

User = get_user_model()


class McpEndpointTests(TestCase):
    """Tests for the MCP dataset endpoint."""

    def setUp(self):
        self.client = Client()
        self.mcp_url = reverse('mcp')

        self.editor_role = Role.objects.create(
            name='Editor',
            permissions={'permissions': ['dataset.create', 'dataset.edit']},
            is_active=True,
        )
        self.viewer_role = Role.objects.create(
            name='Viewer',
            permissions={'permissions': ['dataset.view']},
            is_active=True,
        )
        self.partner_role = Role.objects.create(
            name='External Partner',
            permissions={'permissions': ['dataset.view', 'project.view']},
            is_active=True,
        )

        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='testpass123',
            role=self.editor_role,
            is_approved=True,
        )
        self.editor = User.objects.create_user(
            username='editor',
            email='editor@example.com',
            password='testpass123',
            role=self.editor_role,
            is_approved=True,
        )
        self.viewer = User.objects.create_user(
            username='viewer',
            email='viewer@example.com',
            password='testpass123',
            role=self.viewer_role,
            is_approved=True,
        )
        self.partner = User.objects.create_user(
            username='partner',
            email='partner@example.com',
            password='testpass123',
            role=self.partner_role,
            is_approved=True,
        )
        self.other = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123',
            is_approved=True,
        )

        self.owner_key = APIKey.generate_key(user=self.owner, name='Owner Key')
        self.editor_key = APIKey.generate_key(user=self.editor, name='Editor Key')
        self.viewer_key = APIKey.generate_key(user=self.viewer, name='Viewer Key')
        self.partner_key = APIKey.generate_key(user=self.partner, name='Partner Key')

        self.category = DatasetCategory.objects.create(
            name='Test Category',
            description='Category',
            color='#007bff',
            is_active=True,
        )
        self.publisher = Publisher.objects.create(
            name='Test Publisher',
            description='Publisher',
            is_active=True,
        )

        self.project = Project.objects.create(
            title='Partner Project',
            description='Assigned project',
            owner=self.owner,
            access_level='private',
        )
        self.project.collaborators.add(self.partner)

        self.assigned_dataset = Dataset.objects.create(
            title='Assigned Dataset',
            description='Visible to partner',
            owner=self.owner,
            category=self.category,
            publisher=self.publisher,
            status='published',
        )
        self.assigned_dataset.projects.add(self.project)

        self.other_dataset = Dataset.objects.create(
            title='Other Dataset',
            description='Not visible to partner',
            owner=self.owner,
            category=self.category,
            publisher=self.publisher,
            status='published',
        )

    def _post_mcp(self, payload, api_key=None):
        headers = {}
        if api_key:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {api_key}'
        return self.client.post(
            self.mcp_url,
            data=json.dumps(payload),
            content_type='application/json',
            **headers,
        )

    def _call_tool(self, name, arguments=None, api_key=None):
        response = self._post_mcp(
            {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {
                    'name': name,
                    'arguments': arguments or {},
                },
            },
            api_key=api_key,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('result', body)
        return body['result']

    def test_unauthenticated_request_returns_401(self):
        response = self._post_mcp(
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
        )
        self.assertEqual(response.status_code, 401)

    def test_initialize_and_tools_list(self):
        init_response = self._post_mcp(
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
            api_key=self.owner_key.key,
        )
        self.assertEqual(init_response.status_code, 200)
        init_body = init_response.json()
        self.assertEqual(init_body['result']['serverInfo']['name'], 'isr-repository')

        list_response = self._post_mcp(
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}},
            api_key=self.owner_key.key,
        )
        self.assertEqual(list_response.status_code, 200)
        tool_names = [tool['name'] for tool in list_response.json()['result']['tools']]
        self.assertEqual(
            tool_names,
            ['list_datasets', 'get_dataset', 'create_dataset', 'update_dataset'],
        )

    def test_get_method_returns_405(self):
        response = self.client.get(self.mcp_url)
        self.assertEqual(response.status_code, 405)

    def test_delete_method_returns_204(self):
        response = self.client.delete(
            self.mcp_url,
            HTTP_AUTHORIZATION=f'Bearer {self.owner_key.key}',
        )
        self.assertEqual(response.status_code, 204)

    def test_partner_list_omits_unassigned_datasets(self):
        result = self._call_tool('list_datasets', api_key=self.partner_key.key)
        self.assertFalse(result['isError'])
        payload = json.loads(result['content'][0]['text'])
        titles = [item['title'] for item in payload['datasets']]
        self.assertIn('Assigned Dataset', titles)
        self.assertNotIn('Other Dataset', titles)

    def test_editor_can_create_dataset(self):
        result = self._call_tool(
            'create_dataset',
            {
                'title': 'MCP Created Dataset',
                'description': 'Created through MCP',
                'category_id': self.category.id,
                'project_ids': [self.project.id],
            },
            api_key=self.editor_key.key,
        )
        self.assertFalse(result['isError'])
        payload = json.loads(result['content'][0]['text'])
        self.assertEqual(payload['title'], 'MCP Created Dataset')
        self.assertEqual(payload['owner'], 'editor')
        self.assertTrue(
            Dataset.objects.filter(title='MCP Created Dataset', owner=self.editor).exists()
        )

    def test_viewer_cannot_create_dataset(self):
        result = self._call_tool(
            'create_dataset',
            {
                'title': 'Blocked Dataset',
                'description': 'Should fail',
            },
            api_key=self.viewer_key.key,
        )
        self.assertTrue(result['isError'])
        self.assertIn('Editors and Administrators', result['content'][0]['text'])
        self.assertFalse(Dataset.objects.filter(title='Blocked Dataset').exists())

    def test_partner_cannot_create_dataset(self):
        result = self._call_tool(
            'create_dataset',
            {
                'title': 'Partner Dataset',
                'description': 'Should fail',
            },
            api_key=self.partner_key.key,
        )
        self.assertTrue(result['isError'])
        self.assertFalse(Dataset.objects.filter(title='Partner Dataset').exists())

    def test_get_dataset_returns_payload(self):
        result = self._call_tool(
            'get_dataset',
            {'dataset_id': str(self.assigned_dataset.id)},
            api_key=self.partner_key.key,
        )
        self.assertFalse(result['isError'])
        payload = json.loads(result['content'][0]['text'])
        self.assertEqual(payload['title'], 'Assigned Dataset')
        self.assertIn('/datasets/', payload['url'])

    def test_get_dataset_denies_inaccessible_dataset(self):
        result = self._call_tool(
            'get_dataset',
            {'dataset_id': str(self.other_dataset.id)},
            api_key=self.partner_key.key,
        )
        self.assertTrue(result['isError'])
        self.assertIn('not found', result['content'][0]['text'].lower())

    def test_owner_can_update_dataset(self):
        result = self._call_tool(
            'update_dataset',
            {
                'dataset_id': str(self.assigned_dataset.id),
                'title': 'Updated Assigned Dataset',
            },
            api_key=self.owner_key.key,
        )
        self.assertFalse(result['isError'])
        payload = json.loads(result['content'][0]['text'])
        self.assertEqual(payload['title'], 'Updated Assigned Dataset')
        self.assigned_dataset.refresh_from_db()
        self.assertEqual(self.assigned_dataset.title, 'Updated Assigned Dataset')

    def test_other_user_cannot_update_dataset(self):
        other_key = APIKey.generate_key(user=self.other, name='Other Key')
        result = self._call_tool(
            'update_dataset',
            {
                'dataset_id': str(self.other_dataset.id),
                'title': 'Hijacked Dataset',
            },
            api_key=other_key.key,
        )
        self.assertTrue(result['isError'])
        self.other_dataset.refresh_from_db()
        self.assertEqual(self.other_dataset.title, 'Other Dataset')
