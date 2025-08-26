from django.contrib import admin

# Register your models here.
from .models import RemoteMCPConfig

@admin.register(RemoteMCPConfig)
class RemoteMCPConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'is_active', 'owner', 'created_at', 'updated_at')
    list_filter = ('is_active', 'owner')
    search_fields = ('name', 'url')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'url', 'headers', 'is_active', 'owner')
        }),
    )
