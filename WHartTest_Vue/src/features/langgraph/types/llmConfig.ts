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