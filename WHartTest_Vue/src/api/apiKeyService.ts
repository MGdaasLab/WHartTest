// 修改类型定义，适应新的响应格式
export interface ApiKeyResponseData {
  success: boolean;
  data: ApiKeyItem[] | ApiKeyItem;
  total?: number;
  message?: string;
  error?: string;
}

// 获取API Key列表
export async function getApiKeyList(params: ApiKeyListParams): Promise<ApiKeyResponseData> {
  try {
    return await request({
      url: '/api/v1/api-keys',
      method: 'GET',
      params,
    });
  } catch (error) {
    console.error('获取API Key列表错误:', error);
    throw error;
  }
}

// 创建API Key
export async function createApiKeyRequest(data: ApiKeyCreateData): Promise<ApiKeyResponseData> {
  try {
    return await request({
      url: '/api/v1/api-keys',
      method: 'POST',
      data,
    });
  } catch (error) {
    console.error('创建API Key错误:', error);
    throw error;
  }
}

// 更新API Key
export async function updateApiKeyRequest(id: number | string, data: ApiKeyUpdateData): Promise<ApiKeyResponseData> {
  try {
    return await request({
      url: `/api/v1/api-keys/${id}`,
      method: 'PUT',
      data,
    });
  } catch (error) {
    console.error('更新API Key错误:', error);
    throw error;
  }
}

// 删除API Key
export async function deleteApiKeyRequest(id: number | string): Promise<ApiKeyResponseData> {
  try {
    return await request({
      url: `/api/v1/api-keys/${id}`,
      method: 'DELETE',
    });
  } catch (error) {
    console.error('删除API Key错误:', error);
    throw error;
  }
} 