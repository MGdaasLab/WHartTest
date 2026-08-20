from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ApiTestCase, ApiTestCaseStep, ApiTestReport, ApiTestReportDetail,
    ApiTestCaseTag, ApiTestCaseGroup,
    ApiInterfaceCase, ApiInterfaceCaseStep,
    ApiInterfaceCaseReport, ApiInterfaceCaseReportDetail
)


@admin.register(ApiTestCaseTag)
class ApiTestCaseTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'project', 'created_by', 'created_at']
    list_filter = ['project', 'created_by']
    search_fields = ['name']
    readonly_fields = ['created_at']


@admin.register(ApiTestCaseGroup)
class ApiTestCaseGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'project', 'created_by', 'created_at']
    list_filter = ['project', 'parent', 'created_by']
    search_fields = ['name']
    readonly_fields = ['created_at']


@admin.register(ApiTestCase)
class ApiTestCaseAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'project', 'group', 'priority',
        'created_by', 'created_at'
    ]
    list_filter = ['project', 'group', 'priority', 'tags']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['tags']


@admin.register(ApiTestCaseStep)
class ApiTestCaseStepAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'testcase', 'order',
        'origin_interface', 'last_sync_time'
    ]
    list_filter = ['testcase', 'origin_interface']
    search_fields = ['name']
    readonly_fields = ['last_sync_time']
    ordering = ['testcase', 'order']


@admin.register(ApiInterfaceCase)
class ApiInterfaceCaseAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'interface', 'project', 'group', 'priority',
        'created_by', 'created_at'
    ]
    list_filter = ['project', 'interface', 'group', 'priority', 'tags']
    search_fields = ['name', 'description', 'interface__name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['tags']


@admin.register(ApiInterfaceCaseStep)
class ApiInterfaceCaseStepAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'interface_case', 'role', 'order',
        'origin_interface', 'last_sync_time'
    ]
    list_filter = ['interface_case', 'role', 'origin_interface']
    search_fields = ['name', 'interface_case__name']
    readonly_fields = ['last_sync_time']
    ordering = ['interface_case', 'order']


@admin.register(ApiTestReport)
class ApiTestReportAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'testcase', 'status', 'success_count',
        'fail_count', 'error_count', 'duration',
        'start_time', 'executed_by'
    ]
    list_filter = ['status', 'testcase', 'executed_by']
    search_fields = ['name', 'testcase__name']
    readonly_fields = [
        'name', 'status', 'success_count', 'fail_count',
        'error_count', 'duration', 'start_time', 'summary',
        'testcase', 'environment', 'executed_by'
    ]
    ordering = ['-start_time']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ApiTestReportDetail)
class ApiTestReportDetailAdmin(admin.ModelAdmin):
    list_display = ['report', 'step', 'success', 'elapsed']
    list_filter = ['report', 'success']
    search_fields = ['report__name', 'step__name']
    readonly_fields = [
        'report', 'step', 'success', 'elapsed',
        'request', 'response', 'validators',
        'extracted_variables', 'attachment'
    ]
    ordering = ['report', 'id']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ApiInterfaceCaseReport)
class ApiInterfaceCaseReportAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'interface_case', 'status', 'success_count',
        'fail_count', 'error_count', 'duration',
        'start_time', 'executed_by'
    ]
    list_filter = ['status', 'interface_case', 'executed_by']
    search_fields = ['name', 'interface_case__name']
    readonly_fields = [
        'name', 'status', 'success_count', 'fail_count',
        'error_count', 'duration', 'start_time', 'summary',
        'interface_case', 'environment', 'executed_by'
    ]
    ordering = ['-start_time']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ApiInterfaceCaseReportDetail)
class ApiInterfaceCaseReportDetailAdmin(admin.ModelAdmin):
    list_display = ['report', 'step', 'success', 'elapsed']
    list_filter = ['report', 'success']
    search_fields = ['report__name', 'step__name']
    readonly_fields = [
        'report', 'step', 'success', 'elapsed',
        'request', 'response', 'validators',
        'extracted_variables', 'attachment'
    ]
    ordering = ['report', 'id']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
