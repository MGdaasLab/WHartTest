import { request } from '@/utils/request';

export interface RemoteMcpConfig {
  id?: number;
  name: string;
  url: string;
  transport: 'stdio' | 'streamable_http' | 'sse';
  headers?: Record<string, string>;
  is_active: boolean;
  pinging?: boolean;
  created_at?: string;
  updated_at?: string;
}

interface PingResponse {
  success: boolean;
  message: string;
  response_time?: number;
}

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
