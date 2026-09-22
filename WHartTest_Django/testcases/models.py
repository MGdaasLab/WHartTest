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

    TEST_TYPE_CHOICES = [
        ('smoke', _('冒烟测试')),
        ('functional', _('功能测试')),
        ('boundary', _('边界测试')),
        ('exception', _('异常测试')),
        ('permission', _('权限测试')),
        ('security', _('安全测试')),
        ('compatibility', _('兼容性测试')),
    ]

    REVIEW_STATUS_CHOICES = [
        ('pending_review', _('待审核')),
        ('approved', _('通过')),
        ('needs_optimization', _('优化')),
        ('optimization_pending_review', _('优化待审核')),
        ('unavailable', _('不可用')),
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
    review_status = models.CharField(
        _('审核状态'),
        max_length=30,
        choices=REVIEW_STATUS_CHOICES,
        default='pending_review',
        blank=True,
        null=True,
    )
    test_type = models.CharField(
        _('测试类型'),
        max_length=20,
        choices=TEST_TYPE_CHOICES,
        default='functional',
        blank=True,
    )
    ui_test_case = models.ForeignKey(
        'ui_automation.UiTestCase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bound_testcases',
        verbose_name=_('绑定的UI自动化用例')
    )
    execution_mode = models.CharField(
        _('默认执行模式'),
        max_length=20,
        choices=[
            ('hybrid', _('智能双模(脚本优先+AI介入)')),
            ('script_only', _('仅脚本执行')),
            ('ai_only', _('纯AI执行')),
        ],
        default='hybrid',
        blank=True,
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
    expected_result = models.TextField(_('预期结果'), blank=True, default='')
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
    order = models.IntegerField(_('排序'), default=0)

    class Meta:
        verbose_name = _('用例模块')
        verbose_name_plural = _('用例模块')
        ordering = ['project', 'level', 'order', 'id']
        unique_together = ('project', 'parent', 'name')  # 确保同一父模块下的子模块名称唯一

    def __str__(self):
        if self.parent:
            return f"{self.parent} > {self.name}"
        return self.name

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
        old_level = None
        if self.pk:
            try:
                old_level = TestCaseModule.objects.get(pk=self.pk).level
            except TestCaseModule.DoesNotExist:
                pass
        self.clean()
        super().save(*args, **kwargs)
        if old_level is not None and old_level != self.level:
            self.update_descendants_level()

    def get_all_descendant_ids(self):
        """
        获取当前模块及其所有子模块的ID列表（递归）
        """
        ids = [self.id]
        for child in self.children.all():
            ids.extend(child.get_all_descendant_ids())
        return ids

    def get_max_depth(self):
        """
        获取当前模块子树的最大深度（包括当前模块自己，深度最小为1）
        """
        children = self.children.all()
        if not children:
            return 1
        return 1 + max(child.get_max_depth() for child in children)

    def update_descendants_level(self):
        """
        递归更新所有子模块的级别
        """
        for child in self.children.all():
            child.save()


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
    page_url = models.URLField(_('页面URL'), max_length=2000, blank=True, null=True)

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


class TestSuite(models.Model):
    """
    测试套件模型 - 用于批量执行测试用例
    """
    name = models.CharField(_('套件名称'), max_length=255)
    description = models.TextField(_('套件描述'), blank=True, null=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='test_suites',
        verbose_name=_('所属项目')
    )
    testcases = models.ManyToManyField(
        TestCase,
        related_name='test_suites',
        verbose_name=_('测试用例'),
        blank=True
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_test_suites',
        verbose_name=_('创建人')
    )
    # 并发执行配置
    max_concurrent_tasks = models.PositiveSmallIntegerField(
        _('最大并发数'),
        default=1,
        help_text=_('同时执行的测试用例数量，1表示串行执行，建议值2-5')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)
    
    class Meta:
        verbose_name = _('测试套件')
        verbose_name_plural = _('测试套件')
        ordering = ['-created_at']
        unique_together = ('project', 'name')
    
    def __str__(self):
        return f"{self.project.name} - {self.name}"


class TestExecution(models.Model):
    """
    测试执行记录模型 - 记录测试套件的执行情况
    """
    STATUS_CHOICES = [
        ('pending', _('等待中')),
        ('running', _('执行中')),
        ('completed', _('已完成')),
        ('failed', _('失败')),
        ('cancelled', _('已取消')),
    ]
    
    suite = models.ForeignKey(
        TestSuite,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name=_('测试套件')
    )
    status = models.CharField(
        _('执行状态'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    executor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='test_executions',
        verbose_name=_('执行人')
    )
    started_at = models.DateTimeField(_('开始时间'), null=True, blank=True)
    completed_at = models.DateTimeField(_('完成时间'), null=True, blank=True)
    total_count = models.PositiveIntegerField(_('总用例数'), default=0)
    passed_count = models.PositiveIntegerField(_('通过数'), default=0)
    failed_count = models.PositiveIntegerField(_('失败数'), default=0)
    skipped_count = models.PositiveIntegerField(_('跳过数'), default=0)
    error_count = models.PositiveIntegerField(_('错误数'), default=0)
    
    # Celery任务ID,用于追踪和取消任务
    celery_task_id = models.CharField(_('任务ID'), max_length=255, blank=True, null=True)

    # 是否为功能测试用例生成Playwright脚本
    generate_playwright_script = models.BooleanField(
        _('生成脚本'),
        default=False,
        help_text=_('执行功能测试用例时是否自动生成Playwright脚本')
    )

    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)
    
    class Meta:
        verbose_name = _('测试执行记录')
        verbose_name_plural = _('测试执行记录')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.suite.name} - {self.get_status_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @property
    def duration(self):
        """计算执行时长(秒)"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def pass_rate(self):
        """计算通过率"""
        if self.total_count > 0:
            return round((self.passed_count / self.total_count) * 100, 2)
        return 0.0


class TestCaseResult(models.Model):
    """
    测试用例执行结果模型 - 记录单个用例的执行结果
    """
    STATUS_CHOICES = [
        ('pending', _('等待中')),
        ('running', _('执行中')),
        ('pass', _('通过')),
        ('fail', _('失败')),
        ('skip', _('跳过')),
        ('error', _('错误')),
    ]
    
    execution = models.ForeignKey(
        TestExecution,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name=_('测试执行')
    )
    testcase = models.ForeignKey(
        TestCase,
        on_delete=models.CASCADE,
        related_name='execution_results',
        verbose_name=_('测试用例')
    )
    status = models.CharField(
        _('执行状态'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    error_message = models.TextField(_('错误信息'), blank=True, null=True)
    stack_trace = models.TextField(_('堆栈跟踪'), blank=True, null=True)
    
    # 执行时间统计
    started_at = models.DateTimeField(_('开始时间'), null=True, blank=True)
    completed_at = models.DateTimeField(_('完成时间'), null=True, blank=True)
    execution_time = models.FloatField(_('执行耗时(秒)'), null=True, blank=True)
    
    # MCP相关信息
    mcp_session_id = models.CharField(_('MCP会话ID'), max_length=255, blank=True, null=True)
    
    # 截图信息(JSON格式存储截图路径列表)
    screenshots = models.JSONField(_('截图列表'), default=list, blank=True)
    
    # 执行日志
    execution_log = models.TextField(_('执行日志'), blank=True, null=True)
    
    # 混合执行与AI介入相关信息
    execution_mode = models.CharField(_('执行模式'), max_length=20, default='hybrid', blank=True)
    is_ai_intervened = models.BooleanField(_('是否AI介入'), default=False)
    ai_diagnosis = models.JSONField(_('AI诊断报告'), null=True, blank=True)
    self_healing_info = models.JSONField(_('自愈信息'), null=True, blank=True)
    ui_execution_record = models.ForeignKey(
        'ui_automation.UiExecutionRecord',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='testcase_results',
        verbose_name=_('关联的UI执行记录')
    )
    
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)
    
    class Meta:
        verbose_name = _('测试用例执行结果')
        verbose_name_plural = _('测试用例执行结果')
        ordering = ['execution', 'created_at']
        unique_together = ('execution', 'testcase')
    
    def __str__(self):
        return f"{self.testcase.name} - {self.get_status_display()}"
    
    @property
    def duration(self):
        """计算执行时长(秒)"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return self.execution_time
