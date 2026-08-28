import json
from typing import Any, Dict, Optional

from .models import ApiEnvironment, ApiEnvironmentVariable


PROJECT_VARIABLE_TYPE = 'project'


def infer_environment_variable_type(value: Any) -> str:
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, int) and not isinstance(value, bool):
        return 'integer'
    if isinstance(value, float):
        return 'float'
    if isinstance(value, list):
        return 'list'
    if isinstance(value, dict):
        return 'dict'
    if value is None:
        return 'json'
    return 'string'


def serialize_environment_variable_value(value: Any) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, (list, dict)) or value is None:
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def persist_project_extract_variables(
    *,
    project_id: int,
    environment_id: Optional[int],
    extracted_variables: Optional[Dict[str, Any]],
    extract_meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    result = {
        'matched_count': 0,
        'created_count': 0,
        'updated_count': 0,
        'skipped_no_environment': False,
    }

    if not isinstance(extracted_variables, dict) or not isinstance(extract_meta, dict):
        return result

    matched_items = [
        (name, value)
        for name, value in extracted_variables.items()
        if isinstance(extract_meta.get(name), dict)
        and extract_meta[name].get('variable_type') == PROJECT_VARIABLE_TYPE
    ]

    if not matched_items:
        return result

    result['matched_count'] = len(matched_items)

    if not environment_id:
        result['skipped_no_environment'] = True
        return result

    environment = ApiEnvironment.objects.filter(
        id=environment_id,
        project_id=project_id,
    ).first()
    if environment is None:
        return result

    for variable_name, value in matched_items:
        serialized_value = serialize_environment_variable_value(value)
        variable, created = ApiEnvironmentVariable.objects.get_or_create(
            environment=environment,
            name=variable_name,
            defaults={
                'value': serialized_value,
                'type': infer_environment_variable_type(value),
            },
        )

        if created:
            result['created_count'] += 1
            continue

        if variable.value != serialized_value:
            variable.value = serialized_value
            variable.save(update_fields=['value', 'updated_at'])
            result['updated_count'] += 1

    return result