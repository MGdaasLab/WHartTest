from rest_framework import serializers
from django.db import models

from .models import (
    ApiTestTaskSuite,
    ApiTestTaskCase,
    ApiTestTaskExecution,
    ApiTestTaskCaseResult,
)
from api_testcases.serializers import ApiTestReportSerializer, ApiInterfaceCaseReportSerializer


class ApiTestTaskCaseSimpleSerializer(serializers.ModelSerializer):
    case_id = serializers.SerializerMethodField()
    testcase_id = serializers.SerializerMethodField()
    interface_case_id = serializers.SerializerMethodField()
    testcase_name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()
    interface_name = serializers.SerializerMethodField()

    class Meta:
        model = ApiTestTaskCase
        fields = [
            'id', 'case_type', 'case_id',
            'testcase_id', 'interface_case_id', 'testcase_name',
            'description', 'priority', 'interface_name', 'order',
        ]

    def get_case_id(self, obj):
        return obj.case_id

    def get_testcase_id(self, obj):
        return obj.testcase_id if obj.case_type == ApiTestTaskCase.CASE_TYPE_SCENARIO else None

    def get_interface_case_id(self, obj):
        return obj.interface_case_id if obj.case_type == ApiTestTaskCase.CASE_TYPE_INTERFACE else None

    def get_testcase_name(self, obj):
        return obj.case_name

    def get_description(self, obj):
        case = obj.case_object
        return case.description if case else ''

    def get_priority(self, obj):
        case = obj.case_object
        return case.priority if case else ''

    def get_interface_name(self, obj):
        if obj.case_type != ApiTestTaskCase.CASE_TYPE_INTERFACE or not obj.interface_case:
            return ''
        interface = obj.interface_case.interface
        return interface.name if interface else ''


class ApiTestTaskSuiteSerializer(serializers.ModelSerializer):
    task_cases = ApiTestTaskCaseSimpleSerializer(
        source='api_task_cases', many=True, read_only=True
    )
    created_by_name = serializers.CharField(
        source='created_by.username', read_only=True, default=''
    )
    project_name = serializers.CharField(
        source='project.name', read_only=True, default=''
    )
    test_cases = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        help_text='List of test case IDs to associate with this suite',
    )
    interface_cases = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        help_text='List of interface case IDs to associate with this suite',
    )

    class Meta:
        model = ApiTestTaskSuite
        fields = [
            'id', 'name', 'description', 'priority', 'fail_fast',
            'project', 'project_name', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'task_cases',
            'test_cases', 'interface_cases',
        ]
        read_only_fields = ['id', 'project', 'created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        test_cases = validated_data.pop('test_cases', [])
        interface_cases = validated_data.pop('interface_cases', [])
        instance = super().create(validated_data)
        if test_cases or interface_cases:
            from .services import ApiTestTaskService
            ApiTestTaskService.add_cases(
                instance,
                testcase_ids=test_cases,
                interface_case_ids=interface_cases,
                project_pk=instance.project_id,
            )
        return instance

    def update(self, instance, validated_data):
        test_cases = validated_data.pop('test_cases', None)
        interface_cases = validated_data.pop('interface_cases', None)
        instance = super().update(instance, validated_data)
        if test_cases is not None or interface_cases is not None:
            instance.api_task_cases.all().delete()
            from .services import ApiTestTaskService
            ApiTestTaskService.add_cases(
                instance,
                testcase_ids=test_cases or [],
                interface_case_ids=interface_cases or [],
                project_pk=instance.project_id,
            )
        return instance


class ApiTestTaskCaseCreateSerializer(serializers.Serializer):
    testcase_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text='List of test case IDs to add',
    )
    interface_case_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text='List of interface case IDs to add',
    )

    def validate_testcase_ids(self, value):
        from api_testcases.models import ApiTestCase
        project_pk = self.context.get('project_pk')
        qs = ApiTestCase.objects.filter(id__in=set(value))
        if project_pk:
            qs = qs.filter(project_id=project_pk)
        count = qs.count()
        if count != len(set(value)):
            raise serializers.ValidationError("Some test cases do not exist or do not belong to this project.")
        return value

    def validate_interface_case_ids(self, value):
        from api_testcases.models import ApiInterfaceCase
        project_pk = self.context.get('project_pk')
        qs = ApiInterfaceCase.objects.filter(id__in=set(value))
        if project_pk:
            qs = qs.filter(project_id=project_pk)
        count = qs.count()
        if count != len(set(value)):
            raise serializers.ValidationError("Some interface cases do not exist or do not belong to this project.")
        return value


class ApiTestTaskCaseResultSerializer(serializers.ModelSerializer):
    case_id = serializers.SerializerMethodField()
    testcase_name = serializers.SerializerMethodField()
    interface_case = serializers.IntegerField(source='interface_case_id', read_only=True)
    report = serializers.SerializerMethodField()

    class Meta:
        model = ApiTestTaskCaseResult
        fields = [
            'id', 'case_type', 'case_id',
            'testcase', 'interface_case', 'testcase_name', 'status',
            'start_time', 'end_time', 'duration',
            'error_message', 'report',
        ]
        read_only_fields = fields

    def get_case_id(self, obj):
        case = obj.case_object
        return case.id if case else None

    def get_testcase_name(self, obj):
        return obj.case_name

    def get_report(self, obj):
        if obj.case_type == ApiTestTaskCase.CASE_TYPE_INTERFACE:
            if not obj.interface_report:
                return None
            return ApiInterfaceCaseReportSerializer(obj.interface_report).data
        if not obj.report:
            return None
        return ApiTestReportSerializer(obj.report).data


class ApiTestTaskExecutionSerializer(serializers.ModelSerializer):
    task_suite_name = serializers.CharField(source='task_suite.name', read_only=True)
    executed_by_name = serializers.CharField(
        source='executed_by.username', read_only=True, default=''
    )
    environment_name = serializers.CharField(
        source='environment.name', read_only=True, default=''
    )
    case_results = ApiTestTaskCaseResultSerializer(
        source='api_case_results', many=True, read_only=True
    )
    duration = serializers.FloatField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = ApiTestTaskExecution
        fields = [
            'id', 'task_suite', 'task_suite_name', 'status',
            'environment', 'environment_name',
            'start_time', 'end_time', 'duration',
            'total_count', 'success_count', 'fail_count', 'error_count',
            'success_rate', 'executed_by', 'executed_by_name',
            'created_at', 'case_results',
        ]
        read_only_fields = [
            'id', 'status', 'start_time', 'end_time',
            'total_count', 'success_count', 'fail_count', 'error_count',
            'executed_by', 'created_at',
        ]


class ApiTestTaskExecutionListSerializer(serializers.ModelSerializer):
    task_suite_name = serializers.CharField(
        source='task_suite.name', read_only=True, default=''
    )
    environment_name = serializers.CharField(
        source='environment.name', read_only=True, default=''
    )
    executed_by_name = serializers.CharField(
        source='executed_by.username', read_only=True, default=''
    )
    duration = serializers.FloatField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = ApiTestTaskExecution
        fields = [
            'id', 'task_suite', 'task_suite_name',
            'status', 'environment', 'environment_name',
            'start_time', 'end_time', 'duration',
            'total_count', 'success_rate',
            'executed_by', 'executed_by_name', 'created_at',
        ]
        read_only_fields = fields


class ApiTestTaskExecutionCreateSerializer(serializers.Serializer):
    task_suite_id = serializers.IntegerField(help_text='Task suite ID')
    environment_id = serializers.IntegerField(
        required=False, allow_null=True, help_text='Environment ID'
    )

    def validate_task_suite_id(self, value):
        try:
            lookup = {'id': value}
            project_pk = self.context.get('project_pk')
            if project_pk:
                lookup['project_id'] = project_pk
            suite = ApiTestTaskSuite.objects.get(**lookup)
            if suite.api_task_cases.count() == 0:
                raise serializers.ValidationError("Task suite has no test cases.")
            return value
        except ApiTestTaskSuite.DoesNotExist:
            raise serializers.ValidationError("Task suite does not exist.")
