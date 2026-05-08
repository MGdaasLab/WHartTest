from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0018_add_document_metadata_filters"),
    ]

    operations = [
        migrations.AddField(
            model_name="knowledgeglobalconfig",
            name="chunk_strategy",
            field=models.CharField(
                choices=[
                    ("recursive_character", "固定长度"),
                    ("heading_aware", "结构优先"),
                    ("markdown_header", "Markdown 标题"),
                ],
                default="recursive_character",
                max_length=50,
                verbose_name="默认切分策略",
            ),
        ),
    ]
