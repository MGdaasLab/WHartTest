import type { UserBrief } from './common';

export type TaskSuitePriority = 'P0' | 'P1' | 'P2' | 'P3';
export type ApiTaskCaseType = 'scenario' | 'interface';

export interface ApiTestTaskSuite {
  id: number;
  name: string;
  description: string;
  priority: TaskSuitePriority;
  fail_fast: boolean;
  project: number;
  created_by: UserBrief | null;
  created_at: string;
  updated_at: string;
  [key: string]: any;
}

export interface ApiTestTaskCase {
  id: number;
  task_suite: number;
  case_type: ApiTaskCaseType;
  case_id: number;
  testcase: number | null;
  testcase_id?: number | null;
  interface_case_id?: number | null;
  testcase_name?: string;
  order: number;
  [key: string]: any;
}

export type TaskExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'canceled';

export interface ApiTestTaskExecution {
  id: number;
  task_suite: number;
  status: TaskExecutionStatus;
  environment: number | null;
  start_time: string | null;
  end_time: string | null;
  total_count: number;
  success_count: number;
  fail_count: number;
  error_count: number;
  executed_by: UserBrief | null;
  task_id: string;
  created_at: string;
  duration?: number;
  success_rate?: number;
  [key: string]: any;
}

export type CaseResultStatus = 'pending' | 'running' | 'success' | 'failure' | 'error' | 'skipped';

export interface ApiTestTaskCaseResult {
  id: number;
  case_type: ApiTaskCaseType;
  case_id: number;
  execution: number;
  testcase: number | null;
  interface_case?: number | null;
  report: Record<string, any> | null;
  status: CaseResultStatus;
  start_time: string | null;
  end_time: string | null;
  duration: number;
  error_message: string;
  [key: string]: any;
}
