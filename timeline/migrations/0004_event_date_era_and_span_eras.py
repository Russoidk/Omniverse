from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('timeline', '0003_event_timeline_span_span_marker')]

    operations = [
        migrations.AddField(
            model_name='event',
            name='date_era',
            field=models.CharField(
                choices=[('BC', 'Antes de Cristo (A.C.)'), ('AD', 'Después de Cristo (D.C.)')],
                default='AD', max_length=2, verbose_name='Era histórica',
            ),
        ),
        migrations.AddField(
            model_name='timelinespan',
            name='start_era',
            field=models.CharField(
                choices=[('BC', 'Antes de Cristo (A.C.)'), ('AD', 'Después de Cristo (D.C.)')],
                default='AD', max_length=2, verbose_name='Era de comienzo',
            ),
        ),
        migrations.AddField(
            model_name='timelinespan',
            name='end_era',
            field=models.CharField(
                choices=[('BC', 'Antes de Cristo (A.C.)'), ('AD', 'Después de Cristo (D.C.)')],
                default='AD', max_length=2, verbose_name='Era de finalización',
            ),
        ),
    ]
