import logging

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class ApiDatabaseConfig(models.Model):
    """Database configuration model for API testing."""

    DB_TYPE_CHOICES = (
        ('mysql', _('MySQL')),
        ('postgresql', _('PostgreSQL')),
        ('sqlite', _('SQLite')),
        ('oracle', _('Oracle')),
        ('sqlserver', _('SQL Server')),
    )

    name = models.CharField(_("Name"), max_length=100)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='api_database_configs',
        verbose_name=_("Project"),
    )

    db_type = models.CharField(
        _("Database Type"), max_length=20, choices=DB_TYPE_CHOICES, default='mysql'
    )

    host = models.CharField(_("Host"), max_length=255)
    port = models.IntegerField(_("Port"), default=3306)
    username = models.CharField(_("Username"), max_length=100)
    password = models.CharField(_("Password"), max_length=255)
    database = models.CharField(_("Database Name"), max_length=100)

    charset = models.CharField(_("Charset"), max_length=50, default="utf8mb4")
    is_active = models.BooleanField(_("Active"), default=True)

    description = models.TextField(_("Description"), blank=True, null=True)
    psm = models.CharField(_("PSM"), max_length=255, blank=True, null=True)
    verify_ssl = models.BooleanField(_("Verify SSL"), default=False)
    connection_params = models.JSONField(_("Connection Params"), default=dict, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='api_created_database_configs',
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("API Database Config")
        verbose_name_plural = _("API Database Configs")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.project.name})"

    @property
    def connection_string(self):
        """Build a SQLAlchemy-style connection string."""
        if self.db_type == 'mysql':
            return (
                f"mysql+pymysql://{self.username}:{self.password}"
                f"@{self.host}:{self.port}/{self.database}?charset={self.charset}"
            )
        elif self.db_type == 'postgresql':
            return (
                f"postgresql://{self.username}:{self.password}"
                f"@{self.host}:{self.port}/{self.database}"
            )
        elif self.db_type == 'sqlite':
            return f"sqlite:///{self.database}"
        elif self.db_type == 'oracle':
            return (
                f"oracle://{self.username}:{self.password}"
                f"@{self.host}:{self.port}/{self.database}"
            )
        elif self.db_type == 'sqlserver':
            return (
                f"mssql+pymssql://{self.username}:{self.password}"
                f"@{self.host}:{self.port}/{self.database}"
            )
        else:
            return (
                f"mysql+pymysql://{self.username}:{self.password}"
                f"@{self.host}:{self.port}/{self.database}?charset={self.charset}"
            )

    @classmethod
    def get_by_key(cls, db_key, project_id=None):
        """Look up an active database config by name, scoped to project."""
        if not db_key:
            return None
        try:
            qs = cls.objects.filter(name=db_key, is_active=True)
            if project_id:
                qs = qs.filter(project_id=project_id)
            return qs.first()
        except Exception as e:
            logger.error(f"Failed to get database config: {e}")
            return None
