import { request } from '@/utils/request';

// 操作日志对象接口
export interface OperationLog {
  id: number;
  user: number | null;
  username: string;
  ip_address: string | null;
  user_agent: string;
  path: string;
  method: string;
  module: string;
  action: string;
  request_data: string;
  response_code: number | null;
  response_data: string;
  duration: number;
  created_at: string;
}

// 检索筛选参数接口
export interface OperationLogQueryParams {
  page?: number;
  pageSize?: number;
  username?: string;
  module?: string;
  action?: string;
  method?: string;
  response_code?: number;
  start_time?: string;
  end_time?: string;
  search?: string;
  ordering?: string;
}

// 操作日志列表响应接口
export interface OperationLogListResponse {
  success: boolean;
  data?: OperationLog[];
  total?: number;
  error?: string;
}


export interface OperationLogSettings {
  id: number;
  retention_days: number;
  updated_at?: string;
}

export interface OperationLogSettingsResponse {
  success: boolean;
  data?: OperationLogSettings;
  error?: string;
}

export interface OperationLogCleanupResult {
  status: string;
  retention_days: number;
  cutoff_time: string;
  deleted_count: number;
}

export interface OperationLogCleanupResponse {
  success: boolean;
  data?: OperationLogCleanupResult;
  error?: string;
}

/**
 * 获取用户操作日志列表
 * @param params 过滤筛选与分页参数
 * @returns 统一返回结果
 */
export async function getOperationLogList(params: OperationLogQueryParams = {}): Promise<OperationLogListResponse> {
  const queryParams: any = {
    page: params.page,
    page_size: params.pageSize,
    username: params.username || undefined,
    module: params.module || undefined,
    action: params.action || undefined,
    method: params.method || undefined,
    response_code: params.response_code || undefined,
    start_time: params.start_time || undefined,
    end_time: params.end_time || undefined,
    search: params.search || undefined,
    ordering: params.ordering || undefined,
  };

  // 剔除 undefined 的属性
  Object.keys(queryParams).forEach(key => {
    if (queryParams[key] === undefined) {
      delete queryParams[key];
    }
  });

  try {
    const response = await request<any>({
      url: '/operation-logs/',
      method: 'GET',
      params: queryParams,
    });

    if (response.success && response.data) {
      // 1. 处理后端返回的标准 DRF 分页结构 { count, results }
      if (response.data.results && Array.isArray(response.data.results)) {
        return {
          success: true,
          data: response.data.results,
          total: response.data.count || 0,
        };
      }
      // 2. 处理直接返回普通数组的情况
      if (Array.isArray(response.data)) {
        return {
          success: true,
          data: response.data,
          total: response.total ?? response.data.length,
        };
      }
    }

    return {
      success: false,
      error: response.error || '获取操作日志列表失败：服务器返回的数据格式不正确',
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.message || '获取操作日志列表发生网络异常',
    };
  }
}

export async function cleanupOperationLogsNow(): Promise<OperationLogCleanupResponse> {
  try {
    const response = await request<any>({
      url: '/operation-logs/cleanup-now/',
      method: 'POST',
    });

    if (response.success && response.data) {
      return {
        success: true,
        data: response.data,
      };
    }

    return {
      success: false,
      error: response.error || '立即清理操作日志失败',
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.message || '立即清理操作日志发生网络异常',
    };
  }
}


export async function getOperationLogSettings(): Promise<OperationLogSettingsResponse> {
  try {
    const response = await request<any>({
      url: '/operation-logs/settings/',
      method: 'GET',
    });

    if (response.success && response.data) {
      return { success: true, data: response.data };
    }

    return {
      success: false,
      error: response.error || '加载操作日志自动清理设置失败',
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.message || '加载操作日志自动清理设置发生网络异常',
    };
  }
}

export async function updateOperationLogSettings(data: Partial<Pick<OperationLogSettings, 'retention_days'>>): Promise<OperationLogSettingsResponse> {
  try {
    const response = await request<any>({
      url: '/operation-logs/settings/',
      method: 'PATCH',
      data,
    });

    if (response.success && response.data) {
      return { success: true, data: response.data };
    }

    return {
      success: false,
      error: response.error || '保存操作日志自动清理设置失败',
    };
  } catch (error: any) {
    return {
      success: false,
      error: error.message || '保存操作日志自动清理设置发生网络异常',
    };
  }
}
