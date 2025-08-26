from django.db import models
from django.conf import settings
import secrets
from django.utils import timezone

class APIKey(models.Model):
    """
    Represents an API Key that can be used to authenticate requests to the platform.
    Each API Key is associated with a Django User, inheriting their permissions.
    """
    # The actual API key string. Stored as plain text for direct use by external MCP tools.
    # In a highly sensitive production environment, consider storing a hash of the key
    # and only exposing the raw key once upon creation.
    key = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="API Key")
    
    # A human-readable name for the API Key, e.g., "LangGraph Agent Key"
    name = models.CharField(max_length=100, unique=True, verbose_name="Key Name")
    
    # The user associated with this API Key. Requests authenticated with this key
    # will be treated as coming from this user, inheriting their permissions.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name="Associated User"
    )
    
    # Timestamp when the API Key was created
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    
    # Optional expiration date for the API Key
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Expires At",
        help_text="Optional. If set, the key will expire at this date/time."
    )
    
    # Whether the API Key is currently active and can be used
    is_active = models.BooleanField(default=True, verbose_name="Is Active")

    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        ordering = ['-created_at']

    def __str__(self):
        return f"API Key: {self.name} (User: {self.user.username})"

    def save(self, *args, **kwargs):
        if not self.key: # Generate key only if it's new
            self.key = self.generate_key()
        super().save(*args, **kwargs)

    def generate_key(self):
        """Generates a secure, URL-safe API key."""
        return secrets.token_urlsafe(32) # Generates a 32-byte (approx 43-char) URL-safe string

    def is_valid(self):
        """Checks if the API Key is active and not expired."""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True
