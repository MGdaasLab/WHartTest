import logging
# -*- coding: utf-8 -*-
"""UI 自动化序列化器"""

from rest_framework import serializers

logger = logging.getLogger(__name__)
from file_management.services import validate_file_ids, sync_file_references, serialize_file_for_runtime
from file_management.models import FileReference
from .models import (
    UiModule, UiPage, UiElement, UiPageSteps, UiPageStepsDetailed,
    UiTestCase, UiCaseStepsDetailed, UiExecutionRecord, UiPublicData, UiEnvironmentConfig,
    UiBatchExecutionRecord
)


def _validate_ui_file_ids(file_ids, project, user=None):
    if file_ids in (None, ''):
        return []
    validate_file_ids(file_ids, project, user)
    return file_ids


def _ui_request_user(serializer):
    request = serializer.context.get('request') if hasattr(serializer, 'context') else None
    return request.user if request else None


def _resolve_upload_ope_value(obj, serializer):
    value = dict(obj.ope_value or {})
    if obj.ope_key != 'upload':
        return value
    file_id = value.get('file_id')
    if not file_id:
        return value
    try:
        project = obj.page_step.project if obj.page_step else None
        files = validate_file_ids([file_id], project, _ui_request_user(serializer))
        if files:
            runtime_file = serialize_file_for_runtime(files[0])
            # Prefer shared-storage absolute path; actuators may fall back to download_url.
            resolved_path = runtime_file.get('path') or ''
            value['value'] = resolved_path or value.get('value')
            value['file_path'] = resolved_path
            value['file_name'] = runtime_file.get('name') or value.get('file_name')
            value['mime_type'] = runtime_file.get('mime_type')
            value['file_id'] = runtime_file.get('file_id') or file_id
            value['project_id'] = runtime_file.get('project_id') or (project.id if project else None)
            value['download_url'] = runtime_file.get('download_url') or ''
            value['url'] = runtime_file.get('url') or ''
            value['sha256'] = runtime_file.get('sha256') or ''
            value['size'] = runtime_file.get('size')
    except Exception as exc:
        logger.warning('resolve upload ope_value failed: %s', exc, exc_info=True)
    return value


class UiModuleSerializer(serializers.ModelSerializer):
    """模块序列化器"""
    children = serializers.SerializerMethodField()
    creator_name = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = UiModule
        fields = ['id', 'project', 'name', 'parent', 'level', 'order', 'children', 'creator', 'creator_name', 'created_at', 'updated_at']
        read_only_fields = ['level', 'creator', 'created_at', 'updated_at', 'order']

    def get_children(self, obj):
        children = obj.children.all()
        return UiModuleSerializer(children, many=True).data if children else []


class UiElementSerializer(serializers.ModelSerializer):
    """元素序列化器"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = UiElement
        fields = '__all__'
        read_only_fields = ['creator', 'created_at', 'updated_at']


class UiPageSerializer(serializers.ModelSerializer):
    """页面序列化器"""
    module_name = serializers.CharField(source='module.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    element_count = serializers.SerializerMethodField()

    class Meta:
        model = UiPage
        fields = '__all__'
        read_only_fields = ['creator', 'created_at', 'updated_at']

    def get_element_count(self, obj):
        return obj.elements.count()


class UiPageDetailSerializer(UiPageSerializer):
    """页面详情序列化器（含元素列表）"""
    elements = UiElementSerializer(many=True, read_only=True)

    class Meta(UiPageSerializer.Meta):
        fields = '__all__'


class UiPageStepsDetailedSerializer(serializers.ModelSerializer):
    """步骤详情序列化器"""
    element_name = serializers.CharField(source='element.name', read_only=True)
    page_name = serializers.SerializerMethodField()
    module_name = serializers.SerializerMethodField()

    class Meta:
        model = UiPageStepsDetailed
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_page_name(self, obj):
        if obj.element and obj.element.page:
            return obj.element.page.name
        return None

    def get_module_name(self, obj):
        if obj.element and obj.element.page and obj.element.page.module:
            return obj.element.page.module.name
        return None

    def validate(self, attrs):
        page_step = attrs.get('page_step') or getattr(self.instance, 'page_step', None)
        ope_key = attrs.get('ope_key') if 'ope_key' in attrs else getattr(self.instance, 'ope_key', None)
        ope_value = attrs.get('ope_value') if 'ope_value' in attrs else getattr(self.instance, 'ope_value', {})
        if ope_key == 'upload':
            file_id = (ope_value or {}).get('file_id')
            if not file_id:
                raise serializers.ValidationError({'ope_value': '上传文件操作必须选择文件。'})
            if page_step and page_step.project:
                validate_file_ids([file_id], page_step.project, _ui_request_user(self))
        return attrs


class UiPageStepsDetailedExecuteSerializer(serializers.ModelSerializer):
    """步骤详情序列化器（含元素定位信息，用于执行器）"""
    ope_value = serializers.SerializerMethodField()
    element_name = serializers.CharField(source='element.name', read_only=True)
    locator_type = serializers.CharField(source='element.locator_type', read_only=True)
    locator_value = serializers.CharField(source='element.locator_value', read_only=True)
    locator_index = serializers.IntegerField(source='element.locator_index', read_only=True)
    locator_type_2 = serializers.CharField(source='element.locator_type_2', read_only=True)
    locator_value_2 = serializers.CharField(source='element.locator_value_2', read_only=True)
    locator_index_2 = serializers.IntegerField(source='element.locator_index_2', read_only=True)
    locator_type_3 = serializers.CharField(source='element.locator_type_3', read_only=True)
    locator_value_3 = serializers.CharField(source='element.locator_value_3', read_only=True)
    locator_index_3 = serializers.IntegerField(source='element.locator_index_3', read_only=True)
    wait_time = serializers.IntegerField(source='element.wait_time', read_only=True)
    is_iframe = serializers.BooleanField(source='element.is_iframe', read_only=True)
    iframe_locator = serializers.CharField(source='element.iframe_locator', read_only=True)

    def get_ope_value(self, obj):
        return _resolve_upload_ope_value(obj, self)

    class Meta:
        model = UiPageStepsDetailed
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class UiPageStepsListSerializer(serializers.ModelSerializer):
    """页面步骤列表序列化器（精简字段，提升性能）"""
    page_name = serializers.CharField(source='page.name', read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    step_count = serializers.SerializerMethodField()

    class Meta:
        model = UiPageSteps
        fields = [
            'id', 'project', 'page', 'page_name', 'module', 'module_name',
            'name', 'status', 'file_ids', 'step_count', 'creator', 'creator_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'creator', 'created_at', 'updated_at']

    def get_step_count(self, obj):
        return obj.step_details.count()


class UiPageStepsSerializer(serializers.ModelSerializer):
    """页面步骤序列化器"""
    page_name = serializers.CharField(source='page.name', read_only=True)
    module_name = serializers.CharField(source='module.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    step_count = serializers.SerializerMethodField()

    class Meta:
        model = UiPageSteps
        fields = '__all__'
        read_only_fields = ['status', 'result_data', 'creator', 'created_at', 'updated_at']

    def get_step_count(self, obj):
        return obj.step_details.count()


class UiPageStepsDetailSerializer(UiPageStepsSerializer):
    """页面步骤详情序列化器（含步骤详情列表）"""
    step_details = UiPageStepsDetailedSerializer(many=True, read_only=True)

    class Meta(UiPageStepsSerializer.Meta):
        fields = '__all__'


class UiPageStepsExecuteSerializer(UiPageStepsSerializer):
    """页面步骤执行序列化器（含步骤详情列表和元素定位信息）"""
    step_details = UiPageStepsDetailedExecuteSerializer(many=True, read_only=True)
    page_url = serializers.CharField(source='page.url', read_only=True)
    managed_files = serializers.SerializerMethodField()

    def get_managed_files(self, obj):
        try:
            files = validate_file_ids(obj.file_ids or [], obj.project, _ui_request_user(self))
            return [serialize_file_for_runtime(asset) for asset in files]
        except Exception:
            return []

    class Meta(UiPageStepsSerializer.Meta):
        fields = '__all__'


class UiCaseStepsDetailedSerializer(serializers.ModelSerializer):
    """用例步骤序列化器"""
    page_step_name = serializers.CharField(source='page_step.name', read_only=True)
    page_name = serializers.SerializerMethodField()
    module_name = serializers.SerializerMethodField()

    class Meta:
        model = UiCaseStepsDetailed
        fields = '__all__'
        read_only_fields = ['status', 'error_message', 'result_data', 'created_at', 'updated_at']

    def get_page_name(self, obj):
        if obj.page_step and obj.page_step.page:
            return obj.page_step.page.name
        return None

    def get_module_name(self, obj):
        if obj.page_step and obj.page_step.module:
            return obj.page_step.module.name
        return None


class UiCaseStepsWithDetailSerializer(serializers.ModelSerializer):
    """用例步骤序列化器（含完整page_step详情）- 用于执行时获取步骤详情"""
    page_step = UiPageStepsExecuteSerializer(read_only=True)

    class Meta:
        model = UiCaseStepsDetailed
        fields = '__all__'
        read_only_fields = ['status', 'error_message', 'result_data', 'created_at', 'updated_at']


class UiTestCaseListSerializer(serializers.ModelSerializer):
    """测试用例列表序列化器（精简字段，提升性能）"""
    module_name = serializers.CharField(source='module.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    step_count = serializers.SerializerMethodField()

    class Meta:
        model = UiTestCase
        fields = [
            'id', 'project', 'module', 'module_name', 'name', 'level', 'status',
            'file_ids', 'step_count', 'creator', 'creator_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'creator', 'created_at', 'updated_at']

    def get_step_count(self, obj):
        return obj.case_steps.count()


class UiTestCaseSerializer(serializers.ModelSerializer):
    """测试用例序列化器"""
    module_name = serializers.CharField(source='module.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    step_count = serializers.SerializerMethodField()

    class Meta:
        model = UiTestCase
        fields = '__all__'
        read_only_fields = ['status', 'result_data', 'error_message', 'creator', 'created_at', 'updated_at']

    def get_step_count(self, obj):
        return obj.case_steps.count()


class UiTestCaseDetailSerializer(UiTestCaseSerializer):
    """测试用例详情序列化器（含步骤列表）"""
    case_steps = UiCaseStepsDetailedSerializer(many=True, read_only=True)

    class Meta(UiTestCaseSerializer.Meta):
        fields = '__all__'


class UiTestCaseExecuteSerializer(UiTestCaseSerializer):
    """测试用例执行序列化器（含完整步骤详情，用于执行器获取数据）"""
    case_step_details = UiCaseStepsWithDetailSerializer(source='case_steps', many=True, read_only=True)
    managed_files = serializers.SerializerMethodField()

    def get_managed_files(self, obj):
        try:
            files = validate_file_ids(obj.file_ids or [], obj.project, _ui_request_user(self))
            return [serialize_file_for_runtime(asset) for asset in files]
        except Exception:
            return []

    class Meta(UiTestCaseSerializer.Meta):
        fields = '__all__'


class UiExecutionRecordListSerializer(serializers.ModelSerializer):
    """执行记录列表序列化器（精简字段，提升性能）"""
    test_case_name = serializers.CharField(source='test_case.name', read_only=True)
    executor_name = serializers.CharField(source='executor.username', read_only=True)

    class Meta:
        model = UiExecutionRecord
        fields = [
            'id', 'batch', 'test_case', 'test_case_name', 'executor', 'executor_name',
            'status', 'trigger_type', 'start_time', 'end_time', 'duration', 'created_at'
        ]
        read_only_fields = ['created_at']


class UiExecutionRecordBatchDetailSerializer(serializers.ModelSerializer):
    """批量执行详情中的执行记录序列化器（包含步骤结果和错误信息，不含过大字段）"""
    test_case_name = serializers.CharField(source='test_case.name', read_only=True)
    executor_name = serializers.CharField(source='executor.username', read_only=True)

    class Meta:
        model = UiExecutionRecord
        fields = [
            'id', 'batch', 'test_case', 'test_case_name', 'executor', 'executor_name',
            'status', 'trigger_type', 'start_time', 'end_time', 'duration',
            'step_results', 'screenshots', 'error_message', 'trace_path', 'created_at'
        ]
        read_only_fields = ['created_at']


class UiExecutionRecordSerializer(serializers.ModelSerializer):
    """执行记录序列化器"""
    test_case_name = serializers.CharField(source='test_case.name', read_only=True)
    executor_name = serializers.CharField(source='executor.username', read_only=True)

    class Meta:
        model = UiExecutionRecord
        fields = '__all__'
        read_only_fields = ['created_at']


class UiPublicDataSerializer(serializers.ModelSerializer):
    """公共数据序列化器"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = UiPublicData
        fields = '__all__'
        read_only_fields = ['creator', 'created_at', 'updated_at']


class UiEnvironmentConfigSerializer(serializers.ModelSerializer):
    """环境配置序列化器"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = UiEnvironmentConfig
        fields = '__all__'
        read_only_fields = ['creator', 'created_at', 'updated_at']


class UiBatchExecutionRecordSerializer(serializers.ModelSerializer):
    """批量执行记录序列化器"""
    executor_name = serializers.CharField(source='executor.username', read_only=True)
    success_rate = serializers.SerializerMethodField()

    class Meta:
        model = UiBatchExecutionRecord
        fields = '__all__'
        read_only_fields = ['created_at']

    def get_success_rate(self, obj):
        if obj.total_cases == 0:
            return 0
        return round(obj.passed_cases / obj.total_cases * 100, 1)


class UiBatchExecutionRecordDetailSerializer(UiBatchExecutionRecordSerializer):
    """批量执行记录详情序列化器（含关联执行记录详情：包含步骤结果和错误信息）"""
    execution_records = UiExecutionRecordBatchDetailSerializer(many=True, read_only=True)

    class Meta(UiBatchExecutionRecordSerializer.Meta):
        fields = '__all__'


# 附件 file_ids 校验与引用关系维护

def _ui_page_steps_validate(self, attrs):
    project = attrs.get('project') or (self.instance.project if self.instance else None)
    if 'file_ids' in attrs and project:
        attrs['file_ids'] = _validate_ui_file_ids(attrs.get('file_ids'), project, _ui_request_user(self))
    return attrs


def _ui_page_steps_create(self, validated_data):
    instance = super(UiPageStepsSerializer, self).create(validated_data)
    sync_file_references(instance.file_ids or [], instance.project, FileReference.REF_UI_PAGE_STEPS, instance.id, _ui_request_user(self))
    return instance


def _ui_page_steps_update(self, instance, validated_data):
    instance = super(UiPageStepsSerializer, self).update(instance, validated_data)
    if 'file_ids' in validated_data:
        sync_file_references(instance.file_ids or [], instance.project, FileReference.REF_UI_PAGE_STEPS, instance.id, _ui_request_user(self))
    return instance


def _ui_testcase_validate(self, attrs):
    project = attrs.get('project') or (self.instance.project if self.instance else None)
    if 'file_ids' in attrs and project:
        attrs['file_ids'] = _validate_ui_file_ids(attrs.get('file_ids'), project, _ui_request_user(self))
    return attrs


def _ui_testcase_create(self, validated_data):
    instance = super(UiTestCaseSerializer, self).create(validated_data)
    sync_file_references(instance.file_ids or [], instance.project, FileReference.REF_UI_TESTCASE, instance.id, _ui_request_user(self))
    return instance


def _ui_testcase_update(self, instance, validated_data):
    instance = super(UiTestCaseSerializer, self).update(instance, validated_data)
    if 'file_ids' in validated_data:
        sync_file_references(instance.file_ids or [], instance.project, FileReference.REF_UI_TESTCASE, instance.id, _ui_request_user(self))
    return instance

UiPageStepsSerializer.validate = _ui_page_steps_validate
UiPageStepsSerializer.create = _ui_page_steps_create
UiPageStepsSerializer.update = _ui_page_steps_update
UiTestCaseSerializer.validate = _ui_testcase_validate
UiTestCaseSerializer.create = _ui_testcase_create
UiTestCaseSerializer.update = _ui_testcase_update
