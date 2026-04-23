"""
数据迁移：将已有 ChatSession 的 Token 统计回填到 TokenUsageRecord

每个 request_count > 0 的 ChatSession 生成一条合成记录，
日期使用 updated_at，确保历史统计不会因为切换数据源而丢失。
"""

from django.db import migrations


def backfill_token_usage_records(apps, schema_editor):
    ChatSession = apps.get_model('langgraph_integration', 'ChatSession')
    TokenUsageRecord = apps.get_model('langgraph_integration', 'TokenUsageRecord')

    sessions = ChatSession.objects.filter(request_count__gt=0).select_related('user', 'project')
    records = []
    for session in sessions:
        records.append(TokenUsageRecord(
            user=session.user,
            project=session.project,
            session_id=session.session_id,
            created_at=session.updated_at,
            input_tokens=session.total_input_tokens,
            output_tokens=session.total_output_tokens,
            total_tokens=session.total_tokens,
            cache_read_tokens=0,  # 历史数据无缓存信息
        ))
    if records:
        TokenUsageRecord.objects.bulk_create(records, batch_size=500)


def reverse_backfill(apps, schema_editor):
    # 回滚时删除所有回填记录（cache_read_tokens=0 标识回填数据）
    TokenUsageRecord = apps.get_model('langgraph_integration', 'TokenUsageRecord')
    TokenUsageRecord.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('langgraph_integration', '0023_add_token_usage_record_and_cache_field'),
    ]

    operations = [
        migrations.RunPython(backfill_token_usage_records, reverse_backfill),
    ]
