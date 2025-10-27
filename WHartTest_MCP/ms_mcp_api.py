# -*- coding: utf-8 -*-
# @Author : 西红柿炒蛋
# @Email  : duanduanxc@qq.com
# @Time   : 2025/6/9 09:17

# 加载 .env 文件（本地开发时使用）
from dotenv import load_dotenv
load_dotenv()

import json
import time
import uuid
import base64
import requests
from Crypto.Cipher import AES
from fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP(
    name="testcase_tools"
)

def aes_encrypt(text: str, secret_key: str, iv: str) -> str:
    """
    AES-CBC 加密 + Base64 编码
    text       : 待加密字符串 (AccessKey|UUID|timestamp)
    secret_key : 16 字节 Secret Key
    iv         : 16 字节 Access Key 作为 IV
    """
    bs = AES.block_size  # 16
    # PKCS5Padding
    pad = lambda s: s + (bs - len(s) % bs) * chr(bs - len(s) % bs)
    cipher = AES.new(secret_key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
    encrypted = cipher.encrypt(pad(text).encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf‑8')


class ApiClient:
    """
    API客户端类，复用Session以提高性能
    """
    def __init__(self):
        # 从环境变量读取配置，如果未设置则使用默认值
        import os
        self.api_host = os.getenv("MS_API_HOST", "http://ms.example.com")
        self.access_key = os.getenv("MS_ACCESS_KEY", "your_access_key")
        self.secret_key = os.getenv("MS_SECRET_KEY", "your_secret_key_16")
        self.session = requests.Session()
        self._update_headers()

    def _update_headers(self, content_type="application/json"):
        """更新请求头，包含签名信息"""
        ts = int(time.time() * 1000)
        rnd = str(uuid.uuid4())
        plain = f"{self.access_key}|{rnd}|{ts}"
        signature = aes_encrypt(plain, self.secret_key, self.access_key)

        # 清除之前的headers，重新设置
        self.session.headers.clear()

        headers = {
            "accessKey": self.access_key,
            "signature": signature
        }

        # 只有在非multipart请求时才设置Content-Type
        if content_type and content_type != "multipart/form-data":
            headers["Content-Type"] = content_type

        self.session.headers.update(headers)

    def get(self, endpoint: str, **kwargs):
        """发送GET请求"""
        self._update_headers()  # 每次请求前更新签名
        url = f"{self.api_host}{endpoint}"
        return self.session.get(url, **kwargs)

    def post(self, endpoint: str, json_data=None, files=None, data=None, **kwargs):
        """发送POST请求，支持JSON和multipart"""
        url = f"{self.api_host}{endpoint}"

        if files:
            # multipart/form-data 请求 - 不设置Content-Type让requests自动处理
            self._update_headers(content_type="multipart/form-data")
            return self.session.post(url, files=files, data=data, **kwargs)
        else:
            # application/json 请求
            self._update_headers()
            if json_data:
                kwargs['json'] = json_data
            return self.session.post(url, data=data, **kwargs)

    def post_multipart(self, endpoint: str, files=None, data=None, **kwargs):
        """专门用于multipart/form-data请求"""
        self._update_headers(content_type="multipart/form-data")
        url = f"{self.api_host}{endpoint}"
        return self.session.post(url, files=files, data=data, **kwargs)

    def post_json(self, endpoint: str, json_data=None, **kwargs):
        """专门用于JSON请求"""
        self._update_headers()
        url = f"{self.api_host}{endpoint}"
        return self.session.post(url, json=json_data, **kwargs)

    def put(self, endpoint: str, json_data=None, files=None, data=None, **kwargs):
        """发送PUT请求，支持JSON和multipart"""
        url = f"{self.api_host}{endpoint}"

        if files:
            # multipart/form-data 请求
            self._update_headers(content_type="multipart/form-data")
            return self.session.put(url, files=files, data=data, **kwargs)
        else:
            # application/json 请求
            self._update_headers()
            if json_data:
                kwargs['json'] = json_data
            return self.session.put(url, data=data, **kwargs)

    def delete(self, endpoint: str, **kwargs):
        """发送DELETE请求"""
        self._update_headers()  # 每次请求前更新签名
        url = f"{self.api_host}{endpoint}"
        return self.session.delete(url, **kwargs)

client = ApiClient()

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

@mcp.tool(description="获取项目名称和项目id")
def get_project_name_and_id():
    """
    获取项目名称和项目id
    """
    r = client.get("/project/list/options/100001").json()
    if r.get("code") == 100200:
        project_dict = []
        for project in r.get("data"):
            project_name = project.get("name")
            project_id = project.get("id")
            # 打包为字典，添加到 project_dict 中
            project_dict.append({"project_name": project_name, "project_id": project_id})
        return project_dict
    else:
        return "请求失败，请重试。"

@mcp.tool(description="获取模块的名称和对应id")
def module_to_which_it_belongs(project_id: int = Field(description='项目id')):
    """获取模块的名称和id"""
    data_dict = client.get(f"/functional/case/module/tree/{project_id}").json()
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
            node_info = {
                "id": node.get("id"),
                "name": node.get("name")
            }
            extracted_data.append(node_info)

            # 如果当前节点有 children 且 children 是一个列表，则递归处理 children
            children = node.get("children")
            if isinstance(children, list):
                extract_info(children)  # 递归调用

    # 获取顶层 data 列表
    # 使用 .get('data') 是安全的，如果 'data' 键不存在，返回 None
    initial_nodes = data_dict.get('data')

    # 如果 initial_nodes 存在且是一个列表，则开始处理
    if isinstance(initial_nodes, list):
        extract_info(initial_nodes)
    else:
        print("获取到的数据结构不符合预期，未找到 'data' 列表。")

    # 将提取出的列表转换为 JSON 字符串
    # indent 参数用于格式化输出，ensure_ascii=False 保留中文字符和特殊字符
    output_json_string = json.dumps(extracted_data, indent=4, ensure_ascii=False)

    return output_json_string

@mcp.tool(description="获取用例等级的名称和对应id")
def obtain_use_case_level(project_id: int = Field(description='项目id')):
    """获取用例等级的名称和对应id"""
    data = client.get(f"/functional/case/default/template/field/{project_id}").json()

    # 解析 JSON 字符串为 Python 字典

    # 导航到包含选项列表的部分
    # 使用 .get() 方法安全地访问嵌套键，避免 KeyError
    data_obj = data.get("data")
    if not isinstance(data_obj, dict):
        print("错误: JSON结构中未找到有效的 'data' 对象。")
        exit()

    custom_fields_list = data_obj.get("customFields")
    if not isinstance(custom_fields_list, list) or not custom_fields_list:
        print("错误: JSON结构中未找到有效的 'customFields' 列表或列表为空。")
        exit()

    # 假设第一个 customField 对象就是我们需要的“用例等级”字段
    # 如果实际情况不是这样，您可能需要遍历 custom_fields_list 并检查 fieldName 或 internalFieldKey
    target_field = custom_fields_list[0]  # 获取第一个自定义字段配置

    options_list = target_field.get("options")
    if not isinstance(options_list, list):
        print("错误: 在目标自定义字段中未找到有效的 'options' 列表。")
        exit()

    # 用于存储 P几 对应的 fieldId 的字典
    p_level_field_ids = {}

    # 遍历 options 列表，提取 text 和 fieldId
    for option in options_list:
        # 确保 option 是一个字典
        if isinstance(option, dict):
            text = option.get("text")
            field_id = option.get("fieldId")

            # 检查 text 是否是字符串，并且 fieldId 存在
            if isinstance(text, str) and field_id is not None:
                # 根据您的需求，只提取 text 以 "P" 开头的项
                if text.startswith("P"):
                    p_level_field_ids[text] = field_id

    # 将结果字典转换为 JSON 字符串
    # indent=4 用于格式化输出，ensure_ascii=False 保留中文字符（虽然这里没有）
    output_json_string = json.dumps(p_level_field_ids, indent=4, ensure_ascii=False)

    return output_json_string

@mcp.tool(description='生成测试用例步骤数据')
def steps_for_generating_test_cases(testcases: list = Field(description='传入的步骤格式列表,示例：[{"desc": 输入账号,"result": 输入账号成功},{"desc": 输入密码,"result": 输入密码成功}]')):
    """
    生成测试用例步骤数据
    testcases：传入一个列表包含字典，一个字典就是一个步骤和预期
    示例：[{"desc": 输入账号,"result": 输入账号成功},{"desc": 输入密码,"result": 输入密码成功}]
    """
    # 如果不是 list 就返回错误提示
    if not isinstance(testcases, list):
        return '请传入一个列表,示例：[{"desc": 输入账号,"result": 输入账号成功},{"desc": 输入密码,"result": 输入密码成功}]'
    # 如果 desc 或 result 都是空字符串 就返回错误提示
    if not all(i.get("desc") and i.get("result") for i in testcases):
        return '请传入一个列表,示例：[{"desc": 输入账号,"result": 输入账号成功},{"desc": 输入密码,"result": 输入密码成功}]'
    steps = []
    num = 0
    for i in testcases:
        desc = i.get("desc")
        result = i.get("result")
        cases = {
            "id": generate_custom_id(),
            "num": num,
            "desc": desc,
            "result": result
        }
        steps.append(cases)
        num += 1
    return steps

@mcp.tool(description='保存功能测试用例')
def add_functional_case(
        project_id: int = Field(description='项目id'),
        template_id: int = Field(description='模板id'),
        name: str = Field(description='用例名称'),
        prerequisite: str = Field(description='前置条件'),
        level: str = Field(description='用例等级'),
        field_id:  int = Field(description='用例等级id'),
        module_id: int = Field(description='模块id'),
        steps: list = Field(description='用例步骤,示例：,[{"step_number": 1,"description": "步骤描述1","expected_result": "预期结果1"},{"step_number": 2,"description": "步骤描述2","expected_result": "预期结果2"}]'),
        ):
    """
    保存功能测试用例
    """
    try:
        steps_str = json.dumps(
            steps,  # 要转成字符串的对象
            ensure_ascii=False,  # 不把中文转成 \uXXXX
            separators=(",", ":")  # 去掉空格，生成紧凑格式
        )
        payload = {
            "id": "",
            "projectId": f"{project_id}",
            "templateId": f"{template_id}",
            "name": name,
            "prerequisite": prerequisite,
            "caseEditType": "STEP",
            "steps": steps_str,
            "textDescription": "",
            "expectedResult": "",
            "description": "",
            "publicCase": False,
            "moduleId": module_id,
            "versionId": "",
            "tags": [],
            "customFields": [
                {
                    "fieldId": field_id,
                    "value": level
                }
            ],
            "relateFileMetaIds": [],
            "functionalPriority": "",
            "reviewStatus": "UN_REVIEWED",
            "caseDetailFileIds": []
        }

        # 按照 multipart/form-data 方式传递，requests 会自动生成 boundary
        files = {
            "request": (
                "blob",  # 文件名占位，可随意
                json.dumps(payload),  # JSON 字符串
                "application/json;charset=utf-8"
            )
        }

        # 发起请求
        response = client.post("/functional/case/add",files=files)
        print("status =", response.status_code)
        print("content-type =", response.headers.get("Content-Type"))
        print("body-preview =", response.text[:200])
        # 如有非 2xx 状态码直接抛异常
        response.raise_for_status()
        # 如果code返回100200，代表成功保存
        if response.json().get("code") == 100200:
            return "保存成功"
        else:
            return "保存失败，请重试"
    except requests.exceptions.HTTPError as e:
        print("HTTPError =", e)
        return e

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8007)