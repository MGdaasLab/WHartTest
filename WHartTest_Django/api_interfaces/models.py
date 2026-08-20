from django.db import models
from django.contrib.auth.models import User


class ApiInterface(models.Model):
    TYPE_HTTP = 'http'
    TYPE_SQL = 'sql'

    INTERFACE_TYPE_CHOICES = [
        (TYPE_HTTP, 'HTTP'),
        (TYPE_SQL, 'SQL'),
    ]

    HTTP_METHOD_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE'),
        ('PATCH', 'PATCH'),
    ]

    SQL_METHOD_CHOICES = [
        ('fetchone', 'Fetch One'),
        ('fetchmany', 'Fetch Many'),
        ('fetchall', 'Fetch All'),
        ('insert', 'Insert'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ]

    # Basic info
    name = models.CharField(max_length=100, verbose_name='Interface Name')
    type = models.CharField(
        max_length=20,
        choices=INTERFACE_TYPE_CHOICES,
        default=TYPE_HTTP,
        verbose_name='Interface Type',
    )

    # HTTP-specific fields
    method = models.CharField(
        max_length=20,
        choices=HTTP_METHOD_CHOICES,
        blank=True,
        null=True,
        verbose_name='HTTP Method',
    )
    url = models.TextField(blank=True, null=True, verbose_name='URL')
    headers = models.JSONField(default=dict, blank=True, verbose_name='Headers')
    params = models.JSONField(default=dict, blank=True, verbose_name='Query Params')
    body = models.JSONField(default=dict, blank=True, verbose_name='Request Body')

    # SQL-specific fields
    sql_method = models.CharField(
        max_length=20,
        choices=SQL_METHOD_CHOICES,
        blank=True,
        null=True,
        verbose_name='SQL Method',
    )
    sql = models.TextField(blank=True, null=True, verbose_name='SQL Statement')
    sql_params = models.JSONField(default=dict, blank=True, verbose_name='SQL Params')
    sql_size = models.IntegerField(
        default=10,
        blank=True,
        verbose_name='Fetch Size',
        help_text='Only used for fetchmany method',
    )

    # httprunner fields
    setup_hooks = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Setup Hooks',
        help_text='["${setup_hook_prepare_kwargs($request)}"]',
    )
    teardown_hooks = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Teardown Hooks',
        help_text='["${teardown_hook_sleep_N_secs($response, 2)}"]',
    )
    variables = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Variables',
        help_text='{"username": "testuser", "password": "123456"}',
    )
    validators = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Validators',
        help_text='[{"eq": ["status_code", 200]}]',
    )
    extract = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Extract Variables',
        help_text='{"token": "body.data.token"}',
    )
    extract_meta = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Extract Metadata',
        help_text='Metadata for extract variable rules',
    )
    file_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name='附件 file_id 列表',
        help_text='统一文件管理中的附件ID列表',
    )

    # Relationships
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='api_interfaces',
        verbose_name='Project',
    )
    module = models.ForeignKey(
        'api_modules.ApiModule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_interfaces',
        verbose_name='Module',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='api_interfaces_created',
        verbose_name='Created By',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'API Interface'
        verbose_name_plural = 'API Interfaces'
        ordering = ['-created_at']
        unique_together = ['name', 'project']

    def __str__(self):
        return f"{self.project.name}-{self.name}"

    def save(self, *args, **kwargs):
        if self.module and self.module.project_id != self.project_id:
            raise ValueError("Module must belong to the same project.")

        # Clean type-specific fields
        if self.type == self.TYPE_HTTP:
            self.sql_method = None
            self.sql = None
            self.sql_params = {}
            self.sql_size = 10
        elif self.type == self.TYPE_SQL:
            self.method = None
            self.url = None
            self.headers = {}
            self.params = {}
            self.body = {}

        super().save(*args, **kwargs)

    def get_interface_data(self):
        """Get interface data dict for runner execution."""
        data = {
            'name': self.name,
            'type': self.type,
            'setup_hooks': self.setup_hooks,
            'teardown_hooks': self.teardown_hooks,
            'variables': self.variables,
            'validators': self.validators,
            'extract': self.extract,
            'extract_meta': self.extract_meta,
            'file_ids': self.file_ids or [],
        }

        if self.type == self.TYPE_HTTP:
            data.update({
                'method': self.method,
                'url': self.url,
                'headers': self.headers,
                'params': self.params,
                'body': self.body,
            })
        elif self.type == self.TYPE_SQL:
            data.update({
                'method': self.sql_method,
                'sql': self.sql,
                'params': self.sql_params,
                'size': self.sql_size,
            })

        return data


class ApiInterfaceResult(models.Model):
    interface = models.ForeignKey(
        ApiInterface,
        on_delete=models.CASCADE,
        related_name='api_results',
        verbose_name='Interface',
    )
    environment_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Environment ID',
    )

    # Execution results
    success = models.BooleanField(verbose_name='Success')
    elapsed = models.FloatField(verbose_name='Elapsed (ms)')
    request_data = models.JSONField(verbose_name='Request Info')
    response_data = models.JSONField(verbose_name='Response Info')
    validation_results = models.JSONField(default=list, verbose_name='Validation Results')
    extracted_variables = models.JSONField(default=dict, verbose_name='Extracted Variables')

    # Execution info
    executed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='api_interface_results',
        verbose_name='Executed By',
    )
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'API Interface Result'
        verbose_name_plural = 'API Interface Results'
        ordering = ['-executed_at']

    def __str__(self):
        return f"{self.interface.name}-{self.executed_at}"

    @property
    def project(self):
        """Return the project via the interface FK for permission checks."""
        return self.interface.project if self.interface else None
