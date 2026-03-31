import axios from 'axios';
import { API_BASE_URL } from '@/config/api';
import { useAuthStore } from '@/store/authStore';

// ===== 类型定义 =====

export type TaskStatus = 'disabled' | 'running' | 'executing';
export type ScheduleType = 'once' | 'hourly' | 'daily' | 'weekly';
export type TaskModule = 'ui_automation' | 'test_suite';
export type TriggerType = 'scheduled' | 'manual' | 'api';
export type ExecutionStatus = 'running' | 'success' | 'failed';

export interface ScheduledTask {
  id: number;
  name: string;
  description: string;
  project: number;
  module: TaskModule;
  execution_target: string;
  schedule_type: ScheduleType;
  once_datetime: string | null;
  daily_time: string | null;
  weekly_days: number[];
  weekly_time: string | null;
  hourly_minute: number | null;
  retry_enabled: boolean;
  retry_count: number;
  retry_interval: number;
  status: TaskStatus;
  last_run_at: string | null;
  creator: number | null;
  creator_name: string | null;
  schedule_display: string;
  test_suite: number | null;
  test_suite_name: string | null;
  ui_testcase_ids: number[];
  actuator_id: string;
  created_at: string;
  updated_at: string;
}

export interface TaskFormData {
  name: string;
  description: string;
  module: TaskModule;
  execution_target: string;
  schedule_type: ScheduleType;
  once_datetime?: string | null;
  daily_time?: string | null;
  weekly_days?: number[];
  weekly_time?: string | null;
  hourly_minute?: number | null;
  retry_enabled: boolean;
  retry_count: number;
  retry_interval: number;
  test_suite?: number | null;
  ui_testcase_ids?: number[];
  actuator_id?: string;
}

export interface TaskExecution {
  id: number;
  execution_id: string;
  task: number;
  trigger_type: TriggerType;
  status: ExecutionStatus;
  started_at: string;
  finished_at: string | null;
  duration: string;
  log: string;
  error_message: string;
}

interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ===== API 辅助 =====

function getHeaders() {
  const authStore = useAuthStore();
  return { Authorization: `Bearer ${authStore.getAccessToken}` };
}

function baseUrl(projectId: number) {
  return `${API_BASE_URL}/projects/${projectId}/scheduled-tasks`;
}

/** 从后端标准响应中提取数据 { status, data, ... } */
function extractData(responseData: any): any {
  if (responseData?.status === 'success') {
    return responseData.data;
  }
  return responseData;
}

/** 将后端返回数据转换为统一的分页结构 */
function toPaginated<T>(responseData: any): PaginatedResponse<T> {
  const data = extractData(responseData);
  if (Array.isArray(data)) {
    return { count: data.length, next: null, previous: null, results: data };
  }
  if (data?.results) {
    return { count: data.count, next: data.next, previous: data.previous, results: data.results };
  }
  return { count: 0, next: null, previous: null, results: [] };
}

// ===== 任务 CRUD =====

export async function getTaskList(
  projectId: number,
  params?: { status?: string; module?: string; search?: string; page?: number }
): Promise<PaginatedResponse<ScheduledTask>> {
  const response = await axios.get(`${baseUrl(projectId)}/`, {
    headers: getHeaders(),
    params,
  });
  return toPaginated<ScheduledTask>(response.data);
}

export async function getTaskDetail(projectId: number, taskId: number): Promise<ScheduledTask> {
  const response = await axios.get(`${baseUrl(projectId)}/${taskId}/`, {
    headers: getHeaders(),
  });
  return extractData(response.data);
}

export async function createTask(projectId: number, data: TaskFormData): Promise<ScheduledTask> {
  const response = await axios.post(`${baseUrl(projectId)}/`, data, {
    headers: getHeaders(),
  });
  return extractData(response.data);
}

export async function updateTask(projectId: number, taskId: number, data: Partial<TaskFormData>): Promise<ScheduledTask> {
  const response = await axios.patch(`${baseUrl(projectId)}/${taskId}/`, data, {
    headers: getHeaders(),
  });
  return extractData(response.data);
}

export async function deleteTask(projectId: number, taskId: number): Promise<void> {
  await axios.delete(`${baseUrl(projectId)}/${taskId}/`, {
    headers: getHeaders(),
  });
}

// ===== 任务操作 =====

export async function enableTask(projectId: number, taskId: number): Promise<ScheduledTask> {
  const response = await axios.post(`${baseUrl(projectId)}/${taskId}/enable/`, {}, {
    headers: getHeaders(),
  });
  return extractData(response.data);
}

export async function disableTask(projectId: number, taskId: number): Promise<ScheduledTask> {
  const response = await axios.post(`${baseUrl(projectId)}/${taskId}/disable/`, {}, {
    headers: getHeaders(),
  });
  return extractData(response.data);
}

export async function runTaskNow(projectId: number, taskId: number): Promise<{ message: string; celery_task_id: string }> {
  const response = await axios.post(`${baseUrl(projectId)}/${taskId}/run-now/`, {}, {
    headers: getHeaders(),
  });
  return extractData(response.data);
}

export async function pauseTask(projectId: number, taskId: number): Promise<ScheduledTask> {
  const response = await axios.post(`${baseUrl(projectId)}/${taskId}/pause/`, {}, {
    headers: getHeaders(),
  });
  return extractData(response.data);
}

// ===== 执行记录 =====

export async function getTaskExecutions(
  projectId: number,
  taskId: number,
  params?: { page?: number }
): Promise<PaginatedResponse<TaskExecution>> {
  const response = await axios.get(`${baseUrl(projectId)}/${taskId}/executions/`, {
    headers: getHeaders(),
    params,
  });
  return toPaginated<TaskExecution>(response.data);
}

export async function getExecutionLog(
  projectId: number,
  executionId: number
): Promise<{ execution_id: string; log: string; error_message: string; status: string; duration: string }> {
  const response = await axios.get(
    `${API_BASE_URL}/projects/${projectId}/task-executions/${executionId}/log/`,
    { headers: getHeaders() }
  );
  return extractData(response.data);
}

export async function deleteExecution(projectId: number, executionId: number): Promise<void> {
  await axios.delete(
    `${API_BASE_URL}/projects/${projectId}/task-executions/${executionId}/remove/`,
    { headers: getHeaders() }
  );
}
