# -*- coding: utf-8 -*-
"""
UI 自动化数据模型

核心层级：
- UiModule: 模块管理
- UiPage: 页面管理
- UiElement: 页面元素
- UiPageSteps: 页面步骤（一组操作的集合）
- UiPageStepsDetailed: 步骤详情（具体的操作步骤）
- UiTestCase: 测试用例
- UiCaseStepsDetailed: 用例步骤（引用 PageSteps）
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from projects.models import Project


class UiModule(models.Model):
    """UI 自动化模块，支持5级子模块"""
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='ui_modules', verbose_name=_('所属项目')
    )
    name = models.CharField(_('模块名称'), max_length=100)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children', verbose_name=_('父模块')
    )
    level = models.PositiveSmallIntegerField(_('模块级别'), default=1)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_ui_modules', verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)
    order = models.IntegerField(_('排序'), default=0)

    class Meta:
        verbose_name = _('UI 模块')
        verbose_name_plural = _('UI 模块')
        ordering = ['project', 'level', 'order', 'id']
        unique_together = ('project', 'parent', 'name')
        db_table = 'ui_module'

    def __str__(self):
        return f"{self.parent} > {self.name}" if self.parent else self.name

    def clean(self):
        if self.level > 5:
            raise ValidationError(_('模块级别不能超过5级'))
        if self.parent and self.parent.project_id != self.project_id:
            raise ValidationError(_('父模块必须属于同一个项目'))
        self.level = (self.parent.level + 1) if self.parent else 1

    def save(self, *args, **kwargs):
        old_level = None
        if self.pk:
            try:
                old_level = UiModule.objects.get(pk=self.pk).level
            except UiModule.DoesNotExist:
                pass
        self.clean()
        super().save(*args, **kwargs)
        if old_level is not None and old_level != self.level:
            self.update_descendants_level()

    def get_all_descendant_ids(self):
        """获取当前模块及其所有子模块的ID列表（递归）"""
        ids = [self.id]
        for child in self.children.all():
            ids.extend(child.get_all_descendant_ids())
        return ids

    def get_max_depth(self):
        """获取当前模块子树的最大深度（包括当前模块自己，深度最小为1）"""
        children = self.children.all()
        if not children:
            return 1
        return 1 + max(child.get_max_depth() for child in children)

    def update_descendants_level(self):
        """递归更新所有子模块的级别"""
        for child in self.children.all():
            child.save()



class UiPage(models.Model):
    """页面管理"""
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='ui_pages', verbose_name=_('所属项目')
    )
    module = models.ForeignKey(
        UiModule, on_delete=models.PROTECT,
        related_name='pages', verbose_name=_('所属模块')
    )
    name = models.CharField(_('页面名称'), max_length=64)
    url = models.TextField(_('页面 URL'), blank=True, null=True)
    description = models.TextField(_('页面描述'), blank=True, null=True)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_ui_pages', verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('UI 页面')
        verbose_name_plural = _('UI 页面')
        ordering = ['-id']
        db_table = 'ui_page'

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class UiElement(models.Model):
    """页面元素定位，支持多定位策略"""
    LOCATOR_TYPE_CHOICES = [
        ('css', _('CSS 选择器')),
        ('xpath', _('XPath')),
        ('text', _('文本')),
        ('role', _('Role')),
        ('label', _('Label')),
        ('placeholder', _('Placeholder')),
        ('test_id', _('Test ID')),
        ('id', _('ID')),
        ('name', _('Name')),
    ]

    page = models.ForeignKey(
        UiPage, on_delete=models.CASCADE,
        related_name='elements', verbose_name=_('所属页面')
    )
    name = models.CharField(_('元素名称'), max_length=64)
    # 主定位
    locator_type = models.CharField(_('定位类型'), max_length=20, choices=LOCATOR_TYPE_CHOICES, default='xpath')
    locator_value = models.TextField(_('定位表达式'))
    locator_index = models.SmallIntegerField(_('元素下标'), null=True, blank=True)
    # 备用定位1
    locator_type_2 = models.CharField(_('定位类型2'), max_length=20, choices=LOCATOR_TYPE_CHOICES, null=True, blank=True)
    locator_value_2 = models.TextField(_('定位表达式2'), null=True, blank=True)
    locator_index_2 = models.SmallIntegerField(_('元素下标2'), null=True, blank=True)
    # 备用定位2
    locator_type_3 = models.CharField(_('定位类型3'), max_length=20, choices=LOCATOR_TYPE_CHOICES, null=True, blank=True)
    locator_value_3 = models.TextField(_('定位表达式3'), null=True, blank=True)
    locator_index_3 = models.SmallIntegerField(_('元素下标3'), null=True, blank=True)
    # 配置
    wait_time = models.SmallIntegerField(_('等待时间（秒）'), default=0)
    is_iframe = models.BooleanField(_('是否在 iframe 中'), default=False)
    iframe_locator = models.TextField(_('iframe 定位'), null=True, blank=True)
    description = models.TextField(_('元素描述'), blank=True, null=True)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_ui_elements', verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('UI 元素')
        verbose_name_plural = _('UI 元素')
        ordering = ['-id']
        db_table = 'ui_element'

    def __str__(self):
        return f"{self.page.name} - {self.name}"


class UiPageSteps(models.Model):
    """页面步骤（一组操作的集合），如"登录操作"、"添加商品"等"""
    STATUS_CHOICES = [(0, _('未执行')), (1, _('执行中')), (2, _('成功')), (3, _('失败'))]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='ui_page_steps', verbose_name=_('所属项目')
    )
    page = models.ForeignKey(
        UiPage, on_delete=models.PROTECT,
        related_name='page_steps', verbose_name=_('所属页面')
    )
    module = models.ForeignKey(
        UiModule, on_delete=models.PROTECT,
        related_name='page_steps', verbose_name=_('所属模块')
    )
    name = models.CharField(_('步骤名称'), max_length=64)
    description = models.TextField(_('步骤描述'), blank=True, null=True)
    run_flow = models.TextField(_('执行顺序描述'), null=True, blank=True)
    flow_data = models.JSONField(_('流程图数据'), default=dict, blank=True)
    file_ids = models.JSONField(_('附件 file_id 列表'), default=list, blank=True)
    status = models.SmallIntegerField(_('状态'), choices=STATUS_CHOICES, default=0)
    result_data = models.JSONField(_('最近执行结果'), null=True, blank=True)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_ui_page_steps', verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('页面步骤')
        verbose_name_plural = _('页面步骤')
        ordering = ['-id']
        db_table = 'ui_page_steps'

    def __str__(self):
        return f"{self.page.name} - {self.name}"


class UiPageStepsDetailed(models.Model):
    """步骤详情（具体的一个操作步骤）"""
    STEP_TYPE_CHOICES = [
        (0, _('元素操作')),
        (1, _('断言操作')),
        (2, _('SQL操作')),
        (3, _('自定义变量')),
        (4, _('条件判断')),
        (5, _('Python代码')),
    ]

    page_step = models.ForeignKey(
        UiPageSteps, on_delete=models.CASCADE,
        related_name='step_details', verbose_name=_('所属页面步骤')
    )
    step_type = models.SmallIntegerField(_('步骤类型'), choices=STEP_TYPE_CHOICES, default=0)
    element = models.ForeignKey(
        UiElement, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='step_details', verbose_name=_('操作元素')
    )
    step_sort = models.IntegerField(_('步骤顺序'), default=0)
    ope_key = models.CharField(_('操作方法'), max_length=1048, null=True, blank=True)
    ope_value = models.JSONField(_('操作参数'), null=True, blank=True)
    sql_execute = models.JSONField(_('SQL执行配置'), null=True, blank=True)
    custom = models.JSONField(_('自定义变量'), null=True, blank=True)
    condition_value = models.JSONField(_('条件配置'), null=True, blank=True)
    func = models.TextField(_('Python代码'), null=True, blank=True)
    description = models.TextField(_('步骤描述'), blank=True, null=True)
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('步骤详情')
        verbose_name_plural = _('步骤详情')
        ordering = ['page_step', 'step_sort']
        db_table = 'ui_page_steps_detailed'

    def __str__(self):
        return f"{self.page_step.name} - Step {self.step_sort}"


class UiTestCase(models.Model):
    """UI 测试用例，由多个页面步骤组成"""
    LEVEL_CHOICES = [('P0', 'P0'), ('P1', 'P1'), ('P2', 'P2'), ('P3', 'P3')]
    STATUS_CHOICES = [(0, _('未执行')), (1, _('执行中')), (2, _('成功')), (3, _('失败'))]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='ui_testcases', verbose_name=_('所属项目')
    )
    module = models.ForeignKey(
        UiModule, on_delete=models.PROTECT,
        related_name='testcases', verbose_name=_('所属模块')
    )
    name = models.CharField(_('用例名称'), max_length=255)
    description = models.TextField(_('用例描述'), blank=True, null=True)
    level = models.CharField(_('用例等级'), max_length=2, choices=LEVEL_CHOICES, default='P2')
    status = models.SmallIntegerField(_('状态'), choices=STATUS_CHOICES, default=0)
    front_custom = models.JSONField(_('前置自定义参数'), default=list, blank=True)
    front_sql = models.JSONField(_('前置SQL'), default=list, blank=True)
    posterior_sql = models.JSONField(_('后置SQL'), default=list, blank=True)
    parametrize = models.JSONField(_('参数化数据'), default=list, blank=True)
    case_flow = models.TextField(_('用例流程'), blank=True, null=True)
    file_ids = models.JSONField(_('附件 file_id 列表'), default=list, blank=True)
    result_data = models.JSONField(_('最近执行结果'), null=True, blank=True)
    error_message = models.TextField(_('错误信息'), null=True, blank=True)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_ui_testcases', verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('UI 测试用例')
        verbose_name_plural = _('UI 测试用例')
        ordering = ['-created_at']
        db_table = 'ui_test_case'

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class UiCaseStepsDetailed(models.Model):
    """用例步骤详情（引用页面步骤）"""
    STATUS_CHOICES = [(0, _('未执行')), (1, _('执行中')), (2, _('成功')), (3, _('失败'))]

    test_case = models.ForeignKey(
        UiTestCase, on_delete=models.CASCADE,
        related_name='case_steps', verbose_name=_('所属用例')
    )
    page_step = models.ForeignKey(
        UiPageSteps, on_delete=models.PROTECT,
        related_name='case_usages', verbose_name=_('引用页面步骤')
    )
    case_sort = models.IntegerField(_('步骤顺序'), default=0)
    case_data = models.JSONField(_('步骤数据覆盖'), null=True, blank=True)
    case_cache_data = models.JSONField(_('缓存数据'), null=True, blank=True)
    case_cache_ass = models.JSONField(_('断言缓存'), null=True, blank=True)
    switch_step_open_url = models.BooleanField(_('切换URL'), default=False)
    error_retry = models.SmallIntegerField(_('失败重试次数'), default=0)
    status = models.SmallIntegerField(_('状态'), choices=STATUS_CHOICES, default=0)
    error_message = models.TextField(_('错误信息'), null=True, blank=True)
    result_data = models.JSONField(_('执行结果'), null=True, blank=True)
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('用例步骤')
        verbose_name_plural = _('用例步骤')
        ordering = ['test_case', 'case_sort']
        db_table = 'ui_case_steps_detailed'

    def __str__(self):
        return f"{self.test_case.name} - {self.page_step.name}"


class UiBatchExecutionRecord(models.Model):
    """批量执行记录"""
    STATUS_CHOICES = [
        (0, _('待执行')),
        (1, _('执行中')),
        (2, _('全部成功')),
        (3, _('部分失败')),
        (4, _('全部失败')),
    ]
    TRIGGER_TYPE_CHOICES = [('manual', _('手动执行')), ('scheduled', _('定时执行')), ('api', _('API 触发'))]

    name = models.CharField(_('批次名称'), max_length=255)
    total_cases = models.IntegerField(_('用例总数'), default=0)
    passed_cases = models.IntegerField(_('成功数'), default=0)
    failed_cases = models.IntegerField(_('失败数'), default=0)
    status = models.SmallIntegerField(_('状态'), choices=STATUS_CHOICES, default=0)
    trigger_type = models.CharField(_('触发类型'), max_length=20, choices=TRIGGER_TYPE_CHOICES, default='manual')
    executor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='ui_batch_executions', verbose_name=_('执行人')
    )
    start_time = models.DateTimeField(_('开始时间'), null=True, blank=True)
    end_time = models.DateTimeField(_('结束时间'), null=True, blank=True)
    duration = models.FloatField(_('总时长（秒）'), null=True, blank=True)
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('批量执行记录')
        verbose_name_plural = _('批量执行记录')
        ordering = ['-created_at']
        db_table = 'ui_batch_execution_record'

    def __str__(self):
        return f"{self.name} ({self.passed_cases}/{self.total_cases})"

    def update_statistics(self):
        """更新统计信息"""
        records = self.execution_records.all()
        self.passed_cases = records.filter(status=2).count()
        self.failed_cases = records.filter(status=3).count()
        completed = self.passed_cases + self.failed_cases
        if completed >= self.total_cases:
            if self.failed_cases == 0:
                self.status = 2  # 全部成功
            elif self.passed_cases == 0:
                self.status = 4  # 全部失败
            else:
                self.status = 3  # 部分失败
            from django.utils import timezone
            self.end_time = timezone.now()
            if self.start_time:
                self.duration = (self.end_time - self.start_time).total_seconds()
        self.save()


class UiExecutionRecord(models.Model):
    """UI 测试执行记录"""
    STATUS_CHOICES = [(0, _('未执行')), (1, _('执行中')), (2, _('成功')), (3, _('失败')), (4, _('取消'))]
    TRIGGER_TYPE_CHOICES = [('manual', _('手动执行')), ('scheduled', _('定时执行')), ('api', _('API 触发'))]

    batch = models.ForeignKey(
        UiBatchExecutionRecord, on_delete=models.CASCADE,
        null=True, blank=True, related_name='execution_records', verbose_name=_('所属批次')
    )
    test_case = models.ForeignKey(
        UiTestCase, on_delete=models.CASCADE,
        related_name='execution_records', verbose_name=_('所属用例')
    )
    executor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='ui_executions', verbose_name=_('执行人')
    )
    status = models.SmallIntegerField(_('执行状态'), choices=STATUS_CHOICES, default=0)
    trigger_type = models.CharField(_('触发类型'), max_length=20, choices=TRIGGER_TYPE_CHOICES, default='manual')
    environment = models.JSONField(_('执行环境'), null=True, blank=True)
    step_results = models.JSONField(_('步骤执行详情'), default=list, blank=True)
    screenshots = models.JSONField(_('截图'), default=list, blank=True)
    video_path = models.CharField(_('视频路径'), max_length=500, null=True, blank=True)
    trace_path = models.CharField(_('Trace 文件路径'), max_length=500, null=True, blank=True)
    trace_data = models.JSONField(_('Trace 解析数据'), null=True, blank=True)
    log = models.TextField(_('执行日志'), blank=True, null=True)
    error_message = models.TextField(_('错误信息'), null=True, blank=True)
    start_time = models.DateTimeField(_('开始时间'), null=True, blank=True)
    end_time = models.DateTimeField(_('结束时间'), null=True, blank=True)
    duration = models.FloatField(_('执行时长（秒）'), null=True, blank=True)
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)

    class Meta:
        verbose_name = _('UI 执行记录')
        verbose_name_plural = _('UI 执行记录')
        ordering = ['-created_at']
        db_table = 'ui_execution_record'


class UiPublicData(models.Model):
    """公共数据（跨用例共享变量）"""
    TYPE_CHOICES = [(0, _('字符串')), (1, _('整数')), (2, _('列表')), (3, _('字典'))]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='ui_public_data', verbose_name=_('所属项目')
    )
    type = models.SmallIntegerField(_('类型'), choices=TYPE_CHOICES, default=0)
    key = models.CharField(_('变量名'), max_length=100)
    value = models.TextField(_('变量值'))
    description = models.TextField(_('描述'), blank=True, null=True)
    is_enabled = models.BooleanField(_('是否启用'), default=True)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_ui_public_data', verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('公共数据')
        verbose_name_plural = _('公共数据')
        ordering = ['project', 'key']
        unique_together = ('project', 'key')
        db_table = 'ui_public_data'

    def __str__(self):
        return f"{self.project.name} - {self.key}"


class UiEnvironmentConfig(models.Model):
    """环境配置"""
    BROWSER_CHOICES = [('chromium', 'Chromium'), ('firefox', 'Firefox'), ('webkit', 'WebKit')]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='ui_env_configs', verbose_name=_('所属项目')
    )
    name = models.CharField(_('环境名称'), max_length=64)
    base_url = models.URLField(_('基础 URL'), blank=True, null=True)
    browser = models.CharField(_('浏览器'), max_length=20, choices=BROWSER_CHOICES, default='chromium')
    headless = models.BooleanField(_('无头模式'), default=True)
    viewport_width = models.IntegerField(_('视口宽度'), default=1280)
    viewport_height = models.IntegerField(_('视口高度'), default=720)
    timeout = models.IntegerField(_('默认超时（毫秒）'), default=30000)
    db_c_status = models.BooleanField(_('数据库新增状态'), default=False)
    db_rud_status = models.BooleanField(_('数据库查改删状态'), default=False)
    DB_TYPE_CHOICES = [('mysql', 'MySQL')]
    db_type = models.CharField(_('数据库类型'), max_length=20, choices=DB_TYPE_CHOICES, default='mysql')
    mysql_config = models.JSONField(_('MySQL配置'), null=True, blank=True)
    extra_config = models.JSONField(_('额外配置'), null=True, blank=True)
    is_default = models.BooleanField(_('是否默认'), default=False)
    creator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_ui_env_configs', verbose_name=_('创建人')
    )
    created_at = models.DateTimeField(_('创建时间'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新时间'), auto_now=True)

    class Meta:
        verbose_name = _('环境配置')
        verbose_name_plural = _('环境配置')
        ordering = ['project', 'name']
        unique_together = ('project', 'name')
        db_table = 'ui_environment_config'

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    def save(self, *args, **kwargs):
        if self.is_default:
            UiEnvironmentConfig.objects.filter(project=self.project, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
