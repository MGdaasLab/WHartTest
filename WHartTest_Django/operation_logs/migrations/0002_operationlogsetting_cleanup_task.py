import json

import django.core.validators
from django.db import migrations, models


TASK_NAME = 'operation_logs_cleanup_daily'
TASK_DESCRIPTION = '每日自动清理过期操作日志'
TASK_PATH = 'operation_logs.tasks.cleanup_operation_logs'


def create_default_setting_and_cleanup_task(apps, schema_editor):
    OperationLogSetting = apps.get_model('operation_logs', 'OperationLogSetting')
    OperationLogSetting.objects.get_or_create(id=1, defaults={'retention_days': 7})

    CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute='0',
        hour='3',
        day_of_week='*',
        day_of_month='*',
        month_of_year='*',
        timezone='Asia/Shanghai',
    )

    PeriodicTask.objects.update_or_create(
        name=TASK_NAME,
        defaults={
            'task': TASK_PATH,
            'crontab': schedule,
            'interval': None,
            'clocked': None,
            'one_off': False,
            'enabled': True,
            'queue': 'celery',
            'args': json.dumps([]),
            'description': TASK_DESCRIPTION,
        },
    )


def delete_cleanup_task(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('django_celery_beat', '0019_alter_periodictasks_options'),
        ('operation_logs', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OperationLogSetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('retention_days', models.PositiveIntegerField(default=7, help_text='自动清理超过保留天数的操作日志，默认 7 天', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(3650)], verbose_name='操作日志保留天数')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '操作日志设置',
                'verbose_name_plural': '操作日志设置',
            },
        ),
        migrations.RunPython(create_default_setting_and_cleanup_task, delete_cleanup_task),
    ]
