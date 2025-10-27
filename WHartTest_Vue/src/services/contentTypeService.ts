// src/services/contentTypeService.ts
import axios from 'axios';
import { useAuthStore } from '@/store/authStore';
import { API_BASE_URL } from '@/config/api';

// 内容类型数据接口
export interface ContentType {
  id: number;
  app_label: string;
  model: string;
  model_verbose: string; // 模型的可读名称
}

// 内容类型列表响应接口
export interface ContentTypeListResponse {
  success: boolean;
  data?: ContentType[];
  error?: string;
  statusCode?: number;
  total?: number;
}

// 内容类型查询参数接口
export interface ContentTypeQueryParams {
  app_label?: string;
  search?: string;
}

/**
 * 获取所有内容类型列表
 * @param params 查询参数
 * @returns 返回一个Promise，解析为包含内容类型列表的响应对象
 */
export const getContentTypeList = async (params?: ContentTypeQueryParams): Promise<ContentTypeListResponse> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/accounts/content-types/`, {
      params: params,
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设API返回的数据格式为 { status: 'success', code: 200, message: '数据获取成功', data: [...内容类型数组] }
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
        error: response.data?.message || '获取内容类型列表失败：响应数据格式不正确',
        statusCode: response.data?.code,
      };
    }
  } catch (error) {
    let errorMessage = '获取内容类型列表失败，请稍后再试';
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
          errorMessage = `获取内容类型列表失败：服务器错误 (${statusCode})`;
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
 * 获取特定内容类型详情
 * @param contentTypeId 内容类型ID
 * @returns 返回一个Promise，解析为包含内容类型详情的响应对象
 */
export const getContentTypeDetail = async (contentTypeId: number): Promise<{ success: boolean; data?: ContentType; error?: string }> => {
  const authStore = useAuthStore();
  const accessToken = authStore.getAccessToken;

  if (!accessToken) {
    return {
      success: false,
      error: '未登录或会话已过期',
    };
  }

  try {
    const response = await axios.get(`${API_BASE_URL}/accounts/content-types/${contentTypeId}/`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // 假设内容类型详情API返回的格式与列表接口类似
    if (response.data && response.data.status === 'success' && response.data.data) {
      return {
        success: true,
        data: response.data.data,
      };
    } else {
      return {
        success: false,
        error: response.data?.message || '获取内容类型详情失败：响应数据格式不正确',
      };
    }
  } catch (error) {
    let errorMessage = '获取内容类型详情失败，请稍后再试';

    if (axios.isAxiosError(error)) {
      if (error.response) {
        const statusCode = error.response.status;
        const responseData = error.response.data;

        if (responseData && typeof responseData.message === 'string') {
          errorMessage = responseData.message;
        } else if (responseData && typeof responseData.detail === 'string') {
          errorMessage = responseData.detail;
        } else if (statusCode === 404) {
          errorMessage = '内容类型不存在';
        } else {
          errorMessage = `获取内容类型详情失败：服务器错误 (${statusCode})`;
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
    };
  }
};
