// src/services/organizationService.ts
import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import { API_BASE_URL } from '@/config/api';

// 组织数据接口
export interface Organization {
  id: number;
  name: string;
}

// 用户数据接口（简化版，仅用于组织成员列表）
export interface OrganizationUser {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
}

// 创建组织请求接口
export interface CreateOrganizationRequest {
  name: string;
}

// 更新组织请求接口
export interface UpdateOrganizationRequest {
  name?: string;
}

// 创建组织响应接口
export interface CreateOrganizationResponse {
  success: boolean;
  data?: Organization;
  error?: string;
  statusCode?: number;
}

// 通用操作响应接口
export interface OperationResponse {
  success: boolean;
  message?: string;
  error?: string;
  statusCode?: number;
}

// 组织列表响应接口
export interface OrganizationListResponse {
  success: boolean;
  data?: Organization[];
  error?: string;
  statusCode?: number;
  total?: number;
}

// 组织成员列表响应接口
export interface OrganizationUsersResponse {
  success: boolean;
  data?: OrganizationUser[];
  error?: string;
  statusCode?: number;
  total?: number;
}

// 添加/移除用户请求接口
export interface UserIdsRequest {
  user_ids: number[];
}

// 分页参数接口
export interface PaginationParams {
  page: number;
  pageSize: number;
  search?: string;
}

/**
 * 获取组织列表
 * @param params 分页和搜索参数
 * @returns 返回一个Promise，解析为包含组织列表的响应对象
 */
export const getOrganizationList = async (params: PaginationParams): Promise<OrganizationListResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/accounts/groups/`, {
      params: {
        page: params.page,
        page_size: params.pageSize,
        search: params.search || '',
      },
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设API返回的数据格式为 { status: 'success', code: 200, message: '数据获取成功', data: [...组织数组] }
    if (response.data && response.data.status === 'success' && Array.isArray(response.data.data)) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
        total: response.data.data.length, // 使用数组长度作为总数
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取组织列表失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '获取组织列表失败，请稍后再试';
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
          errorMessage = `获取组织列表失败：服务器错误 (${statusCode})`;
        }

        // 如果是401错误，可能是token过期
        if (statusCode === 401) {
          errorMessage = '登录已过期，请重新登录';
          // 这里可以触发token刷新逻辑或者登出操作
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
 * 创建新组织
 * @param organizationData 组织数据
 * @returns 返回一个Promise，解析为包含创建结果的响应对象
 */
export const createOrganization = async (organizationData: CreateOrganizationRequest): Promise<CreateOrganizationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(`${API_BASE_URL}/accounts/groups/`, organizationData, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设创建组织API返回的格式为 { status: 'success', code: 201, message: '组织创建成功', data: {...组织对象} }
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '创建组织失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '创建组织失败，请稍后再试';
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
          errorMessage = `创建组织失败：服务器错误 (${statusCode})`;
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
 * 删除组织
 * @param organizationId 组织ID
 * @returns 返回一个Promise，解析为包含删除结果的响应对象
 */
export const deleteOrganization = async (organizationId: number): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.delete(`${API_BASE_URL}/accounts/groups/${organizationId}/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设删除组织API返回的格式为 { status: 'success', code: 204, message: '组织删除成功' }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '组织删除成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '删除组织失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '删除组织失败，请稍后再试';
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
          errorMessage = `删除组织失败：服务器错误 (${statusCode})`;
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
 * 更新组织信息
 * @param organizationId 组织ID
 * @param organizationData 要更新的组织数据
 * @returns 返回一个Promise，解析为包含更新结果的响应对象
 */
export const updateOrganization = async (organizationId: number, organizationData: UpdateOrganizationRequest): Promise<{ success: boolean; data?: Organization; error?: string }> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.patch(`${API_BASE_URL}/accounts/groups/${organizationId}/`, organizationData, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设更新组织API返回的格式为 { status: 'success', code: 200, message: '组织更新成功', data: {...组织对象} }
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '更新组织失败：响应数据格式不正确',
      };
    }
  } catch (error) {
    let errorMessage = '更新组织失败，请稍后再试';

    if (axios.isAxiosError(error) && error.response) {
      const statusCode = error.response.status;
      const responseData = error.response.data;

      if (responseData && typeof responseData.message === 'string') {
        errorMessage = responseData.message;
      } else if (responseData && typeof responseData.detail === 'string') {
        errorMessage = responseData.detail;
      } else if (statusCode === 404) {
        errorMessage = '组织不存在';
      } else {
        errorMessage = `更新组织失败：服务器错误 (${statusCode})`;
      }

      // 如果是401错误，可能是token过期
      if (statusCode === 401) {
        errorMessage = '登录已过期，请重新登录';
        authStore.logout();
      }
    }

    return {
      success: false,
      error: errorMessage,
    };
  }
};

/**
 * 获取组织成员列表
 * @param organizationId 组织ID
 * @param params 分页和搜索参数
 * @returns 返回一个Promise，解析为包含组织成员列表的响应对象
 */
export const getOrganizationUsers = async (organizationId: number, params?: PaginationParams): Promise<OrganizationUsersResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/accounts/groups/${organizationId}/users/`, {
      params: params ? {
        page: params.page,
        page_size: params.pageSize,
        search: params.search || '',
      } : undefined,
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设API返回的数据格式为 { status: 'success', code: 200, message: '数据获取成功', data: [...用户数组] }
    if (response.data && response.data.status === 'success' && Array.isArray(response.data.data)) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
        total: response.data.data.length, // 使用数组长度作为总数
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取组织成员列表失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '获取组织成员列表失败，请稍后再试';
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
          errorMessage = `获取组织成员列表失败：服务器错误 (${statusCode})`;
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
 * 向组织中添加用户
 * @param organizationId 组织ID
 * @param userIds 要添加的用户ID数组
 * @returns 返回一个Promise，解析为包含操作结果的响应对象
 */
export const addUsersToOrganization = async (organizationId: number, userIds: number[]): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(`${API_BASE_URL}/accounts/groups/${organizationId}/add_users/`,
      { user_ids: userIds } as UserIdsRequest,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    // 假设API返回的格式为 { status: 'success', code: 200, message: '用户添加成功' }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '用户添加成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '添加用户失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '添加用户失败，请稍后再试';
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
          errorMessage = `添加用户失败：服务器错误 (${statusCode})`;
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
 * 从组织中移除用户
 * @param organizationId 组织ID
 * @param userIds 要移除的用户ID数组
 * @returns 返回一个Promise，解析为包含操作结果的响应对象
 */
export const removeUsersFromOrganization = async (organizationId: number, userIds: number[]): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.post(`${API_BASE_URL}/accounts/groups/${organizationId}/remove_users/`,
      { user_ids: userIds } as UserIdsRequest,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    // 假设API返回的格式为 { status: 'success', code: 200, message: '用户移除成功' }
    if (response.data && response.data.status === 'success') {
      return {
        success: true,
        message: response.data.message || '用户移除成功',
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '移除用户失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '移除用户失败，请稍后再试';
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
          errorMessage = `移除用户失败：服务器错误 (${statusCode})`;
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

export const getOrganizationDetail = async (organizationId: number): Promise<{ success: boolean; data?: Organization; error?: string }> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/accounts/groups/${organizationId}/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设组织详情API返回的格式与列表接口类似
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取组织详情失败：响应数据格式不正确',
      };
    }
  } catch (error) {
    let errorMessage = '获取组织详情失败，请稍后再试';

    if (axios.isAxiosError(error) && error.response) {
      const statusCode = error.response.status;
      const responseData = error.response.data;

      if (responseData && typeof responseData.message === 'string') {
        errorMessage = responseData.message;
      } else if (statusCode === 404) {
        errorMessage = '组织不存在';
      } else {
        errorMessage = `获取组织详情失败：服务器错误 (${statusCode})`;
      }
    }

    return {
      success: false,
      error: errorMessage,
    };
  }
};
