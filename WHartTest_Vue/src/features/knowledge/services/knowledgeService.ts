import { request } from '@/utils/request';
import type {
  KnowledgeBase,
  CreateKnowledgeBaseRequest,
  UpdateKnowledgeBaseRequest,
  Document,
  UploadDocumentRequest,
  DocumentChunk,
  DocumentContentResponse,
  GetDocumentContentParams,
  QueryRequest,
  QueryResponse,
  RagQueryRequest,
  KnowledgeBaseStatistics,
  QueryLog,
  PaginatedResponse,
  SystemStatusResponse,
  EmbeddingServicesResponse,
  KnowledgeGlobalConfig,
} from '../types/knowledge';

const API_BASE_URL = '/knowledge';

/**
 * 知识库管理服务
 */
export class KnowledgeService {
  // ==================== 全局配置管理 ====================

  /**
   * 获取全局配置
   */
  static async getGlobalConfig(): Promise<KnowledgeGlobalConfig> {
    const response = await request<KnowledgeGlobalConfig>({
      url: `${API_BASE_URL}/global-config/`,
      method: 'GET'
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to get global config');
    }
  }

  /**
   * 更新全局配置
   */
  static async updateGlobalConfig(data: Partial<KnowledgeGlobalConfig>): Promise<KnowledgeGlobalConfig> {
    const response = await request<KnowledgeGlobalConfig>({
      url: `${API_BASE_URL}/global-config/`,
      method: 'PUT',
      data
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to update global config');
    }
  }

  // ==================== 知识库管理 ====================

  /**
   * 获取知识库列表
   */
  static async getKnowledgeBases(params?: {
    project?: number | string;
    search?: string;
    is_active?: boolean;
    embedding_service?: string;
    ordering?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<KnowledgeBase> | KnowledgeBase[]> {
    const response = await request<PaginatedResponse<KnowledgeBase> | KnowledgeBase[]>({
      url: `${API_BASE_URL}/knowledge-bases/`,
      method: 'GET',
      params
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to get knowledge bases');
    }
  }

  /**
   * 创建知识库
   */
  static async createKnowledgeBase(data: CreateKnowledgeBaseRequest): Promise<KnowledgeBase> {
    const response = await request<KnowledgeBase>({
      url: `${API_BASE_URL}/knowledge-bases/`,
      method: 'POST',
      data
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to create knowledge base');
    }
  }

  /**
   * 获取知识库详情
   */
  static async getKnowledgeBase(id: string): Promise<KnowledgeBase> {
    const response = await request<KnowledgeBase>({
      url: `${API_BASE_URL}/knowledge-bases/${id}/`,
      method: 'GET'
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to get knowledge base');
    }
  }

  /**
   * 更新知识库
   */
  static async updateKnowledgeBase(id: string, data: UpdateKnowledgeBaseRequest): Promise<KnowledgeBase> {
    const response = await request<KnowledgeBase>({
      url: `${API_BASE_URL}/knowledge-bases/${id}/`,
      method: 'PUT',
      data
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to update knowledge base');
    }
  }

  /**
   * 部分更新知识库
   */
  static async partialUpdateKnowledgeBase(id: string, data: Partial<UpdateKnowledgeBaseRequest>): Promise<KnowledgeBase> {
    const response = await request<KnowledgeBase>({
      url: `${API_BASE_URL}/knowledge-bases/${id}/`,
      method: 'PATCH',
      data
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to update knowledge base');
    }
  }

  /**
   * 删除知识库
   */
  static async deleteKnowledgeBase(id: string): Promise<void> {
    const response = await request<void>({
      url: `${API_BASE_URL}/knowledge-bases/${id}/`,
      method: 'DELETE'
    });

    if (!response.success) {
      throw new Error(response.error || 'Failed to delete knowledge base');
    }
  }

  /**
   * 获取知识库统计信息
   */
  static async getKnowledgeBaseStatistics(id: string): Promise<KnowledgeBaseStatistics> {
    const response = await request<KnowledgeBaseStatistics>({
      url: `${API_BASE_URL}/knowledge-bases/${id}/statistics/`,
      method: 'GET'
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to get knowledge base statistics');
    }
  }

  /**
   * 查询知识库
   */
  static async queryKnowledgeBase(id: string, data: QueryRequest): Promise<QueryResponse> {
    const response = await request<QueryResponse>({
      url: `${API_BASE_URL}/knowledge-bases/${id}/query/`,
      method: 'POST',
      data
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to query knowledge base');
    }
  }

  /**
   * 获取嵌入服务选项
   */
  static async getEmbeddingServices(): Promise<EmbeddingServicesResponse> {
    const response = await request<EmbeddingServicesResponse>({
      url: `${API_BASE_URL}/embedding-services/`,
      method: 'GET'
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to get embedding services');
    }
  }

  /**
   * 测试嵌入服务连接
   */
  static async testEmbeddingConnection(data: {
    embedding_service: string;
    api_base_url: string;
    api_key?: string;
    model_name: string;
  }): Promise<{ success: boolean; message: string }> {
    const response = await request<{ success: boolean; message: string }>({
      url: `${API_BASE_URL}/test-embedding-connection/`,
      method: 'POST',
      data
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to test embedding connection');
    }
  }

  /**
   * 测试 Reranker 服务连接
   */
  static async testRerankerConnection(data: {
    reranker_service: string;
    reranker_api_url: string;
    reranker_api_key?: string;
    reranker_model_name: string;
  }): Promise<{ success: boolean; message: string }> {
    const response = await request<{ success: boolean; message: string }>({
      url: `${API_BASE_URL}/test-reranker-connection/`,
      method: 'POST',
      data
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to test reranker connection');
    }
  }

  /**
   * 获取系统状态
   */
  static async getSystemStatus(): Promise<SystemStatusResponse> {
    const response = await request<SystemStatusResponse>({
      url: `${API_BASE_URL}/knowledge-bases/system_status/`,
      method: 'GET'
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to get system status');
    }
  }

  // ==================== 文档管理 ====================

  /**
   * 获取文档列表
   */
  static async getDocuments(params?: {
    knowledge_base?: string;
    document_type?: string;
    status?: string;
    search?: string;
    module?: string;
    version?: string;
    business_domain?: string;
    document_stage?: string;
  }): Promise<Document[]> {
    const response = await request<Document[]>({
      url: `${API_BASE_URL}/documents/`,
      method: 'GET',
      params
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to get documents');
    }
  }

  /**
   * 上传文档
   */
  static async uploadDocument(data: UploadDocumentRequest): Promise<Document> {
    const formData = new FormData();
    formData.append('knowledge_base', data.knowledge_base);
    formData.append('title', data.title);
    formData.append('document_type', data.document_type);

    if (data.file) {
      formData.append('file', data.file);
    }
    if (data.content) {
      formData.append('content', data.content);
    }
    if (data.url) {
      formData.append('url', data.url);
    }
    if (data.tags?.length) {
      formData.append('tags', JSON.stringify(data.tags));
    }
    if (data.metadata && Object.keys(data.metadata).length > 0) {
      formData.append('metadata', JSON.stringify(data.metadata));
    }
    if (data.module) {
      formData.append('module', data.module);
    }
    if (data.version) {
      formData.append('version', data.version);
    }
    if (data.business_domain) {
      formData.append('business_domain', data.business_domain);
    }
    if (data.document_stage) {
      formData.append('document_stage', data.document_stage);
    }

    const response = await request<Document | Document[]>({
      url: `${API_BASE_URL}/documents/`,
      method: 'POST',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data',
      }
    });

    if (response.success) {
      // 检查返回的数据格式
      const responseData = response.data!;
      if (Array.isArray(responseData)) {
        // 如果返回的是数组，取第一个元素
        return responseData[0];
      } else {
        // 如果返回的是单个对象
        return responseData;
      }
    } else {
      throw new Error(response.error || 'Failed to upload document');
    }
  }

  /**
   * 获取文档详情
   */
  static async getDocument(id: string): Promise<Document> {
    const response = await request<Document>({
      url: `${API_BASE_URL}/documents/${id}/`,
      method: 'GET'
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to get document');
    }
  }

  /**
   * 获取文档完整内容
   */
  static async getDocumentContent(id: string, params?: GetDocumentContentParams): Promise<DocumentContentResponse> {
    const response = await request<DocumentContentResponse>({
      url: `${API_BASE_URL}/documents/${id}/content/`,
      method: 'GET',
      params
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to get document content');
    }
  }

  /**
   * 重新处理文档
   */
  static async reprocessDocument(id: string): Promise<Document> {
    const response = await request<Document>({
      url: `${API_BASE_URL}/documents/${id}/reprocess/`,
      method: 'POST'
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to reprocess document');
    }
  }

  /**
   * 批量重新处理知识库下的文档
   */
  static async reprocessKnowledgeBaseDocuments(id: string): Promise<{
    message: string;
    queued_count: number;
    total_count: number;
  }> {
    const response = await request<{
      message: string;
      queued_count: number;
      total_count: number;
    }>({
      url: `${API_BASE_URL}/knowledge-bases/${id}/reprocess_documents/`,
      method: 'POST'
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to reprocess knowledge base documents');
    }
  }

  /**
   * 删除文档
   */
  static async deleteDocument(id: string): Promise<void> {
    const response = await request<void>({
      url: `${API_BASE_URL}/documents/${id}/`,
      method: 'DELETE'
    });

    if (!response.success) {
      throw new Error(response.error || 'Failed to delete document');
    }
  }

  // ==================== 文档分块 ====================

  /**
   * 获取分块列表
   */
  static async getChunks(params?: {
    document?: string;
    document__knowledge_base?: string;
  }): Promise<PaginatedResponse<DocumentChunk>> {
    const response = await request<PaginatedResponse<DocumentChunk>>({
      url: `${API_BASE_URL}/chunks/`,
      method: 'GET',
      params
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to get chunks');
    }
  }

  // ==================== 查询日志 ====================

  /**
   * 获取查询日志
   */
  static async getQueryLogs(params?: {
    knowledge_base?: string;
    user?: number;
  }): Promise<PaginatedResponse<QueryLog>> {
    const response = await request<PaginatedResponse<QueryLog>>({
      url: `${API_BASE_URL}/query-logs/`,
      method: 'GET',
      params
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to get query logs');
    }
  }

  // ==================== RAG集成 ====================

  /**
   * RAG查询
   */
  static async ragQuery(data: RagQueryRequest): Promise<QueryResponse> {
    const response = await request<QueryResponse>({
      url: '/lg/knowledge/rag/',
      method: 'POST',
      data
    });

    if (response.success) {
      return response.data!;
    } else {
      throw new Error(response.error || 'Failed to perform RAG query');
    }
  }
}

// 导出便捷方法
export const {
  getGlobalConfig,
  updateGlobalConfig,
  getKnowledgeBases,
  createKnowledgeBase,
  getKnowledgeBase,
  updateKnowledgeBase,
  partialUpdateKnowledgeBase,
  deleteKnowledgeBase,
  getKnowledgeBaseStatistics,
  queryKnowledgeBase,
  getSystemStatus,
  getDocuments,
  uploadDocument,
  getDocument,
  getDocumentContent,
  reprocessDocument,
  deleteDocument,
  getChunks,
  getQueryLogs,
  ragQuery,
} = KnowledgeService;
