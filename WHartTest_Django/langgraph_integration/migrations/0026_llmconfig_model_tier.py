# Generated for model_tier field (strong/weak)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('langgraph_integration', '0025_alter_llmconfig_provider'),
    ]

    operations = [
        migrations.AddField(
            model_name='llmconfig',
            name='model_tier',
            field=models.CharField(
                choices=[('strong', '强模型'), ('weak', '弱模型')],
                default='strong',
                help_text='弱模型（如 qwen3-coder 等短上下文模型）启用更激进的上下文压缩与步数限制，避免长循环导致上下文超限与页面卡死',
                max_length=16,
                verbose_name='模型能力分层',
            ),
        ),
    ]