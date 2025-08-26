import { request } from '@/utils/request';

export interface RemoteMcpConfig {
  id?: number;
  name: string;
  url: string;
  transport: 'stdio' | 'streamable_http' | 'sse';
  headers?: Record<string, string>;
  is_active: boolean;
  owner?: string;
  created_at?: string;
  updated_at?: string;
}

interface ApiResponse<T> {
  status: string;
  code: number;
  message: string;
  data: T;
  errors: any;
}

interface PingResponse {
  success: boolean;
  message: string;
  response_time?: number;
}

// 获取所有远程MCP配置
export const fetchRemoteMcpConfigs = async (): Promise<RemoteMcpConfig[]> => {
  try {
    const response = await request<RemoteMcpConfig[]>({
      url: '/mcp_tools/remote-configs/',
      method: 'GET'
    });

    if (response.success) {
      return response.data || [];
    } else {
      throw new Error(response.error || '获取远程MCP配置失败');
    }
  } catch (error) {
    console.error('获取远程MCP配置失败:', error);
    throw error;
  }
};

// 获取单个远程MCP配置
export const fetchRemoteMcpConfigById = async (id: number): Promise<RemoteMcpConfig> => {
  try {
    const response = await request<RemoteMcpConfig>({
      url: `/mcp_tools/remote-configs/${id}/`,
      method: 'GET'
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || `获取远程MCP配置(ID: ${id})失败`);
    }
  } catch (error) {
    console.error(`获取远程MCP配置(ID: ${id})失败:`, error);
    throw error;
  }
};

// 创建新的远程MCP配置
export const createRemoteMcpConfig = async (config: RemoteMcpConfig): Promise<RemoteMcpConfig> => {
  try {
    const response = await request<RemoteMcpConfig>({
      url: '/mcp_tools/remote-configs/',
      method: 'POST',
      data: config
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || '创建远程MCP配置失败');
    }
  } catch (error) {
    console.error('创建远程MCP配置失败:', error);
    throw error;
  }
};

// 更新远程MCP配置
export const updateRemoteMcpConfig = async (id: number, config: Partial<RemoteMcpConfig>): Promise<RemoteMcpConfig> => {
  try {
    const response = await request<RemoteMcpConfig>({
      url: `/mcp_tools/remote-configs/${id}/`,
      method: 'PATCH',
      data: config
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || `更新远程MCP配置(ID: ${id})失败`);
    }
  } catch (error) {
    console.error(`更新远程MCP配置(ID: ${id})失败:`, error);
    throw error;
  }
};

// 删除远程MCP配置
export const deleteRemoteMcpConfig = async (id: number): Promise<void> => {
  try {
    const response = await request<void>({
      url: `/mcp_tools/remote-configs/${id}/`,
      method: 'DELETE'
    });

    if (!response.success) {
      throw new Error(response.error || `删除远程MCP配置(ID: ${id})失败`);
    }
  } catch (error) {
    console.error(`删除远程MCP配置(ID: ${id})失败:`, error);
    throw error;
  }
};

// 测试远程MCP服务器连通性
export const pingRemoteMcpConfig = async (configId: number): Promise<PingResponse> => {
  try {
    const response = await request<any>({
      url: '/mcp_tools/remote-configs/ping/',
      method: 'POST',
      data: {
        config_id: configId
      }
    });

    if (response.success && response.data) {
      const pingResultPayload = response.data;
      // 根据ping结果的内部status判断是否成功
      const isSuccess = pingResultPayload && pingResultPayload.status === 'online';

      return {
        success: isSuccess,
        message: response.message || (isSuccess ? '连接成功' : '连接失败'),
        response_time: pingResultPayload?.response_time
      };
    } else {
      return {
        success: false,
        message: response.error || '连接失败'
      };
    }
  } catch (error) {
    console.error(`测试远程MCP配置(ID: ${configId})连通性失败:`, error);
    let errorMessage = '未知错误';
    if (error instanceof Error) {
      errorMessage = error.message;
    }
    return {
      success: false,
      message: errorMessage
    };
  }
};