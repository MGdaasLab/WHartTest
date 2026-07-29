import { request } from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import type { ApiTestReport, ApiTestReportDetail } from '../types/testcase';
import { wrapListResponse, wrapOneResponse } from './responseHelpers';
import type { ApiInterfaceCaseReport } from '../types/interfaceCase';
import { interfaceCaseReportService } from './interfaceCaseService';

const base = (projectId: number) => `/projects/${projectId}/api-test-reports`;

export const testReportService = {
  list: (projectId: number, params?: Record<string, any>) =>
    request<ApiTestReport[]>({ url: `${base(projectId)}/`, method: 'GET', params }),

  get: (projectId: number, id: number) =>
    request<ApiTestReport & { details: ApiTestReportDetail[] }>({
      url: `${base(projectId)}/${id}/`, method: 'GET',
    }),
};

// ---------------------------------------------------------------------------
// Compatibility exports
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

type ReportType = 'testcase' | 'interface_case';
type ReportListItem = (ApiTestReport | ApiInterfaceCaseReport) & {
  report_type: ReportType;
  report_type_label: string;
};

function _normalizeList(res: any): { results: any[]; count: number } {
  if (!res.success) {
    const err: any = new Error(res.error || res.message || '操作失败');
    err.errors = res.errors;
    throw err;
  }

  const payload = res.data;
  if (Array.isArray(payload)) {
    return { results: payload, count: res.total ?? payload.length };
  }
  if (payload && typeof payload === 'object' && Array.isArray(payload.results)) {
    return { results: payload.results, count: payload.count ?? res.total ?? payload.results.length };
  }
  return { results: [], count: res.total ?? 0 };
}

function _withReportType(report: any, reportType: ReportType): ReportListItem {
  return {
    ...report,
    report_type: reportType,
    report_type_label: reportType === 'interface_case' ? '接口用例' : '场景用例',
  };
}

function _sortReports(reports: ReportListItem[], ordering = '-start_time') {
  const desc = ordering.startsWith('-');
  const field = desc ? ordering.slice(1) : ordering;
  const supportedFields = new Set(['start_time', 'duration', 'success_count', 'fail_count', 'error_count']);
  const sortField = supportedFields.has(field) ? field : 'start_time';

  return [...reports].sort((a, b) => {
    const aValue = sortField === 'start_time'
      ? new Date(a.start_time || 0).getTime()
      : Number((a as any)[sortField] || 0);
    const bValue = sortField === 'start_time'
      ? new Date(b.start_time || 0).getTime()
      : Number((b as any)[sortField] || 0);

    const safeA = Number.isFinite(aValue) ? aValue : 0;
    const safeB = Number.isFinite(bValue) ? bValue : 0;
    if (safeA !== safeB) {
      return desc ? safeB - safeA : safeA - safeB;
    }
    return Number(b.id || 0) - Number(a.id || 0);
  });
}

// Type alias
export type TestReportDetail = ApiTestReport & { details: ApiTestReportDetail[] } & Record<string, any>;
export type { ReportListItem, ReportType };

export async function getTestReports(params: Record<string, any> = {}) {
  const query = { ...params };
  const pid = _pid(query);
  const reportType = query.report_type as ReportType | undefined;
  delete query.report_type;

  if (reportType === 'testcase') {
    const { results, count } = _normalizeList(await testReportService.list(pid, query));
    return {
      data: { results: results.map((item) => _withReportType(item, 'testcase')), count },
      status: 'success',
      message: ''
    };
  }

  if (reportType === 'interface_case') {
    const { results, count } = _normalizeList(await interfaceCaseReportService.list(pid, query));
    return {
      data: { results: results.map((item) => _withReportType(item, 'interface_case')), count },
      status: 'success',
      message: ''
    };
  }

  const page = Math.max(1, Number(query.page) || 1);
  const pageSize = Math.max(1, Number(query.page_size) || 10);
  const mergedPageSize = page * pageSize;
  const mergedQuery = {
    ...query,
    page: 1,
    page_size: mergedPageSize
  };

  const [testcaseReportsRes, interfaceCaseReportsRes] = await Promise.all([
    testReportService.list(pid, mergedQuery),
    interfaceCaseReportService.list(pid, mergedQuery),
  ]);

  const testcaseReports = _normalizeList(testcaseReportsRes);
  const interfaceCaseReports = _normalizeList(interfaceCaseReportsRes);
  const mergedReports = _sortReports([
    ...testcaseReports.results.map((item) => _withReportType(item, 'testcase')),
    ...interfaceCaseReports.results.map((item) => _withReportType(item, 'interface_case')),
  ], String(query.ordering || '-start_time'));
  const start = (page - 1) * pageSize;
  const end = start + pageSize;

  return {
    data: {
      results: mergedReports.slice(start, end),
      count: testcaseReports.count + interfaceCaseReports.count
    },
    status: 'success',
    message: ''
  };
}

export async function getTestReportDetail(id: number) {
  const pid = useProjectStore().currentProjectId ?? 0;
  return _wrapOne(await testReportService.get(pid, id));
}
