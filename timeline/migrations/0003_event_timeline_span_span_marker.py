from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('timeline', '0002_event_sort_order_timelinespan'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='timeline_span',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='events',
                to='timeline.timelinespan',
                verbose_name='Lapso de tiempo',
            ),
        ),
        migrations.AddField(
            model_name='event',
            name='span_marker',
            field=models.CharField(
                blank=True,
                choices=[('START', 'Inicio de lapso'), ('END', 'Final de lapso')],
                default='',
                max_length=5,
                verbose_name='Marca del lapso',
            ),
        ),
    ]
