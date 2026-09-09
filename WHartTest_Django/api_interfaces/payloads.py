import re
import json
from typing import Any


BODY_TYPES = {'none', 'form-data', 'x-www-form-urlencoded', 'raw', 'binary'}


def stringify_pair_value(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def normalize_key_value_pairs(value: Any, field_name: str) -> list[dict[str, Any]]:
    if value is None:
        return []

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f'{field_name} must be a list or object.') from exc

    if isinstance(value, dict):
        return [
            {
                'key': str(key),
                'value': stringify_pair_value(item),
                'description': '',
                'enabled': True,
            }
            for key, item in value.items()
        ]

    if not isinstance(value, list):
        raise ValueError(f'{field_name} must be a list or object.')

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f'{field_name}[{index}] must be an object.')

        key = item.get('key')
        if key in (None, ''):
            raise ValueError(f'{field_name}[{index}].key is required.')

        normalized_item = {
            'key': str(key),
            'value': stringify_pair_value(item.get('value', '')),
            'description': stringify_pair_value(item.get('description', '')),
            'enabled': bool(item.get('enabled', True)),
        }
        value_type = item.get('value_type') or item.get('type')
        if value_type:
            normalized_item['value_type'] = str(value_type)
        if item.get('file_id') not in (None, ''):
            try:
                normalized_item['file_id'] = int(item.get('file_id'))
            except (TypeError, ValueError) as exc:
                raise ValueError(f'{field_name}[{index}].file_id must be an integer.') from exc
        if item.get('file_name'):
            normalized_item['file_name'] = stringify_pair_value(item.get('file_name'))
        if item.get('mime_type'):
            normalized_item['mime_type'] = stringify_pair_value(item.get('mime_type'))
        normalized.append(normalized_item)

    return normalized


def flatten_key_value_pairs(value: Any) -> dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}

    if isinstance(value, dict):
        return value

    if not isinstance(value, list):
        return {}

    flattened: dict[str, Any] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        if not item.get('enabled', True):
            continue
        key = item.get('key')
        if key in (None, ''):
            continue
        flattened[str(key)] = item.get('value', '')

    return flattened


def normalize_request_body(value: Any) -> dict[str, Any]:
    if value is None:
        return {'type': 'none', 'content': None}

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {'type': 'none', 'content': None}
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {'type': 'raw', 'content': value}

    if isinstance(value, dict):
        if 'type' in value:
            body_type = value.get('type') or 'none'
            if body_type not in BODY_TYPES:
                raise ValueError(
                    f"body.type must be one of: {', '.join(sorted(BODY_TYPES))}."
                )

            if body_type == 'none':
                return {'type': 'none', 'content': None}

            content = value.get('content')
            if body_type in {'form-data', 'x-www-form-urlencoded'}:
                return {
                    'type': body_type,
                    'content': normalize_key_value_pairs(content, 'body.content'),
                }

            return {'type': body_type, 'content': content}

        if not value:
            return {'type': 'none', 'content': None}

        return {'type': 'raw', 'content': value}

    if isinstance(value, list):
        return {'type': 'raw', 'content': value}

    return {'type': 'raw', 'content': value}


def prepare_request_body_for_runner(value: Any) -> Any:
    body = normalize_request_body(value)
    body_type = body['type']
    content = body['content']

    if body_type == 'none':
        return None

    if body_type == 'raw':
        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content
        return content

    if body_type in {'form-data', 'x-www-form-urlencoded'}:
        return flatten_key_value_pairs(content)

    return content


def apply_path_params_to_url(url: str, path_params: Any, variables: dict[str, Any] | None = None) -> str:
    """Replace path parameter placeholders in URL with values from path_params.

    Supports both '{param}' / '{ param }' and ':param' formats.
    Also resolves variable references (e.g. '$var_name') if variables dict is provided.
    """
    if not url:
        return ''
    if not path_params:
        return url

    flattened = flatten_key_value_pairs(path_params)
    if not flattened:
        return url

    result = url
    variables = variables or {}

    for key, val in flattened.items():
        if not key:
            continue
        if isinstance(val, str) and val.startswith('$'):
            var_name = val[1:]
            val = variables.get(var_name, val)
        val_str = str(val) if val is not None else ''

        result = re.sub(r'\{\s*' + re.escape(str(key)) + r'\s*\}', lambda _: val_str, result)
        result = re.sub(r':' + re.escape(str(key)) + r'(?=(/|\?|#|$))', lambda _: val_str, result)

    return result
