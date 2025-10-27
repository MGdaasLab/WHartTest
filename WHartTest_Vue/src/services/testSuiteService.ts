// src/services/testSuiteService.ts
import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import { API_BASE_URL } from '@/config/api';
import type { TestCase } from './testcaseService';

// 测试套件接口
export interface TestSuite {
  id: number;
  name: string;
  description?: string;
  project: number;
  testcase_count: number;
  max_concurrent_tasks: number;
  testcases_detail?: TestCase[];
  creator: number;
  creator_detail: {
    id: number;
    username: string;
    email: string;
  };
  created_at: string;
  updated_at: string;
}

// 创建测试套件请求参数
export interface CreateTestSuiteRequest {
  name: string;
  description?: string;
  testcase_ids: number[];
  max_concurrent_tasks?: number;
}

// 更新测试套件请求参数
export interface UpdateTestSuiteRequest {
  name?: string;
  description?: string;
  testcase_ids?: number[];
  max_concurrent_tasks?: number;
}

// 测试套件列表响应接口
export interface TestSuiteListResponse {
  success: boolean;
  data?: TestSuite[];
  total?: number;
  error?: string;
  statusCode?: number;
}

// 单个测试套件响应接口
export interface TestSuiteResponse {
  success: boolean;
  data?: TestSuite;
  error?: string;
  statusCode?: number;
  message?: string;
}

// 操作响应接口
export interface OperationResponse {
  success: boolean;
  message?: string;
  error?: string;
  statusCode?: number;
}

/**
 * 获取项目下的测试套件列表
 * @param projectId 项目ID
 * @param params 查询参数
 * @returns 返回一个Promise，解析为包含测试套件列表的响应对象
 */
export const getTestSuiteList = async (
  projectId: number,
  params?: { search?: string }
): Promise<TestSuiteListResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/projects/${projectId}/test-suites/`, {
      params,
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    if (response.data && response.data.status === 'success') {
      if (Array.isArray(response.data.data)) {
        return {
          success: true,
          data: response.data.data,
          total: response.data.data.length,
          statusCode: response.data.code,
        };
      } else if (response.data.data && response.data.data.results) {
        return {
          success: true,
          data: response.data.data.results,
          total: response.data.data.count,
          statusCode: response.data.code,
        };
      }
    }

    return {
      success: false,
      error: response.data?.message || '获取测试套件列表失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('获取测试套件列表出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '获取测试套件列表时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 创建新测试套件
 * @param projectId 项目ID
 * @param suiteData 测试套件数据
 * @returns 返回一个Promise，解析为创建结果
 */
export const createTestSuite = async (
  projectId: number,
  suiteData: CreateTestSuiteRequest
): Promise<TestSuiteResponse> => {
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
      `${API_BASE_URL}/projects/${projectId}/test-suites/`,
      suiteData,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        message: response.data.message,
        statusCode: response.data.code,
      };
    }

    return {
      success: false,
      error: response.data?.message || '创建测试套件失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('创建测试套件出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '创建测试套件时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 获取测试套件详情
 * @param projectId 项目ID
 * @param suiteId 测试套件ID
 * @returns 返回一个Promise，解析为测试套件详情
 */
export const getTestSuiteDetail = async (
  projectId: number,
  suiteId: number
): Promise<TestSuiteResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(
      `${API_BASE_URL}/projects/${projectId}/test-suites/${suiteId}/`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        statusCode: response.data.code,
      };
    }

    return {
      success: false,
      error: response.data?.message || '获取测试套件详情失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('获取测试套件详情出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '获取测试套件详情时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 更新测试套件
 * @param projectId 项目ID
 * @param suiteId 测试套件ID
 * @param suiteData 更新的测试套件数据
 * @returns 返回一个Promise，解析为更新结果
 */
export const updateTestSuite = async (
  projectId: number,
  suiteId: number,
  suiteData: UpdateTestSuiteRequest
): Promise<TestSuiteResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.patch(
      `${API_BASE_URL}/projects/${projectId}/test-suites/${suiteId}/`,
      suiteData,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      }
    );

    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
        message: response.data.message,
        statusCode: response.data.code,
      };
    }

    return {
      success: false,
      error: response.data?.message || '更新测试套件失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('更新测试套件出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '更新测试套件时发生错误',
      statusCode: error.response?.status,
    };
  }
};

/**
 * 删除测试套件
 * @param projectId 项目ID
 * @param suiteId 测试套件ID
 * @returns 返回一个Promise，解析为删除结果
 */
export const deleteTestSuite = async (
  projectId: number,
  suiteId: number
): Promise<OperationResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.delete(
      `${API_BASE_URL}/projects/${projectId}/test-suites/${suiteId}/`,
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
        message: response.data.message || '测试套件删除成功',
        statusCode: response.data.code,
      };
    }

    return {
      success: false,
      error: response.data?.message || '删除测试套件失败',
      statusCode: response.data?.code,
    };
  } catch (error: any) {
    console.error('删除测试套件出错:', error);
    return {
      success: false,
      error: error.response?.data?.message || error.message || '删除测试套件时发生错误',
      statusCode: error.response?.status,
    };
  }
};