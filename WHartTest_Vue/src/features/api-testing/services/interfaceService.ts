import axiosInstance, { request } from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import type { ApiInterface } from '../types/interface';
import type { ApiModule } from '../types/module';

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

  patch: (projectId: number, id: number, data: Partial<ApiInterface>) =>
    request<ApiInterface>({ url: `${base(projectId)}/${id}/`, method: 'PATCH', data }),

  delete: (projectId: number, id: number) =>
    request<void>({ url: `${base(projectId)}/${id}/`, method: 'DELETE' }),

  batchDelete: (projectId: number, ids: number[]) =>
    request<{ message?: string; deleted_count?: number; deleted_ids?: number[] }>({
      url: `${base(projectId)}/batch-delete/`,
      method: 'POST',
      data: { ids },
    }),

  duplicate: (projectId: number, id: number, data?: { name?: string }) =>
    request<ApiInterface>({ url: `${base(projectId)}/${id}/duplicate/`, method: 'POST', data }),

  run: (projectId: number, id: number, data?: { environment_id?: number }) =>
    request<any>({ url: `${base(projectId)}/${id}/run/`, method: 'POST', data }),

  quickDebug: (projectId: number, data: Record<string, any>) =>
    request<any>({ url: `${base(projectId)}/quick_debug/`, method: 'POST', data }),

  importOpenApi: (projectId: number, data: FormData) =>
    request<OpenApiImportResult>({ url: `${base(projectId)}/import-openapi/`, method: 'POST', data }),
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
export type ApiDocumentExportFormat = 'json' | 'yaml' | 'apifox' | 'apipost' | 'yapi';
export type OpenApiExportFormat = ApiDocumentExportFormat;
export type ApiDocumentImportType =
  | 'swagger'
  | 'postman'
  | 'curl'
  | 'markdown'
  | 'har'
  | 'insomnia'
  | 'apidoc'
  | 'apifox'
  | 'apipost'
  | 'yapi'
  | 'apizza'
  | 'eolink';

export type OpenApiImportResult = {
  format: 'openapi' | ApiDocumentImportType;
  version?: string;
  created_count: number;
  updated_count: number;
  imported_count: number;
  skipped_count: number;
  skipped?: Array<{ method?: string; path?: string; reason?: string }>;
  imported_ids: number[];
  module_count: number;
  created_environments?: Array<{ id: number; name: string; base_url: string }>;
};

export type OpenApiExportResult = {
  blob: Blob;
  filename: string;
};

function _wrapList(res: any): any {
  if (!res.success) {
    const err: any = new Error(res.error || res.message || '操作失败');
    err.errors = res.errors;
    throw err;
  }
  const payload = res.data;
  let results: any[];
  let count: number;
  if (Array.isArray(payload)) {
    results = payload;
    count = res.total ?? payload.length;
  } else if (payload && typeof payload === 'object' && Array.isArray(payload.results)) {
    results = payload.results;
    count = payload.count ?? res.total ?? results.length;
  } else {
    results = [];
    count = res.total ?? 0;
  }
  return { data: { results, count }, status: 'success', message: '' };
}

function _wrapOne(res: any): any {
  if (!res.success) {
    const err: any = new Error(res.error || res.message || '操作失败');
    err.errors = res.errors;
    throw err;
  }
  return { data: res.data ?? null, status: 'success', message: '' };
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

export async function patchInterface(id: number, data: any) {
  const pid = data.project ? Number(data.project) : (useProjectStore().currentProjectId ?? 0);
  delete data.project;
  return _wrapOne(await interfaceService.patch(pid, id, data));
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

export async function batchDeleteInterfaces(ids: number[]) {
  const pid = useProjectStore().currentProjectId ?? 0;
  return _wrapOne(await interfaceService.batchDelete(pid, ids));
}


export async function duplicateInterface(id: number, data?: { name?: string }) {
  const pid = useProjectStore().currentProjectId ?? 0;
  return _wrapOne(await interfaceService.duplicate(pid, id, data));
}

export async function importApiDocument(
  file: File,
  sourceType?: ApiDocumentImportType,
  options?: { strip_base_url?: boolean; create_environments?: boolean },
) {
  const pid = useProjectStore().currentProjectId ?? 0;
  const formData = new FormData();
  formData.append('file', file);
  if (sourceType) formData.append('source_type', sourceType);
  if (options?.strip_base_url !== undefined) {
    formData.append('strip_base_url', String(options.strip_base_url));
  }
  if (options?.create_environments !== undefined) {
    formData.append('create_environments', String(options.create_environments));
  }
  return _wrapOne(await interfaceService.importOpenApi(pid, formData));
}

export async function importApiDocumentText(
  sourceType: 'curl' | 'swagger',
  value: string,
) {
  const pid = useProjectStore().currentProjectId ?? 0;
  const data = sourceType === 'swagger'
    ? { source_type: sourceType, source_url: value }
    : { source_type: sourceType, content: value };
  return _wrapOne(await interfaceService.importOpenApi(pid, data as any));
}

export async function exportApiDocument(format: ApiDocumentExportFormat = 'json'): Promise<OpenApiExportResult> {
  const pid = useProjectStore().currentProjectId ?? 0;
  const response = await axiosInstance({
    url: `${base(pid)}/export-openapi/`,
    method: 'GET',
    params: { export_format: format },
    responseType: 'blob',
  });
  const responseData = response.data as any;
  const payload = responseData?.data ?? responseData;
  const blob = payload instanceof Blob ? payload : new Blob([payload]);
  return {
    blob,
    filename: parseDownloadFilename(response.headers?.['content-disposition']) || defaultExportFilename(format),
  };
}

export const importOpenApiDocument = importApiDocument;
export const exportOpenApiDocument = exportApiDocument;

function defaultExportFilename(format: ApiDocumentExportFormat): string {
  if (format === 'yaml') return 'openapi.yaml';
  if (format === 'json') return 'openapi.json';
  return `${format}.json`;
}

function parseDownloadFilename(contentDisposition?: string): string {
  if (!contentDisposition) return '';

  const encodedMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch?.[1]) {
    try {
      return decodeURIComponent(encodedMatch[1]);
    } catch {
      return encodedMatch[1];
    }
  }

  const plainMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] || '';
}
