import { request } from '@/utils/request';
import type { ApiResponse } from '@/features/langgraph/types/api';
import type {
  LlmConfig,
  CreateLlmConfigRequest,
  UpdateLlmConfigRequest,
  PartialUpdateLlmConfigRequest,
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
