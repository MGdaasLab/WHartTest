# Repair migration for databases that applied an older branch migration which
# deleted langgraph_integration_llmconfig while the current code still uses it.

from django.db import migrations


def restore_llmconfig_table_if_missing(apps, schema_editor):
    table_name = 'langgraph_integration_llmconfig'
    existing_tables = schema_editor.connection.introspection.table_names()
    if table_name in existing_tables:
        return

    LLMConfig = apps.get_model('langgraph_integration', 'LLMConfig')
    schema_editor.create_model(LLMConfig)


def noop_reverse(apps, schema_editor):
    # Do not drop data on rollback. This migration is intentionally repair-only.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('langgraph_integration', '0025_alter_llmconfig_provider'),
    ]

    operations = [
        migrations.RunPython(restore_llmconfig_table_if_missing, noop_reverse),
    ]
