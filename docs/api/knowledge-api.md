# 知识库API接口文档

## 基础信息
- **基础URL**: `http://127.0.0.1:8000`
- **认证**: `Authorization: Bearer <JWT_TOKEN>`
- **Content-Type**: `application/json`

## 1. 知识库管理

### 1.1 获取知识库列表
```http
GET /api/knowledge/knowledge-bases/
```
**查询参数**: `project`(项目ID), `search`(搜索关键词)

**响应示例**:
```json
[{
  "id": "uuid",
  "name": "知识库名称",
  "description": "描述",
  "project": "project_id",
  "project_name": "项目名称",
  "creator_name": "创建人",
  "document_count": 5,
  "chunk_count": 25,
  "created_at": "2024-01-20T10:00:00Z"
}]
```

### 1.2 创建知识库
```http
POST /api/knowledge/knowledge-bases/
```
**请求体**:
```json
{
  "name": "知识库名称",
  "description": "描述",
  "project": "project_id"
}
```

### 1.3 获取知识库详情
```http
GET /api/knowledge/knowledge-bases/{id}/
```

### 1.4 更新知识库
```http
PATCH /api/knowledge/knowledge-bases/{id}/
```

### 1.5 删除知识库
```http
DELETE /api/knowledge/knowledge-bases/{id}/
```

### 1.6 知识库统计
```http
GET /api/knowledge/knowledge-bases/{id}/statistics/
```
**响应**:
```json
{
  "document_count": 10,
  "chunk_count": 50,
  "query_count": 25,
  "document_status_distribution": {"completed": 8, "processing": 1, "failed": 1}
}
```

### 1.7 查询知识库
```http
POST /api/knowledge/knowledge-bases/{id}/query/
```
**请求体**:
```json
{
  "query": "查询内容",
  "knowledge_base_id": "kb_id",
  "top_k": 5,
  "similarity_threshold": 0.7
}
```
**响应**:
```json
{
  "query": "查询内容",
  "answer": "回答内容",
  "sources": [{"content": "相关内容", "similarity_score": 0.85}],
  "retrieval_time": 0.025,
  "total_time": 0.045
}
```

### 1.8 查看知识库内容
```http
GET /api/knowledge/knowledge-bases/{id}/content/
```
**查询参数**:
- `search`: 搜索关键词（可选）
- `document_type`: 文档类型筛选（可选）
- `status`: 文档状态，默认为"completed"
- `page`: 页码，默认为1
- `page_size`: 每页数量，默认为20

**响应示例**:
```json
{
  "total_count": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3,
  "knowledge_base": {
    "id": "kb_id",
    "name": "知识库名称",
    "description": "知识库描述"
  },
  "documents": [
    {
      "id": "doc_id",
      "title": "文档标题",
      "document_type": "pdf",
      "status": "completed",
      "uploader_name": "上传人",
      "uploaded_at": "2024-01-20T10:00:00Z",
      "chunk_count": 15,
      "content_preview": "文档内容预览（前500字符）...",
      "file_size": 1024000,
      "page_count": 10,
      "word_count": 5000,
      "file_name": "document.pdf",
      "file_url": "/media/documents/document.pdf"
    }
  ]
}
```

## 2. 文档管理

### 2.1 获取文档列表
```http
GET /api/knowledge/documents/
```
**查询参数**: `knowledge_base`(知识库ID), `status`(状态), `document_type`(类型)

### 2.2 上传文档
```http
POST /api/knowledge/documents/
```

**文本内容**:
```json
{
  "knowledge_base": "kb_id",
  "title": "文档标题",
  "document_type": "txt",
  "content": "文档内容"
}
```

**文件上传** (multipart/form-data):
```
knowledge_base: kb_id
title: 文档标题
document_type: pdf
file: 文件对象
```

**网页链接**:
```json
{
  "knowledge_base": "kb_id",
  "title": "网页标题",
  "document_type": "url",
  "url": "https://example.com"
}
```

**响应**:
```json
{
  "id": "doc_id",
  "title": "文档标题",
  "document_type": "txt",
  "status": "processing",
  "uploader_name": "上传人",
  "uploaded_at": "2024-01-20T10:00:00Z"
}
```

### 2.3 获取文档详情
```http
GET /api/knowledge/documents/{id}/
```

### 2.4 获取文档处理状态
```http
GET /api/knowledge/documents/{id}/status/
```
**响应**:
```json
{
  "id": "doc_id",
  "status": "processing",
  "progress": 50,
  "error_message": "",
  "chunk_count": 0,
  "processed_at": null
}
```

### 2.5 重新处理文档
```http
POST /api/knowledge/documents/{id}/reprocess/
```

### 2.6 删除文档
```http
DELETE /api/knowledge/documents/{id}/
```

### 2.7 查看文档完整内容
```http
GET /api/knowledge/documents/{id}/content/
```
**查询参数**:
- `include_chunks`: 是否包含分块信息，默认为false
- `chunk_page`: 分块页码，默认为1（仅当include_chunks=true时有效）
- `chunk_page_size`: 分块每页数量，默认为10（仅当include_chunks=true时有效）

**响应示例**:
```json
{
  "id": "doc_id",
  "title": "文档标题",
  "document_type": "pdf",
  "status": "completed",
  "content": "文档完整内容...",
  "uploader_name": "上传人",
  "uploaded_at": "2024-01-20T10:00:00Z",
  "processed_at": "2024-01-20T10:05:00Z",
  "file_size": 1024000,
  "page_count": 10,
  "word_count": 5000,
  "knowledge_base": {
    "id": "kb_id",
    "name": "知识库名称"
  },
  "file_name": "document.pdf",
  "file_url": "/media/documents/document.pdf",
  "chunk_count": 15,
  "chunks": {
    "total_count": 15,
    "page": 1,
    "page_size": 10,
    "total_pages": 2,
    "items": [
      {
        "id": "chunk_id",
        "chunk_index": 0,
        "content": "分块内容...",
        "start_index": 0,
        "end_index": 500,
        "page_number": 1
      }
    ]
  }
}
```

## 3. RAG集成

### 3.1 RAG查询
```http
POST /api/lg/knowledge/rag/
```
**请求体**:
```json
{
  "query": "查询内容",
  "knowledge_base_id": "kb_id",
  "project_id": "project_id"
}
```

## 4. 其他接口

### 4.1 获取文档分块
```http
GET /api/knowledge/chunks/?document={doc_id}
```

### 4.2 获取查询日志
```http
GET /api/knowledge/query-logs/?knowledge_base={kb_id}
```

## 5. 参数说明

### 文档类型
- `pdf`: PDF文档
- `docx`: Word文档
- `pptx`: PowerPoint文档
- `txt`: 文本文件
- `md`: Markdown文档
- `html`: HTML文档
- `url`: 网页链接

### 文档状态
- `pending`: 待处理
- `processing`: 处理中
- `completed`: 已完成
- `failed`: 处理失败

### 状态码
- `200`: 成功
- `201`: 创建成功
- `400`: 参数错误
- `401`: 未认证
- `403`: 权限不足
- `404`: 不存在
- `500`: 服务器错误

## 6. 前端集成示例

### 基础配置
```javascript
const api = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});
```

### 创建知识库
```javascript
const createKB = async (data) => {
  const response = await api.post('/api/knowledge/knowledge-bases/', data);
  return response.data;
};
```

### 上传文档（异步处理）
```javascript
// 文件上传 - 增加超时时间
const uploadFile = async (kbId, file, title) => {
  const formData = new FormData();
  formData.append('knowledge_base', kbId);
  formData.append('title', title);
  formData.append('document_type', 'pdf');
  formData.append('file', file);

  const response = await api.post('/api/knowledge/documents/', formData, {
    headers: {'Content-Type': 'multipart/form-data'},
    timeout: 30000 // 增加到30秒
  });
  return response.data;
};

// 文本上传
const uploadText = async (kbId, title, content) => {
  const data = {
    knowledge_base: kbId,
    title: title,
    document_type: 'txt',
    content: content
  };
  const response = await api.post('/api/knowledge/documents/', data, {
    timeout: 30000 // 增加超时时间
  });
  return response.data;
};

// 轮询文档处理状态
const pollDocumentStatus = async (docId, onProgress) => {
  const checkStatus = async () => {
    try {
      const response = await api.get(`/api/knowledge/documents/${docId}/status/`);
      const { status, progress, error_message } = response.data;

      onProgress(status, progress, error_message);

      if (status === 'completed') {
        return response.data;
      } else if (status === 'failed') {
        throw new Error(error_message || '文档处理失败');
      } else {
        // 继续轮询
        setTimeout(checkStatus, 2000); // 每2秒检查一次
      }
    } catch (error) {
      console.error('检查文档状态失败:', error);
      throw error;
    }
  };

  return checkStatus();
};

// 完整的上传流程
const uploadAndProcess = async (kbId, file, title, onProgress) => {
  try {
    // 1. 上传文档
    const document = await uploadFile(kbId, file, title);
    console.log('文档上传成功:', document.id);

    // 2. 轮询处理状态
    const result = await pollDocumentStatus(document.id, onProgress);
    console.log('文档处理完成:', result);

    return result;
  } catch (error) {
    console.error('上传或处理失败:', error);
    throw error;
  }
};
```

### 查询知识库
```javascript
const queryKB = async (kbId, query) => {
  const data = {
    query: query,
    knowledge_base_id: kbId,
    top_k: 5,
    similarity_threshold: 0.7
  };
  const response = await api.post(`/api/knowledge/knowledge-bases/${kbId}/query/`, data);
  return response.data;
};
```

### 查看知识库内容
```javascript
const getKnowledgeBaseContent = async (kbId, options = {}) => {
  const params = new URLSearchParams({
    page: options.page || 1,
    page_size: options.pageSize || 20,
    status: options.status || 'completed',
    ...options.search && { search: options.search },
    ...options.documentType && { document_type: options.documentType }
  });

  const response = await api.get(`/api/knowledge/knowledge-bases/${kbId}/content/?${params}`);
  return response.data;
};

// 使用示例
const content = await getKnowledgeBaseContent('kb123', {
  page: 1,
  pageSize: 10,
  search: 'Django',
  documentType: 'pdf'
});
```

### 查看文档完整内容
```javascript
const getDocumentContent = async (docId, includeChunks = false) => {
  const params = new URLSearchParams({
    include_chunks: includeChunks,
    ...includeChunks && { chunk_page: 1, chunk_page_size: 10 }
  });

  const response = await api.get(`/api/knowledge/documents/${docId}/content/?${params}`);
  return response.data;
};

// 使用示例
const docContent = await getDocumentContent('doc123', true);
console.log('文档内容:', docContent.content);
console.log('分块数据:', docContent.chunks);
```

## 7. 注意事项

1. **认证**: 所有接口都需要JWT认证
2. **权限**: 用户只能访问自己项目的知识库，或使用管理员账户
3. **文档处理**:
   - 上传后**异步处理**，立即返回文档ID
   - 使用 `/documents/{id}/status/` 轮询处理状态
   - 处理时间取决于文档大小和复杂度
4. **超时处理**:
   - 文件上传建议设置30秒超时
   - 大文件可能需要更长时间
   - 使用状态轮询而不是长时间等待
5. **文件限制**: 最大100MB，支持PDF/Word/PPT/文本等格式
6. **查询优化**: 相似度阈值建议0.6-0.8，top_k建议3-10
7. **错误处理**: 注意处理401(未认证)、403(权限不足)、400(参数错误)、超时等状态码
8. **前端建议**:
   - 显示上传进度条
   - 实时显示处理状态
   - 处理失败时提供重试选项
