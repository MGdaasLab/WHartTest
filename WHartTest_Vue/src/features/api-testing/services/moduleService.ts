import { request } from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import type { ApiModule } from '../types/module';
import { wrapListResponse, wrapOneResponse } from './responseHelpers';

export interface ApiModuleDeleteResult {
  deleted_interface_ids: number[];
  deleted_interface_count: number;
}

const base = (projectId: number) => `/projects/${projectId}/api-modules`;

export const moduleService = {
  list: (projectId: number, params?: Record<string, any>) =>
    request<ApiModule[]>({ url: `${base(projectId)}/`, method: 'GET', params }),

  get: (projectId: number, id: number) =>
    request<ApiModule>({ url: `${base(projectId)}/${id}/`, method: 'GET' }),

  create: (projectId: number, data: Partial<ApiModule>) =>
    request<ApiModule>({ url: `${base(projectId)}/`, method: 'POST', data }),

  update: (projectId: number, id: number, data: Partial<ApiModule>) =>
    request<ApiModule>({ url: `${base(projectId)}/${id}/`, method: 'PUT', data }),

  delete: (projectId: number, id: number) =>
    request<ApiModuleDeleteResult>({ url: `${base(projectId)}/${id}/`, method: 'DELETE' }),

  tree: (projectId: number) =>
    request<ApiModule[]>({ url: `${base(projectId)}/tree/`, method: 'GET' }),

  move: (projectId: number, id: number, data: { target_id: number | null; drop_position: number }) =>
    request<ApiModule>({ url: `${base(projectId)}/${id}/move/`, method: 'POST', data }),
};

// ---------------------------------------------------------------------------
// Compatibility exports
// ---------------------------------------------------------------------------

function _pid(params?: Record<string, any>): number {
  if (params?.project_id) {
    const pid = Number(params.project_id);
    delete params.project_id;
    return pid;
  }
  return useProjectStore().currentProjectId ?? 0;
}

function _normalizeListPayload(payload: any, fallbackTotal?: number): { results: any[]; count: number } {
  let current = payload;
  let countHint = fallbackTotal;

  for (let i = 0; i < 5; i += 1) {
    if (Array.isArray(current)) {
      return { results: current, count: countHint ?? current.length };
    }

    if (!current || typeof current !== 'object') {
      break;
    }

    if (typeof current.count === 'number') {
      countHint = current.count;
    }

    if (Array.isArray(current.results)) {
      return { results: current.results, count: countHint ?? current.results.length };
    }

    if (Array.isArray(current.data)) {
      return { results: current.data, count: countHint ?? current.data.length };
    }

    if (current.data && typeof current.data === 'object' && current.data !== current) {
      current = current.data;
      continue;
    }

    if (current.results && typeof current.results === 'object' && current.results !== current) {
      current = current.results;
      continue;
    }

    break;
  }

  return { results: [], count: countHint ?? 0 };
}

function _wrapList(res: any): any {
  return wrapListResponse(res);
}

function _wrapOne(res: any): any {
  return wrapOneResponse(res);
}

export async function getModules(params: Record<string, any> = {}) {
  const pid = _pid(params);
  return _wrapList(await moduleService.list(pid, params));
}

export async function getModuleTree(projectId?: number) {
  const pid = projectId ?? (useProjectStore().currentProjectId ?? 0);
  return _wrapList(await moduleService.tree(pid));
}

export async function getModuleById(id: number) {
  return _wrapOne(await moduleService.get(_pid(), id));
}

export async function createModule(data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await moduleService.create(pid, data));
}

export async function updateModule(id: number, data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await moduleService.update(pid, id, data));
}

export async function deleteModule(id: number) {
  return _wrapOne(await moduleService.delete(_pid(), id));
}

export async function moveModule(id: number, data: { target_id: number | null; drop_position: number }) {
  return _wrapOne(await moduleService.move(_pid(), id, data));
}

export type { ApiModule };
