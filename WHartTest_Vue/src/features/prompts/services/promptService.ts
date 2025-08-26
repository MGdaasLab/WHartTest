import { request } from '@/utils/request';
import type { ApiResponse } from '@/features/langgraph/types/api';
import type {
  UserPrompt,
  CreateUserPromptRequest,
  UpdateUserPromptRequest,
  PartialUpdateUserPromptRequest,
  UserPromptListParams,
  UserPromptListResponseData,
  BatchOperationResponseData,
  // 新增需求评审相关类型
  PromptType,
  RequirementPromptsResponse,
  GetRequirementPromptParams,
  RequirementPromptApiResponse
} from '../types/prompt';

const API_BASE_URL = '/prompts/user-prompts';

// 从API配置中获取端点
import { API_ENDPOINTS } from '@/config/api';

/**
 * 获取用户提示词列表
 */
export async function getUserPrompts(
  params?: UserPromptListParams
): Promise<ApiResponse<UserPromptListResponseData>> {
  const response = await request<UserPromptListResponseData>({
    url: `${API_BASE_URL}/`,
    method: 'GET',
    params
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
      message: response.error || 'Failed to get user prompts',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 获取默认提示词
 */
export async function getDefaultPrompt(): Promise<ApiResponse<UserPrompt | null>> {
  const response = await request<UserPrompt | null>({
    url: `${API_BASE_URL}/default/`,
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
      message: response.error || 'Failed to get default prompt',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 获取单个提示词详情
 */
export async function getUserPrompt(id: number): Promise<ApiResponse<UserPrompt>> {
  const response = await request<UserPrompt>({
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
      message: response.error || 'Failed to get user prompt',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 创建新提示词
 */
export async function createUserPrompt(
  data: CreateUserPromptRequest
): Promise<ApiResponse<UserPrompt>> {
  const response = await request<UserPrompt>({
    url: `${API_BASE_URL}/`,
    method: 'POST',
    data
  });

  if (response.success) {
    return {
      status: 'success',
      code: 201,
      message: response.message || 'User prompt created successfully',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to create user prompt',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 完整更新提示词
 */
export async function updateUserPrompt(
  id: number,
  data: UpdateUserPromptRequest
): Promise<ApiResponse<UserPrompt>> {
  const response = await request<UserPrompt>({
    url: `${API_BASE_URL}/${id}/`,
    method: 'PUT',
    data
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'User prompt updated successfully',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to update user prompt',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 部分更新提示词
 */
export async function partialUpdateUserPrompt(
  id: number,
  data: PartialUpdateUserPromptRequest
): Promise<ApiResponse<UserPrompt>> {
  const response = await request<UserPrompt>({
    url: `${API_BASE_URL}/${id}/`,
    method: 'PATCH',
    data
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'User prompt updated successfully',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to update user prompt',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 删除提示词
 */
export async function deleteUserPrompt(id: number): Promise<ApiResponse<null>> {
  const response = await request<null>({
    url: `${API_BASE_URL}/${id}/`,
    method: 'DELETE'
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'User prompt deleted successfully',
      data: null,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to delete user prompt',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 设置默认提示词
 */
export async function setDefaultPrompt(id: number): Promise<ApiResponse<UserPrompt>> {
  try {
    const response = await request<UserPrompt>({
      url: `${API_BASE_URL}/${id}/set_default/`,
      method: 'POST'
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'Default prompt set successfully',
        data: response.data!,
        errors: null
      };
    } else {
      // The `request` utility returns a response object even on failure.
      // We'll extract the specific error message if it exists.
      const specificError =
        (response as any).response?.data?.errors?.message ||
        (response as any).response?.data?.errors?.errors?.prompt_type?.[0] ||
        (response as any).error || 
        'Failed to set default prompt';
      
      throw new Error(specificError);
    }
  } catch (error: any) {
    // Re-throw the error to be handled by the calling component
    throw new Error(error.message || 'An unknown error occurred');
  }
}

/**
 * 清除默认提示词设置
 */
export async function clearDefaultPrompt(): Promise<ApiResponse<BatchOperationResponseData>> {
  const response = await request<BatchOperationResponseData>({
    url: `${API_BASE_URL}/clear_default/`,
    method: 'POST'
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || 'Default prompt cleared successfully',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to clear default prompt',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 复制提示词
 */
export async function duplicateUserPrompt(id: number): Promise<ApiResponse<UserPrompt>> {
  const response = await request<UserPrompt>({
    url: `${API_BASE_URL}/${id}/duplicate/`,
    method: 'POST'
  });

  if (response.success) {
    return {
      status: 'success',
      code: 201,
      message: response.message || 'User prompt duplicated successfully',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || 'Failed to duplicate user prompt',
      data: null,
      errors: { detail: response.error }
    };
  }
}

// ==================== 需求评审提示词专用方法 ====================

/**
 * 获取需求评审提示词列表
 * 返回所有需求评审类型的提示词状态
 */
export async function getRequirementPrompts(): Promise<ApiResponse<RequirementPromptsResponse>> {
  const response = await request<RequirementPromptsResponse>({
    url: API_ENDPOINTS.PROMPTS.REQUIREMENT_PROMPTS,
    method: 'GET'
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || '获取需求评审提示词成功',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || '获取需求评审提示词失败',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 获取指定类型的需求评审提示词
 * @param params 包含prompt_type字段的参数对象
 */
export async function getRequirementPrompt(
  params: GetRequirementPromptParams
): Promise<ApiResponse<UserPrompt | null>> {
  const response = await request<UserPrompt | null>({
    url: API_ENDPOINTS.PROMPTS.GET_REQUIREMENT_PROMPT,
    method: 'GET',
    params
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || '获取需求评审提示词成功',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: response.status || 404,
      message: response.error || '未找到需求评审提示词',
      data: null,
      errors: { prompt: ['请先创建需求评审提示词'] }
    };
  }
}

/**
 * 创建需求评审提示词
 * 注意：每种需求评审类型只能创建一个提示词
 */
export async function createRequirementPrompt(
  data: CreateUserPromptRequest
): Promise<ApiResponse<UserPrompt>> {
  // 使用通用的创建方法，但确保设置了正确的prompt_type
  return createUserPrompt(data);
}

/**
 * 获取提示词类型列表
 */
export async function getPromptTypes(): Promise<ApiResponse<Array<{value: string, label: string, is_program_call: boolean}>>> {
  const response = await request<Array<{value: string, label: string, is_program_call: boolean}>>({
    url: `${API_ENDPOINTS.PROMPTS.PROMPT_TYPES}`,
    method: 'GET'
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || '获取成功',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || '获取提示词类型列表失败',
      data: null,
      errors: { detail: response.error }
    };
  }
}

/**
 * 根据类型获取提示词
 */
export async function getPromptByType(type: string): Promise<ApiResponse<UserPrompt | null>> {
  const response = await request<UserPrompt | null>({
    url: `${API_ENDPOINTS.PROMPTS.BY_TYPE}`,
    method: 'GET',
    params: { type }
  });

  if (response.success) {
    return {
      status: 'success',
      code: 200,
      message: response.message || '获取成功',
      data: response.data!,
      errors: null
    };
  } else {
    return {
      status: 'error',
      code: 500,
      message: response.error || `用户暂无${type}类型的提示词`,
      data: null,
      errors: { detail: response.error }
    };
  }
}
