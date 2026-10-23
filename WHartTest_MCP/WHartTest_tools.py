# -*- coding: utf-8 -*-
# @Author : 西红柿炒蛋
# @邮箱   : duanduanxc@qq.com
# @时间   : 2025/4/28 14:46

# 加载 .env 文件（本地开发时使用）
from dotenv import load_dotenv
from pathlib import Path

# 获取当前文件所在目录（WHartTest_MCP/）
current_dir = Path(__file__).parent
# 加载同目录下的 .env 文件
load_dotenv(current_dir / ".env")

from fastmcp import FastMCP
import json
import requests
from typing import Any, Dict, List, Optional
import json
import ast  # ast 模块用于安全地解析 Python 字符串文字，因为您的输入使用了单引号而不是标准的 JSON 双引号
import doctest
import time
from pydantic import Field
from pydantic.v1.networks import host_regex
import os

# mcp 初始化
from mcp_auth import build_mcp_auth

# 鉴权模块缺失时 fail-closed：宁可起不来，也不要以无鉴权形态对外提供服务
# （镜像不再 COPY 该文件，由 compose 以只读方式挂载；见 docker-compose.local.yml）
try:
    from mcp_auth import build_mcp_auth
except ImportError as exc:
    raise SystemExit(
        "缺少 mcp_auth.py：MCP 服务拒绝在无法启用鉴权的情况下启动。"
        "请确认 docker-compose 已把 WHartTest_MCP/mcp_auth.py 挂载到 /app/。"
    ) from exc

mcp = FastMCP(name="WHartTest_tools", auth=build_mcp_auth())

# 从环境变量读取后端地址
# 默认使用 Docker 网络中的 backend 服务名称
base_url = os.getenv("WHARTTEST_BACKEND_URL", "http://backend:8000")

# 从环境变量读取 API Key
# 请在 .env 文件或环境变量中设置 WHARTTEST_API_KEY
api_key = os.getenv("WHARTTEST_API_KEY", "")

headers = {"accept": "application/json, text/plain,*/*", "X-API-Key": api_key}


def generate_custom_id():
    """
    生成一个基于毫秒级时间戳自增 + 静态 '00000' 的 ID。

    逻辑：
    1. 获取当前毫秒时间戳 current_ms。
    2. 如果 current_ms <= 上一次的 last_ts，则 last_ts += 1；否则 last_ts = current_ms。
    3. 返回 str(last_ts) + '00000'。

    Returns:
        str: 生成的 ID，例如 '171188304512300000000'.
    """
    # 第一次调用时初始化 last_ts
    if not hasattr(generate_custom_id, "last_ts"):
        generate_custom_id.last_ts = 0

    # 获取当前毫秒级时间戳
    current_ms = int(time.time() * 1000)

    # 自增逻辑：如果时间没走或者回退，就在上次基础上 +1
    if current_ms <= generate_custom_id.last_ts:
        generate_custom_id.last_ts += 1
    else:
        generate_custom_id.last_ts = current_ms

    # 拼接固定的 '00000'
    return str(generate_custom_id.last_ts) + "00000"


@mcp.tool(description="获取WHartTest平台项目的名称和对应id")
def get_project_name_and_id() -> str:
    """获取WHartTest平台项目的名称和对应id"""
    url = base_url + "/api/projects/"

    try:
        response = requests.get(url, headers=headers)

        # 检查 HTTP 状态码
        if response.status_code != 200:
            error_info = {
                "error": f"API 请求失败",
                "status_code": response.status_code,
                "url": url,
                "response_text": response.text[:500],
            }
            return json.dumps(error_info, indent=4, ensure_ascii=False)

        # 尝试解析 JSON
        data_dict = response.json()

    except requests.exceptions.ConnectionError:
        error_info = {
            "error": "无法连接到 API 服务器",
            "url": url,
            "base_url": base_url,
            "suggestion": "请检查后端服务是否启动，或检查 WHARTTEST_BACKEND_URL 环境变量配置",
        }
        return json.dumps(error_info, indent=4, ensure_ascii=False)
    except requests.exceptions.JSONDecodeError:
        error_info = {
            "error": "API 返回的不是有效的 JSON 格式",
            "status_code": response.status_code,
            "url": url,
            "response_text": response.text[:500],
        }
        return json.dumps(error_info, indent=4, ensure_ascii=False)
    except Exception as e:
        error_info = {"error": f"未知错误: {str(e)}", "url": url}
        return json.dumps(error_info, indent=4, ensure_ascii=False)

    # 用于存储提取出的 id 和 name 的列表
    extracted_data = []

    # 定义一个递归函数来处理嵌套的 children 列表
    def extract_info(nodes_list):
        if not isinstance(nodes_list, list):
            # 如果输入的不是列表，则停止或报错，取决于期望
            # 在您的结构中，data 和 children 应该是列表
            print("警告: 期望输入列表，但收到了非列表类型。")
            return

        for node in nodes_list:
            # 确保当前元素是字典
            if not isinstance(node, dict):
                print("警告: 期望列表元素是字典，但收到了非字典类型。")
                continue

            # 提取当前节点的 id 和 name
            # 使用 .get() 是安全的，即使键不存在也不会报错
            node_info = {"project_id": node.get("id"), "project_name": node.get("name")}
            extracted_data.append(node_info)

            # 如果当前节点有 children 且 children 是一个列表，则递归处理 children
            children = node.get("children")
            if isinstance(children, list):
                extract_info(children)  # 递归调用

    # 获取顶层 data 列表
    # 使用 .get('data') 是安全的，如果 'data' 键不存在，返回 None
    initial_nodes = data_dict.get("data")

    # 如果 initial_nodes 存在且是一个列表，则开始处理
    if isinstance(initial_nodes, list):
        extract_info(initial_nodes)
    else:
        print("获取到的数据结构不符合预期，未找到 'data' 列表。")

    # 将提取出的列表转换为 JSON 字符串
    # indent 参数用于格式化输出，ensure_ascii=False 保留中文字符和特殊字符
    output_json_string = json.dumps(extracted_data, indent=4, ensure_ascii=False)

    return output_json_string


@mcp.tool(description="根据WHartTest平台项目id去获取模块及id")
def module_to_which_it_belongs(project_id: int) -> str:
    """根据WHartTest平台项目id去获取模块及id"""
    url = base_url + f"/api/projects/{project_id}/testcase-modules/"

    data_dict = requests.get(url, headers=headers).json()

    # 用于存储提取出的 id 和 name 的列表
    extracted_data = []

    # 定义一个递归函数来处理嵌套的 children 列表
    def extract_info(nodes_list):
        if not isinstance(nodes_list, list):
            # 如果输入的不是列表，则停止或报错，取决于期望
            # 在您的结构中，data 和 children 应该是列表
            print("警告: 期望输入列表，但收到了非列表类型。")
            return

        for node in nodes_list:
            # 确保当前元素是字典
            if not isinstance(node, dict):
                print("警告: 期望列表元素是字典，但收到了非字典类型。")
                continue


            # 提取当前节点的 id 和 name
            # 使用 .get() 是安全的，即使键不存在也不会报错
            node_info = {"module_id": node.get("id"), "module_name": node.get("name")}
            extracted_data.append(node_info)

            # 如果当前节点有 children 且 children 是一个列表，则递归处理 children
            children = node.get("children")
            if isinstance(children, list):
                extract_info(children)  # 递归调用

    # 获取顶层 data 列表
    # 使用 .get('data') 是安全的，如果 'data' 键不存在，返回 None
    initial_nodes = data_dict.get("data")

    # 如果 initial_nodes 存在且是一个列表，则开始处理
    if isinstance(initial_nodes, list):
        extract_info(initial_nodes)
    else:
        print("获取到的数据结构不符合预期，未找到 'data' 列表。")

    # 将提取出的列表转换为 JSON 字符串
    # indent 参数用于格式化输出，ensure_ascii=False 保留中文字符和特殊字符
    output_json_string = json.dumps(extracted_data, indent=4, ensure_ascii=False)

    return output_json_string


@mcp.tool(description="获取WHartTest平台用例等级")
def obtain_use_case_level() -> list:
    """
    获取WHartTest平台用例等级
    """
    return ["P0", "P1", "P2", "P3"]


@mcp.tool(description="获取WHartTest平台测试类型")
def obtain_test_type() -> list:
    """
    获取WHartTest平台测试类型
    返回测试类型的标识和中文名称
    """
    return [
        {"value": "smoke", "label": "冒烟测试"},
        {"value": "functional", "label": "功能测试"},
        {"value": "boundary", "label": "边界测试"},
        {"value": "exception", "label": "异常测试"},
        {"value": "permission", "label": "权限测试"},
        {"value": "security", "label": "安全测试"},
        {"value": "compatibility", "label": "兼容性测试"},
    ]


@mcp.tool(description="获取WHartTest平台用例名称和对应id")
def get_the_list_of_use_cases(
    project_id: int = Field(description="项目id"),
    module_id: int = Field(description="模块id"),
):
    """获取WHartTest平台用例"""
    url = (
        base_url
        + f"/api/projects/{project_id}/testcases/?page=1&page_size=1000&search=&module_id={module_id}"
    )

    data_dict = requests.get(url, headers=headers).json()

    # 用于存储提取出的 id 和 name 的列表
    extracted_data = []

    for i in data_dict.get("data"):
        extracted_data.append({"case_id": i.get("id"), "case_name": i.get("name")})
    return json.dumps(extracted_data, indent=4, ensure_ascii=False)


@mcp.tool(description="获取WHartTest平台用例详情")
def get_case_details(
    project_id: int = Field(description="项目id"),
    case_id: int = Field(description="用例id"),
):
    """获取WHartTest平台用例详情"""
    url = base_url + f"/api/projects/{project_id}/testcases/{case_id}/"

    data_dict = requests.get(url, headers=headers).json()

    # 用于存储提取出的 id 和 name 的列表
    extracted_data = data_dict.get("data")
    return json.dumps(extracted_data, indent=4, ensure_ascii=False)


@mcp.tool(description="WHartTest平台保存操作截图到对应用例中")
def save_operation_screenshots_to_the_application_case(
    project_id: int = Field(description="项目id"),
    case_id: int = Field(description="用例id"),
    file_path: str = Field(description="文件路径"),
    title: str = Field(description="截图标题"),
    description: str = Field(description="截图描述"),
    step_number: int = Field(description="步骤编号"),
    page_url: str = Field(description="截图页面URL"),
):
    """
    WHartTest平台保存操作截图到对应用例中
    """
    try:
        # 参数验证
        if not project_id:
            return "项目id不能为空"
        if not case_id:
            return "用例id不能为空"
        if not file_path:
            return "文件路径不能为空"
        if not title:
            return "截图标题不能为空"

        # 检查文件是否存在
        import os

        if not os.path.exists(file_path):
            return f"文件不存在: {file_path}"

        url = (
            base_url
            + f"/api/projects/{project_id}/testcases/{case_id}/upload-screenshots/"
        )

        # 根据文件扩展名确定 MIME 类型
        file_ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
        }
        content_type = mime_types.get(file_ext, "image/png")  # 默认为 png

        # 准备文件和表单数据
        with open(file_path, "rb") as file:
            files = {"screenshots": (os.path.basename(file_path), file, content_type)}

            # 只添加有值的字段
            data = {"title": title}  # title 是必填的

            if description and description.strip():
                data["description"] = description
            if step_number is not None:
                data["step_number"] = str(step_number)
            if page_url and page_url.strip():
                data["page_url"] = page_url

            # 发起请求 - 注意这里不使用json参数，而是用data参数
            response = requests.post(url, headers=headers, files=files, data=data)

            # 检查响应状态
            response.raise_for_status()

            # 处理响应
            if response.status_code in [200, 201]:
                return f"截图 '{title}' 上传成功"
            else:
                return (
                    f"上传失败，状态码: {response.status_code}, 响应: {response.text}"
                )

    except FileNotFoundError:
        return f"文件未找到: {file_path}"
    except requests.exceptions.HTTPError as e:
        return f"HTTP错误: {e}, 响应内容: {response.text if 'response' in locals() else '无响应内容'}"
    except Exception as e:
        return f"上传截图时发生错误: {str(e)}"




@mcp.tool(description="保存WHartTest平台功能测试用例")
def add_functional_case(
    project_id: int = Field(description="项目id"),
    name: str = Field(description="用例名称"),
    precondition: str = Field(description="前置条件"),
    level: str = Field(description="用例等级，可选值：P0、P1、P2、P3"),
    module_id: int = Field(description="模块id"),
    steps: list = Field(
        description='用例步骤,示例：,[{"step_number": 1,"description": "步骤描述1","expected_result": "预期结果1"},{"step_number": 2,"description": "步骤描述2","expected_result": "预期结果2"}]'
    ),
    notes: str = Field(description="备注"),
    review_status: str = Field(
        default="pending_review",
        description="审核状态: pending_review(待审核), approved(通过), needs_optimization(优化), optimization_pending_review(优化待审核), unavailable(不可用)",
    ),
    test_type: str = Field(
        default="functional",
        description="测试类型: smoke(冒烟测试), functional(功能测试), boundary(边界测试), exception(异常测试), permission(权限测试), security(安全测试), compatibility(兼容性测试)",
    ),
):
    """
    保WHartTest平台存WHartTest平台功能测试用例
    """
    try:
        if not project_id:
            return "项目id不能为空"
        if not name:
            return "用例名称不能为空"
        if not precondition:
            return "前置条件不能为空"
        if not level:
            return "用例等级不能为空"

        # 验证用例等级是否为合法值
        valid_levels = ["P0", "P1", "P2", "P3"]
        if level not in valid_levels:
            return f"用例等级必须是以下值之一：{', '.join(valid_levels)}，当前值为：{level}"

        # 验证测试类型是否为合法值
        valid_test_types = [
            "smoke",
            "functional",
            "boundary",
            "exception",
            "permission",
            "security",
            "compatibility",
        ]
        if test_type and test_type not in valid_test_types:
            return f"测试类型必须是以下值之一：{', '.join(valid_test_types)}，当前值为：{test_type}"

        if not module_id:
            return "模块id不能为空"
        if not steps:
            return "用例步骤不能为空"

        url = base_url + f"/api/projects/{project_id}/testcases/"
        data = {
            "name": name,
            "precondition": precondition,
            "level": level,
            "module_id": module_id,
            "steps": steps,
            "notes": notes,
            "review_status": review_status,
            "test_type": test_type,
        }

        # 发起请求
        response = requests.post(url, headers=headers, json=data)
        print("status =", response.status_code)
        print("content-type =", response.headers.get("Content-Type"))
        print("body-preview =", response.text[:200])
        # 如有非 2xx 状态码直接抛异常
        response.raise_for_status()

        response_payload = {}
        try:
            response_payload = response.json()
        except ValueError:
            pass

        created_case = {}
        if isinstance(response_payload, dict):
            created_case = response_payload.get("data") or response_payload

        # 返回详细的用例信息,而不是简单的"保存成功"
        testcase_snapshot = {
            "id": created_case.get("id"),
            "name": created_case.get("name", name),
            "module_id": created_case.get("module_id") or module_id,
            "level": created_case.get("level") or level,
            "precondition": created_case.get("precondition") or precondition,
            "notes": created_case.get("notes") or notes,
            "steps": created_case.get("steps") or steps,
            "project_id": created_case.get("project") or project_id,
        }

        # 201，代表成功保存
        if response.json().get("code") == 201:
            return {
                "message": "保存成功",
                "testcase": {
                    "id": created_case.get("id"),
                    "name": created_case.get("name", name),
                },
            }
        else:
            return {"message": "保存失败，请重试", "response": response_payload}
    except requests.exceptions.HTTPError as e:
        print("HTTPError =", e)
        return e



@mcp.tool(description="编辑WHartTest平台功能测试用例")
def edit_functional_case(
    project_id: int = Field(description="项目id"),
    case_id: int = Field(description="用例id"),
    name: str = Field(description="用例名称"),
    precondition: str = Field(description="前置条件"),
    level: str = Field(description="用例等级，可选值：P0、P1、P2、P3"),
    module_id: int = Field(description="模块id"),
    steps: list = Field(
        description='用例步骤,示例：,[{"step_number": 1,"description": "步骤描述1","expected_result": "预期结果1"},{"step_number": 2,"description": "步骤描述2","expected_result": "预期结果2"}]'
    ),
    notes: str = Field(description="备注"),
    review_status: str = Field(
        default=None,
        description="审核状态(可选): pending_review(待审核), approved(通过), needs_optimization(优化), optimization_pending_review(优化待审核), unavailable(不可用)",
    ),
    is_optimization: bool = Field(
        default=False,
        description="是否为优化操作，True时自动设为optimization_pending_review",
    ),
    test_type: str = Field(
        default=None,
        description="测试类型(可选): smoke(冒烟测试), functional(功能测试), boundary(边界测试), exception(异常测试), permission(权限测试), security(安全测试), compatibility(兼容性测试)",
    ),
):
    """
    编辑WHartTest平台功能测试用例
    """
    try:
        if not project_id:
            return "项目id不能为空"
        if not case_id:
            return "用例id不能为空"


        url = base_url + f"/api/projects/{project_id}/testcases/{case_id}/"
        data = {
            "name": name,
            "precondition": precondition,
            "level": level,
            "module_id": module_id,
            "steps": steps,
            "notes": notes,
        }

        # 验证用例等级是否为合法值
        valid_levels = ["P0", "P1", "P2", "P3"]
        if level not in valid_levels:
            return f"用例等级必须是以下值之一：{', '.join(valid_levels)}，当前值为：{level}"

        # 验证测试类型是否为合法值
        valid_test_types = [
            "smoke",
            "functional",
            "boundary",
            "exception",
            "permission",
            "security",
            "compatibility",
        ]
        if test_type:
            if test_type not in valid_test_types:
                return f"测试类型必须是以下值之一：{', '.join(valid_test_types)}，当前值为：{test_type}"
            data["test_type"] = test_type

        # 处理优化工作流
        if is_optimization:
            data["review_status"] = "optimization_pending_review"
        elif review_status:
            data["review_status"] = review_status

        # 发起请求
        response = requests.patch(url, headers=headers, json=data)
        print("status =", response.status_code)
        print("content-type =", response.headers.get("Content-Type"))
        print("body-preview =", response.text[:200])
        # 如有非 2xx 状态码直接抛异常
        response.raise_for_status()
        # 200，代表成功编辑
        if response.json().get("code") == 200:
            return f"用例：{name}编辑成功"
        else:
            return "编辑失败，请重试"
    except requests.exceptions.HTTPError as e:
        print("HTTPError =", e)
        return e


# ============ 图表生成工具 ============




@mcp.tool(
    description="创建新的drawio图表。当用户要求创建新图表或从头开始绘制时使用此工具。如果用户要求在新页面创建图表，请设置page_name参数。"
)
def display_diagram(
    xml: str = Field(description="完整的drawio XML内容，必须是有效的mxGraphModel格式"),
    page_name: str = Field(
        default="",
        description="可选的页面名称。如果指定，将创建新页面而不是替换现有图表。例如：'小狗图表'、'流程图2'",
    ),
) -> str:
    """
    创建新的drawio图表

    Args:
        xml: 完整的drawio XML内容
        page_name: 可选，指定页面名称时会添加为新页面

    Returns:
        成功或失败信息
    """
    # 验证XML基本结构
    if not xml or not xml.strip():
        return json.dumps(
            {"success": False, "error": "XML内容不能为空"}, ensure_ascii=False
        )

    # 检查是否包含必要的drawio结构
    if "<mxGraphModel" not in xml or "<root>" not in xml:
        return json.dumps(
            {
                "success": False,
                "error": "无效的drawio XML格式，必须包含mxGraphModel和root元素",
            },
            ensure_ascii=False,
        )

    # 返回成功，包含XML内容供前端渲染
    result = {
        "success": True,
        "action": "display",
        "xml": xml,
        "message": "图表创建成功",
    }

    # 如果指定了页面名称，添加到结果中
    if page_name and page_name.strip():
        result["page_name"] = page_name.strip()
        result["message"] = f"图表页面 '{page_name}' 创建成功"

    return json.dumps(result, ensure_ascii=False)


@mcp.tool(
    description="""编辑现有的drawio图表。支持以下操作类型：
- replace_page: 替换指定页面的完整内容（推荐，最可靠）
- add: 在指定页面添加新元素
- delete: 删除指定ID的元素
- update: 更新元素的属性

优先使用 replace_page 操作，因为它最可靠。"""
)
def edit_diagram(
    operations: str = Field(
        description="""JSON格式的操作列表。每个操作是一个对象，包含：
- action: 操作类型，可选 "replace_page" | "add" | "delete" | "update"
- page_index: 目标页面索引（从0开始，默认0）

replace_page 操作（推荐）：
- page_xml: 完整的页面 mxGraphModel XML
- page_name: 可选，页面名称

add 操作：
- element: 要添加的 mxCell XML

delete 操作：
- element_id: 要删除的元素ID

update 操作：
- element_id: 要更新的元素ID
- properties: 要更新的属性对象，如 {"value": "新文本", "style": "新样式"}

示例：
[{"action": "replace_page", "page_index": 1, "page_name": "小猫", "page_xml": "<mxGraphModel>...</mxGraphModel>"}]
"""
    ),
) -> str:
    """
    编辑现有的drawio图表（企业级 DOM 操作）

    Args:
        operations: JSON字符串，包含操作列表

    Returns:
        成功或失败信息，包含操作供前端执行
    """
    # 解析操作
    try:
        if isinstance(operations, str):
            op_list = json.loads(operations)
        else:
            op_list = operations
    except json.JSONDecodeError as e:
        return json.dumps(
            {"success": False, "error": f"无法解析操作JSON: {str(e)}"},
            ensure_ascii=False,
        )

    # 验证操作格式
    if not isinstance(op_list, list):
        return json.dumps(
            {"success": False, "error": "operations必须是一个数组"}, ensure_ascii=False
        )

    valid_actions = ["replace_page", "add", "delete", "update"]
    validated_ops = []

    for i, op in enumerate(op_list):
        if not isinstance(op, dict):
            return json.dumps(
                {"success": False, "error": f"第{i + 1}个操作必须是对象"},
                ensure_ascii=False,
            )

        action = op.get("action")
        if action not in valid_actions:
            return json.dumps(
                {
                    "success": False,
                    "error": f"第{i + 1}个操作的action无效，必须是: {', '.join(valid_actions)}",
                },
                ensure_ascii=False,
            )

        validated_op = {"action": action, "pageIndex": op.get("page_index", 0)}

        # 验证各操作类型的必需字段
        if action == "replace_page":
            if "page_xml" not in op:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"第{i + 1}个操作(replace_page)缺少page_xml字段",
                    },
                    ensure_ascii=False,
                )
            validated_op["pageXml"] = op["page_xml"]
            if "page_name" in op:
                validated_op["pageName"] = op["page_name"]

        elif action == "add":
            if "element" not in op:
                return json.dumps(
                    {"success": False, "error": f"第{i + 1}个操作(add)缺少element字段"},
                    ensure_ascii=False,
                )
            validated_op["element"] = op["element"]

        elif action == "delete":
            if "element_id" not in op:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"第{i + 1}个操作(delete)缺少element_id字段",
                    },
                    ensure_ascii=False,
                )
            validated_op["elementId"] = op["element_id"]

        elif action == "update":
            if "element_id" not in op or "properties" not in op:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"第{i + 1}个操作(update)缺少element_id或properties字段",
                    },
                    ensure_ascii=False,
                )
            validated_op["elementId"] = op["element_id"]
            validated_op["properties"] = op["properties"]

        validated_ops.append(validated_op)

    if not validated_ops:
        return json.dumps(
            {"success": False, "error": "至少需要一个操作"}, ensure_ascii=False
        )

    # 返回成功，包含操作供前端执行
    return json.dumps(
        {
            "success": True,
            "action": "edit",
            "operations": validated_ops,
            "message": f"已准备{len(validated_ops)}个编辑操作",
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    # 使用 streamable-http 传输方式
    # host="0.0.0.0" 允许从其他容器访问
    # port=8006 指定端口
    #
    # 鉴权（必须）：服务以 root 绑定 0.0.0.0，历史上无任何鉴权，任何可达方都能
    # 调用全部工具（含本地文件读取与后端 API 代理）。现在通过共享密钥校验 Bearer token；
    # 未配置 MCP_SHARED_TOKEN 且未显式 MCP_ALLOW_UNAUTHENTICATED=true 时拒绝启动。
    from mcp_auth import enforce_auth_or_exit

    # 未配置 MCP_SHARED_TOKEN 且未显式允许裸奔时拒绝启动（fail closed）
    enforce_auth_or_exit("WHartTest_tools")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8006)
