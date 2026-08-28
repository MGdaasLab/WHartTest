import { request } from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import type { ApiEnvironment, ApiEnvironmentVariable, EnvironmentVariableType } from '../types/environment';
import { environmentVariableService } from './environmentVariableService';
import { wrapListResponse, wrapOneResponse } from './responseHelpers';

const base = (projectId: number) => `/projects/${projectId}/api-environments`;

export const environmentService = {
  list: (projectId: number, params?: Record<string, any>) =>
    request<ApiEnvironment[]>({ url: `${base(projectId)}/`, method: 'GET', params }),

  get: (projectId: number, id: number) =>
    request<ApiEnvironment>({ url: `${base(projectId)}/${id}/`, method: 'GET' }),

  create: (projectId: number, data: Partial<ApiEnvironment>) =>
    request<ApiEnvironment>({ url: `${base(projectId)}/`, method: 'POST', data }),

  update: (projectId: number, id: number, data: Partial<ApiEnvironment>) =>
    request<ApiEnvironment>({ url: `${base(projectId)}/${id}/`, method: 'PUT', data }),

  patch: (projectId: number, id: number, data: Partial<ApiEnvironment>) =>
    request<ApiEnvironment>({ url: `${base(projectId)}/${id}/`, method: 'PATCH', data }),

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
export type Environment = Partial<ApiEnvironment> & Record<string, any>;
export type EnvironmentVariable = Partial<ApiEnvironmentVariable> & Record<string, any>;
export type VariableType = EnvironmentVariableType;
export type NewEnvironmentVariableData = {
  name: string;
  value: string;
  type: VariableType;
  description?: string;
  is_sensitive?: boolean;
  [key: string]: any;
};
export type CreateEnvironmentVariableData = NewEnvironmentVariableData & { environment_id?: number; environment?: number };

export const VARIABLE_TYPES: { label: string; value: VariableType }[] = [
  { label: 'String', value: 'string' },
  { label: 'Integer', value: 'integer' },
  { label: 'Float', value: 'float' },
  { label: 'Boolean', value: 'boolean' },
  { label: 'JSON', value: 'json' },
  { label: 'List', value: 'list' },
  { label: 'Dict', value: 'dict' },
];

// --- Environments ---
export async function getEnvironments(params: Record<string, any> = {}) {
  const pid = params.project_id ? Number(params.project_id) : _pid();
  delete params.project_id;
  return _wrapList(await environmentService.list(pid, params));
}

export async function getEnvironmentDetail(id: number) {
  return _wrapOne(await environmentService.get(_pid(), id));
}

export async function createEnvironment(data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await environmentService.create(pid, data));
}

export async function updateEnvironment(id: number, data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await environmentService.update(pid, id, data));
}

export async function deleteEnvironment(id: number) {
  return _wrapOne(await environmentService.delete(_pid(), id));
}

export async function cloneEnvironment(id: number, data?: Record<string, any>) {
  const pid = _pid();
  const original = await environmentService.get(pid, id);
  if (!original.success || !original.data) throw new Error('Failed to fetch environment');
  const cloneData = { ...original.data, ...data, name: data?.name ?? `${original.data.name} - 副本` };
  delete (cloneData as any).id;
  delete (cloneData as any).created_by;
  delete (cloneData as any).created_at;
  delete (cloneData as any).updated_at;
  return _wrapOne(await environmentService.create(pid, cloneData));
}

// --- Environment Variables ---
export async function createEnvironmentVariable(data: any) {
  const pid = _pid();
  return _wrapOne(await environmentVariableService.create(pid, data));
}

export async function updateEnvironmentVariable(id: number, data: any) {
  const pid = _pid();
  return _wrapOne(await environmentVariableService.update(pid, id, data));
}

export async function deleteEnvironmentVariable(id: number) {
  const pid = _pid();
  return _wrapOne(await environmentVariableService.delete(pid, id));
}

export async function batchCreateVariables(data: { environment_id: number; variables: any[] }) {
  const pid = _pid();
  const results = [];
  for (const v of data.variables) {
    results.push(await environmentVariableService.create(pid, { ...v, environment: data.environment_id }));
  }
  return { status: 'success', data: results.map(r => r.data) };
}
