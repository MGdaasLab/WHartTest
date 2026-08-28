import { request } from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import type { ApiGlobalRequestHeader } from '../types/environment';
import { wrapListResponse, wrapOneResponse } from './responseHelpers';

const base = (projectId: number) => `/projects/${projectId}/api-global-headers`;

export const globalHeaderService = {
  list: (projectId: number, params?: Record<string, any>) =>
    request<ApiGlobalRequestHeader[]>({ url: `${base(projectId)}/`, method: 'GET', params }),

  get: (projectId: number, id: number) =>
    request<ApiGlobalRequestHeader>({ url: `${base(projectId)}/${id}/`, method: 'GET' }),

  create: (projectId: number, data: Partial<ApiGlobalRequestHeader>) =>
    request<ApiGlobalRequestHeader>({ url: `${base(projectId)}/`, method: 'POST', data }),

  update: (projectId: number, id: number, data: Partial<ApiGlobalRequestHeader>) =>
    request<ApiGlobalRequestHeader>({ url: `${base(projectId)}/${id}/`, method: 'PUT', data }),

  delete: (projectId: number, id: number) =>
    request<void>({ url: `${base(projectId)}/${id}/`, method: 'DELETE' }),
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
export type GlobalHeader = ApiGlobalRequestHeader & Record<string, any>;
export type CreateGlobalHeaderData = Partial<ApiGlobalRequestHeader> & { project?: number };

export async function getGlobalHeaders(projectId?: number) {
  const pid = projectId ?? _pid();
  return _wrapList(await globalHeaderService.list(pid));
}

export async function createGlobalHeader(data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await globalHeaderService.create(pid, data));
}

export async function updateGlobalHeader(id: number, data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await globalHeaderService.update(pid, id, data));
}

export async function deleteGlobalHeader(id: number) {
  return _wrapOne(await globalHeaderService.delete(_pid(), id));
}
