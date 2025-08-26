from rest_framework import serializers
from django.contrib.auth.models import User
from .models import KnowledgeBase, Document, DocumentChunk, QueryLog
from projects.models import Project


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    """知识库序列化器"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    document_count = serializers.SerializerMethodField()
    chunk_count = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeBase
        fields = [
            'id', 'name', 'description', 'project', 'project_name',
            'creator', 'creator_name', 'is_active',
            'embedding_service', 'api_base_url', 'api_key', 'model_name', 
            'chunk_size', 'chunk_overlap',
            'document_count', 'chunk_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'creator', 'created_at', 'updated_at', 'project_name']
        extra_kwargs = {
            'project': {'required': False}  # 在更新时project字段不是必填的
        }

    def get_document_count(self, obj):
        """获取文档数量"""
        return obj.documents.count()

    def get_chunk_count(self, obj):
        """获取分块数量"""
        return DocumentChunk.objects.filter(document__knowledge_base=obj).count()

    def validate_project(self, value):
        """验证项目权限"""
        # 创建时验证项目权限
        user = self.context['request'].user
        if not user.is_superuser:
            # 检查用户是否是项目成员
            if not value.members.filter(user=user).exists():
                raise serializers.ValidationError("您没有权限在此项目中创建知识库")
        return value

    def update(self, instance, validated_data):
        """更新知识库，项目字段不可更改"""
        # 移除项目字段，防止更新时修改项目
        validated_data.pop('project', None)
        return super().update(instance, validated_data)

    def validate(self, data):
        """验证数据，处理project字段"""
        # 如果是更新操作，始终使用现有实例的project（忽略传入的project值）
        if self.instance is not None:
            data['project'] = self.instance.project
        return super().validate(data)


class DocumentUploadSerializer(serializers.ModelSerializer):
    """文档上传序列化器"""
    uploader_name = serializers.CharField(source='uploader.username', read_only=True)
    knowledge_base_name = serializers.CharField(source='knowledge_base.name', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'knowledge_base', 'knowledge_base_name', 'title',
            'document_type', 'file', 'url', 'content', 'status',
            'error_message', 'file_size', 'page_count', 'word_count',
            'uploader', 'uploader_name', 'uploaded_at', 'processed_at'
        ]
        read_only_fields = [
            'id', 'uploader', 'status', 'error_message',
            'file_size', 'page_count', 'word_count',
            'uploaded_at', 'processed_at'
        ]

    def validate(self, data):
        """验证文档数据"""
        document_type = data.get('document_type')
        file = data.get('file')
        url = data.get('url')
        content = data.get('content')

        if document_type == 'url':
            if not url:
                raise serializers.ValidationError("网页链接类型必须提供URL")
        elif document_type in ['txt', 'md']:
            if not content and not file:
                raise serializers.ValidationError("文本类型文档必须提供内容或文件")
        else:
            if not file:
                raise serializers.ValidationError("此文档类型必须上传文件")

        return data

    def validate_knowledge_base(self, value):
        """验证知识库权限"""
        user = self.context['request'].user
        if not user.is_superuser:
            # 检查用户是否是项目成员
            if not value.project.members.filter(user=user).exists():
                raise serializers.ValidationError("您没有权限向此知识库上传文档")
        return value


class DocumentSerializer(serializers.ModelSerializer):
    """文档详情序列化器"""
    uploader_name = serializers.CharField(source='uploader.username', read_only=True)
    knowledge_base_name = serializers.CharField(source='knowledge_base.name', read_only=True)
    file_extension = serializers.CharField(read_only=True)
    chunk_count = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'knowledge_base', 'knowledge_base_name', 'title',
            'document_type', 'file', 'url', 'content', 'status',
            'error_message', 'file_size', 'page_count', 'word_count',
            'file_extension', 'chunk_count', 'uploader', 'uploader_name',
            'uploaded_at', 'processed_at'
        ]
        read_only_fields = [
            'id', 'uploader', 'file_size', 'page_count', 'word_count',
            'file_extension', 'uploaded_at', 'processed_at'
        ]

    def get_chunk_count(self, obj):
        """获取分块数量"""
        return obj.chunks.count()


class DocumentChunkSerializer(serializers.ModelSerializer):
    """文档分块序列化器"""
    document_title = serializers.CharField(source='document.title', read_only=True)

    class Meta:
        model = DocumentChunk
        fields = [
            'id', 'document', 'document_title', 'chunk_index',
            'content', 'vector_id', 'embedding_hash',
            'start_index', 'end_index', 'page_number', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class QueryLogSerializer(serializers.ModelSerializer):
    """查询日志序列化器"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    knowledge_base_name = serializers.CharField(source='knowledge_base.name', read_only=True)

    class Meta:
        model = QueryLog
        fields = [
            'id', 'knowledge_base', 'knowledge_base_name', 'user', 'user_name',
            'query', 'response', 'retrieved_chunks', 'similarity_scores',
            'retrieval_time', 'generation_time', 'total_time', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']


class KnowledgeQuerySerializer(serializers.Serializer):
    """知识库查询序列化器"""
    query = serializers.CharField(max_length=1000, help_text="查询内容")
    knowledge_base_id = serializers.UUIDField(help_text="知识库ID")
    top_k = serializers.IntegerField(default=5, min_value=1, max_value=20, help_text="返回结果数量")
    similarity_threshold = serializers.FloatField(
        default=0.1, min_value=0.0, max_value=1.0, help_text="相似度阈值"
    )
    include_metadata = serializers.BooleanField(default=True, help_text="是否包含元数据")

    def validate_knowledge_base_id(self, value):
        """验证知识库是否存在且有权限访问"""
        user = self.context['request'].user
        try:
            kb = KnowledgeBase.objects.get(id=value)
            if not user.is_superuser:
                # 检查用户是否是项目成员
                if not kb.project.members.filter(user=user).exists():
                    raise serializers.ValidationError("您没有权限访问此知识库")
            return value
        except KnowledgeBase.DoesNotExist:
            raise serializers.ValidationError("知识库不存在")


class KnowledgeQueryResponseSerializer(serializers.Serializer):
    """知识库查询响应序列化器"""
    query = serializers.CharField()
    answer = serializers.CharField()
    sources = serializers.ListField(child=serializers.DictField())
    retrieval_time = serializers.FloatField()
    generation_time = serializers.FloatField()
    total_time = serializers.FloatField()
