from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    TestCase, TestCaseStep, TestCaseModule, TestCaseScreenshot,
    TestSuite, TestExecution, TestCaseResult
)
from projects.models import Project # 确保导入Project模型以便进行校验
from accounts.serializers import UserDetailSerializer # 用于显示创建者信息
from django.db import transaction

class TestCaseStepSerializer(serializers.ModelSerializer):
    """
    用例步骤序列化器
    """
    id = serializers.IntegerField(required=False) # 在更新时用于标识现有步骤

    class Meta:
        model = TestCaseStep
        fields = ['id', 'step_number', 'description', 'expected_result', 'creator'] # creator 仅用于创建时关联
        read_only_fields = ['creator'] # 通常在创建时由视图设置

    def create(self, validated_data):
        # creator 应该由视图的 perform_create 或序列化器的 save 方法中传递
        # 此处仅为示例，实际创建逻辑在 TestCaseSerializer 中处理
        return super().create(validated_data)

class TestCaseSerializer(serializers.ModelSerializer):
    """
    用例序列化器，支持嵌套创建和更新用例步骤
    """
    steps = TestCaseStepSerializer(many=True)
    screenshots = serializers.SerializerMethodField()
    creator_detail = UserDetailSerializer(source='creator', read_only=True)
    module_id = serializers.PrimaryKeyRelatedField(
        queryset=TestCaseModule.objects.all(),
        source='module', # 关联到模型中的 'module' 字段
        allow_null=False, # 不允许为空
        required=True     # 必填字段
    )
    module_detail = serializers.StringRelatedField(source='module', read_only=True) # 用于只读展示模块名称

    # project 字段在创建时需要，但通常通过 URL 传递，不在请求体中
    # project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all()) # 可以取消注释用于校验

    class Meta:
        model = TestCase
        fields = [
            'id', 'project', 'module_id', 'module_detail', 'name', 'precondition', 'level', 'notes',
            'steps', 'screenshot', 'screenshots', 'creator', 'creator_detail', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'project', 'module_detail', # module_detail 仅用于展示
            'creator', 'creator_detail', 'created_at', 'updated_at'
        ]
        # project 字段在创建时是必需的，但通常从 URL 获取，不在 request.data 中。
        # 如果要通过 request.data 传递 project_id，则需要将其从 read_only_fields 中移除，
        # 并在视图中处理或使用 HiddenField/SerializerMethodField 等。
        # 这里我们假设 project 将从 URL 传递给视图，并在视图的 perform_create 中设置。
        # 因此，对于序列化器本身，project 字段可以被视为只读或在创建时不直接通过此序列化器输入。
        # 为了简单起见，我们先将其保留在 fields 中，视图将负责处理其赋值。

    def create(self, validated_data):
        steps_data = validated_data.pop('steps')
        # project 实例已在 validated_data 中由 perform_create 注入
        # creator 实例也已在 validated_data 中由 perform_create 注入
        test_case = TestCase.objects.create(**validated_data)
        for step_data in steps_data:
            # 确保步骤的 creator 与用例的 creator 一致
            TestCaseStep.objects.create(test_case=test_case, creator=test_case.creator, **step_data)
        return test_case

    @transaction.atomic
    def update(self, instance, validated_data):
        steps_data = validated_data.pop('steps', None)

        # 更新 TestCase 实例的字段
        instance.name = validated_data.get('name', instance.name)
        instance.precondition = validated_data.get('precondition', instance.precondition)
        instance.level = validated_data.get('level', instance.level)
        instance.notes = validated_data.get('notes', instance.notes)
        # project 和 creator 通常不允许通过此接口更新
        instance.save()

        if steps_data is not None:
            existing_steps = {step.id: step for step in instance.steps.all()}
            step_ids_from_payload = set()
            final_steps_to_process = [] # 用于收集将要保存的步骤（新的或更新的）

            # 遍历传入的步骤数据
            for step_data in steps_data:
                step_id = step_data.get('id')
                step_creator = instance.creator # 步骤的创建者应与用例的创建者一致

                if step_id:
                    step_ids_from_payload.add(step_id)
                    if step_id in existing_steps:
                        # 更新现有步骤
                        step_instance = existing_steps[step_id]
                        step_instance.description = step_data.get('description', step_instance.description)
                        step_instance.expected_result = step_data.get('expected_result', step_instance.expected_result)
                        # step_number 将在后面统一重新分配
                        final_steps_to_process.append(step_instance)
                    else:
                        # 如果提供了ID但步骤不存在，可以选择忽略或创建（这里选择忽略，避免意外创建）
                        # 或者可以引发一个 ValidationError
                        # raise serializers.ValidationError(f"Step with id {step_id} not found for this test case.")
                        pass
                else:
                    # 创建新步骤 (但不立即保存，也不立即分配 step_number)
                    new_step = TestCaseStep(
                        test_case=instance,
                        creator=step_creator,
                        description=step_data.get('description'),
                        expected_result=step_data.get('expected_result')
                        # step_number 将在后面统一重新分配
                    )
                    final_steps_to_process.append(new_step)

            # 删除不再需要的步骤
            step_ids_to_delete = set(existing_steps.keys()) - step_ids_from_payload
            if step_ids_to_delete:
                TestCaseStep.objects.filter(id__in=step_ids_to_delete, test_case=instance).delete()

            # 重新编号并保存所有需要保留或新创建的步骤
            for index, step_obj in enumerate(final_steps_to_process):
                step_obj.step_number = index + 1
                step_obj.save() # 这会处理创建新步骤或更新现有步骤

        return instance

    def get_screenshots(self, obj):
        """获取测试用例的所有截屏"""
        screenshots = obj.screenshots.all()
        return TestCaseScreenshotSerializer(
            screenshots,
            many=True,
            context=self.context
        ).data


class TestCaseModuleSerializer(serializers.ModelSerializer):
    """
    用例模块序列化器
    """
    creator_detail = UserDetailSerializer(source='creator', read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=TestCaseModule.objects.all(),
        source='parent',
        required=False,
        allow_null=True
    )
    # 添加用例数量字段
    testcase_count = serializers.SerializerMethodField()

    class Meta:
        model = TestCaseModule
        fields = [
            'id', 'project', 'name', 'parent', 'parent_id', 'level',
            'creator', 'creator_detail', 'created_at', 'updated_at',
            'testcase_count'  # 添加到字段列表
        ]
        read_only_fields = [
            'id', 'project', 'level',
            'creator', 'creator_detail', 'created_at', 'updated_at'
        ]

    # 添加获取用例数量的方法
    def get_testcase_count(self, obj):
        """
        计算模块下的用例数量
        """
        return obj.testcases.count()

    def validate(self, attrs):
        """验证模块数据"""
        # 创建时，确保父模块属于同一个项目
        if self.instance is None and 'parent' in attrs and attrs['parent']:
            project = self.context['project']
            parent = attrs['parent']
            if parent.project_id != project.id:
                raise serializers.ValidationError({"parent": "父模块必须属于同一个项目"})

            # 验证模块级别不超过5级
            if parent.level >= 5:
                raise serializers.ValidationError({"parent": "模块级别不能超过5级"})

        # 更新时，确保父模块属于同一个项目
        elif self.instance and 'parent' in attrs and attrs['parent']:
            parent = attrs['parent']
            if parent.project_id != self.instance.project_id:
                raise serializers.ValidationError({"parent": "父模块必须属于同一个项目"})

            # 验证模块级别不超过5级
            if parent.level >= 5:
                raise serializers.ValidationError({"parent": "模块级别不能超过5级"})

            # 验证父模块不是自己或自己的子模块（避免循环引用）
            if parent.id == self.instance.id:
                raise serializers.ValidationError({"parent": "父模块不能是自己"})

            # 检查是否会形成循环引用
            current_parent = parent
            while current_parent:
                if current_parent.parent_id == self.instance.id:
                    raise serializers.ValidationError({"parent": "不能选择自己的子模块作为父模块"})
                current_parent = current_parent.parent

        return attrs

    def create(self, validated_data):
        # project 实例已在 validated_data 中由 perform_create 注入
        # creator 实例也已在 validated_data 中由 perform_create 注入

        # 设置模块级别
        parent = validated_data.get('parent')
        if parent:
            validated_data['level'] = parent.level + 1
        else:
            validated_data['level'] = 1

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # 更新模块级别
        parent = validated_data.get('parent')
        if parent:
            validated_data['level'] = parent.level + 1
        elif 'parent' in validated_data and validated_data['parent'] is None:
            validated_data['level'] = 1

        return super().update(instance, validated_data)


class TestCaseScreenshotSerializer(serializers.ModelSerializer):
    """
    测试用例截屏序列化器
    """
    uploader_detail = UserDetailSerializer(source='uploader', read_only=True)
    screenshot_url = serializers.SerializerMethodField()

    class Meta:
        model = TestCaseScreenshot
        fields = [
            'id', 'test_case', 'screenshot', 'screenshot_url', 'title', 'description',
            'step_number', 'created_at', 'mcp_session_id', 'page_url',
            'uploader', 'uploader_detail'
        ]
        read_only_fields = ['id', 'created_at', 'uploader', 'uploader_detail']

    def get_screenshot_url(self, obj):
        """获取截屏图片的完整URL"""
        if obj.screenshot:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.screenshot.url)
            return obj.screenshot.url
        return None

    def create(self, validated_data):
        """创建截屏时自动设置上传人"""
        request = self.context.get('request')
        if request and request.user:
            validated_data['uploader'] = request.user
        return super().create(validated_data)




class TestSuiteSerializer(serializers.ModelSerializer):
    """
    测试套件序列化器
    """
    creator_detail = UserDetailSerializer(source='creator', read_only=True)
    testcase_ids = serializers.PrimaryKeyRelatedField(
        queryset=TestCase.objects.all(),
        source='testcases',
        many=True,
        write_only=True
    )
    testcases_detail = TestCaseSerializer(source='testcases', many=True, read_only=True)
    testcase_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TestSuite
        fields = [
            'id', 'name', 'description', 'project',
            'testcase_ids', 'testcases_detail', 'testcase_count',
            'max_concurrent_tasks',
            'creator', 'creator_detail', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'project', 'creator', 'creator_detail', 'created_at', 'updated_at']
    
    def get_testcase_count(self, obj):
        """获取套件中的用例数量"""
        return obj.testcases.count()
    
    def validate_testcase_ids(self, value):
        """验证测试用例是否属于同一项目"""
        if not value:
            raise serializers.ValidationError("测试套件至少需要包含一个测试用例")
        
        # 获取项目ID (创建时从context获取，更新时从instance获取)
        if self.instance:
            project_id = self.instance.project_id
        else:
            project_id = self.context.get('project_id')
        
        if not project_id:
            raise serializers.ValidationError("无法确定项目ID")
        
        # 检查所有用例是否属于同一项目
        for testcase in value:
            if testcase.project_id != project_id:
                raise serializers.ValidationError(
                    f"测试用例 '{testcase.name}' 不属于当前项目"
                )
        
        return value
    
    def validate_max_concurrent_tasks(self, value):
        """验证并发数配置"""
        if value < 1:
            raise serializers.ValidationError("并发数至少为1（串行执行）")
        if value > 10:
            raise serializers.ValidationError("并发数不能超过10，避免系统资源耗尽")
        return value
    
    def create(self, validated_data):
        testcases = validated_data.pop('testcases')
        suite = TestSuite.objects.create(**validated_data)
        suite.testcases.set(testcases)
        return suite
    
    def update(self, instance, validated_data):
        testcases = validated_data.pop('testcases', None)
        
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.max_concurrent_tasks = validated_data.get('max_concurrent_tasks', instance.max_concurrent_tasks)
        instance.save()
        
        if testcases is not None:
            instance.testcases.set(testcases)
        
        return instance


class TestCaseResultSerializer(serializers.ModelSerializer):
    """
    测试用例执行结果序列化器
    """
    testcase_detail = TestCaseSerializer(source='testcase', read_only=True)
    duration = serializers.ReadOnlyField()
    
    class Meta:
        model = TestCaseResult
        fields = [
            'id', 'execution', 'testcase', 'testcase_detail', 'status',
            'error_message', 'stack_trace', 'started_at', 'completed_at',
            'execution_time', 'duration', 'mcp_session_id', 'screenshots',
            'execution_log', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'duration'
        ]


class TestExecutionSerializer(serializers.ModelSerializer):
    """
    测试执行记录序列化器
    """
    suite_detail = TestSuiteSerializer(source='suite', read_only=True)
    executor_detail = UserDetailSerializer(source='executor', read_only=True)
    results = TestCaseResultSerializer(many=True, read_only=True)
    duration = serializers.ReadOnlyField()
    pass_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = TestExecution
        fields = [
            'id', 'suite', 'suite_detail', 'status', 'executor', 'executor_detail',
            'started_at', 'completed_at', 'total_count', 'passed_count',
            'failed_count', 'skipped_count', 'error_count', 'celery_task_id',
            'duration', 'pass_rate', 'results', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'started_at', 'completed_at',
            'total_count', 'passed_count', 'failed_count', 'skipped_count',
            'error_count', 'celery_task_id', 'duration', 'pass_rate',
            'created_at', 'updated_at'
        ]


class TestExecutionCreateSerializer(serializers.Serializer):
    """
    创建测试执行的简化序列化器
    """
    suite_id = serializers.IntegerField(required=True, help_text="测试套件ID")
    
    def validate_suite_id(self, value):
        """验证套件是否存在"""
        try:
            suite = TestSuite.objects.get(id=value)
            # 验证套件是否有测试用例
            if not suite.testcases.exists():
                raise serializers.ValidationError("测试套件中没有测试用例")
            return value
        except TestSuite.DoesNotExist:
            raise serializers.ValidationError("测试套件不存在")
