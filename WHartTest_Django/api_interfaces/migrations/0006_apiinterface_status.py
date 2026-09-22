# Generated manually to restore the apiinterfaces.status field.
#
# 生产数据库已通过同名的历史迁移应用过该字段（api_interfaces_apiinterface 表
# 中存在 status varchar NOT NULL 列且 django_migrations 已记录
# 0006_apiinterface_status），因此生产环境执行 migrate 时该迁移会被跳过；
# 全新数据库（含测试库）会正常创建该列。
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_interfaces', '0005_add_file_ids'),
    ]

    operations = [
        migrations.AddField(
            model_name='apiinterface',
            name='status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('integrating', '对接中'),
                    ('self_testing', '自测中'),
                    ('completed', '已完成'),
                ],
                default='integrating',
                max_length=20,
                verbose_name='Status',
            ),
        ),
    ]