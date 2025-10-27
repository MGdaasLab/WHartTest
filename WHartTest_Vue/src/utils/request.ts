import axios from 'axios';
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/store/authStore';
import { isTokenInvalidError, handleAuthError } from '@/utils/authErrorHandler';

// 定义我们需要的请求配置类型
type RequestConfig = {
  url: string;
  method: string;
  data?: any;
  params?: any;
  headers?: Record<string, string>;
  _retry?: boolean; // 用于标记是否已经重试过
  [key: string]: any;
};

// 获取智能的API基础URL
function getApiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  const useProxy = import.meta.env.VITE_USE_PROXY === 'true' || import.meta.env.VITE_USE_PROXY === true;

  // 如果启用了 Vite 代理，优先使用相对路径以走开发服务器的代理，避免跨域
  if (useProxy) {
    return '/api';
  }

  // 如果环境变量是完整URL（包含http/https），直接使用
  if (envUrl && (envUrl.startsWith('http://') || envUrl.startsWith('https://'))) {
    return envUrl;
  }

  // 如果提供了相对路径或没有配置，使用环境变量（可能是相对路径）或回退到 '/api'
  return envUrl || '/api';
}

// 创建axios实例
const service = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 60000, // 请求超时时间
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 从authStore获取token
    const authStore = useAuthStore();
    const token = authStore.getAccessToken;

    // 如果有token就添加到请求头
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 是否正在刷新token
let isRefreshing = false;
// 等待刷新token的请求队列
let refreshSubscribers: ((token: string) => void)[] = [];

// 将请求添加到队列
function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

// 刷新token完成后执行队列中的请求
function onRefreshed(token: string) {
  refreshSubscribers.forEach(cb => cb(token));
  refreshSubscribers = [];
}

// 刷新token
async function refreshToken() {
  const authStore = useAuthStore();
  const refreshToken = authStore.getRefreshToken;

  if (!refreshToken) {
    // 如果没有refreshToken，直接登出
    authStore.logout();
    return null;
  }

  try {
    // 使用配置好的 baseURL 来刷新 token
    const response = await axios.post(`${getApiBaseUrl()}/token/refresh/`, {
      refresh: refreshToken
    });

    if (response.data && response.data.access) {
      // 更新token
      const newToken = response.data.access;
      // 更新AuthStore中的token
      localStorage.setItem('auth-accessToken', newToken);
      return newToken;
    } else {
      // 刷新失败，清除token并登出
      authStore.logout();
      return null;
    }
  } catch (error) {
    // 刷新失败，清除token并登出
    authStore.logout();
    return null;
  }
}

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    // 后端返回的完整响应
    const res = response.data;

    // 检查后端返回的标准格式 { status, code, message, data, errors }
    if (res && 'status' in res && 'data' in res) {
      return {
        success: res.status === 'success', // 根据后端状态判断是否成功
        data: res.data, // 直接传递data字段
        total: response.headers['x-total-count'] ? parseInt(response.headers['x-total-count']) : undefined,
        message: res.message || 'success'
      };
    }

    // 旧的处理方式，保留兼容性
    return {
      success: true,
      data: res,
      total: response.headers['x-total-count'] ? parseInt(response.headers['x-total-count']) : undefined,
      message: 'success'
    };
  },
  async (error) => {
    const originalRequest = error.config as RequestConfig;
    const { response } = error;
    let message = '未知错误';
    let status = 500;

    // 检查是否是401错误（未授权）
    if (response && response.status === 401) {
      // 对于所有401错误，直接清除token并跳转到登录页
      const authStore = useAuthStore();
      authStore.logout();
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
      return Promise.reject({
        success: false,
        status: 401,
        error: '登录已过期，请重新登录',
      });
    }

    if (response) {
      status = response.status;
      // 尝试从响应中获取错误信息
      try {
        if (response.data) {
          if (typeof response.data === 'string') {
            message = response.data;
          } else if (response.data.errors && response.data.errors.error) {
            // 优先检查是否有errors.error字段（用户报告的错误格式）
            message = response.data.errors.error;
          } else if (response.data.errors && response.data.errors.message) {
            // 然后检查是否有errors.message字段
            message = response.data.errors.message;
          } else if (response.data.detail) {
            message = response.data.detail;
          } else if (response.data.message) {
            message = response.data.message;
          } else if (response.data.error) {
            message = response.data.error;
          } else {
            message = JSON.stringify(response.data);
          }
        } else {
          message = response.statusText;
        }
      } catch (e) {
        message = '解析错误响应失败';
      }

      // 处理特定的错误状态码
      switch (status) {
        case 401:
          // 检查是否是令牌无效的错误，或者是刷新token的请求失败，或者重试后仍然401
          if (isTokenInvalidError(response.data) || originalRequest._retry || originalRequest.url === '/token/refresh/') {
            message = '登录已过期，请重新登录';
            // 清除token并重定向到登录页
            handleAuthError(message);
          }
          break;
        case 403:
          // 对于403错误，优先使用从响应中解析的具体权限错误消息
          // 如果没有解析到具体消息，则使用默认消息
          if (!message || message === '未知错误') {
            message = '没有权限访问该资源';
          }
          break;
        case 404:
          message = '请求的资源不存在';
          break;
        case 500:
          message = '服务器内部错误';
          break;
        default:
          // 使用从响应中解析的消息
          break;
      }
    } else if (error.request) {
      // 请求已发送但没有收到响应
      message = '服务器无响应，请检查网络连接';
    } else {
      // 设置请求时出错
      message = error.message || '请求失败';
    }

    // 返回统一的错误响应格式
    return Promise.reject({
      success: false,
      status,
      error: message,
    });
  }
);

// 封装的请求方法
export async function request<T>(config: RequestConfig): Promise<{
  success: boolean;
  data?: T;
  total?: number;
  error?: string;
  message?: string;
}> {
  try {
    const response = await service(config);
    return response as { success: boolean; data: T; total?: number; message: string };
  } catch (error: any) {
    return error;
  }
}

export default service;