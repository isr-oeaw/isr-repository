"""MCP tool definitions and handlers for dataset metadata."""

import json
from uuid import UUID

from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from datasets.models import Dataset, DatasetCategory, Publisher
from datasets.views import send_dataset_update_notification_email
from projects.models import Project
from user.access import partner_visible_datasets, user_can_access_dataset


class McpToolError(Exception):
    """Raised when a tool call fails with a user-facing message."""

    def __init__(self, message, *, not_found=False, forbidden=False):
        super().__init__(message)
        self.message = message
        self.not_found = not_found
        self.forbidden = forbidden


TOOL_DEFINITIONS = [
    {
        'name': 'list_datasets',
        'description': (
            'List datasets visible to the authenticated user. '
            'External partners only see datasets on assigned projects.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'search': {
                    'type': 'string',
                    'description': 'Search title, description, abstract, or tags.',
                },
                'status': {
                    'type': 'string',
                    'enum': ['draft', 'published', 'archived', 'private'],
                    'description': 'Filter by dataset status.',
                },
                'limit': {
                    'type': 'integer',
                    'minimum': 1,
                    'maximum': 50,
                    'description': 'Maximum number of datasets to return (default 20).',
                },
            },
            'additionalProperties': False,
        },
    },
    {
        'name': 'get_dataset',
        'description': 'Get one dataset by UUID if the user may access it.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'dataset_id': {
                    'type': 'string',
                    'description': 'Dataset UUID.',
                },
            },
            'required': ['dataset_id'],
            'additionalProperties': False,
        },
    },
    {
        'name': 'create_dataset',
        'description': (
            'Create dataset metadata. Requires Editor or Administrator role. '
            'Does not upload files or versions.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string'},
                'description': {'type': 'string'},
                'abstract': {'type': 'string'},
                'category_id': {'type': 'integer'},
                'category': {'type': 'string', 'description': 'Category name if id is omitted.'},
                'tags': {'type': 'string', 'description': 'Comma-separated tags (max 10).'},
                'status': {
                    'type': 'string',
                    'enum': ['draft', 'published', 'archived', 'private'],
                },
                'access_level': {
                    'type': 'string',
                    'enum': ['public', 'restricted', 'private'],
                },
                'license': {'type': 'string'},
                'citation': {'type': 'string'},
                'doi': {'type': 'string'},
                'publisher_id': {'type': 'integer'},
                'publisher': {'type': 'string', 'description': 'Publisher name if id is omitted.'},
                'uri_ref': {'type': 'string'},
                'project_ids': {
                    'type': 'array',
                    'items': {'type': 'integer'},
                    'description': 'Project IDs to associate with the dataset.',
                },
            },
            'required': ['title', 'description'],
            'additionalProperties': False,
        },
    },
    {
        'name': 'update_dataset',
        'description': (
            'Update dataset metadata by UUID. Allowed for owner, contributor, staff, or superuser.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'dataset_id': {'type': 'string', 'description': 'Dataset UUID.'},
                'title': {'type': 'string'},
                'description': {'type': 'string'},
                'abstract': {'type': 'string'},
                'category_id': {'type': 'integer'},
                'category': {'type': 'string'},
                'tags': {'type': 'string'},
                'status': {
                    'type': 'string',
                    'enum': ['draft', 'published', 'archived', 'private'],
                },
                'access_level': {
                    'type': 'string',
                    'enum': ['public', 'restricted', 'private'],
                },
                'license': {'type': 'string'},
                'citation': {'type': 'string'},
                'doi': {'type': 'string'},
                'publisher_id': {'type': 'integer'},
                'publisher': {'type': 'string'},
                'uri_ref': {'type': 'string'},
                'project_ids': {
                    'type': 'array',
                    'items': {'type': 'integer'},
                },
            },
            'required': ['dataset_id'],
            'additionalProperties': False,
        },
    },
]


def user_can_create_dataset(user):
    if user.is_superuser:
        return True
    if user.role and user.role.is_active and user.role.name in ('Editor', 'Administrator'):
        return True
    return False


def user_can_edit_dataset(user, dataset):
    if user.is_staff or user.is_superuser:
        return True
    if user == dataset.owner:
        return True
    return dataset.contributors.filter(pk=user.pk).exists()


def _parse_uuid(value, field_name='dataset_id'):
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise McpToolError(f'Invalid {field_name}: must be a UUID.') from exc


def _resolve_category(category_id=None, category_name=None):
    if category_id is not None:
        category = DatasetCategory.objects.filter(pk=category_id, is_active=True).first()
        if not category:
            raise McpToolError(f'Category with id {category_id} was not found.')
        return category
    if category_name:
        category = DatasetCategory.objects.filter(name__iexact=category_name, is_active=True).first()
        if not category:
            raise McpToolError(f'Category "{category_name}" was not found.')
        return category
    return None


def _resolve_publisher(publisher_id=None, publisher_name=None):
    if publisher_id is not None:
        publisher = Publisher.objects.filter(pk=publisher_id, is_active=True).first()
        if not publisher:
            raise McpToolError(f'Publisher with id {publisher_id} was not found.')
        return publisher
    if publisher_name:
        publisher = Publisher.objects.filter(name__iexact=publisher_name, is_active=True).first()
        if not publisher:
            raise McpToolError(f'Publisher "{publisher_name}" was not found.')
        return publisher
    return None


def _clean_tags(tags):
    if tags is None:
        return None
    tag_list = [tag.strip() for tag in str(tags).split(',') if tag.strip()]
    if len(tag_list) > 10:
        raise McpToolError('Maximum 10 tags allowed.')
    return ', '.join(tag_list)


def _accessible_projects_queryset(user):
    if user.is_superuser:
        return Project.objects.all()
    return Project.objects.filter(
        Q(owner=user) | Q(collaborators=user) | Q(access_level='public')
    ).distinct()


def _resolve_project_ids(user, project_ids):
    if project_ids is None:
        return None
    if not isinstance(project_ids, list):
        raise McpToolError('project_ids must be an array of integers.')
    accessible = _accessible_projects_queryset(user)
    projects = list(accessible.filter(pk__in=project_ids))
    if len(projects) != len(set(project_ids)):
        raise McpToolError('One or more project_ids are invalid or not accessible.')
    return projects


def _list_queryset(user):
    if user.is_external_partner:
        return partner_visible_datasets(user).select_related('owner', 'category', 'publisher')
    return Dataset.objects.all().select_related('owner', 'category', 'publisher')


def serialize_dataset(dataset):
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    detail_path = reverse('datasets:dataset_detail', kwargs={'pk': dataset.pk})
    edit_path = reverse('datasets:dataset_edit', kwargs={'pk': dataset.pk})
    return {
        'id': str(dataset.id),
        'title': dataset.title,
        'description': dataset.description,
        'abstract': dataset.abstract,
        'status': dataset.status,
        'access_level': dataset.access_level,
        'tags': dataset.get_tags_list(),
        'license': dataset.license,
        'citation': dataset.citation,
        'doi': dataset.doi,
        'uri_ref': dataset.uri_ref,
        'category': dataset.category.name if dataset.category else None,
        'category_id': dataset.category_id,
        'publisher': dataset.publisher.name if dataset.publisher else None,
        'publisher_id': dataset.publisher_id,
        'owner': dataset.owner.username,
        'owner_id': dataset.owner_id,
        'project_ids': list(dataset.projects.values_list('id', flat=True)),
        'created_at': dataset.created_at.isoformat(),
        'updated_at': dataset.updated_at.isoformat(),
        'url': f'{site_url}{detail_path}',
        'edit_url': f'{site_url}{edit_path}',
    }


def tool_list_datasets(user, arguments=None):
    arguments = arguments or {}
    queryset = _list_queryset(user)

    search = arguments.get('search')
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(abstract__icontains=search)
            | Q(tags__icontains=search)
        )

    status = arguments.get('status')
    if status:
        queryset = queryset.filter(status=status)

    limit = arguments.get('limit', 20)
    try:
        limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise McpToolError('limit must be an integer.') from exc
    limit = max(1, min(limit, 50))

    datasets = queryset.order_by('-is_featured', '-created_at')[:limit]
    payload = {
        'count': len(datasets),
        'datasets': [serialize_dataset(dataset) for dataset in datasets],
    }
    return json.dumps(payload, indent=2)


def tool_get_dataset(user, arguments):
    dataset_id = _parse_uuid(arguments.get('dataset_id'))
    dataset = Dataset.objects.select_related('owner', 'category', 'publisher').filter(pk=dataset_id).first()
    if not dataset or not user_can_access_dataset(user, dataset):
        raise McpToolError('Dataset not found or access denied.', not_found=True)
    return json.dumps(serialize_dataset(dataset), indent=2)


def tool_create_dataset(user, arguments):
    if not user_can_create_dataset(user):
        raise McpToolError(
            'Only Editors and Administrators can create datasets.',
            forbidden=True,
        )

    title = (arguments.get('title') or '').strip()
    description = (arguments.get('description') or '').strip()
    if not title:
        raise McpToolError('title is required.')
    if not description:
        raise McpToolError('description is required.')

    category = _resolve_category(
        arguments.get('category_id'),
        arguments.get('category'),
    )
    publisher = _resolve_publisher(
        arguments.get('publisher_id'),
        arguments.get('publisher'),
    )
    tags = _clean_tags(arguments.get('tags'))
    projects = _resolve_project_ids(user, arguments.get('project_ids'))

    status = arguments.get('status', 'draft')
    if status not in dict(Dataset.STATUS_CHOICES):
        raise McpToolError(f'Invalid status: {status}')

    access_level = arguments.get('access_level', 'public')
    if access_level not in dict(Dataset.ACCESS_LEVEL_CHOICES):
        raise McpToolError(f'Invalid access_level: {access_level}')

    dataset = Dataset.objects.create(
        title=title,
        description=description,
        abstract=arguments.get('abstract', '') or '',
        category=category,
        publisher=publisher,
        tags=tags or '',
        status=status,
        access_level=access_level,
        license=arguments.get('license', '') or '',
        citation=arguments.get('citation', '') or '',
        doi=arguments.get('doi', '') or '',
        uri_ref=arguments.get('uri_ref', '') or '',
        owner=user,
    )
    if projects is not None:
        dataset.projects.set(projects)

    return json.dumps(serialize_dataset(dataset), indent=2)


def tool_update_dataset(user, arguments):
    dataset_id = _parse_uuid(arguments.get('dataset_id'))
    dataset = Dataset.objects.select_related('owner', 'category', 'publisher').filter(pk=dataset_id).first()
    if not dataset:
        raise McpToolError('Dataset not found.', not_found=True)
    if not user_can_edit_dataset(user, dataset):
        raise McpToolError('You do not have permission to edit this dataset.', forbidden=True)

    if 'title' in arguments:
        title = (arguments.get('title') or '').strip()
        if not title:
            raise McpToolError('title cannot be empty.')
        dataset.title = title

    if 'description' in arguments:
        description = (arguments.get('description') or '').strip()
        if not description:
            raise McpToolError('description cannot be empty.')
        dataset.description = description

    if 'abstract' in arguments:
        dataset.abstract = arguments.get('abstract') or ''

    if 'category_id' in arguments or 'category' in arguments:
        dataset.category = _resolve_category(
            arguments.get('category_id'),
            arguments.get('category'),
        )

    if 'publisher_id' in arguments or 'publisher' in arguments:
        dataset.publisher = _resolve_publisher(
            arguments.get('publisher_id'),
            arguments.get('publisher'),
        )

    if 'tags' in arguments:
        dataset.tags = _clean_tags(arguments.get('tags')) or ''

    if 'status' in arguments:
        status = arguments.get('status')
        if status not in dict(Dataset.STATUS_CHOICES):
            raise McpToolError(f'Invalid status: {status}')
        dataset.status = status

    if 'access_level' in arguments:
        access_level = arguments.get('access_level')
        if access_level not in dict(Dataset.ACCESS_LEVEL_CHOICES):
            raise McpToolError(f'Invalid access_level: {access_level}')
        dataset.access_level = access_level

    for field in ('license', 'citation', 'doi', 'uri_ref'):
        if field in arguments:
            setattr(dataset, field, arguments.get(field) or '')

    dataset.save()

    if 'project_ids' in arguments:
        projects = _resolve_project_ids(user, arguments.get('project_ids'))
        dataset.projects.set(projects or [])

    send_dataset_update_notification_email(dataset)
    return json.dumps(serialize_dataset(dataset), indent=2)


TOOL_HANDLERS = {
    'list_datasets': tool_list_datasets,
    'get_dataset': tool_get_dataset,
    'create_dataset': tool_create_dataset,
    'update_dataset': tool_update_dataset,
}


def call_tool(user, name, arguments=None):
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        raise McpToolError(f'Unknown tool: {name}')
    return handler(user, arguments or {})
