from django.contrib import admin
from .models import APIKey

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'key_preview', 'created_at', 'expires_at', 'is_active')
    list_filter = ('is_active', 'created_at', 'expires_at')
    search_fields = ('name', 'key', 'user__username')
    raw_id_fields = ('user',) # Use a raw ID field for user selection for better performance with many users
    readonly_fields = ('key', 'created_at') # Make key and created_at read-only after creation

    fieldsets = (
        (None, {
            'fields': ('name', 'user', 'is_active')
        }),
        ('Key Details', {
            'fields': ('key', 'created_at', 'expires_at'),
            'classes': ('collapse',) # Collapse this section by default
        }),
    )

    def key_preview(self, obj):
        """Displays a truncated version of the key for readability."""
        return f"{obj.key[:5]}...{obj.key[-5:]}"
    key_preview.short_description = "API Key (Preview)"

    # Override save_model to ensure key is generated if not present
    def save_model(self, request, obj, form, change):
        if not obj.pk: # Only generate key for new objects
            obj.key = obj.generate_key()
        super().save_model(request, obj, form, change)
