// src/services/userService.ts
// src/services/userService.ts
import axios from 'axios';
import { request } from '@/utils/request';
import { useAuthStore } from '@/store/authStore';

// 用户数据接口
export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_active: boolean;
}

// 创建用户请求接口
export interface CreateUserRequest {
  username: string;
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  is_staff?: boolean;
  is_active?: boolean;
}

// 更新用户请求接口
export interface UpdateUserRequest {
  username?: string;
  email?: string;
  password?: string;
  first_name?: string;
  last_name?: string;
  is_staff?: boolean;
  is_active?: boolean;
}

// 创建用户响应接口
export interface CreateUserResponse {
  success: boolean;
  data?: User;
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

// 用户列表响应接口
export interface UserListResponse {
  success: boolean;
  data?: User[];
  error?: string;
  statusCode?: number;
  total?: number;
}

// 分页参数接口
export interface PaginationParams {
  page: number;
  pageSize: number;
  search?: string;
}

/**
 * 获取用户列表
 * @param params 分页和搜索参数
 * @returns 返回一个Promise，解析为包含用户列表的响应对象
 */
export const getUserList = async (params: PaginationParams): Promise<UserListResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await request<User[]>({
      url: '/accounts/users/',
      method: 'GET',
      params: {
        page: params.page,
        page_size: params.pageSize,
        search: params.search || '',
      }
    });

    if (response.success && Array.isArray(response.data)) {
      return {
        success: true,
        data: response.data,
        statusCode: 200,
        total: response.data.length, // 使用数组长度作为总数
      };
    } else {
      return {
        success: false,
        error: response.error || '获取用户列表失败：响应数据格式不正确',
        statusCode: 500,
      };
    }
  } catch (error) {
    let errorMessage = '获取用户列表失败，请稍后再试';
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
          errorMessage = `获取用户列表失败：服务器错误 (${statusCode})`;
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
 * 创建新用户
 * @param userData 用户数据
 * @returns 返回一个Promise，解析为包含创建结果的响应对象
 */
export const createUser = async (userData: CreateUserRequest): Promise<CreateUserResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await request<User>({
      url: '/accounts/users/',
      method: 'POST',
      data: userData
    });

    if (response.success && response.data) {
      return {
        success: true,
        data: response.data,
        statusCode: 201,
      };
    } else {
      return {
        success: false,
        error: response.error || '创建用户失败：响应数据格式不正确',
        statusCode: 500,
      };
    }
  } catch (error) {
    let errorMessage = '创建用户失败，请稍后再试';
    let statusCode: number | undefined;

    if (axios.isAxiosError(error)) {
      if (error.response) {
        statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (responseData && responseData.username && Array.isArray(responseData.username)) {
          errorMessage = `用户名错误: ${responseData.username.join(', ')}`;
        } else if (responseData && responseData.email && Array.isArray(responseData.email)) {
          errorMessage = `邮箱错误: ${responseData.email.join(', ')}`;
        } else if (responseData && responseData.password && Array.isArray(responseData.password)) {
          errorMessage = `密码错误: ${responseData.password.join(', ')}`;
        } else {
          errorMessage = `创建用户失败：服务器错误 (${statusCode})`;
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
 * 删除用户
 * @param userId 用户ID
 * @returns 返回一个Promise，解析为包含删除结果的响应对象
 */
export const deleteUser = async (userId: number): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await request<void>({
      url: `/accounts/users/${userId}/`,
      method: 'DELETE'
    });

    if (response.success) {
      return {
        success: true,
        message: response.message || '用户删除成功',
        statusCode: 200,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '删除用户失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '删除用户失败，请稍后再试';
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
          errorMessage = `删除用户失败：服务器错误 (${statusCode})`;
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
 * 更新用户信息
 * @param userId 用户ID
 * @param userData 要更新的用户数据
 * @returns 返回一个Promise，解析为包含更新结果的响应对象
 */
export const updateUser = async (userId: number, userData: UpdateUserRequest): Promise<{ success: boolean; data?: User; error?: string }> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await request<User>({
      url: `/accounts/users/${userId}/`,
      method: 'PATCH',
      data: userData
    });

    if (response.success && response.data) {
      return {
        success: true,
        data: response.data,
      };
    } else {
      return {
        success: false,
        error: response.error || '更新用户失败：响应数据格式不正确',
      };
    }
  } catch (error) {
    let errorMessage = '更新用户失败，请稍后再试';

    if (axios.isAxiosError(error) && error.response) {
      const statusCode = error.response.status;
      const responseData = error.response.data;

      if (responseData && typeof responseData.message === 'string') {
        errorMessage = responseData.message;
      } else if (responseData && typeof responseData.detail === 'string') {
        errorMessage = responseData.detail;
      } else if (responseData && responseData.username && Array.isArray(responseData.username)) {
        errorMessage = `用户名错误: ${responseData.username.join(', ')}`;
      } else if (responseData && responseData.email && Array.isArray(responseData.email)) {
        errorMessage = `邮箱错误: ${responseData.email.join(', ')}`;
      } else if (responseData && responseData.password && Array.isArray(responseData.password)) {
        errorMessage = `密码错误: ${responseData.password.join(', ')}`;
      } else if (statusCode === 404) {
        errorMessage = '用户不存在';
      } else {
        errorMessage = `更新用户失败：服务器错误 (${statusCode})`;
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
 * 获取用户详情
 * @param userId 用户ID
 * @returns 返回一个Promise，解析为包含用户详情的响应对象
 */
export const getUserDetail = async (userId: number): Promise<{ success: boolean; data?: User; error?: string }> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await request<User>({
      url: `/accounts/users/${userId}/`,
      method: 'GET'
    });

    if (response.success && response.data) {
      return {
        success: true,
        data: response.data,
      };
    } else {
      return {
        success: false,
        error: response.error || '获取用户详情失败：响应数据格式不正确',
      };
    }
  } catch (error) {
    let errorMessage = '获取用户详情失败，请稍后再试';

    if (axios.isAxiosError(error) && error.response) {
      const statusCode = error.response.status;
      const responseData = error.response.data;

      if (responseData && typeof responseData.message === 'string') {
        errorMessage = responseData.message;
      } else if (statusCode === 404) {
        errorMessage = '用户不存在';
      } else {
        errorMessage = `获取用户详情失败：服务器错误 (${statusCode})`;
      }
    }

    return {
      success: false,
      error: errorMessage,
    };
  }
};
