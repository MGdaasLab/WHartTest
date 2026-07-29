from rest_framework import serializers
from .models import ApiInterface, ApiInterfaceResult
from .payloads import normalize_key_value_pairs, normalize_request_body
from .validators import SUPPORTED_COMPARATORS, is_validator_meta_key
from file_management.services import validate_file_ids, sync_file_references
from file_management.models import FileReference


EXTRACT_VARIABLE_TYPES = {'temporary', 'project'}
EXTRACT_SOURCES = {'response', 'request'}


class ApiInterfaceModuleInfoSerializer(serializers.Serializer):
    """Lightweight module serializer for embedding in interface detail."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    parent = serializers.IntegerField(source='parent_id', allow_null=True)


class ApiInterfaceSerializer(serializers.ModelSerializer):
    module_info = ApiInterfaceModuleInfoSerializer(source='module', read_only=True)

    class Meta:
        model = ApiInterface
        fields = '__all__'
        read_only_fields = ['project', 'created_by', 'created_at', 'updated_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        try:
            data['headers'] = normalize_key_value_pairs(data.get('headers'), 'headers')
        except ValueError:
            data['headers'] = []
        try:
            data['params'] = normalize_key_value_pairs(data.get('params'), 'params')
        except ValueError:
            data['params'] = []
        try:
            data['body'] = normalize_request_body(data.get('body'))
        except ValueError:
            data['body'] = {'type': 'raw', 'content': data.get('body')}
        # Strip module_info from list responses, only include in detail
        request = self.context.get('request')
        view_kwargs = getattr(self.context.get('view'), 'kwargs', {}) or {}
        if request and not view_kwargs.get('pk'):
            data.pop('module_info', None)
        return data

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        name = attrs.get('name')
        project = attrs.get('project') or (instance.project if instance else None)
        view = self.context.get('view')
        view_kwargs = getattr(view, 'kwargs', {}) or {}
        project_id = project.id if project else None

        if project_id is None and view:
            project_pk = view_kwargs.get('project_pk')
            if project_pk is not None:
                project_id = int(project_pk)

        if name and project_id is not None:
            query = ApiInterface.objects.filter(name=name, project_id=project_id)
            if instance:
                query = query.exclude(pk=instance.pk)
            if query.exists():
                raise serializers.ValidationError(
                    {"name": [f"An interface named '{name}' already exists in this project."]}
                )

        module = attrs.get('module', instance.module if instance else None)
        if module and project_id is not None and module.project_id != project_id:
            raise serializers.ValidationError(
                {"module": "Module must belong to the same project."}
            )

        if 'file_ids' in attrs:
            if project_id is None:
                raise serializers.ValidationError({"file_ids": "project is required to validate file_ids."})
            from projects.models import Project
            try:
                project_obj = Project.objects.get(id=project_id)
            except Project.DoesNotExist as exc:
                raise serializers.ValidationError({"project": "Project does not exist."}) from exc
            validate_file_ids(attrs.get('file_ids'), project_obj, self.context.get('request').user if self.context.get('request') else None)

        if 'headers' in attrs:
            try:
                attrs['headers'] = normalize_key_value_pairs(attrs.get('headers'), 'headers')
            except ValueError as exc:
                raise serializers.ValidationError({"headers": str(exc)}) from exc
        elif instance is None:
            attrs['headers'] = []

        if 'params' in attrs:
            try:
                attrs['params'] = normalize_key_value_pairs(attrs.get('params'), 'params')
            except ValueError as exc:
                raise serializers.ValidationError({"params": str(exc)}) from exc
        elif instance is None:
            attrs['params'] = []

        if 'body' in attrs:
            try:
                attrs['body'] = normalize_request_body(attrs.get('body'))
            except ValueError as exc:
                raise serializers.ValidationError({"body": str(exc)}) from exc
        elif instance is None:
            attrs['body'] = {'type': 'none', 'content': None}

        setup_hooks = attrs.get('setup_hooks', [])
        if not isinstance(setup_hooks, list):
            raise serializers.ValidationError({"setup_hooks": "Must be a list."})

        teardown_hooks = attrs.get('teardown_hooks', [])
        if not isinstance(teardown_hooks, list):
            raise serializers.ValidationError({"teardown_hooks": "Must be a list."})

        variables = attrs.get('variables', {})
        if not isinstance(variables, dict):
            raise serializers.ValidationError({"variables": "Must be a dict."})

        validators = attrs.get('validators', [])
        if not isinstance(validators, list):
            raise serializers.ValidationError({"validators": "Must be a list."})

        for validator in validators:
            if not isinstance(validator, dict):
                raise serializers.ValidationError({"validators": "Each validator must be a dict."})
            if "check" in validator and "expect" in validator:
                continue
            comparator_keys = [
                key for key in validator.keys()
                if not is_validator_meta_key(key)
            ]
            supported_keys = [
                key for key in comparator_keys
                if key in SUPPORTED_COMPARATORS
            ]
            unsupported_keys = [
                key for key in comparator_keys
                if key not in SUPPORTED_COMPARATORS
            ]
            if unsupported_keys or len(supported_keys) != 1:
                raise serializers.ValidationError({
                    "validators": (
                        f"Validator must use a supported comparator: "
                        f"{', '.join(sorted(SUPPORTED_COMPARATORS))}, or use check/expect format."
                    )
                })
            comparator = supported_keys[0]
            if not isinstance(validator[comparator], list) or len(validator[comparator]) != 2:
                raise serializers.ValidationError({
                    "validators": f"Validator '{comparator}' must be a list of [field, expected_value]."
                })

        extract = attrs.get('extract', {})
        if not isinstance(extract, dict):
            raise serializers.ValidationError({"extract": "Must be a dict."})

        extract_meta = attrs.get(
            'extract_meta',
            instance.extract_meta if instance else {},
        )
        if not isinstance(extract_meta, dict):
            raise serializers.ValidationError({"extract_meta": "Must be a dict."})

        normalized_extract_meta = {}
        for variable_name, meta in extract_meta.items():
            if not isinstance(meta, dict):
                raise serializers.ValidationError({
                    "extract_meta": f"Meta for variable '{variable_name}' must be a dict."
                })

            variable_type = meta.get('variable_type', 'temporary')
            if variable_type not in EXTRACT_VARIABLE_TYPES:
                raise serializers.ValidationError({
                    "extract_meta": (
                        f"Variable '{variable_name}' uses unsupported variable_type '{variable_type}'."
                    )
                })

            normalized_extract_meta[variable_name] = {
                'variable_type': variable_type,
            }
            if 'source' in meta:
                source = meta.get('source', 'response')
                if source not in EXTRACT_SOURCES:
                    raise serializers.ValidationError({
                        "extract_meta": (
                            f"Variable '{variable_name}' uses unsupported source '{source}'."
                        )
                    })
                normalized_extract_meta[variable_name]['source'] = source

        extract_keys = set(extract.keys())
        attrs['extract_meta'] = {
            variable_name: meta
            for variable_name, meta in normalized_extract_meta.items()
            if variable_name in extract_keys
        }

        return attrs


class ApiInterfaceResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiInterfaceResult
        fields = '__all__'
        read_only_fields = ['executed_by', 'executed_at']


# 附件引用关系维护
_original_api_interface_create = ApiInterfaceSerializer.create if hasattr(ApiInterfaceSerializer, 'create') else None
_original_api_interface_update = ApiInterfaceSerializer.update if hasattr(ApiInterfaceSerializer, 'update') else None

def _api_interface_serializer_create(self, validated_data):
    instance = super(ApiInterfaceSerializer, self).create(validated_data)
    sync_file_references(instance.file_ids or [], instance.project, FileReference.REF_API_INTERFACE, instance.id, self.context.get('request').user if self.context.get('request') else None)
    return instance

def _api_interface_serializer_update(self, instance, validated_data):
    instance = super(ApiInterfaceSerializer, self).update(instance, validated_data)
    if 'file_ids' in validated_data:
        sync_file_references(instance.file_ids or [], instance.project, FileReference.REF_API_INTERFACE, instance.id, self.context.get('request').user if self.context.get('request') else None)
    return instance

ApiInterfaceSerializer.create = _api_interface_serializer_create
ApiInterfaceSerializer.update = _api_interface_serializer_update
