# Generated for adding AI操作 step_type choice (value 10).
# SmallIntegerField.choices are enforced only at the application/form level,
# not at the DB level, so this migration solely keeps the embedded choices
# in sync with the model definition.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ui_automation", "0020_remove_db2_support"),
    ]

    operations = [
        migrations.AlterField(
            model_name="uipagestepsdetailed",
            name="step_type",
            field=models.SmallIntegerField(
                choices=[
                    (0, "元素操作"),
                    (1, "断言操作"),
                    (2, "SQL操作"),
                    (3, "自定义变量"),
                    (4, "条件判断"),
                    (5, "Python代码"),
                    (10, "AI操作"),
                ],
                default=0,
                verbose_name="步骤类型",
            ),
        ),
    ]