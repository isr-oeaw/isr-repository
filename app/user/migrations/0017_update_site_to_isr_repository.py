# Generated manually to rename the Django Sites entry

from django.db import migrations
from django.conf import settings


def update_site_to_isr_repository(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    site, created = Site.objects.get_or_create(
        id=settings.SITE_ID,
        defaults={
            'name': 'ISR Repository',
            'domain': 'isrrepository.dataplexity.eu',
        },
    )
    if not created:
        site.name = 'ISR Repository'
        site.domain = 'isrrepository.dataplexity.eu'
        site.save()


def reverse_site_to_isr_datasets(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    try:
        site = Site.objects.get(id=settings.SITE_ID)
        site.name = 'ISR Datasets'
        site.domain = 'isrdatasets.dataplexity.eu'
        site.save()
    except Site.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0016_add_external_partner_role'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(
            update_site_to_isr_repository,
            reverse_site_to_isr_datasets,
        ),
    ]
