from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    RequirementDocument, RequirementModule, ReviewReport, 
    ReviewIssue, ModuleReviewResult
)


class RequirementDocumentSerializer(serializers.ModelSerializer):
    """需求文档序列化器"""
    uploader_name = serializers.CharField(source='uploader.username', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    modules_count = serializers.SerializerMethodField()
    
    class Meta:
        model = RequirementDocument
        fields = [
            'id', 'title', 'description', 'document_type', 'file', 'content',
            'status', 'version', 'is_latest', 'parent_document',
            'uploader', 'uploader_name', 'project', 'project_name',
            'uploaded_at', 'updated_at', 'word_count', 'page_count',
            'modules_count'
        ]
        read_only_fields = ['id', 'uploader', 'uploaded_at', 'updated_at']
    
    def get_modules_count(self, obj):
        """获取模块数量"""
        return obj.modules.count()


class RequirementDocumentUploadSerializer(serializers.ModelSerializer):
    """需求文档上传序列化器"""
    
    class Meta:
        model = RequirementDocument
        fields = [
            'id', 'title', 'description', 'document_type', 'file', 'content', 'project',
            'status', 'word_count', 'uploaded_at'
        ]
        read_only_fields = ['id', 'status', 'word_count', 'uploaded_at']
    
    def validate(self, data):
        """验证文档内容"""
        if not data.get('file') and not data.get('content'):
            raise serializers.ValidationError("必须提供文件或文档内容")
        return data


class RequirementModuleSerializer(serializers.ModelSerializer):
    """需求模块序列化器"""
    issues_count = serializers.SerializerMethodField()
    
    class Meta:
        model = RequirementModule
        fields = [
            'id', 'title', 'content', 'start_page', 'end_page',
            'start_position', 'end_position', 'order', 'parent_module',
            'is_auto_generated', 'confidence_score', 'ai_suggested_title',
            'created_at', 'updated_at', 'issues_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_issues_count(self, obj):
        """获取问题数量"""
        return obj.issues.count()


class ReviewIssueSerializer(serializers.ModelSerializer):
    """评审问题序列化器"""
    module_name = serializers.CharField(source='module.title', read_only=True)
    issue_type_display = serializers.CharField(source='get_issue_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    
    class Meta:
        model = ReviewIssue
        fields = [
            'id', 'issue_type', 'issue_type_display', 'priority', 'priority_display',
            'title', 'description', 'suggestion', 'location', 'page_number', 'section',
            'module', 'module_name', 'is_resolved', 'resolution_note',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ModuleReviewResultSerializer(serializers.ModelSerializer):
    """模块评审结果序列化器"""
    module_name = serializers.CharField(source='module.title', read_only=True)
    module_rating_display = serializers.CharField(source='get_module_rating_display', read_only=True)
    
    class Meta:
        model = ModuleReviewResult
        fields = [
            'id', 'module', 'module_name', 'module_rating', 'module_rating_display',
            'issues_count', 'severity_score', 'analysis_content',
            'strengths', 'weaknesses', 'recommendations',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ReviewReportSerializer(serializers.ModelSerializer):
    """评审报告序列化器"""
    document_title = serializers.CharField(source='document.title', read_only=True)
    overall_rating_display = serializers.CharField(source='get_overall_rating_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    issues = ReviewIssueSerializer(many=True, read_only=True)
    module_results = ModuleReviewResultSerializer(many=True, read_only=True)
    
    class Meta:
        model = ReviewReport
        fields = [
            'id', 'document', 'document_title', 'review_date', 'reviewer',
            'status', 'status_display', 'overall_rating', 'overall_rating_display',
            'completion_score', 'total_issues', 'high_priority_issues',
            'medium_priority_issues', 'low_priority_issues',
            'summary', 'recommendations', 'issues', 'module_results',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'review_date', 'created_at', 'updated_at']


class RequirementDocumentDetailSerializer(RequirementDocumentSerializer):
    """需求文档详情序列化器"""
    modules = RequirementModuleSerializer(many=True, read_only=True)
    review_reports = ReviewReportSerializer(many=True, read_only=True)
    latest_review = serializers.SerializerMethodField()
    
    class Meta(RequirementDocumentSerializer.Meta):
        fields = RequirementDocumentSerializer.Meta.fields + [
            'modules', 'review_reports', 'latest_review'
        ]
    
    def get_latest_review(self, obj):
        """获取最新评审报告"""
        latest_review = obj.review_reports.order_by('-review_date').first()
        if latest_review:
            return ReviewReportSerializer(latest_review).data
        return None


# 用于模块调整的序列化器
class ModuleAdjustmentSerializer(serializers.Serializer):
    """模块调整序列化器"""
    modules = RequirementModuleSerializer(many=True)

    def validate_modules(self, value):
        """验证模块数据"""
        if not value:
            raise serializers.ValidationError("至少需要一个模块")

        # 验证排序唯一性
        orders = [module.get('order', 0) for module in value]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError("模块排序不能重复")

        return value


class ModuleOperationSerializer(serializers.Serializer):
    """模块操作序列化器"""
    operation = serializers.ChoiceField(choices=[
        ('merge', '合并模块'),
        ('split', '拆分模块'),
        ('reorder', '重新排序'),
        ('rename', '重命名'),
        ('delete', '删除'),
        ('create', '创建新模块')
    ])

    # 操作目标
    target_modules = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="目标模块ID列表"
    )

    # 新模块数据
    new_module_data = serializers.DictField(required=False)

    # 合并操作的参数
    merge_title = serializers.CharField(max_length=200, required=False)
    merge_order = serializers.IntegerField(required=False)

    # 拆分操作的参数
    split_points = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="拆分位置列表（字符位置）"
    )
    split_titles = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        help_text="拆分后的模块标题列表"
    )

    # 重排序参数
    new_orders = serializers.DictField(
        child=serializers.IntegerField(),
        required=False,
        help_text="模块ID到新排序的映射"
    )

    def validate(self, data):
        """验证操作参数"""
        operation = data.get('operation')

        if operation == 'merge':
            if not data.get('target_modules') or len(data.get('target_modules', [])) < 2:
                raise serializers.ValidationError("合并操作至少需要2个模块")
            if not data.get('merge_title'):
                raise serializers.ValidationError("合并操作需要提供新模块标题")

        elif operation == 'split':
            if not data.get('target_modules') or len(data.get('target_modules', [])) != 1:
                raise serializers.ValidationError("拆分操作只能针对一个模块")
            if not data.get('split_points') or not data.get('split_titles'):
                raise serializers.ValidationError("拆分操作需要提供拆分点和标题")

        elif operation == 'reorder':
            if not data.get('new_orders'):
                raise serializers.ValidationError("重排序操作需要提供新的排序映射")

        elif operation in ['rename', 'delete']:
            if not data.get('target_modules') or len(data.get('target_modules', [])) != 1:
                raise serializers.ValidationError(f"{operation}操作只能针对一个模块")

        elif operation == 'create':
            if not data.get('new_module_data'):
                raise serializers.ValidationError("创建操作需要提供模块数据")

        return data


class ModuleBatchUpdateSerializer(serializers.Serializer):
    """模块批量更新序列化器"""
    operations = ModuleOperationSerializer(many=True)

    def validate_operations(self, value):
        """验证操作列表"""
        if not value:
            raise serializers.ValidationError("至少需要一个操作")

        # 检查操作冲突
        target_modules = set()
        for op in value:
            if op.get('target_modules'):
                for module_id in op['target_modules']:
                    if module_id in target_modules:
                        raise serializers.ValidationError(f"模块 {module_id} 被多个操作引用")
                    target_modules.add(module_id)

        return value


# 用于评审分析的序列化器
class ReviewAnalysisRequestSerializer(serializers.Serializer):
    """评审分析请求序列化器"""
    analysis_type = serializers.ChoiceField(
        choices=[
            ('comprehensive', '全面评审'),
            ('quick', '快速评审'),
            ('specification_only', '仅规范性检查'),
            ('clarity_only', '仅清晰度检查'),
        ],
        default='comprehensive'
    )
    parallel_processing = serializers.BooleanField(default=True)
    priority_modules = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="优先分析的模块ID列表"
    )
    custom_requirements = serializers.CharField(
        max_length=1000,
        required=False,
        help_text="自定义评审要求"
    )


class ReviewProgressSerializer(serializers.Serializer):
    """评审进度序列化器"""
    task_id = serializers.UUIDField()
    overall_progress = serializers.IntegerField(min_value=0, max_value=100)
    status = serializers.ChoiceField(choices=[
        ('pending', '等待中'),
        ('running', '运行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ])
    current_step = serializers.CharField(max_length=200)
    estimated_remaining_time = serializers.CharField(max_length=50, required=False)
    modules_progress = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )
