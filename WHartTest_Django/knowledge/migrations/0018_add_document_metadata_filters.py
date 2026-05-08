from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0017_remove_document_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="tags",
            field=models.JSONField(blank=True, default=list, verbose_name="标签"),
        ),
        migrations.AddField(
            model_name="document",
            name="metadata",
            field=models.JSONField(blank=True, default=dict, verbose_name="自定义元数据"),
        ),
        migrations.AddField(
            model_name="document",
            name="module",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="业务模块"),
        ),
        migrations.AddField(
            model_name="document",
            name="version",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="版本"),
        ),
        migrations.AddField(
            model_name="document",
            name="business_domain",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="业务域"),
        ),
        migrations.AddField(
            model_name="document",
            name="document_stage",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="文档阶段"),
        ),
        migrations.AddField(
            model_name="querylog",
            name="metadata_filter",
            field=models.JSONField(blank=True, default=dict, verbose_name="元数据过滤条件"),
        ),
    ]
