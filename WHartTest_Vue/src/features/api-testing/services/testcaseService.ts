import { request } from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import type { ApiTestCase, ApiTestCaseStep, ApiTestCaseTag } from '../types/testcase';
import type { TestCaseHistoryReport as _TestCaseHistoryReport, Tag as _Tag, TagStatistics as _TagStatistics } from '../types/testcase';
import type { PaginatedResponse } from '../types/common';
import { testcaseTagService } from './testcaseTagService';
import { wrapListResponse, wrapOneResponse } from './responseHelpers';

const base = (projectId: number) => `/projects/${projectId}/api-testcases`;

export const testcaseService = {
  list: (projectId: number, params?: Record<string, any>) =>
    request<ApiTestCase[]>({ url: `${base(projectId)}/`, method: 'GET', params }),

  get: (projectId: number, id: number) =>
    request<ApiTestCase>({ url: `${base(projectId)}/${id}/`, method: 'GET' }),

  create: (projectId: number, data: Partial<ApiTestCase>) =>
    request<ApiTestCase>({ url: `${base(projectId)}/`, method: 'POST', data }),

  update: (projectId: number, id: number, data: Partial<ApiTestCase>) =>
    request<ApiTestCase>({ url: `${base(projectId)}/${id}/`, method: 'PUT', data }),

  delete: (projectId: number, id: number) =>
    request<void>({ url: `${base(projectId)}/${id}/`, method: 'DELETE' }),

  copy: (projectId: number, id: number, data?: { name?: string }) =>
    request<ApiTestCase>({ url: `${base(projectId)}/${id}/copy/`, method: 'POST', data }),

  run: (projectId: number, id: number, data?: { environment_id?: number }) =>
    request<any>({ url: `${base(projectId)}/${id}/run/`, method: 'POST', data }),

  batchRun: (projectId: number, data: { testcase_ids: number[]; environment_id?: number }) =>
    request<any>({ url: `${base(projectId)}/batch_run/`, method: 'POST', data }),

  availableInterfaces: (projectId: number) =>
    request<any[]>({ url: `${base(projectId)}/available_interfaces/`, method: 'GET' }),

  referencedInterfaces: (projectId: number, id: number) =>
    request<any[]>({ url: `${base(projectId)}/${id}/referenced_interfaces/`, method: 'GET' }),

  historyReports: (projectId: number, id: number, params?: Record<string, any>) =>
    request<PaginatedResponse<_TestCaseHistoryReport> | _TestCaseHistoryReport[]>({
      url: `${base(projectId)}/${id}/history_reports/`,
      method: 'GET',
      params
    }),

  updateStep: (projectId: number, id: number, data: { step_id: number } & Partial<ApiTestCaseStep>) =>
    request<ApiTestCaseStep>({ url: `${base(projectId)}/${id}/update_step/`, method: 'PUT', data }),

  deleteStep: (projectId: number, id: number, stepId: number) =>
    request<void>({ url: `${base(projectId)}/${id}/delete_step/`, method: 'DELETE', params: { step_id: stepId } }),

  reorderSteps: (projectId: number, id: number, data: { steps?: Array<{ step_id: number; order: number }>; step_id?: number; new_order?: number }) =>
    request<void>({ url: `${base(projectId)}/${id}/reorder_steps/`, method: 'POST', data }),
};

// ---------------------------------------------------------------------------
// Compatibility exports: named functions matching component import names.
// Components call these with old-style signatures (single ID, params with
// `project` field, etc.) and expect old-style responses ({ data: { results,
// count }, status: 'success' }).
// ---------------------------------------------------------------------------

function _pid(params?: Record<string, any>): number {
  if (params?.project) {
    const pid = Number(params.project);
    delete params.project;
    return pid;
  }
  return useProjectStore().currentProjectId ?? 0;
}

function _wrapList(res: any): any {
  return wrapListResponse(res);
}

function _wrapOne(res: any): any {
  return wrapOneResponse(res);
}

// Type aliases re-exported for component imports
export type TestCase = Partial<ApiTestCase> & Record<string, any>;
export type TestCaseStep = Partial<ApiTestCaseStep> & Record<string, any>;
export type Tag = _Tag;
export type TestCaseHistoryReport = _TestCaseHistoryReport;
export type TestCaseQueryParams = {
  name?: string;
  description?: string;
  project?: number;
  priority?: string;
  group?: number;
  tags?: number[];
  ordering?: string;
  page?: number;
  page_size?: number;
};
export type CreateTestCaseData = {
  name: string;
  description?: string;
  project: number;
  priority?: string;
  group?: number;
  tags?: number[];
  config?: Record<string, any>;
  steps_info?: any[];
};
export type ReferencedInterface = {
  interface: {
    id: number;
    name: string;
    method: string;
    url: string;
    module: { id: number; name: string } | null;
    project: { id: number; name: string };
  };
  step: {
    id: number;
    name: string;
    order: number;
  };
};

// --- Test Cases ---
export async function getTestCases(params: Record<string, any> = {}) {
  const pid = _pid(params);
  return _wrapList(await testcaseService.list(pid, params));
}

export async function getTestCaseById(id: number) {
  return _wrapOne(await testcaseService.get(_pid(), id));
}

export async function createTestCase(data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await testcaseService.create(pid, data));
}

export async function updateTestCase(id: number, data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await testcaseService.update(pid, id, data));
}

export async function deleteTestCase(id: number) {
  return _wrapOne(await testcaseService.delete(_pid(), id));
}

export async function copyTestCase(id: number, data?: { name?: string }) {
  const pid = _pid();
  return _wrapOne(await testcaseService.copy(pid, id, data));
}

export async function runTestCase(id: number, data?: { environment?: number }) {
  const pid = _pid();
  return _wrapOne(await testcaseService.run(pid, id, data ? { environment_id: data.environment } : undefined));
}

export async function getTestCaseHistoryReports(testcaseId: number, params?: Record<string, any>) {
  const pid = _pid();
  const res = await testcaseService.historyReports(pid, testcaseId, params);
  return _wrapList(res);
}

// --- Steps ---
export async function addTestCaseSteps(testCaseId: number, data: any) {
  const pid = _pid();
  return _wrapOne(await testcaseService.update(pid, testCaseId, data));
}

export async function updateTestCaseStep(testCaseId: number, stepData: any) {
  const pid = _pid();
  return _wrapOne(await testcaseService.updateStep(pid, testCaseId, stepData));
}

export async function deleteTestCaseStep(testCaseId: number, stepId: number) {
  const pid = _pid();
  return _wrapOne(await testcaseService.deleteStep(pid, testCaseId, stepId));
}

export async function updateTestCaseStepOrder(testCaseId: number, data: { step_id: number; order: number }) {
  const pid = _pid();
  return _wrapOne(await testcaseService.reorderSteps(pid, testCaseId, { step_id: data.step_id, new_order: data.order }));
}

// --- Referenced Interfaces ---
export async function getTestCaseReferencedInterfaces(testcaseId: number) {
  const pid = _pid();
  const res = await testcaseService.referencedInterfaces(pid, testcaseId);
  if (!res.success) {
    const err: any = new Error(res.error || res.message || '操作失败');
    const errors = (res as any).errors;
    if (errors) {
      err.errors = errors;
    }
    throw err;
  }
  return { data: res.data ?? [], status: 'success' };
}

// --- Tags (compatibility wrapper around testcaseTagService) ---
export const tagApi = {
  getTags: async (params: Record<string, any> = {}) => {
    const pid = params.project_id ? Number(params.project_id) : _pid();
    delete params.project_id;
    const res = await testcaseTagService.list(pid, params);
    return res.data ?? [];
  },
  createTag: async (data: any) => {
    const pid = data.project ? Number(data.project) : _pid();
    delete data.project;
    const res = await testcaseTagService.create(pid, data);
    return res.data;
  },
  updateTag: async (id: number, data: any) => {
    const pid = data.project ? Number(data.project) : _pid();
    delete data.project;
    const res = await testcaseTagService.update(pid, id, data);
    return res.data;
  },
  deleteTag: async (id: number) => {
    const pid = _pid();
    await testcaseTagService.delete(pid, id);
  },
  getTagStatistics: async (projectId: number) => {
    const res = await testcaseTagService.statistics(projectId);
    return res.data ?? [];
  },
};
