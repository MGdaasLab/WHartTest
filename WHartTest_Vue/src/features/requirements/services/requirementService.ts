import { request } from '@/utils/request';
import type {
  ApiResponse,
  PaginatedResponse,
  RequirementDocument,
  DocumentDetail,
  CreateDocumentRequest,
  DocumentListParams,
  ModuleOperationRequest,
  BatchModuleOperationRequest,
  StartReviewRequest,
  ReviewProgress,
  ReviewIssue,
  IssueListParams,
  UpdateIssueRequest,
  SplitModulesRequest,
  SplitModulesResponse,
  ContextCheckResponse,
  DocumentStructureResponse
} from '../types';

// API基础路径
const BASE_URL = '/requirements';

/**
 * 需求文档管理服务
 */
export class RequirementDocumentService {
  /**
   * 获取文档列表
   */
  static async getDocumentList(params: DocumentListParams): Promise<ApiResponse<PaginatedResponse<RequirementDocument> | RequirementDocument[]>> {
    const response = await request<PaginatedResponse<RequirementDocument> | RequirementDocument[]>({
      url: `${BASE_URL}/documents/`,
      method: 'GET',
      params
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'success',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to get document list',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 上传需求文档
   */
  static async uploadDocument(data: CreateDocumentRequest): Promise<ApiResponse<RequirementDocument>> {
    const formData = new FormData();
    formData.append('title', data.title);
    if (data.description) formData.append('description', data.description);
    formData.append('document_type', data.document_type);
    formData.append('project', data.project);

    if (data.file) {
      formData.append('file', data.file);
    } else if (data.content) {
      formData.append('content', data.content);
    }

    const response = await request<RequirementDocument>({
      url: `${BASE_URL}/documents/`,
      method: 'POST',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });

    if (response.success) {
      return {
        status: 'success',
        code: 201,
        message: response.message || 'Document uploaded successfully',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to upload document',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 获取文档详情
   */
  static async getDocumentDetail(id: string): Promise<ApiResponse<DocumentDetail>> {
    const response = await request<DocumentDetail>({
      url: `${BASE_URL}/documents/${id}/`,
      method: 'GET'
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'success',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to get document detail',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 删除文档
   */
  static async deleteDocument(id: string): Promise<ApiResponse<void>> {
    const response = await request<void>({
      url: `${BASE_URL}/documents/${id}/`,
      method: 'DELETE'
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'Document deleted successfully',
        data: null,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to delete document',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 启动AI模块拆分
   */
  static async splitModules(id: string, params?: SplitModulesRequest): Promise<ApiResponse<SplitModulesResponse>> {
    const response = await request<SplitModulesResponse>({
      url: `${BASE_URL}/documents/${id}/split-modules/`,
      method: 'POST',
      data: params
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'Module split started successfully',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to start module split',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 检查上下文限制
   */
  static async checkContextLimit(id: string, model?: string): Promise<ApiResponse<ContextCheckResponse>> {
    const params = model ? { model } : {};
    const response = await request<ContextCheckResponse>({
      url: `${BASE_URL}/documents/${id}/check-context-limit/`,
      method: 'GET',
      params
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'success',
        data: response.data!
      };
    } else {
      // 尝试获取更详细的错误信息，包括嵌套的errors对象
      let detailedError = response.error || 'Failed to check context limit';
      
      // 如果错误信息中包含嵌套的errors对象，尝试提取更详细的信息
      if (response.error && typeof response.error === 'object') {
        const errorObj = response.error as any;
        if (errorObj.errors && errorObj.errors.error) {
          detailedError = errorObj.errors.error;
        } else if (errorObj.message) {
          detailedError = errorObj.message;
        } else if (errorObj.detail) {
          detailedError = errorObj.detail;
        }
      }
      
      return {
        status: 'error',
        code: 500,
        message: detailedError,
        data: {} as ContextCheckResponse // 返回空对象而不是null，以符合类型要求
      };
    }
  }

  /**
   * 分析文档结构
   */
  static async analyzeStructure(id: string): Promise<ApiResponse<DocumentStructureResponse>> {
    const response = await request<DocumentStructureResponse>({
      url: `${BASE_URL}/documents/${id}/analyze-structure/`,
      method: 'GET'
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'success',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to analyze document structure',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 确认模块拆分结果
   */
  static async confirmModules(id: string): Promise<ApiResponse<any>> {
    const response = await request<any>({
      url: `${BASE_URL}/documents/${id}/confirm-modules/`,
      method: 'POST'
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'Modules confirmed successfully',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to confirm modules',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 模块操作
   */
  static async moduleOperation(id: string, operation: ModuleOperationRequest): Promise<ApiResponse<any>> {
    const response = await request<any>({
      url: `${BASE_URL}/documents/${id}/module-operations/`,
      method: 'POST',
      data: operation
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'Module operation completed successfully',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to perform module operation',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 批量模块操作
   */
  static async batchModuleOperation(id: string, operations: BatchModuleOperationRequest): Promise<ApiResponse<any>> {
    const response = await request<any>({
      url: `${BASE_URL}/documents/${id}/module-operations/`,
      method: 'POST',
      data: operations
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'Batch module operations completed successfully',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to perform batch module operations',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 开始需求评审
   */
  static async startReview(id: string, params: StartReviewRequest): Promise<ApiResponse<any>> {
    const response = await request<any>({
      url: `${BASE_URL}/documents/${id}/start-review/`,
      method: 'POST',
      data: params
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'Review started successfully',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to start review',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 查询评审进度
   */
  static async getReviewProgress(id: string): Promise<ApiResponse<ReviewProgress>> {
    const response = await request<ReviewProgress>({
      url: `${BASE_URL}/documents/${id}/review-progress/`,
      method: 'GET'
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'success',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to get review progress',
        data: null,
        errors: { detail: response.error }
      };
    }
  }
  
  /**
   * 重新开始需求评审
   */
  static async restartReview(id: string, params: StartReviewRequest): Promise<ApiResponse<any>> {
    const response = await request<any>({
      url: `${BASE_URL}/documents/${id}/restart-review/`,
      method: 'POST',
      data: params
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || '重新评审启动成功',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || '重新启动评审失败',
        data: null,
        errors: { detail: response.error }
      };
    }
  }
}

// 评审报告数据通过 RequirementDocumentService.getDocumentDetail 获取
// 不再需要单独的 ReviewReportService

/**
 * 评审问题管理服务
 */
export class ReviewIssueService {
  /**
   * 获取问题列表
   */
  static async getIssueList(params: IssueListParams): Promise<ApiResponse<PaginatedResponse<ReviewIssue>>> {
    const response = await request<PaginatedResponse<ReviewIssue>>({
      url: `${BASE_URL}/issues/`,
      method: 'GET',
      params
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'success',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to get issue list',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 获取问题详情
   */
  static async getIssueDetail(id: string): Promise<ApiResponse<ReviewIssue>> {
    const response = await request<ReviewIssue>({
      url: `${BASE_URL}/issues/${id}/`,
      method: 'GET'
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'success',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to get issue detail',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 更新问题状态
   */
  static async updateIssue(id: string, data: UpdateIssueRequest): Promise<ApiResponse<ReviewIssue>> {
    const response = await request<ReviewIssue>({
      url: `${BASE_URL}/issues/${id}/`,
      method: 'PATCH',
      data
    });

    if (response.success) {
      return {
        status: 'success',
        code: 200,
        message: response.message || 'Issue updated successfully',
        data: response.data!,
        errors: null
      };
    } else {
      return {
        status: 'error',
        code: 500,
        message: response.error || 'Failed to update issue',
        data: null,
        errors: { detail: response.error }
      };
    }
  }

  /**
   * 标记问题已解决
   */
  static async resolveIssue(id: string, resolutionNote?: string): Promise<ApiResponse<ReviewIssue>> {
    return this.updateIssue(id, {
      is_resolved: true,
      resolution_note: resolutionNote
    });
  }

  /**
   * 标记问题未解决
   */
  static async unresolveIssue(id: string): Promise<ApiResponse<ReviewIssue>> {
    return this.updateIssue(id, {
      is_resolved: false,
      resolution_note: undefined
    });
  }
}

// 导出所有服务
export {
  RequirementDocumentService as documentService,
  ReviewIssueService as issueService
};

// 默认导出主要服务
export default RequirementDocumentService;
