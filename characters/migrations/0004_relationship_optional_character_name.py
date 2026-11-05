import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('characters', '0003_character_quote_1_context_character_quote_2_context')]

    operations = [
        migrations.AlterField(
            model_name='characterrelationship',
            name='character_2',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='relationships_to', to='characters.character',
            ),
        ),
        migrations.AddField(
            model_name='characterrelationship',
            name='character_2_name',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
