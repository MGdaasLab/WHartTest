// 需求管理相关的TypeScript类型定义

// 基础响应类型
export interface ApiResponse<T = any> {
  status: 'success' | 'error';
  code: number;
  message: string;
  data: T;
}

// 分页响应类型
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// 文档状态枚举
export type DocumentStatus = 
  | 'uploaded'           // 已上传
  | 'processing'         // 处理中
  | 'module_split'       // 模块拆分中
  | 'user_reviewing'     // 用户调整中
  | 'ready_for_review'   // 待评审
  | 'reviewing'          // 评审中
  | 'review_completed'   // 评审完成
  | 'failed';            // 处理失败

// 文档类型枚举
export type DocumentType = 'pdf' | 'docx' | 'pptx' | 'txt' | 'md' | 'html';

// 需求文档接口
export interface RequirementDocument {
  id: string;
  title: string;
  description: string | null;
  document_type: DocumentType;
  file?: string; // 文件URL
  content?: string | null;
  status: DocumentStatus;
  version: string;
  is_latest: boolean;
  parent_document?: string | null;
  uploader: number; // 用户ID
  uploader_name: string;
  project: string; // 项目ID，根据新API文档更新为字符串类型
  project_name: string;
  uploaded_at: string;
  updated_at: string;
  word_count: number;
  page_count: number;
  modules_count: number;
}

// 创建文档请求
export interface CreateDocumentRequest {
  title: string;
  description?: string;
  document_type: DocumentType;
  project: string; // 项目ID，虽然后端期望数字，但我们在服务层转换
  file?: File;
  content?: string;
}

// 文档模块接口
export interface DocumentModule {
  id: string;
  title: string;
  content: string;
  start_page?: number;
  end_page?: number;
  start_position?: number;
  end_position?: number;
  order: number;
  parent_module?: string | null;
  is_auto_generated?: boolean;
  confidence_score?: number;
  ai_suggested_title?: string;
  created_at?: string;
  updated_at?: string;
  issues_count?: number;
}

// 模块操作类型
export type ModuleOperationType = 'merge' | 'split' | 'rename' | 'reorder' | 'delete' | 'adjust_boundary';

// 模块操作请求
export interface ModuleOperationRequest {
  operation: ModuleOperationType;
  target_modules: string[];
  merge_title?: string;
  merge_order?: number;
  split_points?: number[];
  split_titles?: string[];
  new_module_data?: Partial<DocumentModule>;
  new_orders?: Record<string, number>;
  new_boundary?: {
    start_position: number;
    end_position: number;
  };
}

// 批量模块操作请求
export interface BatchModuleOperationRequest {
  operations: ModuleOperationRequest[];
}

// 拆分级别类型
export type SplitLevel = 'h1' | 'h2' | 'h3' | 'auto';

// 模块拆分请求
export interface SplitModulesRequest {
  split_level: SplitLevel;
  include_context?: boolean;
  chunk_size?: number;
}

// 模块拆分响应
export interface SplitModulesResponse {
  split_options: SplitModulesRequest;
  modules: DocumentModule[];
  status: DocumentStatus;
  total_modules: number;
  suggestions: string[];
}

// 上下文检测建议类型
export type ContextSuggestion = 'OK' | 'SPLIT_RECOMMENDED' | 'SPLIT_REQUIRED';

// 上下文分析结果
export interface ContextAnalysis {
  model_name: string;
  token_count: number;
  context_limit: number;
  available_tokens: number;
  reserved_tokens: number;
  exceeds_limit: boolean;
  usage_percentage: number;
  remaining_tokens?: number;
  suggestion: ContextSuggestion;
  message: string;
  optimal_chunk_size?: number;
}

// 文档信息
export interface DocumentInfo {
  title: string;
  content_length: number;
  word_count: number;
  page_count: number;
}

// 上下文检测响应
export interface ContextCheckResponse {
  document_info: DocumentInfo;
  context_analysis: ContextAnalysis;
  recommendations: string[];
}

// 文档结构分析
export interface DocumentStructure {
  h1_titles: string[];
  h2_titles: string[];
  h3_titles: string[];
}

// 拆分建议
export interface SplitRecommendation {
  level: SplitLevel;
  modules_count: number;
  description: string;
  suitable_for: string;
  recommended?: boolean;
}

// 文档结构分析响应
export interface DocumentStructureResponse {
  document_info: DocumentInfo;
  structure_analysis: DocumentStructure;
  split_recommendations: SplitRecommendation[];
}

// 评审类型
export type AnalysisType = 'comprehensive' | 'quick' | 'custom';

// 开始评审请求
export interface StartReviewRequest {
  analysis_type: AnalysisType;
  parallel_processing?: boolean;
  priority_modules?: string[];
  custom_requirements?: string;
  direct_review?: boolean; // 新增直接评审参数
  // 新增提示词相关参数
  prompt_ids?: {
    requirement_structure?: number;
    requirement_direct?: number;
    requirement_global?: number;
    requirement_module?: number;
    requirement_consistency?: number;
  };
}

// 评审进度
export interface ReviewProgress {
  task_id: string;
  overall_progress: number;
  status: string;
  current_step: string;
  modules_progress: ModuleProgress[];
}

// 模块进度
export interface ModuleProgress {
  module_name: string;
  status: string;
  progress: number;
  issues_found: number;
}

// 评级类型
export type Rating = 'excellent' | 'good' | 'fair' | 'poor';

// 问题类型
export type IssueType = 'specification' | 'clarity' | 'completeness' | 'consistency' | 'feasibility';

// 问题优先级
export type IssuePriority = 'high' | 'medium' | 'low';

// 评审问题
export interface ReviewIssue {
  id: string;
  issue_type: IssueType;
  issue_type_display: string;
  priority: IssuePriority;
  priority_display: string;
  title: string;
  description: string;
  suggestion: string;
  location: string;
  page_number?: number | null;
  section: string;
  module?: string | null;
  module_name?: string;
  is_resolved: boolean;
  resolution_note: string;
  created_at: string;
  updated_at: string;
}

// 模块评审结果
export interface ModuleReviewResult {
  id: string;
  module: string;
  module_name: string;
  module_rating: Rating;
  module_rating_display: string;
  issues_count: number;
  severity_score: number;
  analysis_content?: string;
  strengths?: string;
  weaknesses?: string;
  recommendations?: string;
}

// 评审报告
export interface ReviewReport {
  id: string;
  document: string;
  document_title: string;
  review_date: string;
  reviewer: string;
  status: string;
  status_display: string;
  overall_rating: Rating;
  overall_rating_display: string;
  completion_score: number;
  total_issues: number;
  high_priority_issues: number;
  medium_priority_issues: number;
  low_priority_issues: number;
  summary: string;
  recommendations: string;
  issues: ReviewIssue[];
  module_results: ModuleReviewResult[];
}

// 文档详情（包含模块和评审报告）
export interface DocumentDetail extends RequirementDocument {
  modules: DocumentModule[];
  review_reports: ReviewReport[];
  latest_review?: ReviewReport;
}

// 查询参数接口
export interface DocumentListParams {
  project: string;
  status?: DocumentStatus;
  document_type?: DocumentType;
  search?: string;
  page?: number;
  page_size?: number;
}

export interface ReportListParams {
  document?: string;
  status?: string;
  overall_rating?: Rating;
  page?: number;
  page_size?: number;
}

export interface IssueListParams {
  report?: string;
  module?: string;
  issue_type?: IssueType;
  priority?: IssuePriority;
  is_resolved?: boolean;
  page?: number;
  page_size?: number;
}

// 更新问题请求
export interface UpdateIssueRequest {
  is_resolved?: boolean;
  resolution_note?: string;
}

// 状态显示映射
export const DocumentStatusDisplay: Record<DocumentStatus, string> = {
  uploaded: '已上传',
  processing: '处理中',
  module_split: '模块拆分中',
  user_reviewing: '用户调整中',
  ready_for_review: '待评审',
  reviewing: '评审中',
  review_completed: '评审完成',
  failed: '处理失败'
};

export const DocumentTypeDisplay: Record<DocumentType, string> = {
  pdf: 'PDF',
  docx: 'Word文档',
  pptx: 'PowerPoint',
  txt: '文本文件',
  md: 'Markdown',
  html: 'HTML'
};

export const RatingDisplay: Record<Rating, string> = {
  excellent: '优秀',
  good: '良好',
  fair: '一般',
  poor: '较差'
};

export const IssueTypeDisplay: Record<IssueType, string> = {
  specification: '规范性',
  clarity: '清晰度',
  completeness: '完整性',
  consistency: '一致性',
  feasibility: '可行性'
};

export const IssuePriorityDisplay: Record<IssuePriority, string> = {
  high: '高',
  medium: '中',
  low: '低'
};
