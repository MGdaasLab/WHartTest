import { request } from '@/utils/request';
import type { ApiResponse } from '@/features/langgraph/types/api';
import type {
  LlmConfig,
  CreateLlmConfigRequest,
  UpdateLlmConfigRequest,
  PartialUpdateLlmConfigRequest,
  OrcaRouterCatalog,
  OrcaRouterConnectBegin,
  OrcaRouterConnectResult,
} from '@/features/langgraph/types/llmConfig';


const API_BASE_URL = '/lg/llm-configs'; // 移除多余的/api前缀

/**
 * 列出所有 LLM 配置
 */
export async function listLlmConfigs(): Promise<ApiResponse<LlmConfig[]>> {
  const response = await request<LlmConfig[]>({
    url: `${API_BASE_URL}/`,
    method: 'GET',
    params: {
      _t: Date.now(), // 添加时间戳参数以清除缓存
    }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'success',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to list LLM configs',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 创建一个新的 LLM 配置
 */
export async function createLlmConfig(
  data: CreateLlmConfigRequest
): Promise<ApiResponse<LlmConfig>> {
  const response = await request<LlmConfig>({
    url: `${API_BASE_URL}/`,
    method: 'POST',
    data
  });

  if (response.success) {
    return {
      status: 'success',
      code: 201,
      message: response.message || 'LLM config created successfully',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to create LLM config',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 获取特定 LLM 配置的详细信息
 */
export async function getLlmConfigDetails(id: number): Promise<ApiResponse<LlmConfig>> {
  const response = await request<LlmConfig>({
    url: `${API_BASE_URL}/${id}/`,
    method: 'GET'
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'success',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to get LLM config details',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 更新特定 LLM 配置 (完整更新)
 */
export async function updateLlmConfig(
  id: number,
  data: UpdateLlmConfigRequest
): Promise<ApiResponse<LlmConfig>> {
  const response = await request<LlmConfig>({
    url: `${API_BASE_URL}/${id}/`,
    method: 'PUT',
    data
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'LLM config updated successfully',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to update LLM config',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 部分更新特定 LLM 配置
 */
export async function partialUpdateLlmConfig(
  id: number,
  data: PartialUpdateLlmConfigRequest
): Promise<ApiResponse<LlmConfig>> {
  const response = await request<LlmConfig>({
    url: `${API_BASE_URL}/${id}/`,
    method: 'PATCH',
    data
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'LLM config updated successfully',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to update LLM config',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 删除特定 LLM 配置
 */
export async function deleteLlmConfig(id: number): Promise<ApiResponse<null>> {
  const response = await request<null>({
    url: `${API_BASE_URL}/${id}/`,
    method: 'DELETE'
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'LLM configuration deleted successfully',
      data: null,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to delete LLM config',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 测试 LLM 配置连接（后端发起测试）
 */
export async function testLlmConnection(id: number): Promise<ApiResponse<{ status: string; message: string }>> {
  const response = await request<{ status: string; message: string }>({
    url: `${API_BASE_URL}/${id}/test_connection/`,
    method: 'POST'
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.data?.message || '连接测试成功',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || '连接测试失败',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 获取所有可用的供应商选项
 */
export async function getProviders(): Promise<ApiResponse<{ choices: Array<{ value: string; label: string }> }>> {
  const response = await request<{ choices: Array<{ value: string; label: string }> }>({
    url: `/lg/providers/`,
    method: 'GET',
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'success',
      data: response.data || { choices: [] },
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to get providers',
      data: { choices: [] },
      errors: { detail: response.error }
    };
  }
}

/**
 * 获取当前激活的 LLM 配置
 */
export async function getActiveLlmConfig(): Promise<ApiResponse<LlmConfig | null>> {
  const response = await listLlmConfigs();
  if (response.status === 'success' && response.data) {
    const activeConfig = response.data.find(config => config.is_active);
    return {
      status: 'success',
      code: 200,
      message: 'success',
      data: activeConfig || null,
      errors: null
    };
  }
  return {
    status: 'error',
    code: response.code,
    message: response.message,
    data: null,
    errors: response.errors
  };
}

/**
 * 从 LLM API 获取可用模型列表
 * @param apiUrl API 地址
 * @param apiKey API Key（可选，编辑模式下可从数据库获取）
 * @param configId 配置ID（可选，用于编辑模式从数据库获取 API Key）
 */
export async function fetchModels(
  apiUrl: string,
  apiKey?: string,
  configId?: number
): Promise<ApiResponse<{ models: string[] }>> {
  const response = await request<{ status: string; models?: string[]; message?: string }>({
    url: `${API_BASE_URL}/fetch_models/`,
    method: 'POST',
    data: {
      api_url: apiUrl,
      api_key: apiKey,
      config_id: configId,
    },
  });

  if (response.success && response.data?.status === 'success') {
    return {
      status: 'success',
      code: 200,
      message: 'Models fetched successfully',
      data: { models: response.data.models || [] },
      errors: null,
    };
  } else {
    return {
      status: 'error',
      code: 400,
      message: response.data?.message || response.error || '获取模型列表失败',
      data: null,
      errors: { detail: response.error },
    };
  }
}

/**
 * 拉取 OrcaRouter 能力过滤后的模型目录。
 *
 * 浏览器从不持有 API Key：密钥由后端从既有存储读取并用于请求上游目录。
 *
 * @param capability 目标入口能力（chat / embedding / image / video / rerank）
 * @param inputModalities 该入口实际上传的非文本模态（如 ['image']）
 * @param configId 可选配置ID，用于复用已保存的密钥
 * @param refresh 强制绕过服务端缓存
 */
export async function fetchOrcaRouterModels(params: {
  capability?: string;
  inputModalities?: string[];
  configId?: number | null;
  apiKey?: string;
  apiBase?: string;
  refresh?: boolean;
}): Promise<ApiResponse<OrcaRouterCatalog>> {
  const response = await request<OrcaRouterCatalog>({
    url: '/lg/orcarouter/models/',
    method: 'POST',
    data: {
      capability: params.capability || 'chat',
      input_modalities: params.inputModalities || [],
      config_id: params.configId ?? undefined,
      api_key: params.apiKey || undefined,
      api_base: params.apiBase || undefined,
      refresh: params.refresh || false,
    },
  });

  if (response.success && response.data) {
    return {
      status: 'success',
      code: 200,
      message: 'success',
      data: response.data,
      errors: null,
    };
  }
  return {
    status: 'error',
    code: 400,
    message: response.error || '获取 OrcaRouter 模型目录失败',
    data: null,
    errors: { detail: response.error },
  };
}

/**
 * 开始一次 "Connect with OrcaRouter"（OAuth 2.0 + PKCE）登录。
 * 返回的授权链接需要在浏览器中打开，页面会显示待粘贴的授权码。
 */
export async function beginOrcaRouterConnect(): Promise<ApiResponse<OrcaRouterConnectBegin>> {
  const response = await request<OrcaRouterConnectBegin>({
    url: '/lg/orcarouter/connect/',
    method: 'POST',
    data: { action: 'begin' },
  });

  if (response.success && response.data) {
    return { status: 'success', code: 200, message: 'success', data: response.data, errors: null };
  }
  return {
    status: 'error',
    code: 400,
    message: response.error || '无法开始 OrcaRouter 登录',
    data: null,
    errors: { detail: response.error },
  };
}

/**
 * 用授权码完成 PKCE 登录。密钥由后端直接写入既有存储，不回传浏览器。
 */
export async function completeOrcaRouterConnect(params: {
  attemptId: string;
  code: string;
  state: string;
  configId?: number | null;
}): Promise<ApiResponse<OrcaRouterConnectResult>> {
  const response = await request<OrcaRouterConnectResult>({
    url: '/lg/orcarouter/connect/',
    method: 'POST',
    data: {
      action: 'complete',
      attempt_id: params.attemptId,
      code: params.code,
      state: params.state,
      config_id: params.configId ?? undefined,
    },
  });

  if (response.success && response.data) {
    return { status: 'success', code: 200, message: 'success', data: response.data, errors: null };
  }
  return {
    status: 'error',
    code: 400,
    message: response.error || 'OrcaRouter 登录失败',
    data: null,
    errors: { detail: response.error },
  };
}

/**
 * 取消一次进行中的 OrcaRouter 登录并释放服务端登录锁。
 *
 * 页面隐藏/卸载时通过 keepalive 发出，避免依赖被 generation guard 拦下的
 * finally 分支。
 */
export async function cancelOrcaRouterConnect(attemptId: string): Promise<ApiResponse<null>> {
  const response = await request<null>({
    url: '/lg/orcarouter/connect/',
    method: 'POST',
    data: { action: 'cancel', attempt_id: attemptId },
  });

  if (response.success) {
    return { status: 'success', code: 200, message: 'success', data: null, errors: null };
  }
  return {
    status: 'error',
    code: 400,
    message: response.error || '取消 OrcaRouter 登录失败',
    data: null,
    errors: { detail: response.error },
  };
}
