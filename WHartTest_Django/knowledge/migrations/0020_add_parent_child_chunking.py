from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0019_add_chunk_strategy_to_global_config"),
    ]

    operations = [
        # --- KnowledgeGlobalConfig ---
        migrations.AddField(
            model_name="knowledgeglobalconfig",
            name="parent_child_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When enabled, documents are split into parent chunks (for context) "
                    "and child chunks (for retrieval). Child chunks are indexed in the "
                    "vector store; parent chunks are returned to the LLM."
                ),
                verbose_name="启用 Parent-Child 切分",
            ),
        ),
        migrations.AddField(
            model_name="knowledgeglobalconfig",
            name="parent_chunk_size",
            field=models.PositiveIntegerField(
                default=2000,
                help_text="Character count for parent chunks.",
                verbose_name="Parent 块大小",
            ),
        ),
        migrations.AddField(
            model_name="knowledgeglobalconfig",
            name="parent_chunk_overlap",
            field=models.PositiveIntegerField(
                default=200,
                help_text="Character overlap between parent chunks.",
                verbose_name="Parent 块重叠",
            ),
        ),
        migrations.AddField(
            model_name="knowledgeglobalconfig",
            name="child_chunk_size",
            field=models.PositiveIntegerField(
                default=800,
                help_text=(
                    "Character count for child chunks. Should align with the embedding "
                    "model's optimal input length."
                ),
                verbose_name="Child 块大小",
            ),
        ),
        migrations.AddField(
            model_name="knowledgeglobalconfig",
            name="child_chunk_overlap",
            field=models.PositiveIntegerField(
                default=200,
                help_text="Character overlap between child chunks.",
                verbose_name="Child 块重叠",
            ),
        ),
        # --- KnowledgeBase ---
        migrations.AddField(
            model_name="knowledgebase",
            name="parent_chunk_size",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Override global parent chunk size. Null uses global default.",
                null=True,
                verbose_name="Parent 块大小",
            ),
        ),
        migrations.AddField(
            model_name="knowledgebase",
            name="parent_chunk_overlap",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Override global parent chunk overlap. Null uses global default.",
                null=True,
                verbose_name="Parent 块重叠",
            ),
        ),
        migrations.AddField(
            model_name="knowledgebase",
            name="child_chunk_size",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Override global child chunk size. Null uses global default.",
                null=True,
                verbose_name="Child 块大小",
            ),
        ),
        migrations.AddField(
            model_name="knowledgebase",
            name="child_chunk_overlap",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Override global child chunk overlap. Null uses global default.",
                null=True,
                verbose_name="Child 块重叠",
            ),
        ),
        # --- DocumentChunk ---
        migrations.AddField(
            model_name="documentchunk",
            name="parent_chunk",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name="children",
                to="knowledge.documentchunk",
                verbose_name="父分块",
            ),
        ),
        migrations.AddField(
            model_name="documentchunk",
            name="chunk_level",
            field=models.CharField(
                choices=[("parent", "Parent"), ("child", "Child")],
                default="child",
                max_length=10,
                verbose_name="分块层级",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="documentchunk",
            unique_together={("document", "chunk_index", "chunk_level")},
        ),
    ]
