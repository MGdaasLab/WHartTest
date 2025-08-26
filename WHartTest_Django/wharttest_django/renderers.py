import json
from rest_framework.renderers import JSONRenderer
from rest_framework.utils import encoders

class UnifiedResponseRenderer(JSONRenderer):
    """
    自定义 Renderer，用于将 API 响应统一格式化。
    确保所有 API 端点在成功和错误时都返回遵循以下统一结构的 JSON 响应：
    {
      "status": "success" / "error",
      "code": 200 / 400 / 500,
      "message": "操作成功" / "具体的错误信息",
      "data": { ... } / null,
      "errors": { ... } / null / []
    }
    """
    charset = 'utf-8'
    # ensure_ascii = False # 如果需要支持非 ASCII 字符直接输出，可以取消注释

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context['response']
        status_code = response.status_code

        # 对于 HTTP 204 No Content，将状态码修改为 200 OK
        # 这样可以确保返回统一格式的响应体
        if status_code == 204:
            # 保存原始状态码，以便后续处理
            response._original_status = 204
            response.status_code = 200
            status_code = 200

        # 初始的统一响应结构
        # data 和 errors 默认为 None，以便更明确地控制它们的值
        unified_response = {
            "status": "success",  # 默认为 success
            "code": status_code,
            "message": "",        # 稍后填充
            "data": None,
            "errors": None
        }

        # 检查是否是 simplejwt 的特定响应格式
        if isinstance(data, dict):
            if 'access' in data and 'refresh' in data and status_code == 200: # simplejwt 成功获取 token
                unified_response["status"] = "success"
                unified_response["message"] = "Token 获取成功"
                unified_response["data"] = data
                # errors 保持 None
            elif 'detail' in data and 'code' in data and 'messages' not in data and status_code >= 400: # simplejwt 错误
                # 排除 DRF 的 TokenError (它有 'messages' 字段)
                unified_response["status"] = "error"
                unified_response["message"] = data.get('detail', '认证失败')
                unified_response["errors"] = {'token_error': data.get('detail'), 'error_code': data.get('code')}
                # data 保持 None
                data = None # 将原始 data 置为 None，避免后续处理逻辑的干扰

        # 如果 data 不是 None (即未被 simplejwt 逻辑处理掉)
        if data is not None:
            if status_code >= 400: # HTTP 错误状态码
                unified_response["status"] = "error"
                unified_response["data"] = None # 错误时 data 为 null

                if isinstance(data, dict) and 'detail' in data:
                    # 处理 DRF 的标准错误响应 (例如 NotFound, PermissionDenied 等的 detail 字段)
                    unified_response["message"] = data.get('detail', '请求处理失败')
                    unified_response["errors"] = {'detail': data.get('detail')}
                elif isinstance(data, (dict, list)):
                    # 处理验证错误 (data 是包含字段错误的字典) 或其他列表形式的错误
                    unified_response["message"] = "请求参数有误或处理失败"
                    unified_response["errors"] = data # errors 可以是 dict 或 list
                else: # 其他未知错误类型
                    unified_response["message"] = str(data) # 将错误信息转为字符串
                    unified_response["errors"] = {'detail': str(data)}

            # 原始状态码为 204 的情况已在方法开始处处理
            # 这里不再需要单独处理 204 的情况

            else: # HTTP 成功状态码 (200, 201, 202, 203)
                unified_response["status"] = "success"
                # errors 保持 None
                if isinstance(data, dict) and all(k in data for k in ["status", "code", "message"]):
                    # 如果 data 已经是预期的统一格式 (例如视图中手动构造)
                    # 则直接使用 data 的内容覆盖，避免双重包装
                    # 但要确保原始的 status_code 优先
                    original_code = unified_response["code"]
                    unified_response.update(data)
                    unified_response["code"] = original_code # 保持 DRF response 的 status_code
                else:
                    unified_response["data"] = data # 原始数据作为 data 字段
                    unified_response["message"] = "操作成功"


        # 确保 message 字段不为空
        if not unified_response.get("message"):
            if unified_response["status"] == "success":
                unified_response["message"] = "操作成功完成"
            else:
                # 对于错误，如果 errors 字段有内容，message 可以更通用
                if unified_response.get("errors"):
                    unified_response["message"] = "请求处理失败，请查看错误详情"
                else:
                    unified_response["message"] = "发生未知错误"

        # 根据最终的 status 决定是否包含 data 和 errors 字段 (如果它们是 None)
        # DRF JSONRenderer 默认会序列化 None 为 null，所以这一步主要是为了清晰
        if unified_response["status"] == "success":
            if unified_response.get("errors") is not None: # 理论上成功时 errors 应该是 None
                 unified_response["errors"] = None # 强制设为 None
        elif unified_response["status"] == "error":
            if unified_response.get("data") is not None: # 理论上错误时 data 应该是 None
                unified_response["data"] = None # 强制设为 None

            # 如果 errors 字段是 None (例如，在 status_code >= 400 但 data 不是预期错误格式时)
            # 则填充一个通用的错误信息。
            if unified_response.get("errors") is None:
                 unified_response["errors"] = {'detail': unified_response.get("message", '请求处理时发生错误，具体原因未知。')}

        # 对于原始状态码为 HTTP 204 No Content 的情况
        # 我们已经在方法开始处将其修改为 200 OK
        # 并在这里构建了统一格式的响应体
        # 如果是删除操作（原始状态码为204），添加默认的成功消息
        if status_code == 200 and data is None and getattr(response, '_original_status', None) == 204:
            unified_response["message"] = "删除操作成功完成"

        return super().render(unified_response, accepted_media_type, renderer_context)