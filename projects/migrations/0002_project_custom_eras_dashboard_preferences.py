from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('projects', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='project', name='era_bc_name',
            field=models.CharField(default='Antes de Cristo', max_length=80),
        ),
        migrations.AddField(
            model_name='project', name='era_bc_abbreviation',
            field=models.CharField(default='A.C.', max_length=20),
        ),
        migrations.AddField(
            model_name='project', name='era_ad_name',
            field=models.CharField(default='Después de Cristo', max_length=80),
        ),
        migrations.AddField(
            model_name='project', name='era_ad_abbreviation',
            field=models.CharField(default='D.C.', max_length=20),
        ),
        migrations.AddField(
            model_name='project', name='dashboard_show_stats',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='project', name='dashboard_show_module_cards',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='project', name='dashboard_show_recent_events',
            field=models.BooleanField(default=True),
        ),
    ]
