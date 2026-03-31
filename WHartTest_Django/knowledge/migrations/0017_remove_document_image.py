from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0016_change_default_models_to_qwen3vl'),
    ]

    operations = [
        migrations.DeleteModel(
            name='DocumentImage',
        ),
    ]
