from rest_framework import serializers
from django.db import transaction, models
from file_management.services import validate_file_ids, sync_file_references
from file_management.models import FileReference
from .models import (
    ApiTestCase, ApiTestCaseStep, ApiTestReport, ApiTestReportDetail,
    ApiTestCaseTag, ApiTestCaseGroup,
    ApiInterfaceCase, ApiInterfaceCaseStep,
    ApiInterfaceCaseReport, ApiInterfaceCaseReportDetail
)


class ApiTestCaseTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiTestCaseTag
        fields = ['id', 'name', 'color', 'project', 'created_by', 'created_at']
        read_only_fields = ['project', 'created_by', 'created_at']


class ApiTestCaseGroupSerializer(serializers.ModelSerializer):
    full_path = serializers.CharField(source='get_full_path', read_only=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = ApiTestCaseGroup
        fields = [
            'id', 'name', 'parent', 'project',
            'created_by', 'created_at', 'full_path', 'children'
        ]
        read_only_fields = ['project', 'created_by', 'created_at']

    def get_children(self, obj):
        children = obj.children.all()
        if children:
            return ApiTestCaseGroupSerializer(children, many=True).data
        return []


def validate_file_ids_for_project(file_ids, project_pk, user=None):
    if file_ids in (None, ''):
        return []
    from projects.models import Project
    try:
        project = Project.objects.get(id=project_pk)
    except Project.DoesNotExist as exc:
        raise serializers.ValidationError({'project': 'Project does not exist.'}) from exc
    validate_file_ids(file_ids, project, user)
    return file_ids


def build_interface_data_snapshot(interface, override_data=None):
    """Build a runnable, independent snapshot from an ApiInterface."""
    data = interface.get_interface_data()
    if interface.type == interface.TYPE_SQL:
        data.update({
            'sql_method': interface.sql_method,
            'sql_params': interface.sql_params or {},
            'sql_size': interface.sql_size,
        })
    else:
        data.update({
            'headers': interface.headers or [],
            'params': interface.params or [],
            'body': interface.body or {'type': 'none', 'content': None},
        })

    if isinstance(override_data, dict):
        data.update(override_data)

    return data


def build_interface_info(interface):
    if not interface:
        return None
    return {
        'id': interface.id,
        'name': interface.name,
        'type': interface.type,
        'method': interface.method or interface.sql_method,
        'url': interface.url or interface.sql,
        'module': {
            'id': interface.module.id,
            'name': interface.module.name
        } if interface.module else None,
        'project': {
            'id': interface.project.id,
            'name': interface.project.name
        }
    }


class ApiTestCaseStepSerializer(serializers.ModelSerializer):
    interface_id = serializers.IntegerField(write_only=True, required=False)
    interface_info = serializers.SerializerMethodField(read_only=True)
    interface_data = serializers.JSONField(required=False)

    class Meta:
        model = ApiTestCaseStep
        fields = [
            'id', 'name', 'order', 'interface_id',
            'interface_info', 'interface_data', 'config', 'file_ids',
            'sync_fields', 'last_sync_time'
        ]
        read_only_fields = ['last_sync_time']

    def get_interface_info(self, obj):
        if obj.origin_interface:
            return {
                'id': obj.origin_interface.id,
                'name': obj.origin_interface.name,
                'method': obj.origin_interface.method,
                'url': obj.origin_interface.url,
                'module': {
                    'id': obj.origin_interface.module.id,
                    'name': obj.origin_interface.module.name
                } if obj.origin_interface.module else None,
                'project': {
                    'id': obj.origin_interface.project.id,
                    'name': obj.origin_interface.project.name
                }
            }
        return None

    def _build_interface_data(self, interface):
        return {
            'method': interface.method,
            'url': interface.url,
            'headers': interface.headers or [],
            'params': interface.params or [],
            'body': interface.body or {'type': 'raw', 'content': ''},
            'extract': {},
            'variables': {},
            'validators': [],
            'setup_hooks': [],
            'teardown_hooks': [],
            'file_ids': interface.file_ids or []
        }

    def _create_sync_config(self, step, interface):
        from api_sync.models import ApiSyncConfig, ApiGlobalSyncConfig

        existing_config = ApiSyncConfig.objects.filter(
            interface=interface,
            step=step
        ).first()

        if not existing_config:
            global_config = ApiGlobalSyncConfig.objects.filter(
                project=interface.project,
                is_active=True,
                sync_enabled=True
            ).first()

            if global_config:
                sync_fields = global_config.sync_fields
                sync_trigger = {
                    "fields_to_watch": sync_fields if global_config.sync_mode == 'auto' else []
                }
                ApiSyncConfig.objects.create(
                    name=f'Auto-created - {interface.name}',
                    description='Auto-created from global sync config',
                    interface=interface,
                    testcase=step.testcase,
                    step=step,
                    sync_fields=sync_fields,
                    sync_enabled=global_config.sync_enabled,
                    sync_mode=global_config.sync_mode,
                    sync_trigger=sync_trigger,
                    created_by=self.context['request'].user if 'request' in self.context else None
                )
                return True
        return False

    def _get_project_pk(self):
        """Get project_pk from serializer context (passed by DRF ViewSet)."""
        view = self.context.get('view')
        return view.kwargs.get('project_pk') if view else None

    def validate(self, attrs):
        project_pk = self._get_project_pk()
        if 'file_ids' in attrs and project_pk:
            attrs['file_ids'] = validate_file_ids_for_project(attrs.get('file_ids'), project_pk, self.context.get('request').user if self.context.get('request') else None)
        if 'interface_data' in attrs and isinstance(attrs.get('interface_data'), dict) and 'file_ids' in attrs['interface_data'] and project_pk:
            validate_file_ids_for_project(attrs['interface_data'].get('file_ids'), project_pk, self.context.get('request').user if self.context.get('request') else None)
        return attrs

    def create(self, validated_data):
        from api_interfaces.models import ApiInterface

        interface_id = validated_data.pop('interface_id')
        project_pk = self._get_project_pk()
        interface = ApiInterface.objects.get(id=interface_id, project_id=project_pk)
        validated_data['interface_data'] = self._build_interface_data(interface)
        validated_data['origin_interface'] = interface
        step = super().create(validated_data)
        self._create_sync_config(step, interface)
        return step

    def update(self, instance, validated_data):
        from api_interfaces.models import ApiInterface

        old_interface = instance.origin_interface
        new_interface = None

        if 'interface_id' in validated_data:
            interface_id = validated_data.pop('interface_id')
            project_pk = self._get_project_pk()
            new_interface = ApiInterface.objects.get(id=interface_id, project_id=project_pk)
            current_data = instance.interface_data or {}
            new_data = self._build_interface_data(new_interface)
            new_data.update({
                'extract': current_data.get('extract', {}),
                'variables': current_data.get('variables', {}),
                'validators': current_data.get('validators', []),
                'setup_hooks': current_data.get('setup_hooks', []),
                'teardown_hooks': current_data.get('teardown_hooks', [])
            })
            validated_data['interface_data'] = new_data
            validated_data['origin_interface'] = new_interface

        step = super().update(instance, validated_data)

        if new_interface and new_interface != old_interface:
            from api_sync.models import ApiSyncConfig
            ApiSyncConfig.objects.filter(step=step).delete()
            self._create_sync_config(step, new_interface)

        return step


class ApiTestCaseSerializer(serializers.ModelSerializer):
    steps = ApiTestCaseStepSerializer(many=True, read_only=True)
    steps_info = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
    )
    tags_info = ApiTestCaseTagSerializer(source='tags', many=True, read_only=True)
    group_info = ApiTestCaseGroupSerializer(source='group', read_only=True)
    related_interfaces = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source='created_by.username', read_only=True, default=''
    )

    def get_related_interfaces(self, obj):
        interfaces = {}
        for step in obj.steps.all().select_related(
            'origin_interface__module', 'origin_interface__project'
        ):
            if step.origin_interface:
                interface = step.origin_interface
                module_name = interface.module.name if interface.module else "Uncategorized"
                if module_name not in interfaces:
                    interfaces[module_name] = []
                interfaces[module_name].append({
                    'id': interface.id,
                    'name': interface.name,
                    'method': interface.method,
                    'url': interface.url,
                    'step_name': step.name,
                    'step_order': step.order
                })
        return [
            {
                'module': module_name,
                'interfaces': sorted(interface_list, key=lambda x: x['step_order'])
            }
            for module_name, interface_list in interfaces.items()
        ]

    class Meta:
        model = ApiTestCase
        fields = [
            'id', 'name', 'description', 'priority',
            'config', 'file_ids', 'project', 'group',
            'tags', 'tags_info', 'group_info',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
            'steps', 'steps_info', 'related_interfaces'
        ]
        read_only_fields = ['project', 'created_by', 'created_at', 'updated_at']

    def _get_project_pk(self):
        """Get project_pk from serializer context (passed by DRF ViewSet)."""
        view = self.context.get('view')
        return view.kwargs.get('project_pk') if view else None

    def validate(self, attrs):
        project_pk = self._get_project_pk()
        if 'file_ids' in attrs and project_pk:
            attrs['file_ids'] = validate_file_ids_for_project(attrs.get('file_ids'), project_pk, self.context.get('request').user if self.context.get('request') else None)
        for step_data in attrs.get('steps_info') or []:
            if 'file_ids' in step_data and project_pk:
                validate_file_ids_for_project(step_data.get('file_ids'), project_pk, self.context.get('request').user if self.context.get('request') else None)
            interface_data = step_data.get('interface_data')
            if isinstance(interface_data, dict) and 'file_ids' in interface_data and project_pk:
                validate_file_ids_for_project(interface_data.get('file_ids'), project_pk, self.context.get('request').user if self.context.get('request') else None)
        return attrs

    def _build_interface_data(self, interface):
        return {
            'method': interface.method,
            'url': interface.url,
            'headers': interface.headers or [],
            'params': interface.params or [],
            'body': interface.body or {'type': 'raw', 'content': ''},
            'extract': {},
            'variables': {},
            'validators': [],
            'setup_hooks': [],
            'teardown_hooks': [],
            'file_ids': interface.file_ids or []
        }

    def _create_sync_config(self, step, interface):
        from api_sync.models import ApiSyncConfig, ApiGlobalSyncConfig

        existing_config = ApiSyncConfig.objects.filter(
            interface=interface,
            step=step
        ).first()

        if not existing_config:
            global_config = ApiGlobalSyncConfig.objects.filter(
                project=interface.project,
                is_active=True,
                sync_enabled=True
            ).first()

            if global_config:
                sync_fields = global_config.sync_fields
                sync_trigger = {
                    "fields_to_watch": sync_fields if global_config.sync_mode == 'auto' else []
                }
                ApiSyncConfig.objects.create(
                    name=f'Auto-created - {interface.name}',
                    description='Auto-created from global sync config',
                    interface=interface,
                    testcase=step.testcase,
                    step=step,
                    sync_fields=sync_fields,
                    sync_enabled=global_config.sync_enabled,
                    sync_mode=global_config.sync_mode,
                    sync_trigger=sync_trigger,
                    created_by=self.context['request'].user if 'request' in self.context else None
                )

    def _create_step(self, instance, step_data, order):
        from api_interfaces.models import ApiInterface

        step_data.pop('id', None)
        step_data.pop('step_id', None)
        interface_id = step_data.pop('interface_id')
        project_pk = self._get_project_pk()
        interface = ApiInterface.objects.get(id=interface_id, project_id=project_pk)
        user_interface_data = step_data.pop('interface_data', None)

        if user_interface_data:
            interface_data = {
                'method': user_interface_data.get('method', interface.method),
                'url': user_interface_data.get('url', interface.url),
                'headers': user_interface_data.get('headers', []),
                'params': user_interface_data.get('params', []),
                'body': user_interface_data.get('body', {'type': 'raw', 'content': ''}),
                'extract': user_interface_data.get('extract', {}),
                'variables': user_interface_data.get('variables', {}),
                'validators': user_interface_data.get('validators', []),
                'setup_hooks': user_interface_data.get('setup_hooks', []),
                'teardown_hooks': user_interface_data.get('teardown_hooks', []),
                'file_ids': user_interface_data.get('file_ids', interface.file_ids or [])
            }
        else:
            interface_data = self._build_interface_data(interface)

        step_data.pop('order', None)
        file_ids = step_data.pop('file_ids', interface_data.get('file_ids', []))
        step = ApiTestCaseStep.objects.create(
            testcase=instance,
            order=order,
            origin_interface=interface,
            interface_data=interface_data,
            file_ids=file_ids,
            **step_data
        )
        self._create_sync_config(step, interface)
        return step

    def _update_step(self, step, step_data):
        from api_interfaces.models import ApiInterface

        update_data = step_data.copy()
        update_data.pop('id', None)
        update_data.pop('step_id', None)
        update_data.pop('order', None)

        interface_id = update_data.pop('interface_id', None)
        user_interface_data = update_data.pop('interface_data', None)

        if interface_id:
            project_pk = self._get_project_pk()
            interface = ApiInterface.objects.get(id=interface_id, project_id=project_pk)
            interface_data = self._build_interface_data(interface)
            if isinstance(user_interface_data, dict):
                interface_data.update(user_interface_data)
            step.interface_data = interface_data
            step.origin_interface = interface
        elif user_interface_data is not None:
            current_data = step.interface_data or {}
            if isinstance(current_data, dict) and isinstance(user_interface_data, dict):
                current_data.update(user_interface_data)
                step.interface_data = current_data
            else:
                step.interface_data = user_interface_data

        if 'name' in update_data:
            step.name = update_data['name']
        if 'sync_fields' in update_data:
            step.sync_fields = update_data['sync_fields']
        if 'config' in update_data:
            step.config = update_data['config']
        if 'file_ids' in update_data:
            step.file_ids = update_data['file_ids']
        if isinstance(step.interface_data, dict) and step.file_ids:
            step.interface_data['file_ids'] = step.file_ids

        step.save()
        return step

    def create(self, validated_data):
        steps_info = validated_data.pop('steps_info', [])
        validated_data['created_by'] = self.context['request'].user
        instance = super().create(validated_data)

        for step_data in steps_info:
            if 'order' not in step_data:
                max_order = instance.steps.aggregate(
                    max_order=models.Max('order')
                )['max_order'] or 0
                step_data['order'] = max_order + 1
            self._create_step(
                instance=instance,
                step_data=step_data.copy(),
                order=step_data['order']
            )

        instance.refresh_from_db()
        sync_file_references(instance.file_ids or [], instance.project, FileReference.REF_API_TESTCASE, instance.id, self.context.get('request').user if self.context.get('request') else None)
        return instance

    def update(self, instance, validated_data):
        steps_info = validated_data.pop('steps_info', None)
        update_mode = validated_data.pop('update_mode', 'auto')

        instance = super().update(instance, validated_data)

        if steps_info is not None:
            with transaction.atomic():
                existing_steps = {step.order: step for step in instance.steps.all()}
                existing_steps_by_id = {step.id: step for step in instance.steps.all()}
                existing_orders = set(existing_steps.keys())

                for step_data in steps_info:
                    step_id = step_data.get('id') or step_data.get('step_id')
                    if step_id:
                        try:
                            step_id = int(step_id)
                        except (TypeError, ValueError):
                            step_id = None

                    if step_id and step_id in existing_steps_by_id:
                        self._update_step(existing_steps_by_id[step_id], step_data)
                        continue

                    if 'order' not in step_data:
                        max_order = max(existing_orders) if existing_orders else 0
                        step_data['order'] = max_order + 1

                    current_order = step_data['order']

                    if current_order in existing_orders:
                        existing_step = existing_steps[current_order]
                        is_same_interface = (
                            'interface_id' in step_data
                            and existing_step.origin_interface
                            and existing_step.origin_interface.id == step_data['interface_id']
                        )

                        if update_mode == 'update' or is_same_interface:
                            self._update_step(existing_step, step_data)
                            continue

                        # Auto mode: adjust ordering for conflict
                        steps_to_update = instance.steps.filter(
                            order__gte=current_order
                        ).order_by('-order')
                        for s in steps_to_update:
                            s.order += 1
                            s.save()
                        existing_steps = {
                            (s.order + 1 if s.order >= current_order else s.order): s
                            for s in existing_steps.values()
                        }
                        existing_orders = set(existing_steps.keys())
                        existing_orders.add(current_order)
                    else:
                        existing_orders.add(current_order)

                    step = self._create_step(
                        instance=instance,
                        step_data=step_data.copy(),
                        order=current_order
                    )
                    existing_steps[current_order] = step

            instance.refresh_from_db()

        sync_file_references(instance.file_ids or [], instance.project, FileReference.REF_API_TESTCASE, instance.id, self.context.get('request').user if self.context.get('request') else None)
        return instance


class ApiInterfaceCaseStepSerializer(serializers.ModelSerializer):
    interface_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    interface_info = serializers.SerializerMethodField(read_only=True)
    interface_data = serializers.JSONField(required=False)

    class Meta:
        model = ApiInterfaceCaseStep
        fields = [
            'id', 'name', 'role', 'order', 'interface_id',
            'interface_info', 'interface_data', 'config', 'file_ids',
            'sync_fields', 'last_sync_time'
        ]
        read_only_fields = ['last_sync_time']

    def get_interface_info(self, obj):
        if obj.origin_interface:
            return build_interface_info(obj.origin_interface)

        interface_data = obj.interface_data if isinstance(obj.interface_data, dict) else {}
        return {
            'id': 0,
            'name': obj.name,
            'type': interface_data.get('type', 'http'),
            'method': interface_data.get('method'),
            'url': interface_data.get('url') or interface_data.get('sql'),
            'module': None,
            'project': {
                'id': obj.interface_case.project_id,
                'name': obj.interface_case.project.name
            } if obj.interface_case and obj.interface_case.project else None
        }


class ApiInterfaceCaseSerializer(serializers.ModelSerializer):
    steps = ApiInterfaceCaseStepSerializer(many=True, read_only=True)
    steps_info = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
    )
    interface_id = serializers.IntegerField(write_only=True, required=False)
    interface_info = serializers.SerializerMethodField()
    main_step = serializers.SerializerMethodField()
    precondition_count = serializers.SerializerMethodField()
    tags_info = ApiTestCaseTagSerializer(source='tags', many=True, read_only=True)
    group_info = ApiTestCaseGroupSerializer(source='group', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.username', read_only=True, default=''
    )

    class Meta:
        model = ApiInterfaceCase
        fields = [
            'id', 'name', 'description', 'priority',
            'config', 'file_ids', 'project', 'interface', 'interface_id',
            'interface_info', 'group', 'tags', 'tags_info', 'group_info',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
            'steps', 'steps_info', 'main_step', 'precondition_count'
        ]
        read_only_fields = [
            'project', 'interface', 'created_by', 'created_at', 'updated_at'
        ]

    def get_interface_info(self, obj):
        return build_interface_info(obj.interface)

    def get_main_step(self, obj):
        main_step = obj.steps.filter(role=ApiInterfaceCaseStep.ROLE_MAIN).first()
        return ApiInterfaceCaseStepSerializer(main_step).data if main_step else None

    def get_precondition_count(self, obj):
        return obj.steps.filter(role=ApiInterfaceCaseStep.ROLE_PRECONDITION).count()

    def _get_project_pk(self):
        view = self.context.get('view')
        return view.kwargs.get('project_pk') if view else None

    def _get_interface(self, interface_id):
        from api_interfaces.models import ApiInterface

        project_pk = self._get_project_pk()
        return ApiInterface.objects.get(id=interface_id, project_id=project_pk)

    def validate(self, attrs):
        project_pk = self._get_project_pk()
        if self.instance is None and not attrs.get('interface_id'):
            raise serializers.ValidationError({'interface_id': '请选择绑定接口'})

        if 'file_ids' in attrs and project_pk:
            attrs['file_ids'] = validate_file_ids_for_project(
                attrs.get('file_ids'),
                project_pk,
                self.context.get('request').user if self.context.get('request') else None,
            )

        group = attrs.get('group')
        if group and project_pk and str(group.project_id) != str(project_pk):
            raise serializers.ValidationError({'group': '分组不属于当前项目'})

        tags = attrs.get('tags')
        if tags and project_pk:
            invalid_tags = [tag for tag in tags if str(tag.project_id) != str(project_pk)]
            if invalid_tags:
                raise serializers.ValidationError({'tags': '标签不属于当前项目'})

        for step_data in attrs.get('steps_info') or []:
            if 'file_ids' in step_data and project_pk:
                validate_file_ids_for_project(
                    step_data.get('file_ids'),
                    project_pk,
                    self.context.get('request').user if self.context.get('request') else None,
                )
            interface_data = step_data.get('interface_data')
            if isinstance(interface_data, dict) and 'file_ids' in interface_data and project_pk:
                validate_file_ids_for_project(
                    interface_data.get('file_ids'),
                    project_pk,
                    self.context.get('request').user if self.context.get('request') else None,
                )

        return attrs

    def _step_data_from_interface(self, interface, step_data):
        override_data = step_data.pop('interface_data', None)
        interface_data = build_interface_data_snapshot(interface, override_data)
        return interface_data

    def _create_step(self, instance, step_data, order, role):
        step_data = step_data.copy()
        step_data.pop('id', None)
        step_data.pop('step_id', None)
        step_data.pop('order', None)
        step_data.pop('role', None)

        interface_id = step_data.pop('interface_id', None)
        origin_interface = None

        if role == ApiInterfaceCaseStep.ROLE_MAIN:
            origin_interface = instance.interface
        elif interface_id:
            origin_interface = self._get_interface(interface_id)

        if origin_interface:
            interface_data = self._step_data_from_interface(origin_interface, step_data)
            default_name = origin_interface.name
        else:
            interface_data = step_data.pop('interface_data', None)
            if not isinstance(interface_data, dict):
                raise serializers.ValidationError({'steps_info': '步骤必须选择接口或提供 interface_data'})
            default_name = '自定义接口'

        file_ids = step_data.pop('file_ids', interface_data.get('file_ids', []))
        if file_ids:
            interface_data['file_ids'] = file_ids

        return ApiInterfaceCaseStep.objects.create(
            interface_case=instance,
            order=order,
            role=role,
            origin_interface=origin_interface,
            interface_data=interface_data,
            file_ids=file_ids,
            name=step_data.pop('name', default_name),
            **step_data,
        )

    def _replace_steps(self, instance, steps_info):
        with transaction.atomic():
            instance.steps.all().delete()

            ordered_steps = sorted(
                [step.copy() for step in steps_info],
                key=lambda item: item.get('order') or 0,
            )
            preconditions = [
                step for step in ordered_steps
                if step.get('role') != ApiInterfaceCaseStep.ROLE_MAIN
            ]
            main_steps = [
                step for step in ordered_steps
                if step.get('role') == ApiInterfaceCaseStep.ROLE_MAIN
            ]

            order = 1
            for step_data in preconditions:
                self._create_step(
                    instance,
                    step_data,
                    order=order,
                    role=ApiInterfaceCaseStep.ROLE_PRECONDITION,
                )
                order += 1

            main_data = main_steps[-1] if main_steps else {}
            self._create_step(
                instance,
                main_data,
                order=order,
                role=ApiInterfaceCaseStep.ROLE_MAIN,
            )

    def create(self, validated_data):
        interface_id = validated_data.pop('interface_id')
        steps_info = validated_data.pop('steps_info', [])
        validated_data['created_by'] = self.context['request'].user
        validated_data['interface'] = self._get_interface(interface_id)

        instance = super().create(validated_data)
        self._replace_steps(instance, steps_info)
        instance.refresh_from_db()
        sync_file_references(
            instance.file_ids or [],
            instance.project,
            FileReference.REF_API_INTERFACE_CASE,
            instance.id,
            self.context.get('request').user if self.context.get('request') else None,
        )
        return instance

    def update(self, instance, validated_data):
        steps_info = validated_data.pop('steps_info', None)
        interface_id = validated_data.pop('interface_id', None)

        if interface_id:
            validated_data['interface'] = self._get_interface(interface_id)

        instance = super().update(instance, validated_data)

        if steps_info is not None or interface_id:
            if steps_info is None:
                steps_info = []
                for step in instance.steps.all().order_by('order'):
                    step_payload = {
                        'id': step.id,
                        'name': step.name,
                        'role': step.role,
                        'order': step.order,
                        'interface_id': step.origin_interface_id,
                        'interface_data': step.interface_data,
                        'config': step.config,
                        'file_ids': step.file_ids,
                        'sync_fields': step.sync_fields,
                    }
                    if interface_id and step.role == ApiInterfaceCaseStep.ROLE_MAIN:
                        step_payload.pop('interface_data', None)
                    steps_info.append(step_payload)
            self._replace_steps(instance, steps_info)
            instance.refresh_from_db()

        sync_file_references(
            instance.file_ids or [],
            instance.project,
            FileReference.REF_API_INTERFACE_CASE,
            instance.id,
            self.context.get('request').user if self.context.get('request') else None,
        )
        return instance


class ApiTestReportDetailSerializer(serializers.ModelSerializer):
    step_name = serializers.CharField(source='step.name', read_only=True)

    class Meta:
        model = ApiTestReportDetail
        fields = [
            'id', 'step_name', 'success', 'elapsed',
            'request', 'response', 'validators',
            'extracted_variables', 'attachment'
        ]


class ApiTestReportListSerializer(serializers.ModelSerializer):
    testcase_name = serializers.CharField(source='testcase.name', read_only=True)
    success_rate = serializers.SerializerMethodField()
    environment_name = serializers.CharField(
        source='environment.name', read_only=True, default=''
    )
    executed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ApiTestReport
        fields = [
            'id', 'name', 'testcase_name', 'status',
            'success_count', 'fail_count', 'error_count',
            'success_rate', 'duration', 'start_time',
            'environment_name', 'executed_by_name'
        ]

    def get_success_rate(self, obj):
        total = obj.success_count + obj.fail_count + obj.error_count
        if total == 0:
            return "0"
        rate = obj.success_count / total
        return "1" if rate == 1 else f"{rate:.2f}"

    def get_executed_by_name(self, obj):
        if obj.executed_by:
            return obj.executed_by.username
        return ""


class ApiTestReportSerializer(serializers.ModelSerializer):
    testcase_name = serializers.CharField(source='testcase.name', read_only=True)
    details = ApiTestReportDetailSerializer(many=True, read_only=True)
    success_rate = serializers.SerializerMethodField()
    environment_info = serializers.SerializerMethodField()
    executed_by_info = serializers.SerializerMethodField()

    class Meta:
        model = ApiTestReport
        fields = [
            'id', 'name', 'status', 'success_count',
            'fail_count', 'error_count', 'duration',
            'start_time', 'summary', 'testcase',
            'testcase_name', 'environment', 'environment_info',
            'executed_by', 'executed_by_info', 'details', 'success_rate'
        ]
        read_only_fields = [
            'name', 'status', 'success_count', 'fail_count',
            'error_count', 'duration', 'start_time', 'summary',
            'executed_by', 'success_rate', 'environment_info',
            'executed_by_info'
        ]

    def get_success_rate(self, obj):
        total = obj.success_count + obj.fail_count + obj.error_count
        if total == 0:
            return "0"
        rate = obj.success_count / total
        return "1" if rate == 1 else f"{rate:.2f}"

    def get_environment_info(self, obj):
        if obj.environment:
            return {
                'id': obj.environment.id,
                'name': obj.environment.name,
                'base_url': obj.environment.base_url,
                'description': obj.environment.description,
                'project': {
                    'id': obj.environment.project.id,
                    'name': obj.environment.project.name
                }
            }
        return None

    def get_executed_by_info(self, obj):
        if obj.executed_by:
            return {
                'id': obj.executed_by.id,
                'username': obj.executed_by.username,
                'email': obj.executed_by.email,
                'first_name': obj.executed_by.first_name,
                'last_name': obj.executed_by.last_name
            }
        return None


class ApiInterfaceCaseReportDetailSerializer(serializers.ModelSerializer):
    step_name = serializers.CharField(source='step.name', read_only=True)

    class Meta:
        model = ApiInterfaceCaseReportDetail
        fields = [
            'id', 'step_name', 'success', 'elapsed',
            'request', 'response', 'validators',
            'extracted_variables', 'attachment'
        ]


class ApiInterfaceCaseReportListSerializer(serializers.ModelSerializer):
    testcase = serializers.IntegerField(source='interface_case_id', read_only=True)
    testcase_name = serializers.CharField(source='interface_case.name', read_only=True)
    interface_name = serializers.CharField(source='interface_case.interface.name', read_only=True)
    success_rate = serializers.SerializerMethodField()
    environment_name = serializers.CharField(
        source='environment.name', read_only=True, default=''
    )
    executed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ApiInterfaceCaseReport
        fields = [
            'id', 'name', 'testcase', 'testcase_name', 'interface_name', 'status',
            'success_count', 'fail_count', 'error_count',
            'success_rate', 'duration', 'start_time',
            'environment_name', 'executed_by_name'
        ]

    def get_success_rate(self, obj):
        total = obj.success_count + obj.fail_count + obj.error_count
        if total == 0:
            return "0"
        rate = obj.success_count / total
        return "1" if rate == 1 else f"{rate:.2f}"

    def get_executed_by_name(self, obj):
        if obj.executed_by:
            return obj.executed_by.username
        return ""


class ApiInterfaceCaseReportSerializer(serializers.ModelSerializer):
    testcase = serializers.IntegerField(source='interface_case_id', read_only=True)
    testcase_name = serializers.CharField(source='interface_case.name', read_only=True)
    interface_name = serializers.CharField(source='interface_case.interface.name', read_only=True)
    details = ApiInterfaceCaseReportDetailSerializer(many=True, read_only=True)
    success_rate = serializers.SerializerMethodField()
    environment_info = serializers.SerializerMethodField()
    executed_by_info = serializers.SerializerMethodField()

    class Meta:
        model = ApiInterfaceCaseReport
        fields = [
            'id', 'name', 'status', 'success_count',
            'fail_count', 'error_count', 'duration',
            'start_time', 'summary', 'interface_case',
            'testcase', 'testcase_name', 'interface_name',
            'environment', 'environment_info',
            'executed_by', 'executed_by_info', 'details', 'success_rate'
        ]
        read_only_fields = [
            'name', 'status', 'success_count', 'fail_count',
            'error_count', 'duration', 'start_time', 'summary',
            'executed_by', 'success_rate', 'environment_info',
            'executed_by_info'
        ]

    def get_success_rate(self, obj):
        total = obj.success_count + obj.fail_count + obj.error_count
        if total == 0:
            return "0"
        rate = obj.success_count / total
        return "1" if rate == 1 else f"{rate:.2f}"

    def get_environment_info(self, obj):
        if obj.environment:
            return {
                'id': obj.environment.id,
                'name': obj.environment.name,
                'base_url': obj.environment.base_url,
                'description': obj.environment.description,
                'project': {
                    'id': obj.environment.project.id,
                    'name': obj.environment.project.name
                }
            }
        return None

    def get_executed_by_info(self, obj):
        if obj.executed_by:
            return {
                'id': obj.executed_by.id,
                'username': obj.executed_by.username,
                'email': obj.executed_by.email,
                'first_name': obj.executed_by.first_name,
                'last_name': obj.executed_by.last_name
            }
        return None


class InterfaceOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    method = serializers.CharField()
    url = serializers.CharField()
