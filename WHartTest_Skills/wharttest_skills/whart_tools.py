# -*- coding: utf-8 -*-
import sys
import io

# Windows 终端 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import argparse
import json
import mimetypes
import os
import time
import requests
from pathlib import Path
from urllib.parse import unquote

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

# 配置（运行时读取环境变量，避免 import 时固化导致父进程注入的 Key 失效）
_DEFAULT_BASE_URL = "http://127.0.0.1:8000"
_DEFAULT_API_KEY = "wharttest-default-mcp-key-2025"
IMAGE_MIME_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
}


def _base_url() -> str:
    return (os.environ.get("WHARTTEST_BACKEND_URL") or _DEFAULT_BASE_URL).rstrip("/")


def _api_key() -> str:
    return (os.environ.get("WHARTTEST_API_KEY") or _DEFAULT_API_KEY).strip()


def _headers() -> dict:
    return {
        "accept": "application/json, text/plain,*/*",
        "X-API-Key": _api_key(),
    }


# 兼容旧代码/测试中对模块级常量的引用
BASE_URL = _base_url()
API_KEY = _api_key()
HEADERS = _headers()


def _response_json(resp):
    """解析 JSON 响应，兼容空响应与纯文本错误。"""
    try:
        return resp.json()
    except Exception:
        text = getattr(resp, 'text', '')
        return {"message": text} if text else {}


def _parse_csv_ints(value, field_name="ids"):
    if value in (None, ''):
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_text = str(value).strip()
        try:
            loaded = json.loads(raw_text)
            raw_items = loaded if isinstance(loaded, list) else [loaded]
        except json.JSONDecodeError:
            raw_items = [item.strip() for item in raw_text.split(',') if item.strip()]

    result = []
    for item in raw_items:
        try:
            int_value = int(item)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} 包含非法 ID: {item}")
        if int_value not in result:
            result.append(int_value)
    return result


def _parse_optional_bool(value, field_name):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in ('1', 'true', 'yes', 'y', 'on'):
        return True
    if normalized in ('0', 'false', 'no', 'n', 'off'):
        return False
    raise ValueError(f"{field_name} 必须是 true/false")


def _resolve_local_file_path(file_path: str):
    normalized_path = (file_path or '').strip()
    if not normalized_path:
        return normalized_path
    if os.path.exists(normalized_path):
        return normalized_path
    if os.sep not in normalized_path and '/' not in normalized_path:
        cwd_path = os.path.join(os.getcwd(), normalized_path)
        if os.path.exists(cwd_path):
            return cwd_path
    return normalized_path


def _extract_filename_from_content_disposition(content_disposition: str):
    if not content_disposition:
        return ''
    for part in content_disposition.split(';'):
        item = part.strip()
        if item.lower().startswith("filename*="):
            value = item.split('=', 1)[1].strip().strip('"')
            if "''" in value:
                value = value.split("''", 1)[1]
            return os.path.basename(unquote(value))
        if item.lower().startswith("filename="):
            value = item.split('=', 1)[1].strip().strip('"')
            return os.path.basename(unquote(value))
    return ''


def _save_response_to_file(resp, output_path: str):
    target_path = os.path.abspath(output_path)
    target_dir = os.path.dirname(target_path)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)
    with open(target_path, 'wb') as f:
        if hasattr(resp, 'iter_content'):
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        else:
            f.write(getattr(resp, 'content', b''))
    return target_path


def _extract_tree(nodes_list, id_key, name_key):
    """递归提取树形结构"""
    result = []
    if not isinstance(nodes_list, list):
        return result
    for node in nodes_list:
        if isinstance(node, dict):
            result.append({id_key: node.get("id"), name_key: node.get("name")})
            children = node.get("children")
            if isinstance(children, list):
                result.extend(_extract_tree(children, id_key, name_key))
    return result


def get_projects():
    """获取项目列表"""
    url = f"{_base_url()}/api/projects/"
    try:
        resp = requests.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return _extract_tree(data, "project_id", "project_name")
    except Exception as e:
        return {"error": str(e)}


def get_modules(project_id: int):
    """获取项目下的模块"""
    url = f"{_base_url()}/api/projects/{project_id}/testcase-modules/"
    try:
        resp = requests.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return _extract_tree(data, "module_id", "module_name")
    except Exception as e:
        return {"error": str(e)}


def add_module(project_id: int, name: str, parent_id: int = None):
    """新增用例模块"""
    url = f"{_base_url()}/api/projects/{project_id}/testcase-modules/"
    data = {
        "name": name,
    }
    if parent_id is not None:
        data["parent"] = parent_id
    try:
        resp = requests.post(url, headers=_headers(), json=data)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 201:
            return {"message": "保存成功", "module": {"id": result.get("data", {}).get("id"), "name": result.get("data", {}).get("name", name)}}
        return {"message": "保存失败", "response": result}
    except Exception as e:
        return {"error": str(e)}


def get_levels():
    """获取用例等级"""
    return ["P0", "P1", "P2", "P3"]


def get_testcases(project_id: int, module_id: int):
    """获取用例列表"""
    url = f"{_base_url()}/api/projects/{project_id}/testcases/?page=1&page_size=1000&module_id={module_id}"
    try:
        resp = requests.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [{"case_id": i.get("id"), "case_name": i.get("name")} for i in data]
    except Exception as e:
        return {"error": str(e)}


def get_testcase_detail(project_id: int, case_id: int):
    """获取用例详情"""
    url = f"{_base_url()}/api/projects/{project_id}/testcases/{case_id}/"
    try:
        resp = requests.get(url, headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", {})
    except Exception as e:
        return {"error": str(e)}


def add_testcase(project_id: int, module_id: int, name: str, level: str = "P1",
                 precondition: str = "无", steps: list = None, notes: str = "",
                 review_status: str = "pending_review", test_type: str = "functional"):
    """新增测试用例"""
    url = f"{_base_url()}/api/projects/{project_id}/testcases/"
    data = {
        "name": name,
        "precondition": precondition,
        "level": level,
        "module_id": module_id,
        "steps": steps or [],
        "notes": notes,
        "review_status": review_status,
        "test_type": test_type
    }
    try:
        resp = requests.post(url, headers=_headers(), json=data)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 201:
            return {"message": "保存成功", "testcase": {"id": result.get("data", {}).get("id"),"name": result.get("data", {}).get("name", name)}}
        return {"message": "保存失败", "response": result}
    except Exception as e:
        return {"error": str(e)}


def edit_testcase(project_id: int, case_id: int, name: str = None, level: str = None,
                  module_id: int = None, precondition: str = None, steps: list = None, notes: str = None,
                  review_status: str = None, test_type: str = None, is_optimization: bool = False):
    """编辑测试用例"""
    url = f"{_base_url()}/api/projects/{project_id}/testcases/{case_id}/"
    data = {}
    if name is not None: data["name"] = name
    if level is not None: data["level"] = level
    if module_id is not None: data["module_id"] = module_id
    if precondition is not None: data["precondition"] = precondition
    if steps is not None: data["steps"] = steps
    if notes is not None: data["notes"] = notes
    if test_type is not None: data["test_type"] = test_type

    # 处理优化工作流
    if is_optimization:
        data["review_status"] = "optimization_pending_review"
    elif review_status is not None:
        data["review_status"] = review_status

    try:
        resp = requests.patch(url, headers=_headers(), json=data)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 200:
            status_msg = ""
            if is_optimization:
                status_msg = "，状态已自动设为「优化待审核」"
            elif review_status:
                status_msg = f"，状态已设为「{review_status}」"
            return {
                "success": True,
                "message": f"用例ID {case_id} 编辑成功{status_msg}。任务已完成，无需再次编辑或查询。"
            }
        return {"success": False, "message": "编辑失败", "response": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _collect_screenshot_candidate_dirs():
    """收集截图搜索目录，优先约定目录，再兼容常见临时目录。"""
    candidates = []
    for env_key in ('SCREENSHOT_DIR', 'PLAYWRIGHT_SCREENSHOT_DIR', 'AGENT_BROWSER_SCREENSHOT_DIR'):
        value = os.environ.get(env_key, '').strip()
        if value:
            candidates.append(value)

    current_dir = os.getcwd().strip()
    if current_dir:
        candidates.append(current_dir)

    temp_roots = [
        os.environ.get('TMPDIR', '').strip(),
        os.environ.get('TEMP', '').strip(),
        os.environ.get('TMP', '').strip(),
        '/tmp',
    ]
    for temp_root in temp_roots:
        if not temp_root:
            continue
        candidates.extend([
            temp_root,
            os.path.join(temp_root, 'screenshots'),
            os.path.join(temp_root, 'playwright-output'),
        ])

    normalized = []
    seen = set()
    for path in candidates:
        if not path:
            continue
        abs_path = os.path.abspath(path)
        if abs_path in seen:
            continue
        seen.add(abs_path)
        normalized.append(abs_path)
    return normalized


def _collect_screenshot_recursive_dirs():
    recursive_dirs = set()
    for env_key in ('SCREENSHOT_DIR', 'PLAYWRIGHT_SCREENSHOT_DIR', 'AGENT_BROWSER_SCREENSHOT_DIR'):
        value = os.environ.get(env_key, '').strip()
        if value:
            recursive_dirs.add(os.path.abspath(value))

    for temp_root in (
        os.environ.get('TMPDIR', '').strip(),
        os.environ.get('TEMP', '').strip(),
        os.environ.get('TMP', '').strip(),
        '/tmp',
    ):
        if not temp_root:
            continue
        recursive_dirs.add(os.path.abspath(os.path.join(temp_root, 'screenshots')))
        recursive_dirs.add(os.path.abspath(os.path.join(temp_root, 'playwright-output')))
    return recursive_dirs


def _search_file_in_dirs(target_name: str, search_dirs: list[str]):
    if not target_name:
        return None

    basename = os.path.basename(target_name)
    recursive_dirs = _collect_screenshot_recursive_dirs()
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue

        direct_path = os.path.join(search_dir, target_name)
        if os.path.exists(direct_path):
            return direct_path

        if not basename or os.path.abspath(search_dir) not in recursive_dirs:
            continue

        for current_root, _, files in os.walk(search_dir):
            if basename in files:
                return os.path.join(current_root, basename)

    return None


def _resolve_screenshot_file_path(file_path: str):
    """解析截图路径，兼容固定 SCREENSHOT_DIR 与临时目录兜底。"""
    normalized_path = (file_path or '').strip()
    if not normalized_path:
        return normalized_path, []

    if os.path.exists(normalized_path):
        return normalized_path, []

    search_dirs = _collect_screenshot_candidate_dirs()
    candidate_names = []
    if os.sep not in normalized_path and '/' not in normalized_path:
        candidate_names.append(normalized_path)

    basename = os.path.basename(normalized_path)
    if basename and basename not in candidate_names:
        candidate_names.append(basename)

    for candidate_name in candidate_names:
        resolved_path = _search_file_in_dirs(candidate_name, search_dirs)
        if resolved_path:
            return resolved_path, search_dirs

    return normalized_path, search_dirs


def _build_missing_file_error(original_path: str, searched_dirs: list[str]):
    if not searched_dirs:
        return {"error": f"文件不存在: {original_path}"}
    return {
        "error": f"文件不存在: {original_path}；已搜索目录: {', '.join(searched_dirs)}"
    }


def upload_screenshot(project_id: int, case_id: int, file_path: str, title: str,
                      description: str = "", step_number: int = None, page_url: str = ""):
    """上传单张截图"""
    original_file_path = file_path
    file_path, searched_dirs = _resolve_screenshot_file_path(file_path)

    if not os.path.exists(file_path):
        return _build_missing_file_error(original_file_path, searched_dirs)

    url = f"{_base_url()}/api/projects/{project_id}/testcases/{case_id}/upload-screenshots/"
    ext = os.path.splitext(file_path)[1].lower()
    content_type = IMAGE_MIME_TYPES.get(ext, 'image/png')

    try:
        with open(file_path, 'rb') as f:
            files = {'screenshots': (os.path.basename(file_path), f, content_type)}
            data = {'title': title}
            if description: data['description'] = description
            if step_number is not None: data['step_number'] = str(step_number)
            if page_url: data['page_url'] = page_url

            resp = requests.post(url, headers=_headers(), files=files, data=data)
            resp.raise_for_status()
            return {"message": f"截图 '{title}' 上传成功"}
    except Exception as e:
        return {"error": str(e)}


def upload_screenshots(project_id: int, case_id: int, file_paths: str, title: str,
                       description: str = "", step_number: int = None, page_url: str = ""):
    """批量上传截图（最多10张）"""
    paths = [p.strip() for p in file_paths.split(',') if p.strip()]
    if not paths:
        return {"error": "未提供文件路径"}
    if len(paths) > 10:
        return {"error": "一次最多上传10张图片"}

    resolved_paths = []
    for fp in paths:
        resolved_path, searched_dirs = _resolve_screenshot_file_path(fp)
        if not os.path.exists(resolved_path):
            return _build_missing_file_error(fp, searched_dirs)
        resolved_paths.append(resolved_path)

    url = f"{_base_url()}/api/projects/{project_id}/testcases/{case_id}/upload-screenshots/"

    try:
        files = []
        file_handles = []
        for fp in resolved_paths:
            ext = os.path.splitext(fp)[1].lower()
            content_type = IMAGE_MIME_TYPES.get(ext, 'image/png')
            f = open(fp, 'rb')
            file_handles.append(f)
            files.append(('screenshots', (os.path.basename(fp), f, content_type)))

        data = {'title': title}
        if description: data['description'] = description
        if step_number is not None: data['step_number'] = str(step_number)
        if page_url: data['page_url'] = page_url

        resp = requests.post(url, headers=_headers(), files=files, data=data)
        resp.raise_for_status()

        for f in file_handles:
            f.close()

        return {"message": f"成功上传 {len(resolved_paths)} 张截图"}
    except Exception as e:
        for f in file_handles:
            try: f.close()
            except: pass
        return {"error": str(e)}


def list_files(project_id: int, page: int = 1, page_size: int = 20, search: str = None,
               status: str = None, extension: str = None, mime_type: str = None,
               ordering: str = "-created_at"):
    """获取项目文件列表"""
    url = f"{_base_url()}/api/projects/{project_id}/files/"
    params = {
        "page": page,
        "page_size": page_size,
    }
    if search:
        params["search"] = search
    if status:
        params["status"] = status
    if extension:
        params["extension"] = extension
    if mime_type:
        params["mime_type"] = mime_type
    if ordering:
        params["ordering"] = ordering
    try:
        resp = requests.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        return _response_json(resp)
    except Exception as e:
        return {"error": str(e)}


def get_file_detail(project_id: int, file_id: int):
    """获取文件详情"""
    url = f"{_base_url()}/api/projects/{project_id}/files/{file_id}/"
    try:
        resp = requests.get(url, headers=_headers())
        resp.raise_for_status()
        return _response_json(resp)
    except Exception as e:
        return {"error": str(e)}


def upload_files(project_id: int, file_paths: str):
    """上传一个或多个项目文件"""
    paths = [p.strip() for p in (file_paths or '').split(',') if p.strip()]
    if not paths:
        return {"error": "未提供文件路径"}

    resolved_paths = []
    for fp in paths:
        resolved_path = _resolve_local_file_path(fp)
        if not os.path.exists(resolved_path):
            return {"error": f"文件不存在: {fp}"}
        if not os.path.isfile(resolved_path):
            return {"error": f"不是有效文件: {fp}"}
        resolved_paths.append(resolved_path)

    url = f"{_base_url()}/api/projects/{project_id}/files/"
    file_handles = []
    try:
        files = []
        for fp in resolved_paths:
            content_type = mimetypes.guess_type(fp)[0] or 'application/octet-stream'
            f = open(fp, 'rb')
            file_handles.append(f)
            files.append(('files', (os.path.basename(fp), f, content_type)))

        resp = requests.post(url, headers=_headers(), files=files)
        resp.raise_for_status()
        return _response_json(resp)
    except Exception as e:
        return {"error": str(e)}
    finally:
        for f in file_handles:
            try:
                f.close()
            except Exception:
                pass


def validate_files(project_id: int, file_ids):
    """校验 file_ids 是否存在、属于项目且状态可用"""
    try:
        parsed_ids = _parse_csv_ints(file_ids, "file_ids")
    except ValueError as e:
        return {"error": str(e)}
    url = f"{_base_url()}/api/projects/{project_id}/files/validate/"
    try:
        resp = requests.post(url, headers=_headers(), json={"file_ids": parsed_ids})
        resp.raise_for_status()
        return _response_json(resp)
    except Exception as e:
        return {"error": str(e)}


def get_file_references(project_id: int, file_id: int):
    """获取文件引用详情"""
    url = f"{_base_url()}/api/projects/{project_id}/files/{file_id}/references/"
    try:
        resp = requests.get(url, headers=_headers())
        resp.raise_for_status()
        return _response_json(resp)
    except Exception as e:
        return {"error": str(e)}


def delete_file(project_id: int, file_id: int):
    """删除项目文件；被引用文件由后端执行软删除"""
    url = f"{_base_url()}/api/projects/{project_id}/files/{file_id}/"
    try:
        resp = requests.delete(url, headers=_headers())
        resp.raise_for_status()
        if getattr(resp, 'status_code', None) == 204:
            return {"success": True, "message": f"文件ID {file_id} 删除成功"}
        data = _response_json(resp)
        if data:
            return data
        return {"success": True, "message": f"文件ID {file_id} 删除成功"}
    except Exception as e:
        return {"error": str(e)}


def get_file_settings(project_id: int):
    """获取项目文件管理设置"""
    url = f"{_base_url()}/api/projects/{project_id}/files/settings/"
    try:
        resp = requests.get(url, headers=_headers())
        resp.raise_for_status()
        return _response_json(resp)
    except Exception as e:
        return {"error": str(e)}


def update_file_settings(project_id: int, auto_delete_on_unbind=None, auto_delete_zero_refs=None):
    """更新项目文件管理设置"""
    try:
        on_unbind = _parse_optional_bool(auto_delete_on_unbind, "auto_delete_on_unbind")
        zero_refs = _parse_optional_bool(auto_delete_zero_refs, "auto_delete_zero_refs")
    except ValueError as e:
        return {"error": str(e)}

    data = {}
    if on_unbind is not None:
        data["auto_delete_on_unbind"] = on_unbind
    if zero_refs is not None:
        data["auto_delete_zero_refs"] = zero_refs
    if not data:
        return {"error": "至少需要提供 auto_delete_on_unbind 或 auto_delete_zero_refs"}

    url = f"{_base_url()}/api/projects/{project_id}/files/settings/"
    try:
        resp = requests.post(url, headers=_headers(), json=data)
        resp.raise_for_status()
        return _response_json(resp)
    except Exception as e:
        return {"error": str(e)}


def cleanup_unreferenced_files(project_id: int):
    """清理项目内无引用文件"""
    url = f"{_base_url()}/api/projects/{project_id}/files/cleanup-unreferenced/"
    try:
        resp = requests.post(url, headers=_headers())
        resp.raise_for_status()
        return _response_json(resp)
    except Exception as e:
        return {"error": str(e)}


def download_file(project_id: int, file_id: int, output_path: str = None, output_dir: str = None):
    """下载文件到本地"""
    url = f"{_base_url()}/api/projects/{project_id}/files/{file_id}/download/"
    try:
        resp = requests.get(url, headers=_headers(), stream=True)
        resp.raise_for_status()
        filename = _extract_filename_from_content_disposition(
            getattr(resp, 'headers', {}).get('Content-Disposition', '')
        ) or f"file_{file_id}"
        target_path = output_path or os.path.join(output_dir or os.getcwd(), filename)
        saved_path = _save_response_to_file(resp, target_path)
        return {
            "success": True,
            "message": "文件下载成功",
            "file_id": file_id,
            "output_path": saved_path,
            "content_type": getattr(resp, 'headers', {}).get('Content-Type', ''),
        }
    except Exception as e:
        return {"error": str(e)}


def preview_file(project_id: int, file_id: int, output_path: str = None):
    """预览文件；文本直接返回，二进制可保存到 output_path"""
    url = f"{_base_url()}/api/projects/{project_id}/files/{file_id}/preview/"
    try:
        resp = requests.get(url, headers=_headers(), stream=bool(output_path))
        resp.raise_for_status()
        content_type = getattr(resp, 'headers', {}).get('Content-Type', '')
        if output_path:
            saved_path = _save_response_to_file(resp, output_path)
            return {
                "success": True,
                "message": "文件预览内容已保存",
                "file_id": file_id,
                "output_path": saved_path,
                "content_type": content_type,
            }
        if (
            content_type.startswith('text/')
            or 'json' in content_type
            or 'xml' in content_type
            or 'javascript' in content_type
        ):
            return {
                "file_id": file_id,
                "content_type": content_type,
                "content": getattr(resp, 'text', ''),
            }
        return {
            "file_id": file_id,
            "content_type": content_type,
            "size": len(getattr(resp, 'content', b'')),
            "message": "预览内容为二进制，请使用 --output_path 保存或使用 download_file 下载",
        }
    except Exception as e:
        return {"error": str(e)}


def _parse_steps(steps_str):
    """解析 steps JSON，支持容错，自动修复常见格式问题"""
    if not steps_str:
        return []

    # 先尝试直接解析
    try:
        parsed = json.loads(steps_str)
        if isinstance(parsed, list):
            return parsed
        return [parsed] if isinstance(parsed, dict) else []
    except json.JSONDecodeError:
        pass

    # 尝试修复：给没有引号的键名加上引号
    import re
    fixed = steps_str
    # 匹配 {key: 或 ,key: 形式的未加引号键名
    fixed = re.sub(r'([{,])\s*(\w+)\s*:', r'\1"\2":', fixed)
    # 匹配未加引号的字符串值（排除数字、布尔值、null）
    def quote_value(m):
        val = m.group(1).strip()
        suffix = m.group(2)
        if re.match(r'^-?\d+\.?\d*$', val) or val in ('true', 'false', 'null'):
            return f':{val}{suffix}'
        return f':"{val}"{suffix}'
    fixed = re.sub(r':\s*([^",\[\]{}][^,\[\]{}]*?)([,}\]])', quote_value, fixed)

    try:
        parsed = json.loads(fixed)
        if isinstance(parsed, list):
            return parsed
        return [parsed] if isinstance(parsed, dict) else []
    except json.JSONDecodeError as e:
        return {"error": f"steps JSON 格式错误，无法解析: {str(e)}。正确格式: [{{\"step_number\":1,\"description\":\"...\",\"expected_result\":\"...\"}}]"}


# Action 路由
ACTIONS = {
    "get_projects": lambda args: get_projects(),
    "get_modules": lambda args: get_modules(args.project_id),
    "add_module": lambda args: add_module(args.project_id, args.name, args.parent_id),
    "get_levels": lambda args: get_levels(),
    "get_testcases": lambda args: get_testcases(args.project_id, args.module_id),
    "get_testcase_detail": lambda args: get_testcase_detail(args.project_id, args.case_id),
    "add_testcase": lambda args: (
        _parse_steps(args.steps) if isinstance(_parse_steps(args.steps), dict) else
        add_testcase(
            args.project_id, args.module_id, args.name, args.level,
            args.precondition or "", _parse_steps(args.steps), args.notes or "",
            args.review_status or "pending_review", args.test_type or "functional"
        )
    ),
    "edit_testcase": lambda args: (
        _parse_steps(args.steps) if args.steps and isinstance(_parse_steps(args.steps), dict) else
        edit_testcase(
            args.project_id, args.case_id, args.name, args.level, args.module_id,
            args.precondition, _parse_steps(args.steps) if args.steps else None, args.notes,
            args.review_status, args.test_type, args.is_optimization
        )
    ),
    "upload_screenshot": lambda args: upload_screenshot(
        args.project_id, args.case_id, args.file_path, args.title,
        args.description or "", args.step_number, args.page_url or ""
    ),
    "upload_screenshots": lambda args: upload_screenshots(
        args.project_id, args.case_id, args.file_paths, args.title,
        args.description or "", args.step_number, args.page_url or ""
    ),
    "list_files": lambda args: list_files(
        args.project_id, args.page, args.page_size, args.search, args.status,
        args.extension, args.mime_type, args.ordering
    ),
    "get_file_detail": lambda args: get_file_detail(args.project_id, args.file_id),
    "upload_file": lambda args: upload_files(args.project_id, args.file_path),
    "upload_files": lambda args: upload_files(args.project_id, args.file_paths),
    "validate_files": lambda args: validate_files(args.project_id, args.file_ids),
    "get_file_references": lambda args: get_file_references(args.project_id, args.file_id),
    "delete_file": lambda args: delete_file(args.project_id, args.file_id),
    "get_file_settings": lambda args: get_file_settings(args.project_id),
    "update_file_settings": lambda args: update_file_settings(
        args.project_id, args.auto_delete_on_unbind, args.auto_delete_zero_refs
    ),
    "cleanup_unreferenced_files": lambda args: cleanup_unreferenced_files(args.project_id),
    "download_file": lambda args: download_file(
        args.project_id, args.file_id, args.output_path, args.output_dir
    ),
    "preview_file": lambda args: preview_file(args.project_id, args.file_id, args.output_path),
}


def main():
    parser = argparse.ArgumentParser(description="WHartTest 测试管理平台工具")
    parser.add_argument("--action", required=True, choices=ACTIONS.keys(), help="要执行的操作")
    parser.add_argument("--project_id", type=int, help="项目ID")
    parser.add_argument("--module_id", type=int, help="模块ID")
    parser.add_argument("--parent_id", type=int, help="父模块ID")
    parser.add_argument("--case_id", type=int, help="用例ID")
    parser.add_argument("--name", help="用例名称")
    parser.add_argument("--level", help="用例等级 (P0/P1/P2/P3)")
    parser.add_argument("--precondition", help="前置条件")
    parser.add_argument("--steps", help="用例步骤 (JSON格式)")
    parser.add_argument("--notes", help="备注")
    parser.add_argument("--file_path", help="文件路径（单张上传）")
    parser.add_argument("--file_paths", help="文件路径列表（批量上传，逗号分隔）")
    parser.add_argument("--file_id", type=int, help="文件ID")
    parser.add_argument("--file_ids", help="文件ID列表（JSON数组或逗号分隔）")
    parser.add_argument("--title", help="标题")
    parser.add_argument("--description", help="描述")
    parser.add_argument("--step_number", type=int, help="步骤编号")
    parser.add_argument("--page_url", help="页面URL")
    parser.add_argument("--review_status", help="审核状态 (pending_review/approved/needs_optimization/optimization_pending_review/unavailable)")
    parser.add_argument("--test_type", help="测试类型 (smoke/functional/boundary/exception/permission/security/compatibility)", default="functional")
    parser.add_argument("--is_optimization", action="store_true", help="是否为优化操作（自动设置状态为optimization_pending_review）")
    parser.add_argument("--page", type=int, default=1, help="页码")
    parser.add_argument("--page_size", type=int, default=20, help="每页数量")
    parser.add_argument("--search", help="搜索关键词")
    parser.add_argument("--status", help="文件状态过滤 (available/processing/broken/deleted)")
    parser.add_argument("--extension", help="文件扩展名过滤，如 .pdf")
    parser.add_argument("--mime_type", help="MIME 类型过滤")
    parser.add_argument("--ordering", default="-created_at", help="排序字段，如 -created_at/size/original_name")
    parser.add_argument("--output_path", help="下载或预览保存路径")
    parser.add_argument("--output_dir", help="下载保存目录")
    parser.add_argument("--auto_delete_on_unbind", help="解绑时自动删除无引用文件 (true/false)")
    parser.add_argument("--auto_delete_zero_refs", help="引用为0时自动删除 (true/false)")

    args = parser.parse_args()
    result = ACTIONS[args.action](args)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 如果结果包含 error 字段，返回非零退出码
    if isinstance(result, dict) and "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
