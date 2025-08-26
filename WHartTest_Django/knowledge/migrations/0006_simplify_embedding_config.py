# Generated to simplify embedding configuration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0005_remove_knowledgebase_vector_store_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='knowledgebase',
            name='embedding_service',
            field=models.CharField(
                choices=[('openai', 'OpenAI'), ('azure_openai', 'Azure OpenAI'), ('ollama', 'Ollama'), ('custom', '自定义API')],
                default='openai',
                help_text='选择嵌入服务提供商',
                max_length=50,
                verbose_name='嵌入服务'
            ),
        ),
        migrations.AddField(
            model_name='knowledgebase',
            name='model_name',
            field=models.CharField(
                blank=True,
                default='text-embedding-ada-002',
                help_text='具体的嵌入模型名称',
                max_length=100,
                null=True,
                verbose_name='模型名称'
            ),
        ),
    ]
