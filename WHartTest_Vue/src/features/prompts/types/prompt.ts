/**
 * 提示词类型枚举
 */
export type PromptType =
  | 'general'
  | 'document_structure'
  | 'direct_analysis'
  | 'global_analysis'
  | 'module_analysis'
  | 'consistency_analysis';

/**
 * 提示词类型选项
 */
export const PROMPT_TYPE_CHOICES = [
  { key: 'general', name: '通用对话', isProgramCall: false },
  { key: 'document_structure', name: '文档结构分析', isProgramCall: true },
  { key: 'direct_analysis', name: '直接分析', isProgramCall: true },
  { key: 'global_analysis', name: '全局分析', isProgramCall: true },
  { key: 'module_analysis', name: '模块分析', isProgramCall: true },
  { key: 'consistency_analysis', name: '一致性分析', isProgramCall: true },
] as const;

/**
 * 用户提示词对象
 */
export interface UserPrompt {
  id: number;
  name: string;
  content: string;
  description?: string;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // 新增字段
  prompt_type: PromptType;
  prompt_type_display: string;
  is_requirement_type: boolean;
}

/**
 * 创建用户提示词的请求体
 */
export interface CreateUserPromptRequest {
  name: string;
  content: string;
  description?: string;
  is_default?: boolean;
  is_active?: boolean;
  prompt_type: PromptType; // 新增必填字段
}

/**
 * 更新用户提示词的请求体 (PUT - 完整更新)
 */
export interface UpdateUserPromptRequest extends CreateUserPromptRequest {}

/**
 * 部分更新用户提示词的请求体 (PATCH - 部分更新)
 */
export interface PartialUpdateUserPromptRequest {
  name?: string;
  content?: string;
  description?: string;
  is_default?: boolean;
  is_active?: boolean;
  prompt_type?: PromptType; // 新增可选字段
}

/**
 * 用户提示词列表查询参数
 */
export interface UserPromptListParams {
  page?: number;
  page_size?: number;
  search?: string;
  is_default?: boolean;
  is_active?: boolean;
  ordering?: string;
  prompt_type?: PromptType; // 新增可选字段，用于按类型筛选
}

/**
 * 用户提示词列表响应数据
 */
export interface UserPromptListResponseData {
  count: number;
  next: string | null;
  previous: string | null;
  results: UserPrompt[];
}

/**
 * 批量操作响应数据
 */
export interface BatchOperationResponseData {
  updated_count: number;
}

/**
 * 提示词选择器选项
 */
export interface PromptOption {
  id: number;
  name: string;
  description?: string;
  is_default?: boolean;
}

// ==================== 需求评审提示词专用类型 ====================

/**
 * 需求评审提示词状态信息
 */
export interface RequirementPromptInfo {
  exists: boolean;
  id?: number;
  name?: string;
  description?: string;
  message?: string; // 当不存在时的提示信息
}

/**
 * 需求评审提示词列表响应
 */
export interface RequirementPromptsResponse {
  prompts: Record<string, RequirementPromptInfo>;
  types: Array<{ key: string; name: string }>;
}

/**
 * 获取指定类型需求评审提示词的请求参数
 */
export interface GetRequirementPromptParams {
  prompt_type: PromptType;
}

/**
 * 需求评审提示词API响应数据
 */
export interface RequirementPromptApiResponse {
  status: 'success' | 'error';
  code: number;
  message: string;
  data?: UserPrompt | RequirementPromptsResponse | null;
  errors?: Record<string, string[]> | null;
}

/**
 * 工具函数：判断是否为程序调用类型
 */
export function isProgramCallPromptType(type: PromptType): boolean {
  const choice = PROMPT_TYPE_CHOICES.find(c => c.key === type);
  return choice?.isProgramCall || false;
}

/**
 * 工具函数：判断是否为需求评审类型
 */
export function isRequirementPromptType(type: PromptType): boolean {
  return type !== 'general';
}

/**
 * 工具函数：获取提示词类型显示名称
 */
export function getPromptTypeDisplayName(type: PromptType): string {
  const choice = PROMPT_TYPE_CHOICES.find(c => c.key === type);
  return choice?.name || type;
}
