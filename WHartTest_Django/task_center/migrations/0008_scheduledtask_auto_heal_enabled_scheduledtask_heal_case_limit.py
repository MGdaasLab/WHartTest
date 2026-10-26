from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('task_center', '0004_remove_executing_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheduledtask',
            name='auto_heal_enabled',
            field=models.BooleanField(default=False, verbose_name='启用失败自愈'),
        ),
        migrations.AddField(
            model_name='scheduledtask',
            name='heal_case_limit',
            field=models.PositiveSmallIntegerField(
                default=5,
                help_text='一次定时任务中最多自愈的失败用例数，超出的用例列入待人工确认清单',
                validators=[MinValueValidator(1), MaxValueValidator(20)],
                verbose_name='单次自愈用例数上限',
            ),
        ),
    ]
