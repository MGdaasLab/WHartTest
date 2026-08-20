from django.contrib import admin
from .models import (
    UiModule, UiPage, UiElement, UiPageSteps, UiPageStepsDetailed,
    UiTestCase, UiCaseStepsDetailed, UiExecutionRecord, UiPublicData, UiEnvironmentConfig
)


@admin.register(UiModule)
class UiModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'parent', 'level', 'creator', 'created_at')
    list_filter = ('project', 'level')
    search_fields = ('name',)


@admin.register(UiPage)
class UiPageAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'module', 'url', 'creator', 'created_at')
    list_filter = ('project', 'module')
    search_fields = ('name', 'url')


@admin.register(UiElement)
class UiElementAdmin(admin.ModelAdmin):
    list_display = ('name', 'page', 'locator_type', 'locator_value', 'wait_time', 'is_iframe')
    list_filter = ('page', 'locator_type', 'is_iframe')
    search_fields = ('name', 'locator_value')


class UiPageStepsDetailedInline(admin.TabularInline):
    model = UiPageStepsDetailed
    extra = 1


@admin.register(UiPageSteps)
class UiPageStepsAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'page', 'module', 'status', 'creator', 'created_at')
    list_filter = ('project', 'page', 'status')
    search_fields = ('name',)
    inlines = [UiPageStepsDetailedInline]


@admin.register(UiPageStepsDetailed)
class UiPageStepsDetailedAdmin(admin.ModelAdmin):
    list_display = ('page_step', 'step_type', 'element', 'step_sort', 'ope_key')
    list_filter = ('step_type',)


class UiCaseStepsDetailedInline(admin.TabularInline):
    model = UiCaseStepsDetailed
    extra = 1


@admin.register(UiTestCase)
class UiTestCaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'module', 'level', 'status', 'creator', 'created_at')
    list_filter = ('project', 'module', 'level', 'status')
    search_fields = ('name',)
    inlines = [UiCaseStepsDetailedInline]


@admin.register(UiCaseStepsDetailed)
class UiCaseStepsDetailedAdmin(admin.ModelAdmin):
    list_display = ('test_case', 'page_step', 'case_sort', 'status')
    list_filter = ('status',)


@admin.register(UiExecutionRecord)
class UiExecutionRecordAdmin(admin.ModelAdmin):
    list_display = ('test_case', 'executor', 'status', 'trigger_type', 'duration', 'created_at')
    list_filter = ('status', 'trigger_type')
    search_fields = ('test_case__name',)


@admin.register(UiPublicData)
class UiPublicDataAdmin(admin.ModelAdmin):
    list_display = ('key', 'project', 'type', 'is_enabled', 'creator', 'created_at')
    list_filter = ('project', 'type', 'is_enabled')
    search_fields = ('key',)


@admin.register(UiEnvironmentConfig)
class UiEnvironmentConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'base_url', 'is_default')
    list_filter = ('project', 'is_default')
    search_fields = ('name', 'base_url')
