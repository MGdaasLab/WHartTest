# 知识库API接口更新说明

## 📋 更新概览

根据新的知识库API接口文档，已完成以下更新：

### 1. 🔧 类型定义更新 (`src/features/knowledge/types/knowledge.ts`)

#### 主要变更：
- **知识库对象 (`KnowledgeBase`)**：
  - `project` 字段类型从 `string` 改为 `number`
  - 移除了 `vector_store_type` 字段（系统只支持Chroma）

- **查询响应 (`QueryResponse`)**：
  - 移除了 `answer`、`retrieval_time`、`generation_time`、`total_time` 字段
  - 新增了 `total_results` 字段
  - 新增了 `knowledge_base` 对象字段
  - 更新了 `QuerySource` 结构，新增 `document_title`、`document_id`、`chunk_id` 字段

- **新增系统状态类型 (`SystemStatusResponse`)**：
  - 包含嵌入模型状态、依赖库状态、向量存储状态等信息

### 2. 🛠️ 服务层更新 (`src/features/knowledge/services/knowledgeService.ts`)

#### 主要变更：
- **更新 `ApiResponse` 格式**：适配实际的API响应格式，包含 `status`、`code`、`message`、`data`、`errors` 字段
- **新增系统状态检查接口**：`getSystemStatus()`
- **更新查询参数**：知识库列表接口新增 `embedding_model` 参数支持

#### 实际的API响应格式：
```typescript
interface ApiResponse<T> {
  status: 'success' | 'error';
  code: number;
  message: string;
  data: T;
  errors?: any;
}
```

### 3. 🎨 组件更新

#### 知识库详情组件 (`src/features/knowledge/components/KnowledgeBaseDetail.vue`)
- **查询结果显示更新**：
  - 移除了回答、时间统计显示
  - 新增了查询内容、结果数量、知识库信息显示
  - 更新了来源信息显示格式

#### 知识库管理视图 (`src/features/knowledge/views/KnowledgeManagementView.vue`)
- **项目ID类型处理**：修复了项目ID比较的类型问题
- **新增系统状态检查按钮**：在页面头部添加了系统状态检查功能

#### 新增系统状态弹窗 (`src/features/knowledge/components/SystemStatusModal.vue`)
- **完整的系统状态展示**：
  - 嵌入模型状态（模型名称、状态、维度等）
  - 依赖库状态（各种Python包的安装状态）
  - 向量存储状态（知识库数量、缓存状态等）

### 4. ⚙️ 配置更新 (`src/config/api.ts`)

#### 新增端点：
```typescript
KNOWLEDGE: {
  KNOWLEDGE_BASES: '/knowledge/knowledge-bases/',
  SYSTEM_STATUS: '/knowledge/knowledge-bases/system_status/', // 新增
  DOCUMENTS: '/knowledge/documents/',
  CHUNKS: '/knowledge/chunks/',
  QUERY_LOGS: '/knowledge/query-logs/',
  RAG: '/lg/knowledge/rag/',
}
```

## 🔄 API接口变更对比

### 响应格式说明

#### 实际的API响应格式：
```json
{
  "status": "success",
  "code": 200,
  "message": "操作成功",
  "data": [
    {
      "id": "5cefbc6b-c4f9-4326-a123-24295e3d83de",
      "name": "1324134",
      "description": "",
      "project": 3,
      "project_name": "演示项目",
      "creator": 2,
      "creator_name": "duanxc",
      "is_active": true,
      "embedding_model": "BAAI/bge-m3",
      "chunk_size": 1000,
      "chunk_overlap": 200,
      "document_count": 0,
      "chunk_count": 0,
      "created_at": "2025-06-06T14:26:04.310323+08:00",
      "updated_at": "2025-06-06T14:26:04.311280+08:00"
    }
  ],
  "errors": null
}
```

### 查询响应变更

#### 之前的格式：
```json
{
  "query": "查询内容",
  "answer": "AI生成的回答",
  "sources": [...],
  "retrieval_time": 0.5,
  "generation_time": 1.2,
  "total_time": 1.7
}
```

#### 现在的格式：
```json
{
  "query": "查询内容",
  "sources": [
    {
      "content": "内容",
      "similarity_score": 0.85,
      "document_title": "文档标题",
      "document_id": "doc-id",
      "chunk_id": "chunk-id",
      "metadata": { ... }
    }
  ],
  "total_results": 3,
  "knowledge_base": {
    "id": "kb-id",
    "name": "知识库名称"
  }
}
```

## 🆕 新增功能

### 1. 系统状态检查
- **接口**：`GET /api/knowledge/knowledge-bases/system_status/`
- **功能**：检查嵌入模型、依赖库、向量存储等系统组件状态
- **UI**：在知识库管理页面添加"系统状态"按钮

### 2. 增强的查询结果展示
- 显示文档标题和相似度
- 显示查询结果总数
- 显示所属知识库信息

## 🧪 测试

创建了测试文件 `src/test-knowledge-api.ts`，包含：
- 系统状态检查测试
- 知识库列表获取测试
- 知识库查询测试
- 知识库创建和删除测试
- 响应格式验证

## 🔧 兼容性处理

代码中保留了对旧格式的兼容性处理：
```typescript
// 检查返回的数据格式
if (data && typeof data === 'object' && 'results' in data) {
  // 分页响应格式
  knowledgeBases.value = data.results;
  pagination.value.total = data.count;
} else if (Array.isArray(data)) {
  // 数组格式（向后兼容）
  knowledgeBases.value = data;
  pagination.value.total = data.length;
}
```

## 📝 注意事项

1. **项目ID类型**：确保项目ID在前端正确处理为 `number` 类型
2. **API响应格式**：实际API返回包装格式，包含 `status`、`code`、`message`、`data`、`errors` 字段
3. **查询功能**：新的查询响应不包含AI生成的回答，只返回相关文档片段
4. **系统状态**：新增的系统状态检查可以帮助诊断知识库系统的健康状况

## ✅ 验证清单

- [x] 类型定义更新完成
- [x] 服务层API调用更新完成
- [x] 组件UI适配完成
- [x] 新增系统状态检查功能
- [x] TypeScript编译检查通过
- [x] 保持向后兼容性
- [x] 创建测试文件验证功能

所有更新已完成，系统现在完全适配新的知识库API接口格式！🎉
