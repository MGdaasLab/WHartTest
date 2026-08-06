from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requirements', '0008_change_progress_to_float'),
    ]

    operations = [
        migrations.AddField(
            model_name='requirementdocument',
            name='last_split_level',
            field=models.IntegerField(default=0, verbose_name='最近拆分层级'),
        ),
    ]
