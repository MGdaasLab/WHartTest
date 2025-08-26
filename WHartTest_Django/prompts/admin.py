from django.contrib import admin
from .models import UserPrompt


@admin.register(UserPrompt)
class UserPromptAdmin(admin.ModelAdmin):
    """用户提示词管理界面"""
    list_display = ['name', 'user', 'is_default', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_default', 'is_active', 'created_at', 'user']
    search_fields = ['name', 'user__username', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('user', 'name', 'description')
        }),
        ('提示词内容', {
            'fields': ('content',)
        }),
        ('设置', {
            'fields': ('is_default', 'is_active')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """管理员可以看到所有提示词，普通用户只能看到自己的"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def save_model(self, request, obj, form, change):
        """保存时自动设置用户"""
        if not change:  # 新建时
            obj.user = request.user
        super().save_model(request, obj, form, change)
