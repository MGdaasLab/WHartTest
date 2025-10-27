// src/services/permissionService.ts
import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import { API_BASE_URL } from '@/config/api';

// 权限数据接口
export interface Permission {
  id: number;
  name: string;
  name_cn: string; // 中文权限名称字段
  codename: string;
  content_type: {
    id: number;
    app_label: string;
    app_label_cn: string; // 应用中文名称
    app_label_sort: number; // 应用排序字段（1-6）
    app_label_subcategory: string; // 第二层分类名称
    app_label_subcategory_sort: number; // 第二层分类排序权重
    model: string;
    model_cn: string; // 模型中文名称
    model_verbose: string; // 模型详细名称
  };
}

// 通用操作响应接口
export interface OperationResponse {
  success: boolean;
  message?: string;
  error?: string;
  statusCode?: number;
}

// 权限列表响应接口
export interface PermissionListResponse {
  success: boolean;
  data?: Permission[];
  error?: string;
  statusCode?: number;
  total?: number;
}

// 分页参数接口
export interface PaginationParams {
  page: number;
  pageSize: number;
  search?: string;
  content_type?: number | null; // 添加内容类型ID筛选
  content_type__app_label?: string; // 添加应用标签筛选
}

/**
 * 获取所有权限列表
 * @param params 分页和搜索参数
 * @returns 返回一个Promise，解析为包含权限列表的响应对象
 */
export const getPermissionList = async (params?: PaginationParams): Promise<PermissionListResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    // 构建参数对象
    const requestParams: any = {
      page: params?.page,
      page_size: params?.pageSize,
      search: params?.search || '',
    };

    // 只有当内容类型有值时才传递该参数
    if (params?.content_type !== null && params?.content_type !== undefined) {
      requestParams.content_type = params.content_type;
    }

    // 如果有应用标签，则传递
    if (params?.content_type__app_label) {
      requestParams.content_type__app_label = params.content_type__app_label;
    }

    const response = await axios.get(`${API_BASE_URL}/accounts/permissions/`, {
      params: requestParams,
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设API返回的数据格式为 { status: 'success', code: 200, message: '数据获取成功', data: [...权限数组] }
    if (response.data && response.data.status === 'success' && Array.isArray(response.data.data)) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
        total: response.data.total || response.data.data.length,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取权限列表失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '获取权限列表失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else {
          errorMessage = `获取权限列表失败：服务器错误 (${statusCode})`;
        }

        // 如果是401错误，可能是token过期
        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

/**
 * 获取特定权限详情
 * @param permissionId 权限ID
 * @returns 返回一个Promise，解析为包含权限详情的响应对象
 */
export const getPermissionDetail = async (permissionId: number): Promise<{ success: boolean; data?: Permission; error?: string }> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/accounts/permissions/${permissionId}/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设权限详情API返回的格式与列表接口类似
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取权限详情失败：响应数据格式不正确',
      };
    }
  } catch (error) {
    let errorMessage = '获取权限详情失败，请稍后再试';

    if (axios.isAxiosError(error) && error.response) {
      const statusCode = error.response.status;
      const responseData = error.response.data;

      if (responseData && typeof responseData.message === 'string') {
        errorMessage = responseData.message;
      } else if (statusCode === 404) {
        errorMessage = '权限不存在';
      } else {
        errorMessage = `获取权限详情失败：服务器错误 (${statusCode})`;
      }
    }

    return {
      success: false,
      error: errorMessage,
    };
  }
};

/**
 * 获取特定用户的权限
 * @param userId 用户ID
 * @returns 返回一个Promise，解析为包含用户权限列表的响应对象
 */
export const getUserPermissions = async (userId: number): Promise<PermissionListResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/accounts/users/${userId}/permissions/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设API返回的数据格式为 { status: 'success', code: 200, message: '数据获取成功', data: [...权限数组] }
    if (response.data && response.data.status === 'success' && Array.isArray(response.data.data)) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
        total: response.data.data.length,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取用户权限失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '获取用户权限失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '用户不存在';
        } else {
          errorMessage = `获取用户权限失败：服务器错误 (${statusCode})`;
        }

        // 如果是401错误，可能是token过期
        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

/**
 * 获取特定组织的权限
 * @param groupId 组织ID
 * @returns 返回一个Promise，解析为包含组织权限列表的响应对象
 */
export const getGroupPermissions = async (groupId: number): Promise<PermissionListResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/accounts/groups/${groupId}/permissions/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设API返回的数据格式为 { status: 'success', code: 200, message: '数据获取成功', data: [...权限数组] }
    if (response.data && response.data.status === 'success' && Array.isArray(response.data.data)) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
        total: response.data.data.length,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取组织权限失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '获取组织权限失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '组织不存在';
        } else {
          errorMessage = `获取组织权限失败：服务器错误 (${statusCode})`;
        }

        // 如果是401错误，可能是token过期
        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

/**
 * 将特定权限分配给指定用户
 * @param permissionId 权限ID
 * @param userId 用户ID
 * @returns 返回一个Promise，解析为包含操作结果的响应对象
 */

export const removePermissionFromUser = async (permissionId: number, userId: number): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/accounts/permissions/${permissionId}/remove_from_user/`,
      { user_id: userId },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    // 假设API返回的格式为 { status: 'success', code: 200, message: '权限移除成功' }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '权限移除成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '移除权限失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '移除权限失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '权限或用户不存在';
        } else {
          errorMessage = `移除权限失败：服务器错误 (${statusCode})`;
        }

        // 如果是401错误，可能是token过期
        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

/**
 * 将特定权限分配给指定组织
 * @param permissionId 权限ID
 * @param groupId 组织ID
 * @returns 返回一个Promise，解析为包含操作结果的响应对象
 */
export const assignPermissionToGroup = async (permissionId: number, groupId: number): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/accounts/permissions/${permissionId}/assign_to_group/`,
      { group_id: groupId },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    // 假设API返回的格式为 { status: 'success', code: 200, message: '权限分配成功' }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '权限分配成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '分配权限失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '分配权限失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '权限或组织不存在';
        } else {
          errorMessage = `分配权限失败：服务器错误 (${statusCode})`;
        }

        // 如果是401错误，可能是token过期
        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

/**
 * 从指定组织移除特定权限
 * @param permissionId 权限ID
 * @param groupId 组织ID
 * @returns 返回一个Promise，解析为包含操作结果的响应对象
 */
export const removePermissionFromGroup = async (permissionId: number, groupId: number): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/accounts/permissions/${permissionId}/remove_from_group/`,
      { group_id: groupId },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    // 假设API返回的格式为 { status: 'success', code: 200, message: '权限移除成功' }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '权限移除成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '移除权限失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '移除权限失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '权限或组织不存在';
        } else {
          errorMessage = `移除权限失败：服务器错误 (${statusCode})`;
        }

        // 如果是401错误，可能是token过期
        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

export const assignPermissionToUser = async (permissionId: number, userId: number): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/accounts/permissions/${permissionId}/assign_to_user/`,
      { user_id: userId },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    // 假设API返回的格式为 { status: 'success', code: 200, message: '权限分配成功' }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '权限分配成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '分配权限失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '分配权限失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '权限或用户不存在';
        } else {
          errorMessage = `分配权限失败：服务器错误 (${statusCode})`;
        }

        // 如果是401错误，可能是token过期
        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

/**
 * 批量分配权限给用户
 * @param userId 用户ID
 * @param permissionIds 权限ID数组
 * @returns 返回一个Promise，解析为包含操作结果的响应对象
 */
export const batchAssignPermissionsToUser = async (userId: number, permissionIds: number[]): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  if (!permissionIds || permissionIds.length === 0) {
    return {
      success: false,
      error: '请选择要分配的权限',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/accounts/users/${userId}/batch-assign-permissions/`,
      { permission_ids: permissionIds },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '批量分配权限成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '批量分配权限失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '批量分配权限失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '用户不存在';
        } else {
          errorMessage = `批量分配权限失败：服务器错误 (${statusCode})`;
        }

        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

/**
 * 批量移除用户权限
 * @param userId 用户ID
 * @param permissionIds 权限ID数组
 * @returns 返回一个Promise，解析为包含操作结果的响应对象
 */
export const batchRemovePermissionsFromUser = async (userId: number, permissionIds: number[]): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  if (!permissionIds || permissionIds.length === 0) {
    return {
      success: false,
      error: '请选择要移除的权限',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/accounts/users/${userId}/batch-remove-permissions/`,
      { permission_ids: permissionIds },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '批量移除权限成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '批量移除权限失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '批量移除权限失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '用户不存在';
        } else {
          errorMessage = `批量移除权限失败：服务器错误 (${statusCode})`;
        }

        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

/**
 * 批量分配权限给用户组
 * @param groupId 用户组ID
 * @param permissionIds 权限ID数组
 * @returns 返回一个Promise，解析为包含操作结果的响应对象
 */
export const batchAssignPermissionsToGroup = async (groupId: number, permissionIds: number[]): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  if (!permissionIds || permissionIds.length === 0) {
    return {
      success: false,
      error: '请选择要分配的权限',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/accounts/groups/${groupId}/batch-assign-permissions/`,
      { permission_ids: permissionIds },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '批量分配权限成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '批量分配权限失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '批量分配权限失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '用户组不存在';
        } else {
          errorMessage = `批量分配权限失败：服务器错误 (${statusCode})`;
        }

        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

/**
 * 批量移除用户组权限
 * @param groupId 用户组ID
 * @param permissionIds 权限ID数组
 * @returns 返回一个Promise，解析为包含操作结果的响应对象
 */
export const batchRemovePermissionsFromGroup = async (groupId: number, permissionIds: number[]): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  if (!permissionIds || permissionIds.length === 0) {
    return {
      success: false,
      error: '请选择要移除的权限',
    };
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/accounts/groups/${groupId}/batch-remove-permissions/`,
      { permission_ids: permissionIds },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '批量移除权限成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '批量移除权限失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '批量移除权限失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '用户组不存在';
        } else {
          errorMessage = `批量移除权限失败：服务器错误 (${statusCode})`;
        }

        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

/**
 * 完全替换用户的直接权限列表
 * @param userId 用户ID
 * @param permissionIds 权限ID数组
 * @returns 返回一个Promise，解析为包含操作结果的响应对象
 */
export const updateUserPermissions = async (userId: number, permissionIds: number[]): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.put(
      `${API_BASE_URL}/accounts/users/${userId}/update-permissions/`,
      { permission_ids: permissionIds },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '权限更新成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '权限更新失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '权限更新失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '用户不存在';
        } else {
          errorMessage = `权限更新失败：服务器错误 (${statusCode})`;
        }

        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};

/**
 * 完全替换组织的直接权限列表
 * @param groupId 组织ID
 * @param permissionIds 权限ID数组
 * @returns 返回一个Promise，解析为包含操作结果的响应对象
 */
export const updateGroupPermissions = async (groupId: number, permissionIds: number[]): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.put(
      `${API_BASE_URL}/accounts/groups/${groupId}/update-permissions/`,
      { permission_ids: permissionIds },
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '权限更新成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '权限更新失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '权限更新失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '组织不存在';
        } else {
          errorMessage = `权限更新失败：服务器错误 (${statusCode})`;
        }

        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          authStore.logout();
        }
      } else if (error.request) {
        errorMessage = '网络连接超时或服务器无响应';
      }
    }

    return {
      success: false,
      error: errorMessage,
      statusCode,
    };
  }
};