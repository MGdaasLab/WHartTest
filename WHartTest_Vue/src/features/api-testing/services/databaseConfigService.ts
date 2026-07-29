import { request } from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import type { ApiDatabaseConfig } from '../types/databaseConfig';
import { wrapListResponse, wrapOneResponse } from './responseHelpers';

const base = (projectId: number) => `/projects/${projectId}/api-database-configs`;

export const databaseConfigService = {
  list: (projectId: number, params?: Record<string, any>) =>
    request<ApiDatabaseConfig[]>({ url: `${base(projectId)}/`, method: 'GET', params }),

  get: (projectId: number, id: number) =>
    request<ApiDatabaseConfig>({ url: `${base(projectId)}/${id}/`, method: 'GET' }),

  create: (projectId: number, data: Partial<ApiDatabaseConfig>) =>
    request<ApiDatabaseConfig>({ url: `${base(projectId)}/`, method: 'POST', data }),

  update: (projectId: number, id: number, data: Partial<ApiDatabaseConfig>) =>
    request<ApiDatabaseConfig>({ url: `${base(projectId)}/${id}/`, method: 'PUT', data }),

  delete: (projectId: number, id: number) =>
    request<void>({ url: `${base(projectId)}/${id}/`, method: 'DELETE' }),

  testConnection: (projectId: number, data: Partial<ApiDatabaseConfig>) =>
    request<{ success: boolean; message: string }>({
      url: `${base(projectId)}/test-connection/`, method: 'POST', data,
    }),

  testSavedConnection: (projectId: number, id: number) =>
    request<{ success: boolean; message: string }>({
      url: `${base(projectId)}/${id}/test-connection/`, method: 'POST',
    }),
};

// ---------------------------------------------------------------------------
// Compatibility exports
// ---------------------------------------------------------------------------

function _pid(): number {
  return useProjectStore().currentProjectId ?? 0;
}

function _wrapList(res: any): any {
  return wrapListResponse(res);
}

function _wrapOne(res: any): any {
  return wrapOneResponse(res);
}

// Type aliases
export type DatabaseConfig = Partial<ApiDatabaseConfig> & Record<string, any>;
export type CreateDatabaseConfigData = Partial<ApiDatabaseConfig> & { project?: number };
export type UpdateDatabaseConfigData = Partial<ApiDatabaseConfig>;
export type TestConnectionData = {
  db_type: string;
  host: string;
  port: number;
  username: string;
  password: string;
  database: string;
  charset?: string;
  [key: string]: any;
};

export async function getDatabaseConfigs(projectId?: number) {
  const pid = projectId ?? _pid();
  return _wrapList(await databaseConfigService.list(pid));
}

export async function createDatabaseConfig(data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await databaseConfigService.create(pid, data));
}

export async function updateDatabaseConfig(id: number, data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await databaseConfigService.update(pid, id, data));
}

export async function deleteDatabaseConfig(id: number) {
  return _wrapOne(await databaseConfigService.delete(_pid(), id));
}

export async function testDatabaseConnection(id: number) {
  return _wrapOne(await databaseConfigService.testSavedConnection(_pid(), id));
}

export async function testConnection(data: TestConnectionData) {
  return _wrapOne(await databaseConfigService.testConnection(_pid(), data as any));
}
