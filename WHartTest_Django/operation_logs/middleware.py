import time
import json
import logging
import re
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from django.urls import resolve
from .models import OperationLog

logger = logging.getLogger(__name__)
User = get_user_model()

# 敏感字段掩码列表
SENSITIVE_EXACT_KEYS = {
    'password', 'password_confirm', 'token', 'access', 'refresh',
    'secret', 'api_key', 'key', 'private_key', 'authorization', 'credential'
}

SENSITIVE_PARTIAL_KEYS = {
    'password', 'token', 'secret', 'private_key', 'authorization', 'credential'
}

USERNAME_CANDIDATE_KEYS = {
    'username', 'user_name', 'account', 'login', 'email', 'raw_account_id'
}

ALWAYS_IGNORED_PATH_KEYWORDS = (
    '/operation-logs/',
    '/token/refresh/',
)

READ_ONLY_IGNORED_PATH_KEYWORDS = (
    '/accounts/me/',
    '/schema/',
)

IGNORED_METHODS = {'HEAD', 'OPTIONS'}

APP_LABEL_MAPPINGS = {
    'accounts': '用户管理',
    'projects': '项目管理',
    'testcases': '测试用例',
    'skills': '技能管理',
    'task_center': '任务中心',
    'api_keys': 'API Key管理',
    'mcp_tools': 'MCP配置管理',
    'knowledge': '知识库管理',
    'prompts': '提示词管理',
    'requirements': '需求管理',
    'orchestrator_integration': '智能编排',
    'langgraph_integration': 'AI对话',
    'ui_automation': 'UI自动化',
    'weixin_integration': '微信集成',
    'api_database_configs': 'API数据库配置',
    'api_environments': 'API环境管理',
    'api_modules': 'API接口模块',
    'api_functions': 'API自定义函数',
    'api_interfaces': 'API接口管理',
    'api_testcases': 'API测试用例',
    'api_testtasks': 'API测试任务',
    'api_sync': 'API接口同步',
    'operation_logs': '操作日志审计',
    'file_management': '文件管理',
}

# 视图类与模块中文对应映射
MODULE_MAPPINGS = {
    # 认证与用户
    'MyTokenObtainPairView': '用户认证',
    'TokenRefreshView': '用户认证',
    'UserViewSet': '用户管理',
    'UserManagementView': '用户管理',
    'GroupViewSet': '用户组管理',
    'ContentTypeViewSet': '系统权限资源',
    'OrganizationViewSet': '组织管理',
    'OrganizationManagementView': '组织管理',
    'PermissionViewSet': '权限管理',
    'PermissionManagementView': '权限管理',
    
    # 系统与通用
    'SystemConfigViewSet': '系统配置',
    'SystemConfigView': '系统配置',
    'OperationLogViewSet': '操作日志审计',
    
    # 项目与用例
    'ProjectViewSet': '项目管理',
    'TestCaseViewSet': '测试用例',
    'TestCaseModuleViewSet': '用例模块',
    'TestSuiteViewSet': '测试套件',
    'TestExecutionViewSet': '测试执行',
    'RequirementViewSet': '需求管理',
    'TemplateViewSet': '用例模板',
    
    # 需求文档与评审
    'RequirementDocumentViewSet': '需求文档',
    'RequirementModuleViewSet': '需求模块',
    'ReviewReportViewSet': '评审报告',
    'ReviewIssueViewSet': '评审问题',
    'ModuleReviewResultViewSet': '模块评审结果',

    # 定时任务与技能
    'SkillViewSet': '技能管理',
    'ScheduledTaskViewSet': '定时任务',
    'TaskExecutionViewSet': '任务执行',
    
    # API管理与配置
    'APIKeyViewSet': 'API Key管理',
    'ApiKeyViewSet': 'API Key管理',
    'RemoteMCPConfigViewSet': 'MCP配置管理',
    'RemoteMcpConfigViewSet': 'MCP配置管理',
    'KnowledgeViewSet': '知识库管理',
    'KnowledgeBaseViewSet': '知识库管理',
    'DocumentViewSet': '知识库文档',
    'DocumentChunkViewSet': '文档切片',
    'QueryLogViewSet': '知识库检索日志',
    
    # 协同与大模型集成
    'ProjectSubAgentViewSet': '项目子代理',
    'UserPromptViewSet': '用户提示词',
    'LLMConfigBundleViewSet': 'LLM配置',
    'UserToolApprovalViewSet': '工具审批',
    'OrchestratorTaskViewSet': '协同任务',
    'AgentLoopStreamAPIView': '智能编排',
    'AgentLoopStopAPIView': '智能编排',
    'AgentLoopResumeAPIView': '智能编排',
    'ChatAPIView': 'AI对话',
    'ChatBatchDeleteAPIView': 'AI对话',
    'ChatHistoryAPIView': 'AI对话',
    'ChatResumeAPIView': 'AI对话',
    'ProviderChoicesAPIView': 'LLM配置',
    'KnowledgeRAGAPIView': '知识库检索',
    'TokenUsageStatsAPIView': 'Token使用统计',
    'UserChatSessionsAPIView': 'AI对话',
    
    # API测试模块
    'UiAutomationViewSet': 'UI自动化',
    'ApiTestingViewSet': '接口自动化',
    'ApiDatabaseConfigViewSet': 'API数据库配置',
    'ApiEnvironmentViewSet': 'API环境管理',
    'ApiEnvironmentVariableViewSet': 'API环境变量',
    'ApiGlobalRequestHeaderViewSet': 'API全局请求头',
    'ApiCustomFunctionViewSet': 'API自定义函数',
    'ApiModuleViewSet': 'API接口模块',
    'ApiInterfaceViewSet': 'API接口管理',
    'ApiInterfaceResultViewSet': 'API接口结果',
    'ApiTestCaseViewSet': 'API测试用例',
    'ApiTestCaseTagViewSet': 'API用例标签',
    'ApiTestCaseGroupViewSet': 'API用例组',
    'ApiTestReportViewSet': 'API测试报告',
    'ApiTestTaskSuiteViewSet': 'API测试任务集',
    'ApiTestTaskExecutionViewSet': 'API任务执行',
    'ApiSyncConfigViewSet': 'API接口同步',
    'ApiSyncHistoryViewSet': 'API同步历史',
    'ApiGlobalSyncConfigViewSet': 'API全局同步配置',
    
    # UI自动化模块
    'UiModuleViewSet': 'UI模块',
    'UiPageViewSet': 'UI页面',
    'UiElementViewSet': 'UI元素',
    'UiPageStepsViewSet': 'UI页面步骤',
    'UiPageStepsDetailedViewSet': 'UI页面步骤详情',
    'UiTestCaseViewSet': 'UI用例',
    'UiCaseStepsDetailedViewSet': 'UI用例步骤详情',
    'UiExecutionRecordViewSet': 'UI执行记录',
    'UiPublicDataViewSet': 'UI公共数据',
    'UiEnvironmentConfigViewSet': 'UI环境配置',
    'ActuatorViewSet': '执行器',
    'UiBatchExecutionRecordViewSet': 'UI批量执行记录',
    'ImportExportTemplateViewSet': '导入导出模板',

    # 账户 / 系统 / 微信 / MCP
    'CurrentUserAPIView': '当前用户',
    'UserCreateAPIView': '用户管理',
    'SystemConfigPublicView': '系统配置',
    'KnowledgeGlobalConfigView': '知识库管理',
    'MCPToolRunnerView': 'MCP配置管理',
    'RemoteMCPConfigPingView': 'MCP配置管理',
    'WeixinLoginStartAPIView': '微信集成',
    'WeixinLoginStatusAPIView': '微信集成',
    'WeixinBotAccountListAPIView': '微信集成',
    'WeixinBotAccountToggleAPIView': '微信集成',
    'WeixinPluginInboundAPIView': '微信集成',
    'FileAssetViewSet': '文件管理',
}

# 方法与动作对应映射
ACTION_MAPPINGS = {
    # 标准 RESTful 动作
    'create': '新建',
    'update': '更新',
    'partial_update': '部分更新',
    'destroy': '删除',
    'list': '列表查询',
    'retrieve': '详情查询',
    
    # 常用及自定义业务动作
    'login': '登录',
    'logout': '退出登录',
    'run': '运行',
    'execute': '执行',
    'sync': '同步',
    'export': '导出',
    'import': '导入',
    'available_tools': '获取可用工具',
    'available-tools': '获取可用工具',
    'test_connection': '测试连接',
    'test-connection': '测试连接',
    'add_testcases': '添加用例',
    'add-testcases': '添加用例',
    'case_results': '用例结果',
    'case-results': '用例结果',
    'cancel': '取消',
    'users': '关联用户',
    'permissions': '关联权限',
    'list_actuators': '获取执行器列表',
    'status': '状态统计',
    'tree': '树形查询',
    'members': '成员管理',
    'quick_debug': '快捷调试',
    'quick-debug': '快捷调试',
    'statistics': '统计',
    'runtime_current': '当前运行时配置',
    'default': '默认',
    'content': '内容',
    'upload': '上传',
    'store_manifest': '存储清单',
    'store_config': '存储配置',
    'system_config': '系统配置',
    'initialize_default_subagents': '初始化默认子代理',
    'activate': '激活',
    'view': '查看',
    'fetch_models': '获取模型列表',
    'cleanup_unreferenced': '清理未引用文件',
    'file_settings': '文件管理设置',
    'download': '下载文件',
    'preview': '预览文件',
    'references': '查看文件引用详情',

    # APIView / URL name 补充映射
    'register': '用户注册',
    'user_register': '用户注册',
    'user_me': '当前用户信息',
    'system_config_public': '公共系统配置',
    'agent_loop_stream': '发起智能编排会话',
    'agent_loop_stop': '停止智能编排会话',
    'agent_loop_resume': '恢复智能编排会话',
    'chat': '发起对话',
    'chat_api': '发起对话',
    'chat_history': '查询对话历史',
    'chat_resume': '恢复对话',
    'chat_batch_delete': '批量删除对话',
    'user_chat_sessions': '查询用户会话',
    'provider_choices': '查询模型供应商',
    'knowledge_rag': '知识库检索',
    'token_usage_stats': '查询Token使用统计',
    'remote_mcp_config_ping': '检测MCP连通性',
    'mcp_call_tool': '调用MCP工具',
    'weixin_login_start': '发起微信登录',
    'weixin_login_status': '查询微信登录状态',
    'weixin_account_list': '查询微信账号列表',
    'weixin_account_toggle': '切换微信账号状态',
    'weixin_plugin_inbound': '接收微信插件消息',
}


def normalize_action_key(value):
    """
    将动作标识统一为可比对的蛇形命名。
    """
    normalized = re.sub(r'[^a-zA-Z0-9]+', '_', (value or '').strip())
    return normalized.strip('_').lower()


def normalize_field_key(value):
    """
    统一字段名格式，兼容 camelCase / kebab-case / snake_case。
    """
    camel_spaced = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', str(value or ''))
    normalized = re.sub(r'[^a-zA-Z0-9]+', '_', camel_spaced)
    return normalized.strip('_').lower()


def is_sensitive_key(key):
    """
    精确判断字段名是否属于敏感信息，避免误伤 keyword 等普通业务字段。
    """
    normalized = normalize_field_key(key)
    if not normalized:
        return False

    if normalized in SENSITIVE_EXACT_KEYS:
        return True

    return any(fragment in normalized for fragment in SENSITIVE_PARTIAL_KEYS)


def dumps_json(data):
    """
    统一 JSON 序列化，尽量容忍 datetime / Decimal 等对象。
    """
    return json.dumps(data, ensure_ascii=False, default=str)


def querydict_to_data(query_dict):
    """
    保留多值参数，避免 QueryDict.dict() 丢失重复字段。
    """
    data = {}
    for key in query_dict.keys():
        values = query_dict.getlist(key)
        data[key] = values if len(values) > 1 else values[0]
    return data


def extract_actor_identifier(data):
    """
    从请求载荷中提取可识别的操作者标识，用于未认证场景（如登录失败）。
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in USERNAME_CANDIDATE_KEYS and value not in (None, ''):
                return str(value)
            actor = extract_actor_identifier(value)
            if actor:
                return actor
    elif isinstance(data, list):
        for item in data:
            actor = extract_actor_identifier(item)
            if actor:
                return actor
    return ''


def get_module_name(view_name, view_class=None, view_func=None):
    """
    获取操作模块名称，优先使用显式映射，缺失时退回到 app 级别映射。
    """
    if view_name and view_name in MODULE_MAPPINGS:
        return MODULE_MAPPINGS[view_name]

    module_path = ''
    if view_class is not None:
        module_path = getattr(view_class, '__module__', '')
    elif view_func is not None:
        module_path = getattr(view_func, '__module__', '')

    app_label = module_path.split('.', 1)[0] if module_path else ''
    if app_label in APP_LABEL_MAPPINGS:
        return APP_LABEL_MAPPINGS[app_label]

    return view_name or '系统视图'


def get_action_name(action):
    """
    获取友好的动作名称，兼容 DRF action、url_name 与普通函数名。
    """
    normalized = normalize_action_key(action)
    if not normalized:
        return ''

    candidates = []

    def add_candidate(value):
        if value and value not in candidates:
            candidates.append(value)

    add_candidate(normalized)
    for suffix in ('_api', '_view'):
        if normalized.endswith(suffix):
            add_candidate(normalized[:-len(suffix)])

    parts = [part for part in normalized.split('_') if part]
    if parts:
        add_candidate(parts[-1])
    if len(parts) >= 2:
        add_candidate('_'.join(parts[-2:]))
    if len(parts) >= 3:
        add_candidate('_'.join(parts[-3:]))

    for candidate in candidates:
        if candidate in ACTION_MAPPINGS:
            return ACTION_MAPPINGS[candidate]

    return action.replace('_', ' ').replace('-', ' ')

def mask_data(data):
    """
    递归对请求参数中敏感字段进行掩码处理
    """
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            if is_sensitive_key(k):
                masked[k] = '******'
            else:
                masked[k] = mask_data(v)
        return masked
    elif isinstance(data, list):
        return [mask_data(item) for item in data]
    else:
        return data

def get_client_ip(request):
    """
    安全获取客户端真实 IP
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def normalize_request_path(path):
    """
    统一路径尾部，便于关键字匹配。
    """
    return f"{path.rstrip('/')}/"


def should_log_request(request):
    """
    判断当前请求是否需要进入操作日志审计。
    """
    if not request.path.startswith('/api/'):
        return False

    if request.method in IGNORED_METHODS:
        return False

    normalized_path = normalize_request_path(request.path)
    if any(keyword in normalized_path for keyword in ALWAYS_IGNORED_PATH_KEYWORDS):
        return False

    if request.method == 'GET' and any(
        keyword in normalized_path for keyword in READ_ONLY_IGNORED_PATH_KEYWORDS
    ):
        return False

    return True


def build_request_payload(request, resolver_match=None):
    """
    组装请求参数，补齐 query/path/body 三类上下文。
    """
    payload = {}

    query_params = querydict_to_data(request.GET)
    if query_params:
        payload['query_params'] = query_params

    path_params = getattr(resolver_match, 'kwargs', None) or {}
    if path_params:
        payload['path_params'] = path_params

    try:
        body_data = None
        if request.content_type == 'application/json' and request.body:
            body_data = json.loads(request.body.decode('utf-8'))
        elif request.content_type and request.content_type.startswith('multipart/form-data'):
            body_data = '[文件上传或二进制表单数据]'
        elif request.method not in ('GET', 'HEAD', 'OPTIONS'):
            form_data = querydict_to_data(request.POST)
            if form_data:
                body_data = form_data
            elif request.body:
                raw_text = request.body.decode('utf-8', errors='replace').strip()
                if raw_text:
                    body_data = {
                        'raw_body': raw_text,
                        'content_type': request.content_type or '',
                    }

        if body_data not in (None, '', {}, []):
            payload['body'] = body_data
    except Exception as err:
        payload['body'] = f'[解析请求参数出错]: {str(err)}'

    return payload


def build_response_payload(response):
    """
    组装响应摘要，JSON 响应尽量保留内容，非 JSON 记录元信息。
    """
    content_type = response.get('Content-Type', '')

    if content_type.startswith('application/json'):
        if hasattr(response, 'data'):
            return response.data
        if hasattr(response, 'content'):
            return json.loads(response.content.decode('utf-8'))

    return {
        'content_type': content_type,
        'streaming': bool(getattr(response, 'streaming', False)),
    }

class OperationLogMiddleware(MiddlewareMixin):
    """
    全局用户操作日志记录中间件
    """
    def process_request(self, request):
        # 记录请求进入时间
        request.start_time = time.time()

    def process_response(self, request, response):
        if not should_log_request(request):
            return response

        try:
            self._save_log(request, response)
        except Exception as e:
            # 捕获一切异常，防止操作日志报错导致主业务流阻断
            logger.error(f"[OperationLogMiddleware] 记录日志失败: {str(e)}", exc_info=True)

        return response

    def _save_log(self, request, response):
        # 计算耗时
        start_time = getattr(request, 'start_time', None)
        duration = int((time.time() - start_time) * 1000) if start_time else 0

        # 解析路由，提取视图类名与 Action
        module_name = '系统模块'
        action_name = ''

        resolver_match = getattr(request, 'resolver_match', None)
        if not resolver_match:
            try:
                resolver_match = resolve(request.path)
            except Exception:
                pass

        if resolver_match:
            view_func = resolver_match.func
            view_class = getattr(view_func, 'cls', None)
            
            if view_class:
                view_name = view_class.__name__
                module_name = get_module_name(view_name, view_class=view_class, view_func=view_func)
                
                # 获取 DRF viewset 的 action
                drf_action = getattr(view_func, 'actions', {}).get(request.method.lower(), '')
                if not drf_action:
                    # 尝试从视图的对应方法或 url_name 提取
                    drf_action = getattr(resolver_match, 'url_name', '')
                
                action_name = get_action_name(drf_action)
            else:
                func_name = getattr(view_func, '__name__', '')
                route_name = getattr(resolver_match, 'url_name', '')
                module_name = get_module_name(func_name, view_func=view_func)
                action_name = get_action_name(route_name or func_name)

        # 构建最终操作描述
        if not action_name:
            method_action_map = {
                'POST': '新建',
                'PUT': '全量更新',
                'PATCH': '局部更新',
                'DELETE': '删除'
            }
            action_name = method_action_map.get(request.method, request.method)

        full_action = f"{action_name} {module_name}" if module_name else action_name
        
        # 针对登录接口做特殊友好描述
        if '/token/' in request.path and request.method == 'POST':
            module_name = '用户认证'
            full_action = '用户登录'

        # 获取当前用户；未认证场景下尽量从请求参数中回填操作者标识。
        user_obj = getattr(request, 'user', None)
        user = user_obj if user_obj and user_obj.is_authenticated else None
        request_payload = build_request_payload(request, resolver_match=resolver_match)
        fallback_username = extract_actor_identifier(request_payload)
        username = user.username if user else (fallback_username or '匿名用户')

        # 解析请求数据
        req_data_str = dumps_json(mask_data(request_payload)) if request_payload else '{}'

        # 截断请求数据防数据库膨胀
        if len(req_data_str) > 2000:
            req_data_str = req_data_str[:2000] + "... (已截断)"

        # 解析响应数据
        resp_data_str = ""
        try:
            resp_payload = build_response_payload(response)
            resp_data_str = dumps_json(mask_data(resp_payload))
        except Exception:
            resp_data_str = "[响应解析失败]"

        # 截断响应数据防数据库膨胀
        if len(resp_data_str) > 2000:
            resp_data_str = resp_data_str[:2000] + "... (已截断)"

        # 保存到数据库
        OperationLog.objects.create(
            user=user,
            username=username,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            path=request.path[:255],
            method=request.method,
            module=module_name[:100],
            action=full_action[:255],
            request_data=req_data_str,
            response_code=response.status_code,
            response_data=resp_data_str,
            duration=duration
        )
