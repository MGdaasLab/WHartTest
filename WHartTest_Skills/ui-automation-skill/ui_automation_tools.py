# -*- coding: utf-8 -*-
"""
WHartTest UI 自动化管理工具

管理 UI 自动化测试的完整生命周期：模块 → 页面 → 元素 → 页面步骤 → 测试用例
"""
import sys
import io

# Windows 终端 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import argparse
import json
import os
import requests
from pathlib import Path

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

# 配置（运行时读取环境变量，避免 import 时固化）
_DEFAULT_BASE_URL = "http://127.0.0.1:8000"
_DEFAULT_API_KEY = "wharttest-default-mcp-key-2025"


def _base_url() -> str:
    return (os.environ.get("WHARTTEST_BACKEND_URL") or _DEFAULT_BASE_URL).rstrip("/")


def _api_key() -> str:
    return (os.environ.get("WHARTTEST_API_KEY") or _DEFAULT_API_KEY).strip()


def _headers() -> dict:
    return {
        "accept": "application/json",
        "Content-Type": "application/json",
        "X-API-Key": _api_key(),
    }


# 兼容旧引用
BASE_URL = _base_url()
API_KEY = _api_key()
HEADERS = _headers()


def _request(method: str, endpoint: str, data: dict = None, params: dict = None):
    """统一请求封装"""
    url = f"{_base_url()}/api/ui-automation/{endpoint}"
    try:
        resp = requests.request(method, url, headers=_headers(), json=data, params=params)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        try:
            error_data = e.response.json()
            return {"status": "error", "message": error_data.get("message", str(e))}
        except Exception:
            return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_current_user():
    """获取当前API Key对应的用户信息"""
    try:
        url = f"{_base_url()}/api/accounts/me/"
        resp = requests.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        print(f"获取当前用户信息成功，原始数据: {data}")
        
        # 检查数据格式，可能是嵌套的
        if isinstance(data, dict):
            # 如果返回的是标准API格式，提取data字段
            if 'data' in data and isinstance(data['data'], dict):
                user_data = data['data']
                if 'id' in user_data:
                    return user_data
            # 如果直接返回用户数据
            elif 'id' in data:
                return data
                
        print(f"获取当前用户信息失败: 返回数据格式无效 - {data}")
        return None
    except Exception as e:
        print(f"获取当前用户信息失败: {e}")
        if hasattr(e, 'response') and e.response:
            try:
                error_data = e.response.json()
                print(f"错误响应: {error_data}")
            except:
                print(f"错误响应文本: {e.response.text}")
        
        # 如果me端点失败，尝试通过API Key获取用户信息
        print("尝试通过API Key获取用户信息...")
        return get_user_by_api_key()


def get_user_by_api_key():
    """通过API Key获取用户信息"""
    try:
        # 尝试获取API Key列表，第一个应该属于当前用户
        url = f"{_base_url()}/api/api-keys/"
        resp = requests.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        
        print(f"获取API Key列表成功，原始数据: {data}")
        
        if isinstance(data, list) and len(data) > 0:
            # 获取第一个API Key的用户信息
            first_key = data[0]
            if 'user' in first_key:
                user_data = first_key['user']
                if isinstance(user_data, dict) and 'id' in user_data:
                    return user_data
                elif isinstance(user_data, int):
                    # 如果user字段只是用户ID，返回简化数据
                    return {'id': user_data, 'username': first_key.get('user_username', f'user_{user_data}')}
                    
        print("通过API Key获取用户信息失败: 无法从API Key列表中提取用户信息")
        return None
    except Exception as e:
        print(f"通过API Key获取用户信息失败: {e}")
        return None


def _filter_images(data):
    """过滤数据中的图片/base64/大型日志内容，避免占用过多tokens"""
    if isinstance(data, dict):
        filtered = {}
        for k, v in data.items():
            # 过滤截图、图片、base64数据
            if k in ('screenshots', 'screenshot', 'image', 'images', 'base64'):
                if isinstance(v, list):
                    filtered[k] = f"[{len(v)} images filtered]"
                elif isinstance(v, str) and len(v) > 500:
                    filtered[k] = "[image data filtered]"
                else:
                    filtered[k] = v
            # 过滤网络日志、快照等大型数据
            elif k in ('network_logs', 'console_logs', 'har_data', 'network_requests', 'snapshots'):
                if isinstance(v, list):
                    filtered[k] = f"[{len(v)} entries filtered]"
                elif isinstance(v, dict):
                    filtered[k] = "[data filtered]"
                else:
                    filtered[k] = v
            # 过滤 trace_data 中的详细内容，只保留摘要
            elif k == 'trace_data' and isinstance(v, dict):
                filtered[k] = {
                    "summary": v.get("summary", {}),
                    "duration": v.get("duration"),
                    "total_actions": len(v.get("actions", [])),
                    "actions_summary": [{"type": a.get("type"), "selector": a.get("selector")} for a in v.get("actions", [])[:10]],
                    "[filtered]": "详细 snapshots/network_requests 已过滤，使用 get_execution_trace 获取完整数据"
                }
            # 过滤 result_data 中的步骤截图（递归处理）
            elif k == 'result_data' and isinstance(v, dict):
                filtered[k] = _filter_images(v)
            # 过滤步骤详情中的长 base64 字符串
            elif isinstance(v, str) and len(v) > 1000 and (v.startswith(('data:image', '/9j/', 'iVBOR')) or 'base64' in v[:100]):
                filtered[k] = "[base64 image filtered]"
            else:
                filtered[k] = _filter_images(v)
        return filtered
    elif isinstance(data, list):
        return [_filter_images(item) for item in data]
    else:
        return data


# ==================== 模块管理 ====================

def get_ui_modules(project_id: int):
    """获取 UI 模块树"""
    result = _request("GET", "modules/tree/", params={"project": project_id})
    return result.get("data", result)


def create_ui_module(project_id: int, name: str, parent_id: int = None):
    """创建 UI 模块"""
    data = {"project": project_id, "name": name}
    if parent_id:
        data["parent"] = parent_id
    result = _request("POST", "modules/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "模块创建成功", "data": result.get("data", result)}
    return result


def update_ui_module(module_id: int, name: str):
    """更新 UI 模块"""
    result = _request("PATCH", f"modules/{module_id}/", data={"name": name})
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "模块更新成功", "data": result.get("data", result)}
    return result


def delete_ui_module(module_id: int):
    """删除 UI 模块"""
    result = _request("DELETE", f"modules/{module_id}/")
    return {"status": "success", "message": "模块删除成功"}


# ==================== 页面管理 ====================

def get_ui_pages(project_id: int, module_id: int = None):
    """获取页面列表"""
    params = {"project": project_id}
    if module_id:
        params["module"] = module_id
    result = _request("GET", "pages/", params=params)
    return result.get("data", result)


def get_ui_page(page_id: int):
    """获取页面详情（含元素）"""
    result = _request("GET", f"pages/{page_id}/")
    return result.get("data", result)


def create_ui_page(project_id: int, module_id: int, name: str, url: str = None, description: str = None):
    """创建页面"""
    data = {"project": project_id, "module": module_id, "name": name}
    if url:
        data["url"] = url
    if description:
        data["description"] = description
    result = _request("POST", "pages/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "页面创建成功", "data": result.get("data", result)}
    return result


def update_ui_page(page_id: int, name: str = None, url: str = None, description: str = None):
    """更新页面"""
    data = {}
    if name:
        data["name"] = name
    if url:
        data["url"] = url
    if description:
        data["description"] = description
    result = _request("PATCH", f"pages/{page_id}/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "页面更新成功", "data": result.get("data", result)}
    return result


def delete_ui_page(page_id: int):
    """删除页面"""
    _request("DELETE", f"pages/{page_id}/")
    return {"status": "success", "message": "页面删除成功"}


# ==================== 元素管理 ====================

def get_elements(page_id: int):
    """获取页面元素列表"""
    result = _request("GET", "elements/", params={"page": page_id})
    return result.get("data", result)


def create_element(page_id: int, name: str, locator_type: str, locator_value: str,
                   locator_type_2: str = None, locator_value_2: str = None,
                   locator_type_3: str = None, locator_value_3: str = None,
                   wait_time: int = 0, is_iframe: bool = False, iframe_locator: str = None,
                   description: str = None):
    """创建元素"""
    data = {
        "page": page_id,
        "name": name,
        "locator_type": locator_type,
        "locator_value": locator_value,
        "wait_time": wait_time,
        "is_iframe": is_iframe
    }
    if locator_type_2:
        data["locator_type_2"] = locator_type_2
    if locator_value_2:
        data["locator_value_2"] = locator_value_2
    if locator_type_3:
        data["locator_type_3"] = locator_type_3
    if locator_value_3:
        data["locator_value_3"] = locator_value_3
    if iframe_locator:
        data["iframe_locator"] = iframe_locator
    if description:
        data["description"] = description
    result = _request("POST", "elements/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "元素创建成功", "data": result.get("data", result)}
    return result


def update_element(element_id: int, **kwargs):
    """更新元素"""
    data = {k: v for k, v in kwargs.items() if v is not None}
    result = _request("PATCH", f"elements/{element_id}/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "元素更新成功", "data": result.get("data", result)}
    return result


def delete_element(element_id: int):
    """删除元素"""
    _request("DELETE", f"elements/{element_id}/")
    return {"status": "success", "message": "元素删除成功"}


def batch_create_elements(page_id: int, elements: list):
    """批量创建元素"""
    results = []
    for elem in elements:
        elem["page"] = page_id
        result = _request("POST", "elements/", data=elem)
        results.append(result.get("data", result))
    return {"status": "success", "message": f"批量创建 {len(results)} 个元素", "data": results}


# ==================== 页面步骤管理 ====================

def get_page_steps(project_id: int, page_id: int = None, module_id: int = None):
    """获取页面步骤列表"""
    params = {"project": project_id}
    if page_id:
        params["page"] = page_id
    if module_id:
        params["module"] = module_id
    result = _request("GET", "page-steps/", params=params)
    return result.get("data", result)


def get_page_step(step_id: int):
    """获取页面步骤详情（过滤截图数据）"""
    result = _request("GET", f"page-steps/{step_id}/")
    data = result.get("data", result)
    return _filter_images(data)


def create_page_step(project_id: int, page_id: int, module_id: int, name: str, description: str = None):
    """创建页面步骤"""
    data = {
        "project": project_id,
        "page": page_id,
        "module": module_id,
        "name": name
    }
    if description:
        data["description"] = description
    result = _request("POST", "page-steps/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "页面步骤创建成功", "data": result.get("data", result)}
    return result


def update_page_step(step_id: int, name: str = None, description: str = None):
    """更新页面步骤"""
    data = {}
    if name:
        data["name"] = name
    if description:
        data["description"] = description
    result = _request("PATCH", f"page-steps/{step_id}/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "页面步骤更新成功", "data": result.get("data", result)}
    return result


def delete_page_step(step_id: int):
    """删除页面步骤"""
    _request("DELETE", f"page-steps/{step_id}/")
    return {"status": "success", "message": "页面步骤删除成功"}


def set_step_details(step_id: int, steps: list):
    """设置步骤详情（批量更新）"""
    data = {"page_step": step_id, "steps": steps}
    result = _request("POST", "page-steps-detailed/batch_update/", data=data)
    if result.get("status") == "success" or result.get("message") == "批量更新成功":
        return {"status": "success", "message": "步骤详情设置成功"}
    return result


# ==================== 测试用例管理 ====================

def get_testcases(project_id: int, module_id: int = None, level: str = None, limit: int = 50):
    """
    获取测试用例列表（精简版，只返回基本信息）
    
    Args:
        project_id: 项目 ID
        module_id: 模块 ID（可选）
        level: 用例等级（可选）
        limit: 返回数量限制（默认 50）
    """
    params = {"project": project_id}
    if module_id:
        params["module"] = module_id
    if level:
        params["level"] = level
    result = _request("GET", "testcases/", params=params)
    data = result.get("data", result)
    
    # 处理返回数据，只保留关键字段
    if isinstance(data, list):
        simplified = []
        for item in data[:limit]:  # 限制数量
            simplified.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "level": item.get("level"),
                "status": item.get("status"),
                "module": item.get("module"),
                "module_name": item.get("module_name"),
                "description": item.get("description", "")[:100],  # 描述截断
                "created_at": item.get("created_at"),
            })
        return {
            "total": len(data),
            "returned": len(simplified),
            "items": simplified
        }
    return data


def get_testcase(testcase_id: int):
    """获取测试用例详情（过滤截图数据）"""
    result = _request("GET", f"testcases/{testcase_id}/")
    data = result.get("data", result)
    return _filter_images(data)


def create_testcase(project_id: int, module_id: int, name: str, description: str = None, level: str = "P2"):
    """创建测试用例"""
    data = {
        "project": project_id,
        "module": module_id,
        "name": name,
        "level": level
    }
    if description:
        data["description"] = description
    result = _request("POST", "testcases/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "测试用例创建成功", "data": result.get("data", result)}
    return result


def update_testcase(testcase_id: int, name: str = None, description: str = None, level: str = None):
    """更新测试用例"""
    data = {}
    if name:
        data["name"] = name
    if description:
        data["description"] = description
    if level:
        data["level"] = level
    result = _request("PATCH", f"testcases/{testcase_id}/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "测试用例更新成功", "data": result.get("data", result)}
    return result


def delete_testcase(testcase_id: int):
    """删除测试用例"""
    _request("DELETE", f"testcases/{testcase_id}/")
    return {"status": "success", "message": "测试用例删除成功"}


def set_case_steps(testcase_id: int, page_step_ids: list):
    """设置用例步骤（批量更新）"""
    steps = [{"page_step": pid} for pid in page_step_ids]
    data = {"test_case": testcase_id, "steps": steps}
    result = _request("POST", "case-steps/batch_update/", data=data)
    if result.get("status") == "success" or result.get("message") == "批量更新成功":
        return {"status": "success", "message": "用例步骤设置成功"}
    return result


# ==================== 公共数据管理 ====================

def get_public_data(project_id: int):
    """获取公共数据列表"""
    result = _request("GET", "public-data/", params={"project": project_id})
    return result.get("data", result)


def create_public_data(project_id: int, key: str, value: str, data_type: int = 0, description: str = None, is_enabled: bool = True):
    """创建公共数据"""
    data = {
        "project": project_id,
        "key": key,
        "value": value,
        "type": data_type,
        "is_enabled": is_enabled
    }
    if description:
        data["description"] = description
    result = _request("POST", "public-data/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "公共数据创建成功", "data": result.get("data", result)}
    return result


def update_public_data(data_id: int, **kwargs):
    """更新公共数据"""
    data = {k: v for k, v in kwargs.items() if v is not None}
    result = _request("PATCH", f"public-data/{data_id}/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "公共数据更新成功", "data": result.get("data", result)}
    return result


def delete_public_data(data_id: int):
    """删除公共数据"""
    _request("DELETE", f"public-data/{data_id}/")
    return {"status": "success", "message": "公共数据删除成功"}


# ==================== 执行记录管理 ====================

def get_execution_records(testcase_id: int = None, status: int = None, limit: int = 20):
    """获取执行记录列表（过滤图片数据）"""
    params = {}
    if testcase_id:
        params["test_case"] = testcase_id
    if status is not None:
        params["status"] = status
    result = _request("GET", "execution-records/", params=params)
    data = result.get("data", result)
    if isinstance(data, list):
        data = data[:limit]
    return _filter_images(data)


def get_execution_record(record_id: int):
    """获取执行记录详情（过滤图片数据）"""
    result = _request("GET", f"execution-records/{record_id}/")
    data = result.get("data", result)
    return _filter_images(data)


def get_execution_trace(record_id: int, refresh: bool = False):
    """获取执行记录的 Trace 数据"""
    params = {"refresh": "1"} if refresh else {}
    result = _request("GET", f"execution-records/{record_id}/trace/", params=params)
    return result


def delete_execution_record(record_id: int):
    """删除执行记录"""
    _request("DELETE", f"execution-records/{record_id}/")
    return {"status": "success", "message": "执行记录删除成功"}


# ==================== 批量执行记录管理 ====================

def get_batch_records(status: int = None, limit: int = 20):
    """获取批量执行记录列表（过滤截图）"""
    params = {}
    if status is not None:
        params["status"] = status
    result = _request("GET", "batch-records/", params=params)
    data = result.get("data", result)
    if isinstance(data, list):
        return _filter_images(data[:limit])
    return _filter_images(data)


def get_batch_record(batch_id: int):
    """获取批量执行记录详情（过滤截图，包含各用例执行情况）"""
    result = _request("GET", f"batch-records/{batch_id}/")
    data = result.get("data", result)
    return _filter_images(data)


def delete_batch_record(batch_id: int):
    """删除批量执行记录"""
    _request("DELETE", f"batch-records/{batch_id}/")
    return {"status": "success", "message": "批量执行记录删除成功"}


# ==================== 环境配置管理 ====================

def get_env_configs(project_id: int):
    """获取环境配置列表"""
    result = _request("GET", "env-configs/", params={"project": project_id})
    return result.get("data", result)


def create_env_config(project_id: int, name: str, base_url: str = None, browser: str = "chromium",
                      headless: bool = True, viewport_width: int = 1280, viewport_height: int = 720,
                      timeout: int = 30000, is_default: bool = False):
    """创建环境配置"""
    data = {
        "project": project_id,
        "name": name,
        "browser": browser,
        "headless": headless,
        "viewport_width": viewport_width,
        "viewport_height": viewport_height,
        "timeout": timeout,
        "is_default": is_default
    }
    if base_url:
        data["base_url"] = base_url
    result = _request("POST", "env-configs/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "环境配置创建成功", "data": result.get("data", result)}
    return result


def update_env_config(config_id: int, **kwargs):
    """更新环境配置"""
    data = {k: v for k, v in kwargs.items() if v is not None}
    result = _request("PATCH", f"env-configs/{config_id}/", data=data)
    if result.get("status") == "success" or result.get("data"):
        return {"status": "success", "message": "环境配置更新成功", "data": result.get("data", result)}
    return result


def delete_env_config(config_id: int):
    """删除环境配置"""
    _request("DELETE", f"env-configs/{config_id}/")
    return {"status": "success", "message": "环境配置删除成功"}


# ==================== 执行器管理 ====================

def get_actuators():
    """获取在线执行器列表"""
    result = _request("GET", "actuators/list_actuators/")
    return result.get("data", result)


def get_actuator_status():
    """获取执行器状态统计"""
    result = _request("GET", "actuators/status/")
    return result.get("data", result)


# ==================== 用例执行数据 ====================

def get_testcase_execute_data(testcase_id: int):
    """获取测试用例完整执行数据（过滤图片，包含所有步骤详情和元素定位）"""
    result = _request("GET", f"testcases/{testcase_id}/execute-data/")
    data = result.get("data", result)
    return _filter_images(data)


def get_page_step_execute_data(step_id: int):
    """获取页面步骤执行数据（过滤图片，包含元素定位信息）"""
    result = _request("GET", f"page-steps/{step_id}/execute-data/")
    data = result.get("data", result)
    return _filter_images(data)


# ==================== 用例执行 ====================

# WebSocket 依赖检查
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False


def execute_testcase(testcase_id: int, env_config_id: int = None, actuator_id: str = None, wait_result: bool = True, timeout: int = 120):
    """
    执行测试用例
    
    Args:
        testcase_id: 测试用例 ID
        env_config_id: 环境配置 ID（可选，不传使用默认配置）
        actuator_id: 执行器 ID（可选，不传自动选择可用执行器）
        wait_result: 是否等待执行结果（默认 True）
        timeout: 等待超时时间（秒，默认 120）
    
    Returns:
        执行结果或任务状态
    """
    if not WEBSOCKET_AVAILABLE:
        return {"status": "error", "message": "执行功能需要 websocket-client 模块，请运行: pip install websocket-client"}
    
    import threading
    import time
    
    # WebSocket 地址
    ws_url = _base_url().replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/ui/web/'
    
    result = {"status": "pending", "message": "任务已发送"}
    execution_done = threading.Event()
    
    def on_message(ws, message):
        nonlocal result
        try:
            data = json.loads(message)
            # 检查是否是执行结果
            if data.get("data", {}).get("func_name") in ("u_case_result", "case_result"):
                func_args = data.get("data", {}).get("func_args", {})
                if func_args.get("case_id") == testcase_id:
                    result = {
                        "status": "success" if func_args.get("status") == "success" else "failed",
                        "case_id": testcase_id,
                        "message": func_args.get("message", ""),
                        "total_steps": func_args.get("total_steps", 0),
                        "passed_steps": func_args.get("passed_steps", 0),
                        "failed_steps": func_args.get("failed_steps", 0),
                        "duration": func_args.get("duration", 0),
                    }
                    execution_done.set()
            # 检查错误消息
            elif data.get("code") != 200 and data.get("msg"):
                if "执行器" in data.get("msg", "") or "失败" in data.get("msg", ""):
                    result = {"status": "error", "message": data.get("msg")}
                    execution_done.set()
        except Exception:
            pass
    
    def on_error(ws, error):
        nonlocal result
        result = {"status": "error", "message": str(error)}
        execution_done.set()
    
    def on_open(ws):
        # 发送执行命令，包含执行人信息
        cmd = {
            "data": {
                "func_name": "u_test_case",
                "func_args": {
                    "case_id": testcase_id,
                }
            }
        }
        if env_config_id:
            cmd["data"]["func_args"]["env_config_id"] = env_config_id
        if actuator_id:
            cmd["data"]["func_args"]["actuator_id"] = actuator_id
        
        # 从API Key获取用户信息（如果可用）
        try:
            # 尝试获取当前用户信息
            user_info = get_current_user()
            if user_info and user_info.get("id"):
                cmd["data"]["func_args"]["executor_id"] = user_info["id"]
                cmd["data"]["func_args"]["executor_name"] = user_info.get("username", "")
                print(f"成功获取当前用户信息: ID={user_info['id']}, 用户名={user_info.get('username', '')}")
            else:
                print("获取当前用户信息失败: 返回数据无效")
        except Exception as e:
            # 如果获取用户信息失败，继续执行但不包含执行人信息
            print(f"获取当前用户信息失败: {e}")
            pass
        
        ws.send(json.dumps(cmd))
    
    # 连接 WebSocket
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_error=on_error,
        on_open=on_open,
    )
    
    # 在后台线程运行 WebSocket
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()
    
    if wait_result:
        # 等待执行结果
        if execution_done.wait(timeout=timeout):
            ws.close()
            return result
        else:
            ws.close()
            # 超时后查询最新执行记录
            records = get_execution_records(testcase_id=testcase_id, limit=1)
            if records and len(records) > 0:
                latest = records[0]
                return _filter_images({
                    "status": "timeout",
                    "message": f"等待超时，最新记录状态: {latest.get('status')}",
                    "latest_record": latest
                })
            return {"status": "timeout", "message": f"等待执行结果超时 ({timeout}s)"}
    else:
        # 不等待，直接返回
        time.sleep(1)  # 等待命令发送
        ws.close()
        return {"status": "sent", "message": "执行命令已发送，请稍后查询执行记录"}


def execute_page_steps(step_id: int, env_config_id: int = None, actuator_id: str = None):
    """
    执行页面步骤（调试用）
    
    Args:
        step_id: 页面步骤 ID
        env_config_id: 环境配置 ID（可选）
        actuator_id: 执行器 ID（可选）
    """
    if not WEBSOCKET_AVAILABLE:
        return {"status": "error", "message": "执行功能需要 websocket-client 模块，请运行: pip install websocket-client"}
    
    import time
    
    ws_url = _base_url().replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/ui/web/'
    result = {"status": "sent", "message": "执行命令已发送"}
    
    def on_open(ws):
        cmd = {
            "data": {
                "func_name": "u_page_steps",
                "func_args": {
                    "page_step_id": step_id,
                }
            }
        }
        if env_config_id:
            cmd["data"]["func_args"]["env_config_id"] = env_config_id
        if actuator_id:
            cmd["data"]["func_args"]["actuator_id"] = actuator_id
        ws.send(json.dumps(cmd))
        time.sleep(1)
        ws.close()
    
    ws = websocket.WebSocketApp(ws_url, on_open=on_open)
    ws.run_forever()
    return result


# ==================== 命令行入口 ====================

def main():
    parser = argparse.ArgumentParser(description="WHartTest UI 自动化管理工具")
    parser.add_argument("--action", required=True, help="操作名称")
    
    # 通用参数
    parser.add_argument("--project_id", type=int, help="项目 ID")
    parser.add_argument("--module_id", type=int, help="模块 ID")
    parser.add_argument("--page_id", type=int, help="页面 ID")
    parser.add_argument("--element_id", type=int, help="元素 ID")
    parser.add_argument("--step_id", type=int, help="页面步骤 ID")
    parser.add_argument("--testcase_id", type=int, help="测试用例 ID")
    parser.add_argument("--data_id", type=int, help="公共数据 ID")
    
    # 模块参数
    parser.add_argument("--parent_id", type=int, help="父模块 ID")
    
    # 页面/元素参数
    parser.add_argument("--name", help="名称")
    parser.add_argument("--url", help="页面 URL")
    parser.add_argument("--description", help="描述")
    
    # 元素定位参数
    parser.add_argument("--locator_type", help="定位类型")
    parser.add_argument("--locator_value", help="定位值")
    parser.add_argument("--locator_type_2", help="备用定位类型2")
    parser.add_argument("--locator_value_2", help="备用定位值2")
    parser.add_argument("--locator_type_3", help="备用定位类型3")
    parser.add_argument("--locator_value_3", help="备用定位值3")
    parser.add_argument("--wait_time", type=int, default=0, help="等待时间（单位：秒）")
    parser.add_argument("--is_iframe", action="store_true", help="是否在 iframe 中")
    parser.add_argument("--iframe_locator", help="iframe 定位")
    
    # 批量操作参数
    parser.add_argument("--elements", help="元素列表 (JSON)")
    parser.add_argument("--steps", help="步骤列表 (JSON)")
    parser.add_argument("--page_step_ids", help="页面步骤 ID 列表 (逗号分隔)")
    
    # 用例参数
    parser.add_argument("--level", help="用例等级 (P0/P1/P2/P3)")
    
    # 公共数据参数
    parser.add_argument("--key", help="数据键名")
    parser.add_argument("--value", help="数据值")
    parser.add_argument("--type", type=int, default=0, help="数据类型")
    parser.add_argument("--is_enabled", action="store_true", help="是否启用")
    
    # 执行记录参数
    parser.add_argument("--record_id", type=int, help="执行记录 ID")
    parser.add_argument("--batch_id", type=int, help="批量执行记录 ID")
    parser.add_argument("--config_id", type=int, help="环境配置 ID")
    parser.add_argument("--status", type=int, help="状态")
    parser.add_argument("--limit", type=int, default=20, help="限制返回数量")
    parser.add_argument("--refresh", action="store_true", help="强制刷新")
    
    # 环境配置参数
    parser.add_argument("--base_url", help="基础 URL")
    parser.add_argument("--browser", help="浏览器类型 (chromium/firefox/webkit)")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--viewport_width", type=int, default=1280, help="视口宽度")
    parser.add_argument("--viewport_height", type=int, default=720, help="视口高度")
    parser.add_argument("--timeout", type=int, default=30000, help="超时时间（毫秒）")
    parser.add_argument("--is_default", action="store_true", help="是否默认配置")
    
    # 执行参数
    parser.add_argument("--actuator_id", help="执行器 ID")
    parser.add_argument("--wait_result", action="store_true", help="等待执行结果")
    parser.add_argument("--exec_timeout", type=int, default=120, help="执行等待超时（秒）")
    
    args = parser.parse_args()
    action = args.action
    
    # 动作路由
    actions = {
        # 模块
        "get_ui_modules": lambda: get_ui_modules(args.project_id),
        "create_ui_module": lambda: create_ui_module(args.project_id, args.name, args.parent_id),
        "update_ui_module": lambda: update_ui_module(args.module_id, args.name),
        "delete_ui_module": lambda: delete_ui_module(args.module_id),
        # 页面
        "get_ui_pages": lambda: get_ui_pages(args.project_id, args.module_id),
        "get_ui_page": lambda: get_ui_page(args.page_id),
        "create_ui_page": lambda: create_ui_page(args.project_id, args.module_id, args.name, args.url, args.description),
        "update_ui_page": lambda: update_ui_page(args.page_id, args.name, args.url, args.description),
        "delete_ui_page": lambda: delete_ui_page(args.page_id),
        # 元素
        "get_elements": lambda: get_elements(args.page_id),
        "create_element": lambda: create_element(
            args.page_id, args.name, args.locator_type, args.locator_value,
            args.locator_type_2, args.locator_value_2,
            args.locator_type_3, args.locator_value_3,
            args.wait_time, args.is_iframe, args.iframe_locator, args.description
        ),
        "update_element": lambda: update_element(
            args.element_id,
            name=args.name, locator_type=args.locator_type, locator_value=args.locator_value,
            locator_type_2=args.locator_type_2, locator_value_2=args.locator_value_2,
            wait_time=args.wait_time, is_iframe=args.is_iframe, iframe_locator=args.iframe_locator,
            description=args.description
        ),
        "delete_element": lambda: delete_element(args.element_id),
        "batch_create_elements": lambda: batch_create_elements(args.page_id, json.loads(args.elements)),
        # 页面步骤
        "get_page_steps": lambda: get_page_steps(args.project_id, args.page_id, args.module_id),
        "get_page_step": lambda: get_page_step(args.step_id),
        "create_page_step": lambda: create_page_step(args.project_id, args.page_id, args.module_id, args.name, args.description),
        "update_page_step": lambda: update_page_step(args.step_id, args.name, args.description),
        "delete_page_step": lambda: delete_page_step(args.step_id),
        "set_step_details": lambda: set_step_details(args.step_id, json.loads(args.steps)),
        # 测试用例
        "get_testcases": lambda: get_testcases(args.project_id, args.module_id, args.level, args.limit),
        "get_testcase": lambda: get_testcase(args.testcase_id),
        "create_testcase": lambda: create_testcase(args.project_id, args.module_id, args.name, args.description, args.level or "P2"),
        "update_testcase": lambda: update_testcase(args.testcase_id, args.name, args.description, args.level),
        "delete_testcase": lambda: delete_testcase(args.testcase_id),
        "set_case_steps": lambda: set_case_steps(args.testcase_id, [int(x) for x in args.page_step_ids.split(",")]),
        # 公共数据
        "get_public_data": lambda: get_public_data(args.project_id),
        "create_public_data": lambda: create_public_data(args.project_id, args.key, args.value, args.type, args.description),
        "update_public_data": lambda: update_public_data(args.data_id, key=args.key, value=args.value, is_enabled=args.is_enabled),
        "delete_public_data": lambda: delete_public_data(args.data_id),
        # 执行记录
        "get_execution_records": lambda: get_execution_records(args.testcase_id, args.status, args.limit),
        "get_execution_record": lambda: get_execution_record(args.record_id),
        "get_execution_trace": lambda: get_execution_trace(args.record_id, args.refresh),
        "delete_execution_record": lambda: delete_execution_record(args.record_id),
        # 批量执行记录
        "get_batch_records": lambda: get_batch_records(args.status, args.limit),
        "get_batch_record": lambda: get_batch_record(args.batch_id),
        "delete_batch_record": lambda: delete_batch_record(args.batch_id),
        # 环境配置
        "get_env_configs": lambda: get_env_configs(args.project_id),
        "create_env_config": lambda: create_env_config(
            args.project_id, args.name, args.base_url, args.browser or "chromium",
            args.headless, args.viewport_width, args.viewport_height, args.timeout, args.is_default
        ),
        "update_env_config": lambda: update_env_config(
            args.config_id, name=args.name, base_url=args.base_url, browser=args.browser,
            headless=args.headless, viewport_width=args.viewport_width, viewport_height=args.viewport_height,
            timeout=args.timeout, is_default=args.is_default
        ),
        "delete_env_config": lambda: delete_env_config(args.config_id),
        # 执行器
        "get_actuators": lambda: get_actuators(),
        "get_actuator_status": lambda: get_actuator_status(),
        # 执行数据
        "get_testcase_execute_data": lambda: get_testcase_execute_data(args.testcase_id),
        "get_page_step_execute_data": lambda: get_page_step_execute_data(args.step_id),
        # 执行用例
        "execute_testcase": lambda: execute_testcase(
            args.testcase_id, args.config_id, args.actuator_id, args.wait_result, args.exec_timeout
        ),
        "execute_page_steps": lambda: execute_page_steps(args.step_id, args.config_id, args.actuator_id),
    }
    
    if action not in actions:
        print(json.dumps({"status": "error", "message": f"未知操作: {action}"}, ensure_ascii=False))
        sys.exit(1)
    
    result = actions[action]()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
