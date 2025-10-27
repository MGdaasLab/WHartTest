/**
 * API 配置文件
 * 统一管理所有API相关的配置
 */

// 获取API基础URL
// 生产环境默认使用相对路径 /api，通过 Nginx 代理到后端
// 开发环境可以通过 .env 文件配置为 /api 或完整 URL
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

// 开发环境下的代理路径
export const DEV_PROXY_PATH = '/api';

// 判断是否为开发环境
export const isDevelopment = import.meta.env.DEV;

// 获取实际使用的API基础URL
export function getApiBaseUrl(): string {
  // 在开发环境下，如果使用代理，则返回代理路径
  if (isDevelopment && import.meta.env.VITE_USE_PROXY === 'true') {
    return DEV_PROXY_PATH;
  }

  // 如果配置的是相对路径，则使用相对路径（适用于同域部署）
  if (API_BASE_URL.startsWith('/')) {
    return API_BASE_URL;
  }

  // 如果没有配置或配置为空，尝试使用相对路径
  if (!API_BASE_URL || API_BASE_URL === '') {
    return '/api';
  }

  return API_BASE_URL;
}

// 智能API基础URL获取（推荐使用）
export function getSmartApiBaseUrl(): string {
  // 如果明确配置了完整URL，直接使用
  if (API_BASE_URL && (API_BASE_URL.startsWith('http://') || API_BASE_URL.startsWith('https://'))) {
    return API_BASE_URL;
  }

  // 否则使用相对路径，让浏览器自动解析到当前域名
  return '/api';
}

// API端点配置
export const API_ENDPOINTS = {
  // 认证相关
  AUTH: {
    LOGIN: '/token/',
    REGISTER: '/accounts/register/',
    REFRESH: '/token/refresh/',
  },

  // 项目相关
  PROJECTS: '/projects/',

  // 测试用例相关
  TESTCASES: '/testcases/',

  // 测试用例模块相关
  TESTCASE_MODULES: '/testcase-modules/',

  // 用户相关
  USERS: '/users/',

  // 组织相关
  ORGANIZATIONS: '/organizations/',

  // 权限相关
  PERMISSIONS: '/permissions/',

  // 内容类型相关
  CONTENT_TYPES: '/content-types/',

  // API Key相关
  API_KEYS: '/api-keys/',

  // LangGraph相关
  LANGGRAPH: {
    CHAT: '/lg/chat/',
    CHAT_STREAM: '/lg/chat/stream/',
    CHAT_HISTORY: '/lg/chat/history/',
    CHAT_SESSIONS: '/lg/chat/sessions/',
    LLM_CONFIGS: '/lg/llm-configs/',
  },

  // 知识库相关
  KNOWLEDGE: {
    KNOWLEDGE_BASES: '/knowledge/knowledge-bases/',
    SYSTEM_STATUS: '/knowledge/knowledge-bases/system_status/',
    DOCUMENTS: '/knowledge/documents/',
    CHUNKS: '/knowledge/chunks/',
    QUERY_LOGS: '/knowledge/query-logs/',
    RAG: '/lg/knowledge/rag/',
  },

  // MCP工具相关
  MCP_TOOLS: {
    REMOTE_CONFIGS: '/mcp_tools/remote-configs/',
    PING: '/mcp_tools/remote-configs/ping/',
  },

  // 提示词管理相关
  PROMPTS: {
    USER_PROMPTS: '/prompts/user-prompts/',
    DEFAULT_PROMPT: '/prompts/user-prompts/default/',
    SET_DEFAULT: '/prompts/user-prompts/{id}/set_default/',
    CLEAR_DEFAULT: '/prompts/user-prompts/clear_default/',
    DUPLICATE: '/prompts/user-prompts/{id}/duplicate/',
    // 提示词类型相关端点
    PROMPT_TYPES: '/prompts/user-prompts/types/',
    BY_TYPE: '/prompts/user-prompts/by_type/',
    // 需求评审提示词专用端点
    REQUIREMENT_PROMPTS: '/prompts/user-prompts/requirement_prompts/',
    GET_REQUIREMENT_PROMPT: '/prompts/user-prompts/get_requirement_prompt/',
  },

  // 需求管理相关
  REQUIREMENTS: {
    DOCUMENTS: '/requirements/documents/',
    DOCUMENT_DETAIL: '/requirements/documents/{id}/',
    SPLIT_MODULES: '/requirements/documents/{id}/split-modules/',
    CHECK_CONTEXT_LIMIT: '/requirements/documents/{id}/check-context-limit/',
    ANALYZE_STRUCTURE: '/requirements/documents/{id}/analyze-structure/',
    CONFIRM_MODULES: '/requirements/documents/{id}/confirm-modules/',
    MODULE_OPERATIONS: '/requirements/documents/{id}/module-operations/',
    START_REVIEW: '/requirements/documents/{id}/start-review/',
    RESTART_REVIEW: '/requirements/documents/{id}/restart-review/',
    REVIEW_PROGRESS: '/requirements/documents/{id}/review-progress/',
    ISSUES: '/requirements/issues/',
    ISSUE_DETAIL: '/requirements/issues/{id}/',
  },
} as const;

// 构建完整的API URL
export function buildApiUrl(endpoint: string, params?: Record<string, string | number>): string {
  let url = endpoint;

  // 替换URL中的参数占位符
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url = url.replace(`{${key}}`, String(value));
    });
  }

  return url;
}

// 项目相关的API URL构建器
export function buildProjectApiUrl(projectId: string | number, endpoint: string): string {
  return `/projects/${projectId}${endpoint}`;
}

// 导出默认配置
export default {
  API_BASE_URL,
  DEV_PROXY_PATH,
  isDevelopment,
  getApiBaseUrl,
  API_ENDPOINTS,
  buildApiUrl,
  buildProjectApiUrl,
};
