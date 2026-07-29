import { request } from '@/utils/request'
import { useProjectStore } from '@/store/projectStore'
import type { PaginatedResponse } from '../types/common'
import type { ApiInterfaceCase, ApiInterfaceCaseReport } from '../types/interfaceCase'

const base = (projectId: number) => `/projects/${projectId}/api-interface-cases`
const reportBase = (projectId: number) => `/projects/${projectId}/api-interface-case-reports`

export const interfaceCaseService = {
  list: (projectId: number, params?: Record<string, any>) =>
    request<ApiInterfaceCase[] | PaginatedResponse<ApiInterfaceCase>>({
      url: `${base(projectId)}/`,
      method: 'GET',
      params
    }),

  get: (projectId: number, id: number) =>
    request<ApiInterfaceCase>({ url: `${base(projectId)}/${id}/`, method: 'GET' }),

  create: (projectId: number, data: Partial<ApiInterfaceCase> & Record<string, any>) =>
    request<ApiInterfaceCase>({ url: `${base(projectId)}/`, method: 'POST', data }),

  update: (projectId: number, id: number, data: Partial<ApiInterfaceCase> & Record<string, any>) =>
    request<ApiInterfaceCase>({ url: `${base(projectId)}/${id}/`, method: 'PUT', data }),

  delete: (projectId: number, id: number) =>
    request<void>({ url: `${base(projectId)}/${id}/`, method: 'DELETE' }),

  copy: (projectId: number, id: number, data?: { name?: string }) =>
    request<ApiInterfaceCase>({ url: `${base(projectId)}/${id}/copy/`, method: 'POST', data }),

  run: (projectId: number, id: number, data?: { environment_id?: number }) =>
    request<any>({ url: `${base(projectId)}/${id}/run/`, method: 'POST', data }),

  historyReports: (projectId: number, id: number, params?: Record<string, any>) =>
    request<ApiInterfaceCaseReport[] | PaginatedResponse<ApiInterfaceCaseReport>>({
      url: `${base(projectId)}/${id}/history_reports/`,
      method: 'GET',
      params
    }),
}

export const interfaceCaseReportService = {
  list: (projectId: number, params?: Record<string, any>) =>
    request<ApiInterfaceCaseReport[] | PaginatedResponse<ApiInterfaceCaseReport>>({
      url: `${reportBase(projectId)}/`,
      method: 'GET',
      params
    }),

  get: (projectId: number, id: number) =>
    request<ApiInterfaceCaseReport>({ url: `${reportBase(projectId)}/${id}/`, method: 'GET' }),
}

function currentProjectId() {
  return useProjectStore().currentProjectId ?? 0
}

export async function getInterfaceCases(params: Record<string, any> = {}) {
  const projectId = params.project ? Number(params.project) : currentProjectId()
  delete params.project
  return interfaceCaseService.list(projectId, params)
}

