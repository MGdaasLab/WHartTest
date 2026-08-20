from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from projects.models import Project
import uuid
import os


class KnowledgeGlobalConfig(models.Model):
    """
    知识库全局配置模型，存储嵌入服务的默认配置
    采用单例模式，系统中只有一条配置记录
    """
    EMBEDDING_SERVICE_CHOICES = [
        ('openai', 'OpenAI'),
        ('azure_openai', 'Azure OpenAI'),
        ('ollama', 'Ollama'),
        ('xinference', 'Xinference'),
        ('custom', '自定义API'),
    ]

    RERANKER_SERVICE_CHOICES = [
        ('none', '不启用'),
        ('xinference', 'Xinference'),
        ('custom', '自定义API'),
    ]

    # Embedding 配置
    embedding_service = models.CharField(
        _('嵌入服务'),
        max_length=50,
        choices=EMBEDDING_SERVICE_CHOICES,
        default='custom',
        help_text=_('选择嵌入服务提供商')
    )
    api_base_url = models.CharField(
        _('API基础URL'),
        max_length=500,
        blank=True,
        null=True,
        help_text=_('API服务的基础URL，如：https://api.openai.com/v1 或 http://xinference:9997')
    )
    api_key = models.CharField(
        _('API密钥'),
        max_length=500,
        blank=True,
        null=True,
        help_text=_('API服务的密钥')
    )
    model_name = models.CharField(
        _('模型名称'),
        max_length=100,
        default='qwen3-vl-emb-2b',
        help_text=_('具体的嵌入模型名称')
    )

    # Reranker 配置（独立）
    reranker_service = models.CharField(
        _('Reranker服务'),
        max_length=50,
        choices=RERANKER_SERVICE_CHOICES,
        default='none',
        help_text=_('选择Reranker精排服务，可独立于嵌入服务配置')
    )
    reranker_api_url = models.CharField(
        _('Reranker API地址'),
        max_length=500,
        blank=True,
        null=True,
        help_text=_('Reranker服务的API地址，如：http://xinference:9997')
    )
    reranker_api_key = models.CharField(
        _('Reranker API密钥'),
        max_length=500,
        blank=True,
        null=True,
        help_text=_('Reranker服务的API密钥（自定义API可能需要）')
    )
    reranker_model_name = models.CharField(
        _('Reranker模型名称'),
        max_length=100,
        default='Qwen3-VL-Reranker-2B',
        blank=True,
        help_text=_('Reranker模型名称')
    )

    chunk_size = models.PositiveIntegerField(_('默认分块大小'), default=1000)
    chunk_overlap = models.PositiveIntegerField(_('默认分块重叠'), default=200)
    
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_knowledge_configs',
        verbose_name=_('更新人')
    )

    class Meta:
        verbose_name = _('知识库全局配置')
        verbose_name_plural = _('知识库全局配置')

    def __str__(self):
        return f"知识库全局配置 ({self.get_embedding_service_display()})"
    
    def save(self, *args, **kwargs):
        """确保只有一条记录（单例模式）"""
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        """获取全局配置，如果不存在则创建默认配置"""
        config, _ = cls.objects.get_or_create(pk=1)
        return config


class KnowledgeBase(models.Model):
    """
    知识库模型，支持项目级别的知识库管理
    嵌入服务配置统一使用 KnowledgeGlobalConfig 全局配置
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('知识库名称'), max_length=200)
    description = models.TextField(_('描述'), blank=True, null=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='knowledge_bases',
        verbose_name=_('所属项目')
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_knowledge_bases',
        verbose_name=_('创建人')
    )
    is_active = models.BooleanField(_('是否启用'), default=True)
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)
    
    # 文档处理配置（可覆盖全局默认值）
    chunk_size = models.PositiveIntegerField(_('分块大小'), default=1000)
    chunk_overlap = models.PositiveIntegerField(_('分块重叠'), default=200)

    class Meta:
        verbose_name = _('知识库')
        verbose_name_plural = _('知识库')
        ordering = ['-created_at']
        unique_together = ['project', 'name']

    def __str__(self):
        return f"{self.project.name} - {self.name}"


def document_upload_path(instance, filename):
    """生成文档上传路径"""
    return f'knowledge_bases/{instance.knowledge_base.id}/documents/{filename}'


def document_image_upload_path(instance, filename):
    """生成文档图片上传路径（保留供 migration 引用）"""
    return f'knowledge_bases/{instance.document.knowledge_base.id}/images/{filename}'


class Document(models.Model):
    """
    文档模型，支持多种文档类型
    """
    DOCUMENT_TYPES = [
        ('pdf', 'PDF'),
        ('docx', 'Word文档'),
        ('doc', 'Word文档(旧版)'),
        ('xlsx', 'Excel表格'),
        ('xls', 'Excel表格(旧版)'),
        ('pptx', 'PowerPoint'),
        ('txt', '文本文件'),
        ('md', 'Markdown'),
        ('html', 'HTML'),
        ('url', '网页链接'),
    ]

    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('failed', '处理失败'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_('所属知识库')
    )
    title = models.CharField(_('文档标题'), max_length=200)
    document_type = models.CharField(
        _('文档类型'),
        max_length=10,
        choices=DOCUMENT_TYPES
    )
    file = models.FileField(
        _('文件'),
        upload_to=document_upload_path,
        blank=True,
        null=True
    )
    url = models.URLField(_('网页链接'), blank=True, null=True)
    content = models.TextField(_('文档内容'), blank=True, null=True)

    # 处理状态
    status = models.CharField(
        _('处理状态'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    error_message = models.TextField(_('错误信息'), blank=True, null=True)

    # 元数据
    file_size = models.PositiveIntegerField(_('文件大小(字节)'), null=True, blank=True)
    page_count = models.PositiveIntegerField(_('页数'), null=True, blank=True)
    word_count = models.PositiveIntegerField(_('字数'), null=True, blank=True)

    uploader = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents',
        verbose_name=_('上传人')
    )
    uploaded_at = models.DateTimeField(_('上传时间'), auto_now_add=True)
    processed_at = models.DateTimeField(_('处理时间'), null=True, blank=True)

    class Meta:
        verbose_name = _('文档')
        verbose_name_plural = _('文档')
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.knowledge_base.name} - {self.title}"

    @property
    def file_extension(self):
        """获取文件扩展名"""
        if self.file:
            return os.path.splitext(self.file.name)[1].lower()
        return None


class DocumentChunk(models.Model):
    """
    文档分块模型，存储向量化后的文档片段
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='chunks',
        verbose_name=_('所属文档')
    )
    chunk_index = models.PositiveIntegerField(_('分块索引'))
    content = models.TextField(_('分块内容'))

    # 向量存储相关
    vector_id = models.CharField(_('向量ID'), max_length=100, blank=True, null=True)
    embedding_hash = models.CharField(_('嵌入哈希'), max_length=64, blank=True, null=True)

    # 元数据
    start_index = models.PositiveIntegerField(_('起始位置'), null=True, blank=True)
    end_index = models.PositiveIntegerField(_('结束位置'), null=True, blank=True)
    page_number = models.PositiveIntegerField(_('页码'), null=True, blank=True)

    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('文档分块')
        verbose_name_plural = _('文档分块')
        ordering = ['document', 'chunk_index']
        unique_together = ['document', 'chunk_index']

    def __str__(self):
        return f"{self.document.title} - 分块 {self.chunk_index}"


class QueryLog(models.Model):
    """
    查询日志模型，记录知识库查询历史
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    knowledge_base = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='query_logs',
        verbose_name=_('知识库')
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='knowledge_queries',
        verbose_name=_('查询用户')
    )
    query = models.TextField(_('查询内容'))
    response = models.TextField(_('响应内容'), blank=True, null=True)

    # 检索结果
    retrieved_chunks = models.JSONField(_('检索到的分块'), default=list, blank=True)
    similarity_scores = models.JSONField(_('相似度分数'), default=list, blank=True)

    # 性能指标
    retrieval_time = models.FloatField(_('检索耗时(秒)'), null=True, blank=True)
    generation_time = models.FloatField(_('生成耗时(秒)'), null=True, blank=True)
    total_time = models.FloatField(_('总耗时(秒)'), null=True, blank=True)

    created_at = models.DateTimeField(_('查询时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('查询日志')
        verbose_name_plural = _('查询日志')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.knowledge_base.name} - {self.query[:50]}..."
