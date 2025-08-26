/**
 * 嵌入服务类型
 */
export type EmbeddingServiceType = 'openai' | 'azure_openai' | 'ollama' | 'custom';

/**
 * 嵌入服务选项接口
 */
export interface EmbeddingServiceOption {
  value: string;
  label: string;
}

/**
 * 嵌入服务选项响应
 */
export interface EmbeddingServicesResponse {
  services: EmbeddingServiceOption[];
}

/**
 * 需要API配置的服务类型
 */
export const SERVICES_REQUIRING_API_CONFIG: EmbeddingServiceType[] = [
  'openai',
  'azure_openai',
  'ollama',
  'custom'
];

/**
 * 获取字段验证规则
 */
export const getRequiredFieldsForEmbeddingService = (embedding_service: string): string[] => {
  const required: string[] = ['api_base_url', 'model_name'];
  
  if (embedding_service === 'openai' || embedding_service === 'azure_openai') {
    required.push('api_key');
  }
  
  return required;
};

/**
 * 知识库对象
 */
export interface KnowledgeBase {
  id: string;
  name: string;
  description?: string;
  project: number | string;  // 允许字符串或数字
  project_name?: string;
  creator: number;
  creator_name?: string;
  is_active: boolean;
  embedding_service: EmbeddingServiceType;
  api_base_url: string;
  api_key?: string;
  model_name: string;
  chunk_size: number;
  chunk_overlap: number;
  document_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

/**
 * 创建知识库的请求体
 */
export interface CreateKnowledgeBaseRequest {
  name: string;                    // 必填，字符串，最大200字符
  description?: string;            // 可选，字符串，文本类型
  project: number;                 // 必填，整数，项目ID
  embedding_service: EmbeddingServiceType; // 必填，嵌入服务选择
  api_base_url: string;            // 必填，API基础URL
  api_key?: string;                // 可选，API密钥（OpenAI/Azure必填，Ollama可选）
  model_name: string;              // 必填，模型名称
  chunk_size?: number;             // 可选，分块大小，默认1000
  chunk_overlap?: number;          // 可选，分块重叠，默认200
  is_active?: boolean;             // 可选，是否启用，默认true
}

/**
 * 更新知识库的请求体
 */
export interface UpdateKnowledgeBaseRequest extends Partial<CreateKnowledgeBaseRequest> {}

/**
 * 文档类型
 */
export type DocumentType = 'pdf' | 'docx' | 'pptx' | 'txt' | 'md' | 'html' | 'url';

/**
 * 文档处理状态
 */
export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

/**
 * 文档对象
 */
export interface Document {
  id: string;
  knowledge_base: string;
  knowledge_base_name: string;
  title: string;
  document_type: DocumentType;
  status: DocumentStatus;
  file_size?: number;
  page_count?: number;
  word_count?: number;
  chunk_count: number;
  uploader: number;
  uploader_name: string;
  uploaded_at: string;
  processed_at?: string;
  url?: string;
  file?: string;
  file_name?: string;
  file_url?: string;
  error_message?: string;
}

/**
 * 上传文档的请求体
 */
export interface UploadDocumentRequest {
  knowledge_base: string;
  title: string;
  document_type: DocumentType;
  file?: File;
  content?: string;
  url?: string;
}

/**
 * 文档分块对象
 */
export interface DocumentChunk {
  id: string;
  document: string;
  document_title: string;
  chunk_index: number;
  content: string;
  vector_id?: string;
  start_index: number;
  end_index: number;
  page_number?: number;
  created_at: string;
}

/**
 * 文档完整内容响应
 */
export interface DocumentContentResponse {
  id: string;
  title: string;
  document_type: DocumentType;
  status: DocumentStatus;
  content: string;
  uploader_name: string;
  uploaded_at: string;
  processed_at?: string;
  file_size?: number;
  page_count?: number;
  word_count?: number;
  knowledge_base: {
    id: string;
    name: string;
  };
  file_name?: string;
  file_url?: string;
  url?: string; // 添加 URL 字段支持
  chunk_count: number;
  chunks?: {
    total_count: number;
    page: number;
    page_size: number;
    total_pages: number;
    items: DocumentChunk[];
  };
}

/**
 * 获取文档内容的查询参数
 */
export interface GetDocumentContentParams {
  include_chunks?: boolean;
  chunk_page?: number;
  chunk_page_size?: number;
}

/**
 * 查询请求
 */
export interface QueryRequest {
  query: string;
  knowledge_base_id: string;
  top_k?: number;
  similarity_threshold?: number;
  include_metadata?: boolean;
}

/**
 * 查询结果中的来源信息
 */
export interface QuerySource {
  content: string;
  similarity_score: number;
  metadata: {
    title: string;
    file_path: string;
    source: string;
    document_type: string;
    document_id: string;
    page?: number;
    [key: string]: any;
  };
}

/**
 * 查询响应
 */
export interface QueryResponse {
  query: string;
  answer: string;
  sources: QuerySource[];
  retrieval_time: number;
  generation_time: number;
  total_time: number;
}

/**
 * RAG查询请求
 */
export interface RagQueryRequest {
  query: string;
  knowledge_base_id: string;
  project_id?: string;
}

/**
 * 知识库统计信息
 */
export interface KnowledgeBaseStatistics {
  document_count: number;
  chunk_count: number;
  query_count: number;
  document_status_distribution: {
    completed: number;
    processing: number;
    failed: number;
  };
  recent_queries: Array<{
    query: string;
    total_time: number;
    created_at: string;
  }>;
}

/**
 * 查询日志
 */
export interface QueryLog {
  id: string;
  knowledge_base: string;
  user: number;
  query: string;
  response?: string;
  retrieval_time: number;
  generation_time: number;
  total_time: number;
  created_at: string;
}

/**
 * 分页响应
 */
export interface PaginatedResponse<T> {
  count: number;
  next?: string;
  previous?: string;
  results: T[];
}

/**
 * API响应格式
 */
export interface ApiResponse<T> {
  status: 'success' | 'error';
  code: number;
  message: string;
  data: T;
  errors?: any;
}

/**
 * 系统状态响应
 */
export interface SystemStatusResponse {
  timestamp: number;
  embedding_model: {
    status: 'working' | 'error';
    model_name: string;
    cache_path: string;
    model_exists: boolean;
    load_test: boolean;
    dimension: number;
  };
  dependencies: {
    langchain_huggingface: boolean;
    langchain_chroma: boolean;
    sentence_transformers: boolean;
    torch: boolean;
  };
  vector_stores: {
    total_knowledge_bases: number;
    active_knowledge_bases: number;
    cache_status: string;
  };
  overall_status: 'healthy' | 'error';
}

/**
 * 错误响应格式
 */
export interface ErrorResponse {
  error: string;
  detail?: string;
  [key: string]: any;
}
