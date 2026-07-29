/**
 * UI 自动化 API 服务
 */

import request from '@/utils/request'
import type {
  UiModule,
  UiPage,
  UiPageDetail,
  UiElement,
  UiPageSteps,
  UiPageStepsDetail,
  UiPageStepsDetailed,
  UiTestCase,
  UiTestCaseDetail,
  UiCaseStepsDetailed,
  UiExecutionRecord,
  UiBatchExecutionRecord,
  UiPublicData,
  UiEnvironmentConfig,
  UiModuleForm,
  UiPageForm,
  UiElementForm,
  UiPageStepsForm,
  UiTestCaseForm,
  UiPublicDataForm,
  UiEnvironmentConfigForm,
  PaginatedResponse,
  TraceData,
} from '../types'

const BASE_URL = '/ui-automation'

// ==================== 模块管理 ====================
export const moduleApi = {
  list: (params?: { project?: number; parent?: number }) =>
    request.get<PaginatedResponse<UiModule>>(`${BASE_URL}/modules/`, { params }),

  tree: (projectId: number) =>
    request.get<UiModule[]>(`${BASE_URL}/modules/tree/`, { params: { project: projectId } }),

  get: (id: number) => request.get<UiModule>(`${BASE_URL}/modules/${id}/`),

  create: (data: UiModuleForm) => request.post<UiModule>(`${BASE_URL}/modules/`, data),

  update: (id: number, data: Partial<UiModuleForm>) =>
    request.patch<UiModule>(`${BASE_URL}/modules/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/modules/${id}/`),

  move: (id: number, data: { target_id: number | null; drop_position: number }) =>
    request.post<UiModule>(`${BASE_URL}/modules/${id}/move/`, data),
}

// ==================== 页面管理 ====================
export const pageApi = {
  list: (params?: { project?: number; module?: number; search?: string }) =>
    request.get<PaginatedResponse<UiPage>>(`${BASE_URL}/pages/`, { params }),

  get: (id: number) => request.get<UiPageDetail>(`${BASE_URL}/pages/${id}/`),

  create: (data: UiPageForm) => request.post<UiPage>(`${BASE_URL}/pages/`, data),

  update: (id: number, data: Partial<UiPageForm>) =>
    request.patch<UiPage>(`${BASE_URL}/pages/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/pages/${id}/`),

  copy: (id: number, data?: { name?: string; target_module_id?: number; module?: number }) =>
    request.post<UiPage>(`${BASE_URL}/pages/${id}/copy/`, data || {}),
}

// ==================== 元素管理 ====================
export const elementApi = {
  list: (params?: { page?: number; locator_type?: string; search?: string }) =>
    request.get<PaginatedResponse<UiElement>>(`${BASE_URL}/elements/`, { params }),

  get: (id: number) => request.get<UiElement>(`${BASE_URL}/elements/${id}/`),

  create: (data: UiElementForm) => request.post<UiElement>(`${BASE_URL}/elements/`, data),

  update: (id: number, data: Partial<UiElementForm>) =>
    request.patch<UiElement>(`${BASE_URL}/elements/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/elements/${id}/`),
}

// ==================== 页面步骤管理 ====================
export const pageStepsApi = {
  list: (params?: { project?: number; page?: number; module?: number; search?: string }) =>
    request.get<PaginatedResponse<UiPageSteps>>(`${BASE_URL}/page-steps/`, { params }),

  get: (id: number) => request.get<UiPageStepsDetail>(`${BASE_URL}/page-steps/${id}/`),

  create: (data: UiPageStepsForm) => request.post<UiPageSteps>(`${BASE_URL}/page-steps/`, data),

  update: (id: number, data: Partial<UiPageStepsForm>) =>
    request.patch<UiPageSteps>(`${BASE_URL}/page-steps/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/page-steps/${id}/`),

  copy: (id: number, data?: { name?: string; target_page_id?: number; page?: number }) =>
    request.post<UiPageSteps>(`${BASE_URL}/page-steps/${id}/copy/`, data || {}),
}

// ==================== 步骤详情管理 ====================
export const pageStepsDetailedApi = {
  list: (params?: { page_step?: number; step_type?: number }) =>
    request.get<PaginatedResponse<UiPageStepsDetailed>>(`${BASE_URL}/page-steps-detailed/`, { params }),

  get: (id: number) => request.get<UiPageStepsDetailed>(`${BASE_URL}/page-steps-detailed/${id}/`),

  create: (data: Omit<UiPageStepsDetailed, 'id' | 'created_at' | 'updated_at'>) =>
    request.post<UiPageStepsDetailed>(`${BASE_URL}/page-steps-detailed/`, data),

  update: (id: number, data: Partial<UiPageStepsDetailed>) =>
    request.patch<UiPageStepsDetailed>(`${BASE_URL}/page-steps-detailed/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/page-steps-detailed/${id}/`),

  batchUpdate: (pageStepId: number, steps: Omit<UiPageStepsDetailed, 'id' | 'page_step' | 'created_at' | 'updated_at'>[]) =>
    request.post(`${BASE_URL}/page-steps-detailed/batch_update/`, { page_step: pageStepId, steps }),
}

// ==================== 测试用例管理 ====================
export const testCaseApi = {
  list: (params?: { project?: number; module?: number; level?: string; status?: number; search?: string }) =>
    request.get<PaginatedResponse<UiTestCase>>(`${BASE_URL}/testcases/`, { params }),

  get: (id: number) => request.get<UiTestCaseDetail>(`${BASE_URL}/testcases/${id}/`),

  create: (data: UiTestCaseForm) => request.post<UiTestCase>(`${BASE_URL}/testcases/`, data),

  update: (id: number, data: Partial<UiTestCaseForm>) =>
    request.patch<UiTestCase>(`${BASE_URL}/testcases/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/testcases/${id}/`),

  batchDelete: (ids: number[]) => request.post(`${BASE_URL}/testcases/batch-delete/`, { ids }),

  copy: (id: number, data?: { name?: string; target_module_id?: number; module?: number }) =>
    request.post<UiTestCase>(`${BASE_URL}/testcases/${id}/copy/`, data || {}),
}

// ==================== 用例步骤管理 ====================
export const caseStepsApi = {
  list: (params?: { test_case?: number; status?: number }) =>
    request.get<PaginatedResponse<UiCaseStepsDetailed>>(`${BASE_URL}/case-steps/`, { params }),

  get: (id: number) => request.get<UiCaseStepsDetailed>(`${BASE_URL}/case-steps/${id}/`),

  create: (data: Omit<UiCaseStepsDetailed, 'id' | 'status' | 'error_message' | 'result_data' | 'created_at' | 'updated_at'>) =>
    request.post<UiCaseStepsDetailed>(`${BASE_URL}/case-steps/`, data),

  update: (id: number, data: Partial<UiCaseStepsDetailed>) =>
    request.patch<UiCaseStepsDetailed>(`${BASE_URL}/case-steps/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/case-steps/${id}/`),

  batchUpdate: (testCaseId: number, steps: Omit<UiCaseStepsDetailed, 'id' | 'test_case' | 'status' | 'error_message' | 'result_data' | 'created_at' | 'updated_at'>[]) =>
    request.post(`${BASE_URL}/case-steps/batch_update/`, { test_case: testCaseId, steps }),
}

// ==================== 执行记录管理 ====================
export const executionRecordApi = {
  list: (params?: { project?: number; test_case?: number; status?: number; trigger_type?: string }) =>
    request.get<PaginatedResponse<UiExecutionRecord>>(`${BASE_URL}/execution-records/`, { params }),

  get: (id: number) => request.get<UiExecutionRecord>(`${BASE_URL}/execution-records/${id}/`),

  create: (data: Partial<UiExecutionRecord>) =>
    request.post<UiExecutionRecord>(`${BASE_URL}/execution-records/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/execution-records/${id}/`),

  /** 获取执行记录的 Trace 数据 */
  getTrace: (id: number, refresh?: boolean) =>
    request.get<TraceData>(`${BASE_URL}/execution-records/${id}/trace/`, { params: refresh ? { refresh: '1' } : {} }),
}

// ==================== 批量执行记录管理 ====================
export const batchRecordApi = {
  list: (params?: { project?: number; status?: number; trigger_type?: string }) =>
    request.get<PaginatedResponse<UiBatchExecutionRecord>>(`${BASE_URL}/batch-records/`, { params }),

  get: (id: number) => request.get<UiBatchExecutionRecord>(`${BASE_URL}/batch-records/${id}/`),

  delete: (id: number) => request.delete(`${BASE_URL}/batch-records/${id}/`),
}

// ==================== 公共数据管理 ====================
export const publicDataApi = {
  list: (params?: { project?: number; type?: number; is_enabled?: boolean; search?: string }) =>
    request.get<PaginatedResponse<UiPublicData>>(`${BASE_URL}/public-data/`, { params }),

  get: (id: number) => request.get<UiPublicData>(`${BASE_URL}/public-data/${id}/`),

  create: (data: UiPublicDataForm) => request.post<UiPublicData>(`${BASE_URL}/public-data/`, data),

  update: (id: number, data: Partial<UiPublicDataForm>) =>
    request.patch<UiPublicData>(`${BASE_URL}/public-data/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/public-data/${id}/`),
}

// ==================== 环境配置管理 ====================
export const envConfigApi = {
  list: (params?: { project?: number; browser?: string; is_default?: boolean; search?: string }) =>
    request.get<PaginatedResponse<UiEnvironmentConfig>>(`${BASE_URL}/env-configs/`, { params }),

  get: (id: number) => request.get<UiEnvironmentConfig>(`${BASE_URL}/env-configs/${id}/`),

  create: (data: UiEnvironmentConfigForm) =>
    request.post<UiEnvironmentConfig>(`${BASE_URL}/env-configs/`, data),

  update: (id: number, data: Partial<UiEnvironmentConfigForm>) =>
    request.patch<UiEnvironmentConfig>(`${BASE_URL}/env-configs/${id}/`, data),

  delete: (id: number) => request.delete(`${BASE_URL}/env-configs/${id}/`),
}

// ==================== 执行器管理 ====================
export interface ActuatorInfo {
  id: string
  name: string
  ip: string
  type: string
  is_open: boolean
  debug: boolean
  browser_type: string
  headless: boolean
  connected_at: string
}

export interface ActuatorStatus {
  total_actuators: number
  has_available: boolean
  web_users: number
}

export const actuatorApi = {
  list: () =>
    request.get<{ count: number; items: ActuatorInfo[] }>(`${BASE_URL}/actuators/list_actuators/`),

  status: () => request.get<ActuatorStatus>(`${BASE_URL}/actuators/status/`),
}


export { fileService as uiFileService } from '@/features/file-management/services/fileService'
