import { request } from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import type { ApiCustomFunction } from '../types/function';
import { wrapListResponse, wrapOneResponse } from './responseHelpers';

const base = (projectId: number) => `/projects/${projectId}/api-functions`;

export const functionService = {
  list: (projectId: number, params?: Record<string, any>) =>
    request<ApiCustomFunction[]>({ url: `${base(projectId)}/`, method: 'GET', params }),

  get: (projectId: number, id: number) =>
    request<ApiCustomFunction>({ url: `${base(projectId)}/${id}/`, method: 'GET' }),

  create: (projectId: number, data: Partial<ApiCustomFunction>) =>
    request<ApiCustomFunction>({ url: `${base(projectId)}/`, method: 'POST', data }),

  update: (projectId: number, id: number, data: Partial<ApiCustomFunction>) =>
    request<ApiCustomFunction>({ url: `${base(projectId)}/${id}/`, method: 'PUT', data }),

  delete: (projectId: number, id: number) =>
    request<void>({ url: `${base(projectId)}/${id}/`, method: 'DELETE' }),

  generateDebugtalk: (projectId: number) =>
    request<{ content: string }>({ url: `${base(projectId)}/generate_debugtalk/`, method: 'GET' }),

  execute: (projectId: number, data: { code: string; test_args?: any }) =>
    request<{ result: any }>({ url: `${base(projectId)}/execute/`, method: 'POST', data }),
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

// Type alias – components import `Function` from this file
export type Function = ApiCustomFunction & Record<string, any>;

export async function getFunctions(params: Record<string, any> = {}) {
  const pid = params.project_id ? Number(params.project_id) : _pid();
  delete params.project_id;
  return _wrapList(await functionService.list(pid, params));
}

export async function getFunctionDetail(id: number) {
  return _wrapOne(await functionService.get(_pid(), id));
}

export async function createFunction(data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await functionService.create(pid, data));
}

export async function updateFunction(id: number, data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await functionService.update(pid, id, data));
}

export async function deleteFunction(id: number) {
  return _wrapOne(await functionService.delete(_pid(), id));
}

export async function testFunction(data: { code: string; test_args?: any }) {
  const pid = _pid();
  return _wrapOne(await functionService.execute(pid, { code: data.code, test_args: data.test_args }));
}
