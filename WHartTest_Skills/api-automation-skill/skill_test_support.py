import json
import subprocess
import sys
import uuid
from pathlib import Path
from urllib import error, parse, request

ROOT_DIR = Path(__file__).resolve().parents[2]
SKILL_PATH = Path(__file__).resolve().with_name('api_automation_tools.py')
BASE_URL = 'http://127.0.0.1:8000'
API_KEY = 'wharttest-default-mcp-key-2025'
DEFAULT_HEADERS = {
    'accept': 'application/json',
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
}


def _decode_json(raw_body):
    text = raw_body.decode('utf-8', errors='replace')
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


class BackendAdmin:
    def __init__(self, base_url=BASE_URL, api_key=API_KEY):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
            'X-API-Key': api_key,
        }

    def request(self, method, path, payload=None, params=None):
        url = f'{self.base_url}{path}'
        if params:
            query = parse.urlencode(params, doseq=True)
            url = f'{url}?{query}'
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with request.urlopen(req, timeout=60) as response:
                return response.status, _decode_json(response.read())
        except error.HTTPError as exc:
            return exc.code, _decode_json(exc.read())

    def create_project(self, prefix='api-skill-fulltest'):
        suffix = uuid.uuid4().hex[:8]
        status, body = self.request(
            'POST',
            '/api/projects/',
            payload={
                'name': f'{prefix}-{suffix}',
                'description': 'api automation skill full integration test',
            },
        )
        if status not in {200, 201} or body.get('status') != 'success':
            raise AssertionError(f'创建测试项目失败: status={status}, body={body}')
        return body['data']

    def delete_project(self, project_id):
        status, body = self.request('DELETE', f'/api/projects/{project_id}/')
        if status not in {200, 204}:
            raise AssertionError(f'删除测试项目失败: status={status}, body={body}')
        if isinstance(body, dict) and body.get('status') == 'error':
            raise AssertionError(f'删除测试项目失败: body={body}')


class SkillCLI:
    def __init__(self, project_id, base_url=BASE_URL, api_key=API_KEY):
        self.project_id = project_id
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.executed_actions = set()

    def run(self, action, payload=None, params=None, expect_success=True, **id_args):
        command = [
            sys.executable,
            str(SKILL_PATH),
            '--action',
            action,
            '--project_id',
            str(self.project_id),
            '--base_url',
            self.base_url,
            '--api_key',
            self.api_key,
        ]
        if payload is not None:
            command.extend(['--payload', json.dumps(payload, ensure_ascii=False)])
        if params is not None:
            command.extend(['--params', json.dumps(params, ensure_ascii=False)])
        for key, value in id_args.items():
            if value is not None:
                command.extend([f'--{key}', str(value)])

        completed = subprocess.run(
            command,
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.executed_actions.add(action)

        stdout = completed.stdout.strip()
        try:
            result = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f'action={action} 返回了非 JSON 输出: stdout={completed.stdout!r}, stderr={completed.stderr!r}'
            ) from exc

        if expect_success:
            if completed.returncode != 0 or result.get('status') != 'success':
                raise AssertionError(
                    f'action={action} 执行失败: returncode={completed.returncode}, result={result}, stderr={completed.stderr}'
                )
        elif result.get('status') != 'error':
            raise AssertionError(f'action={action} 预期失败但实际结果不是 error: {result}')
        return result


class ResultReader:
    @staticmethod
    def data(result):
        return result.get('data')

    @staticmethod
    def extract_id(result):
        data = ResultReader.data(result)
        if isinstance(data, dict) and 'id' in data:
            return data['id']
        raise AssertionError(f'无法从结果中提取 id: {result}')

    @staticmethod
    def items(result):
        data = ResultReader.data(result)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ('results', 'items', 'records', 'data'):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    @staticmethod
    def find_by_name(result, name):
        for item in ResultReader.items(result):
            if isinstance(item, dict) and item.get('name') == name:
                return item
        raise AssertionError(f'未找到名称为 {name!r} 的资源: {result}')

    @staticmethod
    def latest_id(result):
        items = ResultReader.items(result)
        if items and isinstance(items[0], dict) and 'id' in items[0]:
            return items[0]['id']
        raise AssertionError(f'无法从列表结果中提取最新 id: {result}')
