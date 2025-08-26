import axios from 'axios'; // 使用 axios 替代 apiClient
import { useAuthStore } from '@/store/authStore'; // 导入 authStore 获取 token
// import type { APIResponse } from './types'; // 暂时在下方定义

// 通用 API 响应类型
export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  statusCode?: number;
  total?: number; // 用于分页
}

export interface TestCaseModule {
  id: number;
  name: string;
  project: number; // 项目ID
  parent: number | null; // 父模块ID
  parent_id: number | null; // 父模块ID (另一种表示)
  level: number; // 模块层级
  creator: number; // 创建者ID
  creator_detail?: {
    id: number;
    username: string;
    email: string;
    first_name: string;
    last_name: string;
    is_staff: boolean;
    is_active: boolean;
    groups: any[];
  };
  created_at: string;
  updated_at: string;
  // 可能的附加字段
  children_count?: number;
  test_case_count?: number;
  // 前端构建树时可能需要
  children?: TestCaseModule[];
  key?: number | string; // for a-tree
  title?: string; // for a-tree
}

export interface CreateTestCaseModuleRequest {
  name: string;
  parent?: number | null; // 父模块ID，可选, Django后端通常接受null作为无父级
}

export interface UpdateTestCaseModuleRequest {
  name?: string;
  parent?: number | null; // 父模块ID，可选
}

// 使用环境变量获取 API 基础 URL
const APP_API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// TODO: CSRF TOKEN 管理需要更健壮的方案
const CSRF_TOKEN = 'kMNlyN2uN6c2QRr9r2rDQbfxBGsVzjPFY1h1as93VNMRTjo5kRpDbVq5ii8FFcKW'; // 暂时使用 authService 中的一个

const getApiBasePath = (projectId: string | number | undefined | null) => {
  if (!projectId) {
    // 在调用函数前应该已经检查过 projectId，这里作为最后防线
    console.error('Project ID is undefined in API call');
    throw new Error('Project ID is required for test case module API calls.');
  }
  return `${APP_API_BASE_URL}/projects/${projectId}/testcase-modules/`;
};

// 辅助函数处理 Axios 错误
const handleError = (error: any, defaultMessage: string): APIResponse<any> => {
  console.error(defaultMessage, error);
  if (axios.isAxiosError(error)) {
    const responseData = error.response?.data;
    const message = responseData?.detail || responseData?.message || (typeof responseData === 'string' ? responseData : defaultMessage);
    return {
      success: false,
      error: message,
      statusCode: error.response?.status,
    };
  }
  return { success: false, error: error.message || defaultMessage };
};


// 获取模块列表
// API 响应格式
interface ApiResponse<T> {
  status: string;
  code: number;
  message: string;
  data: T;
  errors: any;
}

export const getTestCaseModules = async (
  projectId: string | number | undefined | null,
  params?: { search?: string; page?: number; pageSize?: number } // 添加分页参数
): Promise<APIResponse<TestCaseModule[]>> => {
  if (!projectId) return { success: false, error: '项目ID不能为空' };

  // 获取认证 token
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const basePath = getApiBasePath(projectId);
    // Django分页参数通常是 page 和 page_size
    const queryParams = {
        search: params?.search,
        page: params?.page,
        page_size: params?.pageSize,
    };
    const response = await axios.get<ApiResponse<TestCaseModule[]>>(basePath, {
      params: queryParams,
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 处理API响应格式
    if (response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data, // 直接使用 data 字段
        total: response.data.data.length, // 使用数组长度作为总数
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data.message || '获取模块列表失败',
        statusCode: response.data.code,
      };
    }
  } catch (error: any) {
    return handleError(error, '获取模块列表失败');
  }
};

// 创建模块
export const createTestCaseModule = async (
  projectId: string | number | undefined | null,
  data: CreateTestCaseModuleRequest
): Promise<APIResponse<TestCaseModule>> => {
  if (!projectId) return { success: false, error: '项目ID不能为空' };

  // 获取认证 token
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const basePath = getApiBasePath(projectId);
    const response = await axios.post<ApiResponse<TestCaseModule>>(basePath, data, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-CSRFTOKEN': CSRF_TOKEN, // 添加 CSRF Token
      },
    });

    // 处理API响应格式
    if (response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data.message || '创建模块失败',
        statusCode: response.data.code,
      };
    }
  } catch (error: any) {
    return handleError(error, '创建模块失败');
  }
};

// 获取模块详情
export const getTestCaseModuleDetail = async (
  projectId: string | number | undefined | null,
  moduleId: number
): Promise<APIResponse<TestCaseModule>> => {
  if (!projectId) return { success: false, error: '项目ID不能为空' };

  // 获取认证 token
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const basePath = getApiBasePath(projectId);
    const response = await axios.get<ApiResponse<TestCaseModule>>(`${basePath}${moduleId}/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 处理API响应格式
    if (response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data.message || '获取模块详情失败',
        statusCode: response.data.code,
      };
    }
  } catch (error: any) {
    return handleError(error, '获取模块详情失败');
  }
};

// 更新模块
export const updateTestCaseModule = async (
  projectId: string | number | undefined | null,
  moduleId: number,
  data: UpdateTestCaseModuleRequest
): Promise<APIResponse<TestCaseModule>> => {
  if (!projectId) return { success: false, error: '项目ID不能为空' };

  // 获取认证 token
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const basePath = getApiBasePath(projectId);
    const response = await axios.put<ApiResponse<TestCaseModule>>(`${basePath}${moduleId}/`, data, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-CSRFTOKEN': CSRF_TOKEN, // 添加 CSRF Token
      },
    });

    // 处理API响应格式
    if (response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data.message || '更新模块失败',
        statusCode: response.data.code,
      };
    }
  } catch (error: any) {
    return handleError(error, '更新模块失败');
  }
};

// 删除模块
export const deleteTestCaseModule = async (
  projectId: string | number | undefined | null,
  moduleId: number
): Promise<APIResponse<null>> => { // data 为 null
  if (!projectId) return { success: false, error: '项目ID不能为空' };

  // 获取认证 token
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const basePath = getApiBasePath(projectId);
    const response = await axios.delete<ApiResponse<null>>(`${basePath}${moduleId}/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-CSRFTOKEN': CSRF_TOKEN, // 添加 CSRF Token
      },
    });

    // 处理API响应格式
    if (response.data.status === 'success') {
      return {
        success: true,
        data: null,
        statusCode: response.data.code,
      };
    } else {
      return {
        success: false,
        error: response.data.message || '删除模块失败',
        statusCode: response.data.code,
      };
    }
  } catch (error: any) {
    return handleError(error, '删除模块失败');
  }
};