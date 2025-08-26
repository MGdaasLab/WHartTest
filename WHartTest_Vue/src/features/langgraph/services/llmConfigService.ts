import { request } from '@/utils/request';
import type { ApiResponse } from '@/features/langgraph/types/api';
import type {
  LlmConfig,
  CreateLlmConfigRequest,
  UpdateLlmConfigRequest,
  PartialUpdateLlmConfigRequest,
} from '@/features/langgraph/types/llmConfig';

export interface ProviderOption {
  value: string;
  label: string;
}

export interface ProvidersResponse {
  choices: ProviderOption[];
}

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
 * 获取所有可用的供应商选项
 */
export async function getProviders(): Promise<ApiResponse<ProvidersResponse>> {
  const response = await request<ProvidersResponse>({
    url: '/lg/providers/',
    method: 'GET',
    params: {
      _t: Date.now(),
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
      message: response.error || 'Failed to get providers',
      data: null,
      errors: { detail: response.error }
    };
  }
}