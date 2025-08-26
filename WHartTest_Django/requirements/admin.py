from django.contrib import admin
from .models import (
    RequirementDocument, RequirementModule, ReviewReport,
    ReviewIssue, ModuleReviewResult
)


@admin.register(RequirementDocument)
class RequirementDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'project', 'status', 'document_type', 'uploader', 'uploaded_at']
    list_filter = ['status', 'document_type', 'is_latest', 'uploaded_at']
    search_fields = ['title', 'description', 'content']
    readonly_fields = ['id', 'uploaded_at', 'updated_at', 'word_count', 'page_count']

    fieldsets = (
        ('基本信息', {
            'fields': ('title', 'description', 'project', 'document_type')
        }),
        ('文档内容', {
            'fields': ('file', 'content')
        }),
        ('状态管理', {
            'fields': ('status', 'version', 'is_latest', 'parent_document')
        }),
        ('元数据', {
            'fields': ('uploader', 'uploaded_at', 'updated_at', 'word_count', 'page_count'),
            'classes': ('collapse',)
        }),
    )


@admin.register(RequirementModule)
class RequirementModuleAdmin(admin.ModelAdmin):
    list_display = ['title', 'document', 'order', 'is_auto_generated', 'confidence_score']
    list_filter = ['is_auto_generated', 'document__project']
    search_fields = ['title', 'content']
    readonly_fields = ['id', 'created_at', 'updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('document', 'title', 'content')
        }),
        ('位置信息', {
            'fields': ('start_page', 'end_page', 'start_position', 'end_position', 'order')
        }),
        ('AI分析', {
            'fields': ('is_auto_generated', 'confidence_score', 'ai_suggested_title'),
            'classes': ('collapse',)
        }),
        ('层级关系', {
            'fields': ('parent_module',),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ['document', 'overall_rating', 'completion_score', 'total_issues', 'status', 'review_date']
    list_filter = ['status', 'overall_rating', 'review_date']
    search_fields = ['document__title', 'summary', 'recommendations']
    readonly_fields = ['id', 'review_date', 'created_at', 'updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('document', 'reviewer', 'status')
        }),
        ('评审结果', {
            'fields': ('overall_rating', 'completion_score')
        }),
        ('问题统计', {
            'fields': ('total_issues', 'high_priority_issues', 'medium_priority_issues', 'low_priority_issues')
        }),
        ('评审内容', {
            'fields': ('summary', 'recommendations')
        }),
        ('元数据', {
            'fields': ('review_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReviewIssue)
class ReviewIssueAdmin(admin.ModelAdmin):
    list_display = ['title', 'issue_type', 'priority', 'module', 'is_resolved']
    list_filter = ['issue_type', 'priority', 'is_resolved', 'report__document__project']
    search_fields = ['title', 'description', 'suggestion']
    readonly_fields = ['id', 'created_at', 'updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('report', 'module', 'title')
        }),
        ('问题分类', {
            'fields': ('issue_type', 'priority')
        }),
        ('问题描述', {
            'fields': ('description', 'suggestion')
        }),
        ('位置信息', {
            'fields': ('location', 'page_number', 'section')
        }),
        ('状态管理', {
            'fields': ('is_resolved', 'resolution_note')
        }),
    )


@admin.register(ModuleReviewResult)
class ModuleReviewResultAdmin(admin.ModelAdmin):
    list_display = ['module', 'module_rating', 'issues_count', 'severity_score']
    list_filter = ['module_rating', 'report__document__project']
    search_fields = ['module__title', 'analysis_content', 'recommendations']
    readonly_fields = ['id', 'created_at', 'updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('report', 'module')
        }),
        ('评审结果', {
            'fields': ('module_rating', 'issues_count', 'severity_score')
        }),
        ('详细分析', {
            'fields': ('analysis_content', 'strengths', 'weaknesses', 'recommendations')
        }),
    )
