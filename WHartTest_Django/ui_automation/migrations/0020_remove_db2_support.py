from django.db import migrations, models


def migrate_db2_environment_configs(apps, schema_editor):
    UiEnvironmentConfig = apps.get_model("ui_automation", "UiEnvironmentConfig")
    UiEnvironmentConfig.objects.filter(db_type="db2").update(
        db_type="mysql",
        db_c_status=False,
        db_rud_status=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("ui_automation", "0019_add_file_ids"),
    ]

    operations = [
        migrations.RunPython(
            code=migrate_db2_environment_configs,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="uienvironmentconfig",
            name="db2_config",
        ),
        migrations.AlterField(
            model_name="uienvironmentconfig",
            name="db_type",
            field=models.CharField(
                choices=[("mysql", "MySQL")],
                default="mysql",
                max_length=20,
                verbose_name="数据库类型",
            ),
        ),
    ]
