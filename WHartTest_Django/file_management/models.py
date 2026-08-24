import os
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


def managed_file_upload_path(instance, filename):
    ext = os.path.splitext(filename or '')[1]
    project_id = instance.project_id or 'unassigned'
    return f'file_management/projects/{project_id}/{timezone.now():%Y/%m/%d}/{uuid.uuid4().hex}{ext}'


class FileAsset(models.Model):
    STATUS_AVAILABLE = 'available'
    STATUS_PROCESSING = 'processing'
    STATUS_BROKEN = 'broken'
    STATUS_DELETED = 'deleted'
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, '可用'),
        (STATUS_PROCESSING, '处理中'),
        (STATUS_BROKEN, '损坏'),
        (STATUS_DELETED, '已删除'),
    ]

    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='managed_files')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='managed_files')
    file = models.FileField(upload_to=managed_file_upload_path, max_length=512)
    original_name = models.CharField(max_length=255)
    extension = models.CharField(max_length=32, blank=True)
    mime_type = models.CharField(max_length=255, blank=True)
    size = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'is_deleted', 'status']),
            models.Index(fields=['project', 'original_name']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.original_name

    def delete(self, *args, **kwargs):
        storage = self.file.storage if self.file else None
        storage_name = self.file.name if self.file else ''
        super().delete(*args, **kwargs)
        if storage and storage_name:
            try:
                if storage.exists(storage_name):
                    storage.delete(storage_name)
            except Exception:
                pass

    @property
    def storage_path(self):
        return self.file.name if self.file else ''

    @property
    def filename(self):
        return self.original_name


class FileReference(models.Model):
    REF_API_INTERFACE = 'api_interface'
    REF_API_TESTCASE = 'api_testcase'
    REF_API_INTERFACE_CASE = 'api_interface_case'
    REF_UI_TESTCASE = 'ui_testcase'
    REF_UI_PAGE_STEPS = 'ui_page_steps'
    REF_LLM_CHAT = 'llm_chat'
    REF_CHOICES = [
        (REF_API_INTERFACE, '接口'),
        (REF_API_TESTCASE, '测试用例'),
        (REF_API_INTERFACE_CASE, '接口用例'),
        (REF_UI_TESTCASE, 'UI用例'),
        (REF_UI_PAGE_STEPS, 'UI页面步骤'),
        (REF_LLM_CHAT, 'LLM对话'),
    ]

    file = models.ForeignKey(FileAsset, on_delete=models.CASCADE, related_name='references')
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='file_references')
    ref_type = models.CharField(max_length=50, choices=REF_CHOICES)
    ref_id = models.CharField(max_length=128)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='file_references')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('file', 'ref_type', 'ref_id')
        indexes = [
            models.Index(fields=['project', 'ref_type', 'ref_id']),
            models.Index(fields=['file', 'ref_type']),
        ]

    def __str__(self):
        return f'{self.ref_type}:{self.ref_id} -> {self.file_id}'



class FileManagementSetting(models.Model):
    """Project-level file cleanup policy.

    Defaults are intentionally conservative: no automatic deletion unless the
    project admin explicitly enables it from the File Management page.
    """
    project = models.OneToOneField('projects.Project', on_delete=models.CASCADE, related_name='file_management_setting')
    auto_delete_on_unbind = models.BooleanField(default=False)
    auto_delete_zero_refs = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'file_management_setting'
        verbose_name = '文件管理设置'
        verbose_name_plural = '文件管理设置'

    def __str__(self):
        return f'FileManagementSetting(project={self.project_id})'
