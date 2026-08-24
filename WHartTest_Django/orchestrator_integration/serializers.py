"""DRF序列化器"""
from rest_framework import serializers
from .models import OrchestratorTask


class OrchestratorTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrchestratorTask
        fields = ['id', 'user', 'project', 'requirement',
                 'status', 'requirement_analysis', 'knowledge_docs', 'testcases',
                 'execution_log', 'error_message', 'created_at', 'started_at', 'completed_at']
        read_only_fields = ['id', 'user', 'status', 'requirement_analysis', 'knowledge_docs',
                           'testcases', 'execution_log', 'error_message',
                           'created_at', 'started_at', 'completed_at']


class OrchestratorTaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrchestratorTask
        fields = ['requirement', 'project']  # 自动使用项目下所有知识库
