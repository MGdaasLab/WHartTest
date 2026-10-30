from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('task_center', '0008_scheduledtask_auto_heal_enabled_scheduledtask_heal_case_limit'),
        ('ui_automation', '0023_uipagesteps_auth_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='uibatchexecutionrecord',
            name='scheduled_task',
            field=models.ForeignKey(
                blank=True,
                help_text='定时任务触发的批次记录来源任务；手动/API 触发时为空',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='batch_executions',
                to='task_center.scheduledtask',
                verbose_name='关联定时任务',
            ),
        ),
    ]
