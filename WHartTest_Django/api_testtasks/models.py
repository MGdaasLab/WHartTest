from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ApiTestTaskSuite(models.Model):
    PRIORITY_CHOICES = [
        ('P0', 'P0 - Critical'),
        ('P1', 'P1 - High'),
        ('P2', 'P2 - Normal'),
        ('P3', 'P3 - Low'),
    ]

    name = models.CharField(max_length=100, verbose_name='Suite Name')
    description = models.TextField(blank=True, verbose_name='Description')
    priority = models.CharField(
        max_length=2,
        choices=PRIORITY_CHOICES,
        default='P2',
        verbose_name='Priority',
    )
    fail_fast = models.BooleanField(
        default=False,
        verbose_name='Fail Fast',
        help_text='Stop executing subsequent cases when one fails',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='api_test_task_suites',
        verbose_name='Project',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='api_test_task_suites_created',
        verbose_name='Created By',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'API Test Task Suite'
        verbose_name_plural = 'API Test Task Suites'
        ordering = ['-created_at']
        unique_together = ['name', 'project']

    def __str__(self):
        return self.name


class ApiTestTaskCase(models.Model):
    CASE_TYPE_SCENARIO = 'scenario'
    CASE_TYPE_INTERFACE = 'interface'
    CASE_TYPE_CHOICES = [
        (CASE_TYPE_SCENARIO, 'Scenario Case'),
        (CASE_TYPE_INTERFACE, 'Interface Case'),
    ]

    task_suite = models.ForeignKey(
        ApiTestTaskSuite,
        on_delete=models.CASCADE,
        related_name='api_task_cases',
        verbose_name='Task Suite',
    )
    case_type = models.CharField(
        max_length=20,
        choices=CASE_TYPE_CHOICES,
        default=CASE_TYPE_SCENARIO,
        verbose_name='Case Type',
    )
    testcase = models.ForeignKey(
        'api_testcases.ApiTestCase',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='api_task_cases',
        verbose_name='Test Case',
    )
    interface_case = models.ForeignKey(
        'api_testcases.ApiInterfaceCase',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='api_task_cases',
        verbose_name='Interface Case',
    )
    order = models.IntegerField(default=0, verbose_name='Execution Order')

    class Meta:
        verbose_name = 'API Test Task Case'
        verbose_name_plural = 'API Test Task Cases'
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(
                fields=['task_suite', 'testcase'],
                condition=models.Q(testcase__isnull=False),
                name='uniq_api_task_suite_case',
            ),
            models.UniqueConstraint(
                fields=['task_suite', 'interface_case'],
                condition=models.Q(interface_case__isnull=False),
                name='uniq_api_task_suite_iface_case',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        case_type='scenario',
                        testcase__isnull=False,
                        interface_case__isnull=True,
                    )
                    | models.Q(
                        case_type='interface',
                        testcase__isnull=True,
                        interface_case__isnull=False,
                    )
                ),
                name='valid_api_task_case_target',
            ),
        ]

    @property
    def case_object(self):
        if self.case_type == self.CASE_TYPE_INTERFACE:
            return self.interface_case
        return self.testcase

    @property
    def case_id(self):
        case = self.case_object
        return case.id if case else None

    @property
    def case_name(self):
        case = self.case_object
        return case.name if case else ''

    def __str__(self):
        return f"{self.task_suite.name}-{self.case_name}"


class ApiTestTaskExecution(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('canceled', 'Canceled'),
    ]

    task_suite = models.ForeignKey(
        ApiTestTaskSuite,
        on_delete=models.CASCADE,
        related_name='api_executions',
        verbose_name='Task Suite',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Status',
    )
    environment = models.ForeignKey(
        'api_environments.ApiEnvironment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_task_executions',
        verbose_name='Environment',
    )

    start_time = models.DateTimeField(null=True, blank=True, verbose_name='Start Time')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='End Time')

    total_count = models.IntegerField(default=0, verbose_name='Total Cases')
    success_count = models.IntegerField(default=0, verbose_name='Success Count')
    fail_count = models.IntegerField(default=0, verbose_name='Fail Count')
    error_count = models.IntegerField(default=0, verbose_name='Error Count')

    executed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='api_task_executions',
        verbose_name='Executed By',
    )
    task_id = models.CharField(max_length=100, blank=True, verbose_name='Celery Task ID')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'API Test Task Execution'
        verbose_name_plural = 'API Test Task Executions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.task_suite.name}-{self.created_at.strftime('%Y%m%d%H%M%S')}"

    @property
    def project(self):
        """Return the project via the task_suite FK for permission checks."""
        return self.task_suite.project if self.task_suite else None

    @property
    def duration(self):
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0

    @property
    def success_rate(self):
        if self.total_count > 0:
            return round(self.success_count / self.total_count, 2)
        return 0.00

    def start(self):
        self.status = 'running'
        self.start_time = timezone.now()
        self.save()

    def complete(self, success_count, fail_count, error_count):
        self.status = 'completed'
        self.end_time = timezone.now()
        self.success_count = success_count
        self.fail_count = fail_count
        self.error_count = error_count
        self.save()

    def fail(self):
        self.status = 'failed'
        self.end_time = timezone.now()
        self.save()

    def cancel(self):
        self.status = 'canceled'
        self.end_time = timezone.now()
        self.save()


class ApiTestTaskCaseResult(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('success', 'Success'),
        ('failure', 'Failure'),
        ('error', 'Error'),
        ('skipped', 'Skipped'),
    ]

    execution = models.ForeignKey(
        ApiTestTaskExecution,
        on_delete=models.CASCADE,
        related_name='api_case_results',
        verbose_name='Execution',
    )
    case_type = models.CharField(
        max_length=20,
        choices=ApiTestTaskCase.CASE_TYPE_CHOICES,
        default=ApiTestTaskCase.CASE_TYPE_SCENARIO,
        verbose_name='Case Type',
    )
    testcase = models.ForeignKey(
        'api_testcases.ApiTestCase',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='api_task_results',
        verbose_name='Test Case',
    )
    interface_case = models.ForeignKey(
        'api_testcases.ApiInterfaceCase',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='api_task_results',
        verbose_name='Interface Case',
    )
    report = models.ForeignKey(
        'api_testcases.ApiTestReport',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_task_results',
        verbose_name='Test Report',
    )
    interface_report = models.ForeignKey(
        'api_testcases.ApiInterfaceCaseReport',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_task_results',
        verbose_name='Interface Case Report',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Status',
    )

    start_time = models.DateTimeField(null=True, blank=True, verbose_name='Start Time')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='End Time')
    duration = models.FloatField(default=0, verbose_name='Duration (seconds)')
    error_message = models.TextField(blank=True, verbose_name='Error Message')

    class Meta:
        verbose_name = 'API Test Task Case Result'
        verbose_name_plural = 'API Test Task Case Results'
        ordering = ['id']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        case_type='scenario',
                        testcase__isnull=False,
                        interface_case__isnull=True,
                    )
                    | models.Q(
                        case_type='interface',
                        testcase__isnull=True,
                        interface_case__isnull=False,
                    )
                ),
                name='valid_api_task_result_target',
            ),
        ]

    @property
    def case_object(self):
        if self.case_type == ApiTestTaskCase.CASE_TYPE_INTERFACE:
            return self.interface_case
        return self.testcase

    @property
    def report_object(self):
        if self.case_type == ApiTestTaskCase.CASE_TYPE_INTERFACE:
            return self.interface_report
        return self.report

    @property
    def case_name(self):
        case = self.case_object
        return case.name if case else ''

    def __str__(self):
        return f"{self.execution}-{self.case_name}"
