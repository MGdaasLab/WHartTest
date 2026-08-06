from rest_framework import serializers
from .models import ApiCustomFunction


class ApiCustomFunctionSerializer(serializers.ModelSerializer):
    code = serializers.CharField(trim_whitespace=False)
    created_by_name = serializers.CharField(
        source='created_by.username', read_only=True, default=''
    )

    class Meta:
        model = ApiCustomFunction
        fields = [
            'id', 'name', 'code', 'description', 'project',
            'is_active', 'created_by', 'created_by_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'project']

    def validate_code(self, value):
        if len(value) > 10000:
            raise serializers.ValidationError(
                "Function code must not exceed 10000 characters."
            )
        if not value.strip().startswith('def '):
            raise serializers.ValidationError(
                "Code must start with a 'def' function definition."
            )
        forbidden_keywords = [
            'eval(', 'exec(', 'execfile(',
            'import os', 'import subprocess', 'import sys',
            '__import__', 'open(', 'file(',
            'remove(', 'rmdir(', 'unlink(',
            'system(', 'popen(', 'spawn',
        ]
        for keyword in forbidden_keywords:
            if keyword in value:
                raise serializers.ValidationError(
                    f"Code must not contain dangerous function or module: {keyword}"
                )
        return value

    def validate(self, attrs):
        view = self.context.get('view')
        if view and getattr(view, 'action', None) == 'create':
            project_pk = view.kwargs.get('project_pk')
            name = attrs.get('name')
            if (
                project_pk
                and name
                and ApiCustomFunction.objects.filter(
                    project_id=project_pk,
                    name=name,
                ).exists()
            ):
                raise serializers.ValidationError(
                    {"name": f"A function named '{name}' already exists in this project."}
                )
        return attrs
