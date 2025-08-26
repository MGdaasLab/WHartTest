from django.contrib import admin
from .models import TestCase, TestCaseStep, TestCaseModule

class TestCaseStepInline(admin.TabularInline):
    """
    用例步骤的内联显示，用于在 TestCase Admin 页面直接编辑步骤。
    """
    model = TestCaseStep
    extra = 1 # 默认显示一个空的步骤表单
    fields = ('step_number', 'description', 'expected_result', 'creator')
    # readonly_fields = ('creator',) # 如果希望创建者字段在内联中只读

@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    """
    TestCase 模型的 Admin 配置。
    """
    list_display = ('name', 'project', 'level', 'creator', 'created_at', 'updated_at')
    list_filter = ('project', 'level', 'creator', 'created_at')
    search_fields = ('name', 'project__name', 'precondition')
    inlines = [TestCaseStepInline] # 嵌入 TestCaseStep 的编辑
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('project', 'name', 'level', 'precondition')
        }),
        ('创建信息', {
            'fields': ('creator', 'created_at', 'updated_at'),
            'classes': ('collapse',), # 默认折叠此字段集
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        在 Admin 中保存 TestCase 时，如果创建者为空，则设置为当前用户。
        """
        if not obj.creator_id:
            obj.creator = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """
        在 Admin 中保存内联的 TestCaseStep 时，如果创建者为空，则设置为当前用户。
        """
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, TestCaseStep) and not instance.creator_id:
                instance.creator = request.user
            instance.save()
        formset.save_m2m()


@admin.register(TestCaseStep)
class TestCaseStepAdmin(admin.ModelAdmin):
    """
    TestCaseStep 模型的 Admin 配置 (主要用于独立查看，通常通过 TestCase Admin 内联编辑)。
    """
    list_display = ('test_case', 'step_number', 'description_short', 'creator', 'created_at')
    list_filter = ('test_case__project', 'test_case', 'creator', 'created_at')
    search_fields = ('description', 'expected_result', 'test_case__name')
    readonly_fields = ('created_at', 'updated_at')

    def description_short(self, obj):
        """
        返回步骤描述的缩略版。
        """
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = '步骤描述'


class TestCaseModuleInline(admin.TabularInline):
    """
    子模块的内联显示，用于在父模块的Admin页面直接编辑子模块
    """
    model = TestCaseModule
    extra = 1
    fields = ('name', 'level', 'creator')
    readonly_fields = ('level',)
    fk_name = 'parent'


@admin.register(TestCaseModule)
class TestCaseModuleAdmin(admin.ModelAdmin):
    """
    TestCaseModule 模型的 Admin 配置
    """
    list_display = ('name', 'project', 'parent', 'level', 'creator', 'created_at')
    list_filter = ('project', 'level', 'creator', 'created_at')
    search_fields = ('name', 'project__name')
    readonly_fields = ('level', 'created_at', 'updated_at')
    inlines = [TestCaseModuleInline]
    fieldsets = (
        (None, {
            'fields': ('project', 'name', 'parent', 'level')
        }),
        ('创建信息', {
            'fields': ('creator', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        在 Admin 中保存 TestCaseModule 时，如果创建者为空，则设置为当前用户
        """
        if not obj.creator_id:
            obj.creator = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """
        在 Admin 中保存内联的子模块时，如果创建者为空，则设置为当前用户
        """
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, TestCaseModule) and not instance.creator_id:
                instance.creator = request.user
            instance.save()
        formset.save_m2m()
