from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('timeline', '0001_initial')]
    operations = [
        migrations.AddField(
            model_name='event',
            name='sort_order',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name='event',
            options={'ordering': ['date_value', 'sort_order', 'created_at', 'title']},
        ),
        migrations.CreateModel(
            name='TimelineSpan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('start_value', models.CharField(max_length=200)),
                ('end_value', models.CharField(max_length=200)),
                ('span_type', models.CharField(blank=True, max_length=200)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timeline_spans', to='projects.project')),
            ],
            options={'ordering': ['start_value', 'created_at', 'title']},
        ),
    ]
