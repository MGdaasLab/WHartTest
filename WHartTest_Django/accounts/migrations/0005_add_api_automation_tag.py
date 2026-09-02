# Generated manually: 登录页特色标签默认值新增「接口自动化」

from django.db import migrations, models

OLD_TAGS = 'AI 智能生成, RAG 知识库, MCP 工具调用, Skills 技能库, Playwright 自动化, LangGraph'
NEW_TAGS = 'AI 智能生成, RAG 知识库, MCP 工具调用, Skills 技能库, Playwright 自动化, LangGraph, 接口自动化'

# 仅同步仍使用旧默认值的配置行，用户自定义过的标签不做改动
def append_api_automation_tag(apps, schema_editor):
    SystemConfig = apps.get_model('accounts', 'SystemConfig')
    SystemConfig.objects.filter(login_tags=OLD_TAGS).update(login_tags=NEW_TAGS)


def restore_old_tags(apps, schema_editor):
    SystemConfig = apps.get_model('accounts', 'SystemConfig')
    SystemConfig.objects.filter(login_tags=NEW_TAGS).update(login_tags=OLD_TAGS)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_userloginstate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemconfig',
            name='login_tags',
            field=models.TextField(
                default='AI 智能生成, RAG 知识库, MCP 工具调用, Skills 技能库, Playwright 自动化, LangGraph, 接口自动化',
                help_text='登录页面显示的平台特色标签，用逗号或中文逗号分隔',
                verbose_name='登录页特色标签',
            ),
        ),
        migrations.RunPython(append_api_automation_tag, restore_old_tags),
    ]