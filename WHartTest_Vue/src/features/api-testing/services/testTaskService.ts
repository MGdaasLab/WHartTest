import { request } from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import type { ApiTestTaskSuite, ApiTestTaskExecution, ApiTestTaskCaseResult } from '../types/testtask';
import type { ApiTestCase } from '../types/testcase';
import { normalizeListPayload, wrapListResponse, wrapOneResponse } from './responseHelpers';
import type { ApiInterfaceCase } from '../types/interfaceCase';

const suiteBase = (projectId: number) => `/projects/${projectId}/api-task-suites`;
const execBase = (projectId: number) => `/projects/${projectId}/api-task-executions`;

export const testTaskService = {
  // --- Suites ---
  listSuites: (projectId: number, params?: Record<string, any>) =>
    request<ApiTestTaskSuite[]>({ url: `${suiteBase(projectId)}/`, method: 'GET', params }),

  getSuite: (projectId: number, id: number) =>
    request<ApiTestTaskSuite>({ url: `${suiteBase(projectId)}/${id}/`, method: 'GET' }),

  createSuite: (projectId: number, data: Partial<ApiTestTaskSuite>) =>
    request<ApiTestTaskSuite>({ url: `${suiteBase(projectId)}/`, method: 'POST', data }),

  updateSuite: (projectId: number, id: number, data: Partial<ApiTestTaskSuite>) =>
    request<ApiTestTaskSuite>({ url: `${suiteBase(projectId)}/${id}/`, method: 'PUT', data }),

  deleteSuite: (projectId: number, id: number) =>
    request<void>({ url: `${suiteBase(projectId)}/${id}/`, method: 'DELETE' }),

  addTestcases: (
    projectId: number,
    suiteId: number,
    data: { testcase_ids?: number[]; interface_case_ids?: number[] }
  ) =>
    request<void>({ url: `${suiteBase(projectId)}/${suiteId}/add-testcases/`, method: 'POST', data }),

  removeTestcase: (projectId: number, suiteId: number, testcaseId: number) =>
    request<void>({
      url: `${suiteBase(projectId)}/${suiteId}/remove-testcase/${testcaseId}/`, method: 'DELETE',
    }),

  removeCase: (projectId: number, suiteId: number, caseType: 'scenario' | 'interface', caseId: number) =>
    request<void>({
      url: `${suiteBase(projectId)}/${suiteId}/remove-case/${caseType}/${caseId}/`,
      method: 'DELETE',
    }),

  // --- Executions ---
  listExecutions: (projectId: number, params?: Record<string, any>) =>
    request<ApiTestTaskExecution[]>({ url: `${execBase(projectId)}/`, method: 'GET', params }),

  getExecution: (projectId: number, id: number) =>
    request<ApiTestTaskExecution>({ url: `${execBase(projectId)}/${id}/`, method: 'GET' }),

  createExecution: (projectId: number, data: { task_suite_id: number; environment_id?: number }) =>
    request<ApiTestTaskExecution>({ url: `${execBase(projectId)}/`, method: 'POST', data }),

  cancelExecution: (projectId: number, id: number) =>
    request<void>({ url: `${execBase(projectId)}/${id}/cancel/`, method: 'POST' }),

  caseResults: (projectId: number, executionId: number) =>
    request<ApiTestTaskCaseResult[]>({
      url: `${execBase(projectId)}/${executionId}/case-results/`, method: 'GET',
    }),
};

// ---------------------------------------------------------------------------
// Compatibility exports: named functions matching old TestRunner import names.
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

// Type aliases
export type TestTaskSuite = ApiTestTaskSuite & Record<string, any>;
export type TestTaskExecution = ApiTestTaskExecution & Record<string, any>;
export type TestCase = ApiTestCase & Record<string, any>;
export type InterfaceCase = ApiInterfaceCase & Record<string, any>;
export type TestTaskCaseType = 'scenario' | 'interface';
export type TestTaskSuiteForm = Partial<ApiTestTaskSuite> & {
  project?: number;
  test_cases?: number[];
  interface_cases?: number[];
};

// Suites
export async function getTestTaskSuites(params: Record<string, any> = {}) {
  const pid = _pid(params);
  return _wrapList(await testTaskService.listSuites(pid, params));
}

export async function getTestTaskSuite(id: number) {
  return _wrapOne(await testTaskService.getSuite(_pid(), id));
}

export async function createTestTaskSuite(data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await testTaskService.createSuite(pid, data));
}

export async function updateTestTaskSuite(id: number, data: any) {
  const pid = data.project ? Number(data.project) : _pid();
  delete data.project;
  return _wrapOne(await testTaskService.updateSuite(pid, id, data));
}

export async function deleteTestTaskSuite(id: number) {
  return _wrapOne(await testTaskService.deleteSuite(_pid(), id));
}

// Executions
export async function getTestTaskExecutions(params: Record<string, any> = {}) {
  const pid = _pid(params);
  return _wrapList(await testTaskService.listExecutions(pid, params));
}

export async function getTestTaskExecution(id: number) {
  return _wrapOne(await testTaskService.getExecution(_pid(), id));
}

export async function createTestTaskExecution(data: any) {
  const pid = _pid();
  return _wrapOne(await testTaskService.createExecution(pid, {
    task_suite_id: data.task_suite_id ?? data.task_suite,
    environment_id: data.environment_id ?? data.environment,
  }));
}

export async function cancelTestTaskExecution(id: number) {
  return _wrapOne(await testTaskService.cancelExecution(_pid(), id));
}

export async function getTestTaskExecutionCaseResults(id: number) {
  const res = await testTaskService.caseResults(_pid(), id);
  if (!res.success) {
    const err: any = new Error(res.error || res.message || '操作失败');
    const errors = (res as any).errors;
    if (errors) {
      err.errors = errors;
    }
    throw err;
  }
  return { data: normalizeListPayload(res.data, res.total).results, status: 'success' };
}

// Suite test-case management
export async function addCasesToSuite(
  suiteId: number,
  testcaseIds: number[] = [],
  interfaceCaseIds: number[] = []
) {
  return _wrapOne(await testTaskService.addTestcases(_pid(), suiteId, {
    testcase_ids: testcaseIds,
    interface_case_ids: interfaceCaseIds,
  }));
}

export async function addTestCaseToSuite(suiteId: number, testcaseIds: number[]) {
  return addCasesToSuite(suiteId, testcaseIds, []);
}

export async function removeCaseFromSuite(
  suiteId: number,
  caseType: TestTaskCaseType,
  caseId: number
) {
  return _wrapOne(await testTaskService.removeCase(_pid(), suiteId, caseType, caseId));
}

export async function removeTestCaseFromSuite(suiteId: number, testcaseId: number) {
  return _wrapOne(await testTaskService.removeTestcase(_pid(), suiteId, testcaseId));
}

// Test cases (fetched for task suite association)
export async function getTestCases(params: Record<string, any> = {}) {
  const pid = _pid(params);
  return _wrapList(await request<any>({ url: `/projects/${pid}/api-testcases/`, method: 'GET', params }));
}

export async function getInterfaceCasesForTask(params: Record<string, any> = {}) {
  const pid = _pid(params);
  return _wrapList(await request<any>({ url: `/projects/${pid}/api-interface-cases/`, method: 'GET', params }));
}
