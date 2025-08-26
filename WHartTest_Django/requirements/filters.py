import django_filters
from django.db import models
from .models import (
    RequirementDocument, RequirementModule, ReviewReport, 
    ReviewIssue, ModuleReviewResult
)


class RequirementDocumentFilter(django_filters.FilterSet):
    """需求文档过滤器"""
    
    # 基础字段过滤
    project = django_filters.NumberFilter(field_name='project__id')
    status = django_filters.ChoiceFilter(choices=RequirementDocument.STATUS_CHOICES)
    document_type = django_filters.ChoiceFilter(choices=RequirementDocument.DOCUMENT_TYPES)
    uploader = django_filters.UUIDFilter(field_name='uploader__id')
    
    # 时间范围过滤
    uploaded_after = django_filters.DateTimeFilter(field_name='uploaded_at', lookup_expr='gte')
    uploaded_before = django_filters.DateTimeFilter(field_name='uploaded_at', lookup_expr='lte')
    updated_after = django_filters.DateTimeFilter(field_name='updated_at', lookup_expr='gte')
    updated_before = django_filters.DateTimeFilter(field_name='updated_at', lookup_expr='lte')
    
    # 版本过滤
    is_latest = django_filters.BooleanFilter()
    version = django_filters.CharFilter(lookup_expr='icontains')
    
    # 内容过滤
    title = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')
    content = django_filters.CharFilter(lookup_expr='icontains')
    
    # 统计信息过滤
    word_count_min = django_filters.NumberFilter(field_name='word_count', lookup_expr='gte')
    word_count_max = django_filters.NumberFilter(field_name='word_count', lookup_expr='lte')
    page_count_min = django_filters.NumberFilter(field_name='page_count', lookup_expr='gte')
    page_count_max = django_filters.NumberFilter(field_name='page_count', lookup_expr='lte')
    
    # 是否有评审报告
    has_review = django_filters.BooleanFilter(method='filter_has_review')
    
    class Meta:
        model = RequirementDocument
        fields = [
            'project', 'status', 'document_type', 'uploader', 'is_latest',
            'uploaded_after', 'uploaded_before', 'updated_after', 'updated_before',
            'title', 'description', 'content', 'version',
            'word_count_min', 'word_count_max', 'page_count_min', 'page_count_max',
            'has_review'
        ]
    
    def filter_has_review(self, queryset, name, value):
        """过滤是否有评审报告"""
        if value:
            return queryset.filter(review_reports__isnull=False).distinct()
        else:
            return queryset.filter(review_reports__isnull=True)


class RequirementModuleFilter(django_filters.FilterSet):
    """需求模块过滤器"""
    
    # 基础字段过滤
    document = django_filters.UUIDFilter(field_name='document__id')
    parent_module = django_filters.UUIDFilter(field_name='parent_module__id')
    is_auto_generated = django_filters.BooleanFilter()
    
    # 内容过滤
    title = django_filters.CharFilter(lookup_expr='icontains')
    content = django_filters.CharFilter(lookup_expr='icontains')
    
    # 位置过滤
    start_page_min = django_filters.NumberFilter(field_name='start_page', lookup_expr='gte')
    start_page_max = django_filters.NumberFilter(field_name='start_page', lookup_expr='lte')
    end_page_min = django_filters.NumberFilter(field_name='end_page', lookup_expr='gte')
    end_page_max = django_filters.NumberFilter(field_name='end_page', lookup_expr='lte')
    
    # 置信度过滤
    confidence_min = django_filters.NumberFilter(field_name='confidence_score', lookup_expr='gte')
    confidence_max = django_filters.NumberFilter(field_name='confidence_score', lookup_expr='lte')
    
    # 排序过滤
    order_min = django_filters.NumberFilter(field_name='order', lookup_expr='gte')
    order_max = django_filters.NumberFilter(field_name='order', lookup_expr='lte')
    
    # 是否有问题
    has_issues = django_filters.BooleanFilter(method='filter_has_issues')
    
    class Meta:
        model = RequirementModule
        fields = [
            'document', 'parent_module', 'is_auto_generated',
            'title', 'content',
            'start_page_min', 'start_page_max', 'end_page_min', 'end_page_max',
            'confidence_min', 'confidence_max', 'order_min', 'order_max',
            'has_issues'
        ]
    
    def filter_has_issues(self, queryset, name, value):
        """过滤是否有问题"""
        if value:
            return queryset.filter(issues__isnull=False).distinct()
        else:
            return queryset.filter(issues__isnull=True)


class ReviewReportFilter(django_filters.FilterSet):
    """评审报告过滤器"""
    
    # 基础字段过滤
    document = django_filters.UUIDFilter(field_name='document__id')
    status = django_filters.ChoiceFilter(choices=ReviewReport.REVIEW_STATUS_CHOICES)
    overall_rating = django_filters.ChoiceFilter(choices=ReviewReport.OVERALL_RATING_CHOICES)
    reviewer = django_filters.CharFilter(lookup_expr='icontains')
    
    # 时间范围过滤
    review_after = django_filters.DateTimeFilter(field_name='review_date', lookup_expr='gte')
    review_before = django_filters.DateTimeFilter(field_name='review_date', lookup_expr='lte')
    
    # 评分过滤
    completion_score_min = django_filters.NumberFilter(field_name='completion_score', lookup_expr='gte')
    completion_score_max = django_filters.NumberFilter(field_name='completion_score', lookup_expr='lte')
    
    # 问题数量过滤
    total_issues_min = django_filters.NumberFilter(field_name='total_issues', lookup_expr='gte')
    total_issues_max = django_filters.NumberFilter(field_name='total_issues', lookup_expr='lte')
    high_priority_min = django_filters.NumberFilter(field_name='high_priority_issues', lookup_expr='gte')
    high_priority_max = django_filters.NumberFilter(field_name='high_priority_issues', lookup_expr='lte')
    
    # 内容过滤
    summary = django_filters.CharFilter(lookup_expr='icontains')
    recommendations = django_filters.CharFilter(lookup_expr='icontains')
    
    class Meta:
        model = ReviewReport
        fields = [
            'document', 'status', 'overall_rating', 'reviewer',
            'review_after', 'review_before',
            'completion_score_min', 'completion_score_max',
            'total_issues_min', 'total_issues_max',
            'high_priority_min', 'high_priority_max',
            'summary', 'recommendations'
        ]


class ReviewIssueFilter(django_filters.FilterSet):
    """评审问题过滤器"""
    
    # 基础字段过滤
    report = django_filters.UUIDFilter(field_name='report__id')
    module = django_filters.UUIDFilter(field_name='module__id')
    issue_type = django_filters.ChoiceFilter(choices=ReviewIssue.ISSUE_TYPES)
    priority = django_filters.ChoiceFilter(choices=ReviewIssue.PRIORITY_CHOICES)
    is_resolved = django_filters.BooleanFilter()
    
    # 内容过滤
    title = django_filters.CharFilter(lookup_expr='icontains')
    description = django_filters.CharFilter(lookup_expr='icontains')
    suggestion = django_filters.CharFilter(lookup_expr='icontains')
    location = django_filters.CharFilter(lookup_expr='icontains')
    section = django_filters.CharFilter(lookup_expr='icontains')
    
    # 位置过滤
    page_number_min = django_filters.NumberFilter(field_name='page_number', lookup_expr='gte')
    page_number_max = django_filters.NumberFilter(field_name='page_number', lookup_expr='lte')
    
    # 时间过滤
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = ReviewIssue
        fields = [
            'report', 'module', 'issue_type', 'priority', 'is_resolved',
            'title', 'description', 'suggestion', 'location', 'section',
            'page_number_min', 'page_number_max',
            'created_after', 'created_before'
        ]


class ModuleReviewResultFilter(django_filters.FilterSet):
    """模块评审结果过滤器"""
    
    # 基础字段过滤
    report = django_filters.UUIDFilter(field_name='report__id')
    module = django_filters.UUIDFilter(field_name='module__id')
    module_rating = django_filters.ChoiceFilter(choices=ReviewReport.OVERALL_RATING_CHOICES)
    
    # 评分过滤
    issues_count_min = django_filters.NumberFilter(field_name='issues_count', lookup_expr='gte')
    issues_count_max = django_filters.NumberFilter(field_name='issues_count', lookup_expr='lte')
    severity_score_min = django_filters.NumberFilter(field_name='severity_score', lookup_expr='gte')
    severity_score_max = django_filters.NumberFilter(field_name='severity_score', lookup_expr='lte')
    
    # 内容过滤
    analysis_content = django_filters.CharFilter(lookup_expr='icontains')
    strengths = django_filters.CharFilter(lookup_expr='icontains')
    weaknesses = django_filters.CharFilter(lookup_expr='icontains')
    recommendations = django_filters.CharFilter(lookup_expr='icontains')
    
    class Meta:
        model = ModuleReviewResult
        fields = [
            'report', 'module', 'module_rating',
            'issues_count_min', 'issues_count_max',
            'severity_score_min', 'severity_score_max',
            'analysis_content', 'strengths', 'weaknesses', 'recommendations'
        ]
