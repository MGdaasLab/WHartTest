import type { UserBrief } from './common';

export type InterfaceType = 'http' | 'sql';
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
export type SqlMethod = 'fetchone' | 'fetchmany' | 'fetchall' | 'insert' | 'update' | 'delete';
export type ApiBodyType = 'none' | 'form-data' | 'x-www-form-urlencoded' | 'raw' | 'binary';
export type InterfaceStatus = 'self_testing' | 'integrating' | 'completed' | 'deprecated';

export const DEFAULT_INTERFACE_STATUS: InterfaceStatus = 'self_testing';

/** Single source of truth for interface lifecycle status (value/label/color). */
export const INTERFACE_STATUS_OPTIONS = [
  { value: 'self_testing', label: '自测中', color: 'orangered', buttonClass: 'status-self-testing' },
  { value: 'integrating', label: '联调中', color: 'arcoblue', buttonClass: 'status-integrating' },
  { value: 'completed', label: '已完成', color: 'green', buttonClass: 'status-completed' },
  { value: 'deprecated', label: '已废弃', color: 'gray', buttonClass: 'status-deprecated' },
] as const satisfies ReadonlyArray<{
  value: InterfaceStatus;
  label: string;
  color: string;
  buttonClass: string;
}>;

export type InterfaceStatusOption = (typeof INTERFACE_STATUS_OPTIONS)[number];

export function getInterfaceStatusMeta(status?: string | null): InterfaceStatusOption | {
  value: string;
  label: string;
  color: string;
  buttonClass: string;
} {
  const found = INTERFACE_STATUS_OPTIONS.find((item) => item.value === status);
  if (found) return found;
  return { value: status || '', label: status || '-', color: 'gray', buttonClass: 'status-default' };
}

export function getInterfaceStatusLabel(
  status?: string | null,
  statusDisplay?: string | null,
): string {
  if (statusDisplay) return statusDisplay;
  return getInterfaceStatusMeta(status).label;
}

export function getInterfaceStatusColor(status?: string | null): string {
  return getInterfaceStatusMeta(status).color;
}
export type ExtractVariableType = 'temporary' | 'project';
export type ExtractSource = 'response' | 'request';

export interface ApiExtractMetaRule {
  variable_type: ExtractVariableType;
  source?: ExtractSource;
}

export type ApiExtractMeta = Record<string, ApiExtractMetaRule>;

export interface ApiExtractPayload {
  extract: Record<string, string>;
  extractMeta: ApiExtractMeta;
}

export interface ApiExtractPersistenceResult {
  matched_count: number;
  created_count: number;
  updated_count: number;
  skipped_no_environment: boolean;
}

export interface ApiKeyValuePair {
  key: string;
  value: string;
  enabled?: boolean;
  description?: string;
  [key: string]: any;
}

export interface ApiRequestBody {
  type: ApiBodyType;
  content: any;
}

export interface ApiInterface {
  id: number;
  name: string;
  type: InterfaceType;

  // HTTP fields
  method: HttpMethod | null;
  url: string | null;
  headers: ApiKeyValuePair[];
  params: ApiKeyValuePair[];
  path_params?: ApiKeyValuePair[];
  body: ApiRequestBody;
  file_ids: number[];

  // SQL fields
  sql_method: SqlMethod | null;
  sql: string | null;
  sql_params: Record<string, any>;
  sql_size: number;

  // httprunner fields
  setup_hooks: string[];
  teardown_hooks: string[];
  variables: Record<string, any>;
  validators: any[];
  extract: Record<string, string>;
  extract_meta: ApiExtractMeta;

  // Status
  status?: InterfaceStatus;
  status_display?: string;

  // Relationships
  project: number;
  module: number | null;
  module_info?: { id: number; name: string } | null;
  created_by: UserBrief | null;
  created_at: string;
  updated_at: string;
  [key: string]: any;
}

export interface ApiInterfaceResult {
  id: number;
  interface: number;
  environment_id: number | null;
  success: boolean;
  elapsed: number;
  request_data: Record<string, any>;
  response_data: Record<string, any>;
  validation_results: any[];
  extracted_variables: Record<string, any>;
  executed_by: UserBrief | null;
  executed_at: string;
  [key: string]: any;
}
