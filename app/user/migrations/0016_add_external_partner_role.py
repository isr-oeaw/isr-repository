# Generated manually for External Partner role

from django.db import migrations


def create_external_partner_role(apps, schema_editor):
    Role = apps.get_model('user', 'Role')

    role_data = {
        'name': 'External Partner',
        'description': 'Invited collaborator with access limited to assigned projects',
        'permissions': {
            'permissions': [
                'dataset.view',
                'project.view',
            ]
        },
        'is_active': True,
    }

    role, created = Role.objects.get_or_create(
        name=role_data['name'],
        defaults={
            'description': role_data['description'],
            'permissions': role_data['permissions'],
            'is_active': role_data['is_active'],
        },
    )

    if not created:
        role.description = role_data['description']
        role.permissions = role_data['permissions']
        role.is_active = role_data['is_active']
        role.save()


def reverse_external_partner_role(apps, schema_editor):
    Role = apps.get_model('user', 'Role')
    Role.objects.filter(name='External Partner').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0015_rename_user_apikey_key_idx_user_apikey_key_c2af0e_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(
            create_external_partner_role,
            reverse_external_partner_role,
        ),
    ]
