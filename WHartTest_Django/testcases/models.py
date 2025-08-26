from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from projects.models import Project # 确保从正确的应用导入Project模型
import os


def testcase_screenshot_path(instance, filename):
    """
    生成测试用例截屏的文件路径
    路径格式: testcase_screenshots/{project_id}/{testcase_id}/{filename}
    """
    return f"testcase_screenshots/{instance.test_case.project.id}/{instance.test_case.id}/{filename}"

class TestCase(models.Model):
    """
    用例模型
    """
    LEVEL_CHOICES = [
        ('P0', _('P0')),
        ('P1', _('P1')),
        ('P2', _('P2')),
        ('P3', _('P3')),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='testcases',
        verbose_name=_('所属项目')
    )
    module = models.ForeignKey(
        'TestCaseModule',
        on_delete=models.PROTECT, # 有用例时不能删除模块
        null=False,  # 不允许为空
        blank=False, # 表单中必填
        related_name='testcases',
        verbose_name=_('所属模块')
    )
    name = models.CharField(_('用例名称'), max_length=255)
    precondition = models.TextField(_('前置描述'), blank=True, null=True)
    level = models.CharField(
        _('用例等级'),
        max_length=2,
        choices=LEVEL_CHOICES,
        default='P2' # 可以设置一个默认等级
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_testcases',
        verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)
    notes = models.TextField(_('备注'), blank=True, null=True)
    screenshot = models.ImageField(
        _('截屏图片'),
        upload_to='testcase_screenshots/',
        blank=True,
        null=True,
        help_text=_('测试用例的截屏图片')
    )

    class Meta:
        verbose_name = _('用例')
        verbose_name_plural = _('用例')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.project.name} - {self.name}"

class TestCaseStep(models.Model):
    """
    用例步骤模型
    """
    test_case = models.ForeignKey(
        TestCase,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name=_('所属用例')
    )
    step_number = models.PositiveIntegerField(_('步骤编号'))
    description = models.TextField(_('步骤描述'))
    expected_result = models.TextField(_('预期结果'))
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_testcase_steps',
        verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('用例步骤')
        verbose_name_plural = _('用例步骤')
        ordering = ['test_case', 'step_number']
        unique_together = ('test_case', 'step_number') #确保同一用例下的步骤编号唯一

    def __str__(self):
        return f"{self.test_case.name} - Step {self.step_number}"


class TestCaseModule(models.Model):
    """
    用例模块模型，支持5级子模块
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='testcase_modules',
        verbose_name=_('所属项目')
    )
    name = models.CharField(_('模块名称'), max_length=100)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name=_('父模块')
    )
    level = models.PositiveSmallIntegerField(_('模块级别'), default=1)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_testcase_modules',
        verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('用例模块')
        verbose_name_plural = _('用例模块')
        ordering = ['project', 'level', 'name']
        unique_together = ('project', 'parent', 'name')  # 确保同一父模块下的子模块名称唯一

    def __str__(self):
        if self.parent:
            return f"{self.parent} > {self.name}"
        return f"{self.project.name} - {self.name}"

    def clean(self):
        """验证模块级别不超过5级"""
        if self.level > 5:
            raise ValidationError(_('模块级别不能超过5级'))

        # 验证父模块属于同一个项目
        if self.parent and self.parent.project_id != self.project_id:
            raise ValidationError(_('父模块必须属于同一个项目'))

        # 验证父模块的级别比当前模块低一级
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 1

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class TestCaseScreenshot(models.Model):
    """
    测试用例截屏模型 - 支持一个用例多张截屏
    """
    test_case = models.ForeignKey(
        TestCase,
        on_delete=models.CASCADE,
        related_name='screenshots',
        verbose_name=_('测试用例')
    )
    screenshot = models.ImageField(
        _('截屏图片'),
        upload_to=testcase_screenshot_path,
        help_text=_('测试用例的截屏图片')
    )
    title = models.CharField(_('图片标题'), max_length=255, blank=True, null=True)
    description = models.TextField(_('图片描述'), blank=True, null=True)
    step_number = models.PositiveIntegerField(_('对应步骤'), blank=True, null=True)
    created_at = models.DateTimeField(_('上传时间'), auto_now_add=True)

    # MCP执行相关信息
    mcp_session_id = models.CharField(_('MCP会话ID'), max_length=255, blank=True, null=True)
    page_url = models.URLField(_('页面URL'), blank=True, null=True)

    # 上传人信息
    uploader = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_screenshots',
        verbose_name=_('上传人')
    )

    class Meta:
        verbose_name = _('测试用例截屏')
        verbose_name_plural = _('测试用例截屏')
        ordering = ['test_case', 'step_number', 'created_at']

    def __str__(self):
        if self.title:
            return f"{self.test_case.name} - {self.title}"
        elif self.step_number:
            return f"{self.test_case.name} - Step {self.step_number}"
        return f"{self.test_case.name} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

    def delete(self, *args, **kwargs):
        """删除模型时同时删除文件"""
        if self.screenshot:
            if os.path.isfile(self.screenshot.path):
                os.remove(self.screenshot.path)
        super().delete(*args, **kwargs)
