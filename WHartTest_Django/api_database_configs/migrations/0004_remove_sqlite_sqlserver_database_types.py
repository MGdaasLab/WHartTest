from django.db import migrations, models
import django.utils.translation


class Migration(migrations.Migration):

    dependencies = [
        ("api_database_configs", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            code=lambda apps, schema_editor: apps.get_model(
                "api_database_configs", "ApiDatabaseConfig"
            )
            .objects.filter(db_type__in=["sqlite", "sqlserver"])
            .update(db_type="mysql", is_active=False),
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="apidatabaseconfig",
            name="db_type",
            field=models.CharField(
                choices=[
                    ("mysql", django.utils.translation.gettext_lazy("MySQL")),
                    ("postgresql", django.utils.translation.gettext_lazy("PostgreSQL")),
                    ("oracle", django.utils.translation.gettext_lazy("Oracle")),
                ],
                default="mysql",
                max_length=20,
                verbose_name=django.utils.translation.gettext_lazy("Database Type"),
            ),
        ),
    ]
