import { request } from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import type { ApiInterface } from '../types/interface';
import type { ApiModule } from '../types/module';
import { wrapListResponse, wrapOneResponse } from './responseHelpers';

const base = (projectId: number) => `/projects/${projectId}/api-interfaces`;

export const interfaceService = {
  list: (projectId: number, params?: Record<string, any>) =>
    request<ApiInterface[]>({ url: `${base(projectId)}/`, method: 'GET', params }),

  get: (projectId: number, id: number) =>
    request<ApiInterface>({ url: `${base(projectId)}/${id}/`, method: 'GET' }),

  create: (projectId: number, data: Partial<ApiInterface>) =>
    request<ApiInterface>({ url: `${base(projectId)}/`, method: 'POST', data }),

  update: (projectId: number, id: number, data: Partial<ApiInterface>) =>
    request<ApiInterface>({ url: `${base(projectId)}/${id}/`, method: 'PUT', data }),

  delete: (projectId: number, id: number) =>
    request<void>({ url: `${base(projectId)}/${id}/`, method: 'DELETE' }),

  duplicate: (projectId: number, id: number, data?: { name?: string }) =>
    request<ApiInterface>({ url: `${base(projectId)}/${id}/duplicate/`, method: 'POST', data }),

  run: (projectId: number, id: number, data?: { environment_id?: number }) =>
    request<any>({ url: `${base(projectId)}/${id}/run/`, method: 'POST', data }),

  quickDebug: (projectId: number, data: Record<string, any>) =>
    request<any>({ url: `${base(projectId)}/quick_debug/`, method: 'POST', data }),
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

// Type aliases re-exported for component imports
export type { ApiInterface, ApiModule };
export type PaginatedData<T> = { results: T[]; count: number };
export type KeyValuePair = { key: string; value: string; enabled?: boolean; description?: string; [k: string]: any };
export type ApiValidator = { comparator: string; check: string; expect: any; [k: string]: any };
export type DebugInterfaceRequest = Record<string, any>;
export type QuickDebugInterfaceRequest = Record<string, any>;

function _normalizeListPayload(payload: any, fallbackTotal?: number): PaginatedData<any> {
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

export async function getInterfaces(params: Record<string, any> = {}) {
  const pid = _pid(params);
  return _wrapList(await interfaceService.list(pid, params));
}

export async function createInterface(data: any) {
  const pid = data.project ? Number(data.project) : (useProjectStore().currentProjectId ?? 0);
  delete data.project;
  return _wrapOne(await interfaceService.create(pid, data));
}

export async function updateInterface(id: number, data: any) {
  const pid = data.project ? Number(data.project) : (useProjectStore().currentProjectId ?? 0);
  delete data.project;
  return _wrapOne(await interfaceService.update(pid, id, data));
}

export async function debugInterface(id: number, data?: any) {
  const pid = useProjectStore().currentProjectId ?? 0;
  return _wrapOne(await interfaceService.run(pid, id, data));
}

export async function quickDebugInterface(data?: any) {
  const pid = useProjectStore().currentProjectId ?? 0;
  return _wrapOne(await interfaceService.quickDebug(pid, data));
}

export async function getInterfaceById(id: number) {
  const pid = useProjectStore().currentProjectId ?? 0;
  return _wrapOne(await interfaceService.get(pid, id));
}

export async function deleteInterface(id: number) {
  const pid = useProjectStore().currentProjectId ?? 0;
  return _wrapOne(await interfaceService.delete(pid, id));
}


export async function duplicateInterface(id: number, data?: { name?: string }) {
  const pid = useProjectStore().currentProjectId ?? 0;
  return _wrapOne(await interfaceService.duplicate(pid, id, data));
}
