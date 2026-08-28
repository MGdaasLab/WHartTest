from django.contrib import admin
from .models import (
    ApiTestTaskSuite,
    ApiTestTaskCase,
    ApiTestTaskExecution,
    ApiTestTaskCaseResult,
)


@admin.register(ApiTestTaskSuite)
class ApiTestTaskSuiteAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'project', 'priority', 'fail_fast', 'created_by', 'created_at']
    list_filter = ['project', 'priority', 'fail_fast']
    search_fields = ['name', 'description']


@admin.register(ApiTestTaskCase)
class ApiTestTaskCaseAdmin(admin.ModelAdmin):
    list_display = ['id', 'task_suite', 'case_type', 'testcase', 'interface_case', 'order']
    list_filter = ['task_suite', 'case_type']


@admin.register(ApiTestTaskExecution)
class ApiTestTaskExecutionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'task_suite', 'status', 'environment',
        'start_time', 'end_time', 'total_count', 'success_count',
        'fail_count', 'error_count', 'executed_by',
    ]
    list_filter = ['status']
    search_fields = ['task_suite__name']


@admin.register(ApiTestTaskCaseResult)
class ApiTestTaskCaseResultAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'execution', 'case_type', 'testcase', 'interface_case',
        'status', 'start_time', 'end_time', 'duration'
    ]
    list_filter = ['status', 'case_type']
