import type { UserBrief } from './common'
import type { ApiTestCaseGroup, ApiTestCaseTag, TestCasePriority, TestReportStatus } from './testcase'
import type { ApiInterface } from './interface'

export type InterfaceCaseStepRole = 'precondition' | 'main'

export interface ApiInterfaceCaseStep {
  id: number
  name: string
  role: InterfaceCaseStepRole
  order: number
  interface_info: {
    id: number
    name: string
    type?: string
    method: string | null
    url: string | null
    module: { id: number; name: string } | null
    project: { id: number; name: string } | null
    module_info?: { id: number; name: string } | null
  } | null
  interface_data: Record<string, any>
  config: Record<string, any>
  file_ids: number[]
  sync_fields: string[]
  last_sync_time: string | null
  [key: string]: any
}

export interface ApiInterfaceCase {
  id: number
  name: string
  description: string
  priority: TestCasePriority
  config: Record<string, any>
  file_ids: number[]
  project: number
  interface: number
  interface_info: Partial<ApiInterface> & {
    id: number
    name: string
    method?: string | null
    url?: string | null
    module?: { id: number; name: string } | null
  }
  group: number | null
  tags: number[] | ApiTestCaseTag[]
  tags_info?: ApiTestCaseTag[]
  group_info?: ApiTestCaseGroup | null
  created_by: UserBrief | null
  created_by_name?: string
  created_at: string
  updated_at: string
  steps?: ApiInterfaceCaseStep[]
  main_step?: ApiInterfaceCaseStep | null
  precondition_count?: number
}

export interface ApiInterfaceCaseReport {
  id: number
  name: string
  status: TestReportStatus
  success_count: number
  fail_count: number
  error_count: number
  duration: number
  start_time: string
  summary: Record<string, any>
  interface_case: number
  testcase: number
  testcase_name: string
  interface_name?: string
  environment: number | null
  environment_info?: Record<string, any> | null
  executed_by: UserBrief | null
  executed_by_info?: Record<string, any> | null
  details?: ApiInterfaceCaseReportDetail[]
  [key: string]: any
}

export interface ApiInterfaceCaseReportDetail {
  id: number
  step_name: string
  success: boolean
  elapsed: number
  request: Record<string, any>
  response: Record<string, any>
  validators: any[] | Record<string, any>
  extracted_variables: Record<string, any>
  attachment: string
  [key: string]: any
}

