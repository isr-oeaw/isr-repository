# Generated manually for dataset version data description

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0025_remove_dataset_uuid_alter_comment_dataset_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='datasetversion',
            name='observation_count',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Number of observations'),
        ),
        migrations.AddField(
            model_name='datasetversion',
            name='spatial_coverage',
            field=models.CharField(
                blank=True,
                help_text='Geographic area covered (e.g. Germany, NUTS-2)',
                max_length=500,
                verbose_name='Spatial coverage',
            ),
        ),
        migrations.AddField(
            model_name='datasetversion',
            name='temporal_end',
            field=models.DateField(
                blank=True,
                help_text='End of the time period covered by this version',
                null=True,
                verbose_name='Temporal coverage end',
            ),
        ),
        migrations.AddField(
            model_name='datasetversion',
            name='temporal_start',
            field=models.DateField(
                blank=True,
                help_text='Start of the time period covered by this version',
                null=True,
                verbose_name='Temporal coverage start',
            ),
        ),
        migrations.AddField(
            model_name='datasetversion',
            name='unit_of_analysis',
            field=models.CharField(
                blank=True,
                help_text='e.g. person, household, country-year',
                max_length=200,
                verbose_name='Unit of analysis',
            ),
        ),
        migrations.CreateModel(
            name='DatasetVersionColumn',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveIntegerField(default=0)),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('label', models.CharField(blank=True, max_length=255, verbose_name='Label')),
                (
                    'data_type',
                    models.CharField(
                        choices=[
                            ('text', 'Text'),
                            ('integer', 'Integer'),
                            ('decimal', 'Decimal'),
                            ('date', 'Date'),
                            ('boolean', 'Boolean'),
                            ('categorical', 'Categorical'),
                        ],
                        default='text',
                        max_length=20,
                        verbose_name='Data type',
                    ),
                ),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                (
                    'version',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='columns',
                        to='datasets.datasetversion',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Dataset version column',
                'verbose_name_plural': 'Dataset version columns',
                'ordering': ['position', 'id'],
            },
        ),
    ]
