import { request } from '@/utils/request';

// API Key接口定义
export interface ApiKey {
  id: number;
  name: string;
  key: string; // 完整的key只在创建时返回一次
  user: string;
  created_at: string;
  expires_at: string | null;
  is_active: boolean;
}

// 创建API Key请求参数
export interface CreateApiKeyRequest {
  name: string;
  expires_at?: string | null;
  is_active?: boolean;
}

// 更新API Key请求参数
export interface UpdateApiKeyRequest {
  name?: string;
  expires_at?: string | null;
  is_active?: boolean;
}

// 获取API Key列表查询参数
export interface ApiKeyQueryParams {
  page?: number;
  pageSize?: number;
  search?: string;
}

// 获取API Key列表
export async function getApiKeyList(params: ApiKeyQueryParams = {}) {
  return request<ApiKey[]>({
    url: '/api-keys/',
    method: 'GET',
    params
  });
}

// 获取单个API Key详情
export async function getApiKeyDetail(id: number) {
  return request<ApiKey>({
    url: `/api-keys/${id}/`,
    method: 'GET'
  });
}

// 创建API Key
export async function createApiKey(data: CreateApiKeyRequest) {
  return request<ApiKey>({
    url: '/api-keys/',
    method: 'POST',
    data
  });
}

// 更新API Key
export async function updateApiKey(id: number, data: UpdateApiKeyRequest) {
  return request<ApiKey>({
    url: `/api-keys/${id}/`,
    method: 'PATCH',
    data
  });
}

// 删除API Key
export async function deleteApiKey(id: number) {
  return request<void>({
    url: `/api-keys/${id}/`,
    method: 'DELETE'
  });
}