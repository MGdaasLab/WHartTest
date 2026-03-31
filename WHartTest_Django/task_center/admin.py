from django.contrib import admin
from .models import ScheduledTask, TaskExecution


@admin.register(ScheduledTask)
class ScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'module', 'schedule_type', 'status', 'last_run_at', 'created_at']
    list_filter = ['status', 'module', 'schedule_type']
    search_fields = ['name']
    readonly_fields = ['celery_task_id', 'last_run_at', 'created_at', 'updated_at']


@admin.register(TaskExecution)
class TaskExecutionAdmin(admin.ModelAdmin):
    list_display = ['execution_id', 'task', 'trigger_type', 'status', 'started_at', 'finished_at']
    list_filter = ['status', 'trigger_type']
    search_fields = ['execution_id']
    readonly_fields = ['execution_id', 'started_at']
