/**
 * LLM 配置对象
 */
export interface LlmConfig {
  id: number;
  config_name: string; // 配置名称
  provider: string; // 供应商
  name: string; // 模型名称
  api_url: string;
  api_key?: string; // 在列表视图中可能不返回，在详细视图中可能返回
  system_prompt?: string; // 系统提示词
  supports_vision?: boolean; // 是否支持图片/多模态输入
  context_limit?: number; // 上下文Token限制
  // v2.0.0: 中间件配置
  enable_summarization?: boolean; // 启用上下文摘要
  enable_hitl?: boolean; // 启用人工审批（Human-in-the-Loop）
  enable_streaming?: boolean; // 启用流式输出
  is_active: boolean;
  created_at: string; // ISO 8601 date string
  updated_at: string; // ISO 8601 date string
}

/**
 * OrcaRouter 模型目录中的单个模型（最小元数据）
 */
export interface OrcaRouterModel {
  id: string; // vendor/model 命名空间原样保留
  name: string;
  context_length?: number | null;
  input_modalities?: string[];
  endpoint_types?: string[];
  reasoning_efforts?: string[];
}

/**
 * 能力过滤后的 OrcaRouter 模型目录结果
 */
export interface OrcaRouterCatalog {
  models: OrcaRouterModel[];
  total?: number;
  filtered?: number;
  source: 'live' | 'fallback' | string; // live=实时目录，fallback=已验证回退目录
  degraded: boolean; // true 时 UI 必须显示降级提示
  capability?: string;
  error_code?: string;
}

/**
 * OrcaRouter 凭据来源：粘贴 API Key 或 OAuth 2.0 + PKCE 登录
 */
export type OrcaRouterCredentialSource = 'api_key' | 'pkce';

/**
 * 开始一次 PKCE 登录的返回结果
 */
export interface OrcaRouterConnectBegin {
  attempt_id: string;
  authorize_url: string;
  state: string;
  auth_base: string;
  callback_mode: string;
}

/**
 * PKCE 登录完成后的结果（密钥本身永不返回前端）
 */
export interface OrcaRouterConnectResult {
  credential_source: OrcaRouterCredentialSource;
  scope: string;
  account_ref?: string | null;
  config_id?: number | null;
}

/**
 * 创建 LLM 配置的请求体
 */
export interface CreateLlmConfigRequest {
  config_name: string; // 配置名称
  provider: string; // 供应商
  name: string; // 模型名称
  api_url: string;
  api_key: string;
  system_prompt?: string; // 系统提示词（可选）
  supports_vision?: boolean; // 是否支持图片/多模态输入（可选）
  context_limit?: number; // 上下文Token限制（可选，默认128000）
  // v2.0.0: 中间件配置
  enable_summarization?: boolean; // 启用上下文摘要（可选，默认true）
  enable_hitl?: boolean; // 启用人工审批（可选，默认false）
  enable_streaming?: boolean; // 启用流式输出（可选，默认true）
  is_active?: boolean; // 可选,布尔值, 默认为 false
}

/**
 * 更新 LLM 配置的请求体 (PUT - 完整更新)
 */
export interface UpdateLlmConfigRequest extends CreateLlmConfigRequest {}

/**
 * 部分更新 LLM 配置的请求体 (PATCH)
 */
export interface PartialUpdateLlmConfigRequest {
  config_name?: string; // 配置名称
  provider?: string; // 供应商
  name?: string; // 模型名称
  api_url?: string;
  api_key?: string;
  system_prompt?: string; // 系统提示词（可选）
  supports_vision?: boolean; // 是否支持图片/多模态输入（可选）
  context_limit?: number; // 上下文Token限制（可选）
  // v2.0.0: 中间件配置
  enable_summarization?: boolean; // 启用上下文摘要
  enable_hitl?: boolean; // 启用人工审批
  enable_streaming?: boolean; // 启用流式输出
  is_active?: boolean;
}