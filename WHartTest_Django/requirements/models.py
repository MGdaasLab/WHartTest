from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from projects.models import Project
import uuid


def requirement_document_upload_path(instance, filename):
    """需求文档上传路径"""
    return f'requirement_documents/{instance.project.id}/{filename}'


def document_image_upload_path(instance, filename):
    """文档图片上传路径"""
    return f'requirement_documents/{instance.document.project.id}/{instance.document.id}/images/{filename}'


class RequirementDocument(models.Model):
    """
    需求文档模型
    """
    DOCUMENT_TYPES = [
        ('pdf', 'PDF'),
        ('doc', 'Word文档'),
        ('docx', 'Word文档'),
        ('txt', '文本文件'),
        ('md', 'Markdown'),
    ]

    STATUS_CHOICES = [
        ('uploaded', '已上传'),
        ('processing', '处理中'),
        ('module_split', '模块拆分中'),
        ('user_reviewing', '用户调整中'),
        ('ready_for_review', '待评审'),
        ('reviewing', '评审中'),
        ('review_completed', '评审完成'),
        ('failed', '处理失败'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='requirement_documents',
        verbose_name=_('所属项目')
    )
    title = models.CharField(_('文档标题'), max_length=200)
    description = models.TextField(_('文档描述'), blank=True, null=True)
    document_type = models.CharField(
        _('文档类型'),
        max_length=10,
        choices=DOCUMENT_TYPES
    )
    file = models.FileField(
        _('文件'),
        upload_to=requirement_document_upload_path,
        blank=True,
        null=True
    )
    content = models.TextField(_('文档内容'), blank=True, null=True)

    # 状态管理
    status = models.CharField(
        _('状态'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='uploaded'
    )

    # 版本管理
    version = models.CharField(_('版本号'), max_length=20, default='1.0')
    is_latest = models.BooleanField(_('是否最新版本'), default=True)
    parent_document = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='versions',
        verbose_name=_('父文档')
    )

    # 元数据
    uploader = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_requirement_documents',
        verbose_name=_('上传人')
    )
    uploaded_at = models.DateTimeField(_('上传时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    # 统计信息
    word_count = models.IntegerField(_('字数'), default=0)
    page_count = models.IntegerField(_('页数'), default=0)

    # 图片信息
    has_images = models.BooleanField(_('包含图片'), default=False)
    image_count = models.IntegerField(_('图片数量'), default=0)

    # 拆分层级
    last_split_level = models.IntegerField(_('最近拆分层级'), default=0)

    class Meta:
        verbose_name = _('需求文档')
        verbose_name_plural = _('需求文档')
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['uploader', 'uploaded_at']),
        ]

    def check_context_limit(self, model_name: str = None) -> dict:
        """检查文档是否超过模型上下文限制"""
        from .context_limits import check_document_context_limit
        return check_document_context_limit(self.content or '', model_name)

    def get_optimal_split_size(self, model_name: str = None) -> int:
        """获取最优拆分大小"""
        from .context_limits import get_optimal_split_size
        return get_optimal_split_size(self.content or '', model_name)

    def __str__(self):
        return f"{self.project.name} - {self.title} v{self.version}"


class DocumentImage(models.Model):
    """
    文档图片模型 - 存储从需求文档中提取的图片
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        RequirementDocument,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_('所属文档')
    )

    # 图片文件
    image_file = models.ImageField(
        _('图片文件'),
        upload_to=document_image_upload_path
    )

    # 图片标识（用于占位符匹配）
    image_id = models.CharField(_('图片ID'), max_length=50, help_text='如 img_001，用于占位符匹配')

    # 排序
    order = models.IntegerField(_('排序'), default=0)

    # 图片元数据
    original_filename = models.CharField(_('原始文件名'), max_length=255, blank=True)
    content_type = models.CharField(_('MIME类型'), max_length=100, default='image/png')
    width = models.IntegerField(_('宽度'), null=True, blank=True)
    height = models.IntegerField(_('高度'), null=True, blank=True)
    file_size = models.IntegerField(_('文件大小'), default=0)

    # 时间戳
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('文档图片')
        verbose_name_plural = _('文档图片')
        ordering = ['document', 'order']
        indexes = [
            models.Index(fields=['document', 'order']),
            models.Index(fields=['document', 'image_id']),
        ]

    def __str__(self):
        return f"{self.document.title} - {self.image_id}"


class RequirementModule(models.Model):
    """
    需求模块模型 - AI拆分或用户手动调整的功能模块
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        RequirementDocument,
        on_delete=models.CASCADE,
        related_name='modules',
        verbose_name=_('所属文档')
    )
    title = models.CharField(_('模块名称'), max_length=200)
    content = models.TextField(_('模块内容'))

    # 位置信息
    start_page = models.IntegerField(_('起始页码'), null=True, blank=True)
    end_page = models.IntegerField(_('结束页码'), null=True, blank=True)
    start_position = models.IntegerField(_('起始位置'), null=True, blank=True)
    end_position = models.IntegerField(_('结束位置'), null=True, blank=True)

    # 排序和分组
    order = models.IntegerField(_('排序'), default=0)
    parent_module = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_modules',
        verbose_name=_('父模块')
    )

    # AI分析信息
    is_auto_generated = models.BooleanField(_('AI自动生成'), default=True)
    confidence_score = models.FloatField(_('置信度'), null=True, blank=True)
    ai_suggested_title = models.CharField(_('AI建议标题'), max_length=200, blank=True)

    # 元数据
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('需求模块')
        verbose_name_plural = _('需求模块')
        ordering = ['document', 'order']
        indexes = [
            models.Index(fields=['document', 'order']),
        ]

    def __str__(self):
        return f"{self.document.title} - {self.title}"


class ReviewReport(models.Model):
    """
    评审报告模型
    """
    REVIEW_STATUS_CHOICES = [
        ('pending', '待开始'),
        ('in_progress', '评审中'),
        ('completed', '已完成'),
        ('failed', '评审失败'),
    ]

    OVERALL_RATING_CHOICES = [
        ('excellent', '优秀'),
        ('good', '良好'),
        ('average', '一般'),
        ('needs_improvement', '需改进'),
        ('poor', '较差'),
    ]

    REVIEW_TYPE_CHOICES = [
        ('direct', '直接评审'),
        ('comprehensive', '全面评审'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        RequirementDocument,
        on_delete=models.CASCADE,
        related_name='review_reports',
        verbose_name=_('评审文档')
    )

    # 评审基本信息
    review_date = models.DateTimeField(_('评审时间'), auto_now_add=True)
    reviewer = models.CharField(_('评审人'), max_length=100, default='AI需求评审助手')
    review_type = models.CharField(
        _('评审类型'),
        max_length=20,
        choices=REVIEW_TYPE_CHOICES,
        default='comprehensive'
    )
    status = models.CharField(
        _('评审状态'),
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
        default='pending'
    )

    # 进度跟踪字段
    progress = models.FloatField(_('评审进度'), default=0, help_text='0-1小数')
    current_step = models.CharField(_('当前步骤'), max_length=50, blank=True, default='')
    completed_steps = models.JSONField(_('已完成步骤'), default=list, blank=True)

    # 评审结果
    overall_rating = models.CharField(
        _('总体评价'),
        max_length=20,
        choices=OVERALL_RATING_CHOICES,
        null=True,
        blank=True
    )
    completion_score = models.IntegerField(_('完整度评分'), default=0, help_text='0-100分')
    clarity_score = models.IntegerField(_('清晰度评分'), default=0, help_text='0-100分')
    consistency_score = models.IntegerField(_('一致性评分'), default=0, help_text='0-100分')
    completeness_score = models.IntegerField(_('完整性评分'), default=0, help_text='0-100分')
    testability_score = models.IntegerField(_('可测性评分'), default=0, help_text='0-100分')
    feasibility_score = models.IntegerField(_('可行性评分'), default=0, help_text='0-100分')
    logic_score = models.IntegerField(_('逻辑分析评分'), default=0, help_text='0-100分')

    # 问题统计
    total_issues = models.IntegerField(_('问题总数'), default=0)
    high_priority_issues = models.IntegerField(_('高优先级问题'), default=0)
    medium_priority_issues = models.IntegerField(_('中优先级问题'), default=0)
    low_priority_issues = models.IntegerField(_('低优先级问题'), default=0)

    # 评审内容
    summary = models.TextField(_('评审摘要'), blank=True)
    recommendations = models.TextField(_('改进建议'), blank=True)
    
    # 专项分析详细结果（存储完整的issues, strengths, recommendations等）
    specialized_analyses = models.JSONField(
        _('专项分析详情'),
        default=dict,
        blank=True,
        help_text='存储完整性、一致性、可测性、可行性、清晰度、逻辑分析6个专项分析的详细结果'
    )

    # 元数据
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('评审报告')
        verbose_name_plural = _('评审报告')
        ordering = ['-review_date']

    def __str__(self):
        return f"{self.document.title} - 评审报告 ({self.review_date.strftime('%Y-%m-%d')})"


class ReviewIssue(models.Model):
    """
    评审问题模型
    """
    ISSUE_TYPES = [
        ('specification', '规范性'),
        ('clarity', '清晰度'),
        ('completeness', '完整性'),
        ('consistency', '一致性'),
        ('feasibility', '可行性'),
        ('logic', '逻辑性'),
    ]

    PRIORITY_CHOICES = [
        ('high', '高'),
        ('medium', '中'),
        ('low', '低'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        ReviewReport,
        on_delete=models.CASCADE,
        related_name='issues',
        verbose_name=_('所属报告')
    )
    module = models.ForeignKey(
        RequirementModule,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='issues',
        verbose_name=_('相关模块')
    )

    # 问题信息
    issue_type = models.CharField(
        _('问题类型'),
        max_length=20,
        choices=ISSUE_TYPES
    )
    priority = models.CharField(
        _('优先级'),
        max_length=10,
        choices=PRIORITY_CHOICES
    )
    title = models.CharField(_('问题标题'), max_length=200)
    description = models.TextField(_('问题描述'))
    suggestion = models.TextField(_('改进建议'), blank=True)

    # 位置信息
    location = models.CharField(_('问题位置'), max_length=200, blank=True)
    page_number = models.IntegerField(_('页码'), null=True, blank=True)
    section = models.CharField(_('章节'), max_length=100, blank=True)

    # 状态管理
    is_resolved = models.BooleanField(_('已解决'), default=False)
    resolution_note = models.TextField(_('解决说明'), blank=True)

    # 元数据
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('评审问题')
        verbose_name_plural = _('评审问题')
        ordering = ['priority', '-created_at']
        indexes = [
            models.Index(fields=['report', 'priority']),
            models.Index(fields=['module', 'issue_type']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_priority_display()})"


class ModuleReviewResult(models.Model):
    """
    模块评审结果模型
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        ReviewReport,
        on_delete=models.CASCADE,
        related_name='module_results',
        verbose_name=_('所属报告')
    )
    module = models.ForeignKey(
        RequirementModule,
        on_delete=models.CASCADE,
        related_name='review_results',
        verbose_name=_('评审模块')
    )

    # 评审结果
    module_rating = models.CharField(
        _('模块评价'),
        max_length=20,
        choices=ReviewReport.OVERALL_RATING_CHOICES,
        null=True,
        blank=True
    )
    issues_count = models.IntegerField(_('问题数量'), default=0)
    severity_score = models.IntegerField(_('严重程度评分'), default=0, help_text='0-100分，分数越高问题越严重')

    # 详细分析
    analysis_content = models.TextField(_('分析内容'), blank=True)
    strengths = models.TextField(_('优点'), blank=True)
    weaknesses = models.TextField(_('不足'), blank=True)
    recommendations = models.TextField(_('改进建议'), blank=True)

    # 元数据
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('模块评审结果')
        verbose_name_plural = _('模块评审结果')
        ordering = ['module__order']
        unique_together = ['report', 'module']

    def __str__(self):
        return f"{self.module.title} - {self.module_rating or '未评级'}"
