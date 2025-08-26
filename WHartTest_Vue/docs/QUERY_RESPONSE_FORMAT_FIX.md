# 知识库查询响应格式修正

## 📋 问题发现

在测试知识库查询功能时，发现实际的API响应格式与之前定义的类型不匹配。

### 实际的查询API响应：
```json
{
  "status": "success",
  "code": 200,
  "message": "操作成功",
  "data": {
    "query": "用户",
    "answer": "基于查询「用户」检索到的相关内容：\n\n用户用户用户用户用户用户",
    "sources": [
      {
        "content": "用户用户用户用户用户用户",
        "metadata": {
          "title": "注册用户",
          "file_path": "D:\\Google\\WHartTest_django\\media\\knowledge_bases\\5cefbc6b-c4f9-4326-a123-24295e3d83de\\documents\\注册用户.txt",
          "source": "注册用户",
          "document_type": "txt",
          "document_id": "c67cd6a7-304c-475f-8f7c-cc11d147da35"
        },
        "similarity_score": 0.9109437763690948
      }
    ],
    "retrieval_time": 0.5057508945465088,
    "generation_time": 0,
    "total_time": 0.5107424259185791
  },
  "errors": null
}
```

## 🔧 修正内容

### 1. 更新 `QueryResponse` 类型定义

```typescript
// 修正后的查询响应接口
export interface QueryResponse {
  query: string;
  answer: string;                    // ✅ 恢复 answer 字段
  sources: QuerySource[];
  retrieval_time: number;            // ✅ 恢复时间统计字段
  generation_time: number;
  total_time: number;
}
```

### 2. 更新 `QuerySource` 类型定义

```typescript
// 修正后的查询来源接口
export interface QuerySource {
  content: string;
  similarity_score: number;
  metadata: {
    title: string;                   // ✅ 文档标题
    file_path: string;               // ✅ 文件路径
    source: string;                  // ✅ 来源
    document_type: string;           // ✅ 文档类型
    document_id: string;             // ✅ 文档ID
    page?: number;                   // ✅ 页码（可选）
    [key: string]: any;
  };
}
```

### 3. 更新查询结果显示组件

恢复了完整的查询结果显示，包括：

- **查询内容**：显示用户输入的查询文本
- **AI回答**：显示基于检索内容生成的回答
- **相关内容**：显示检索到的文档片段
- **时间统计**：显示检索时间、生成时间和总时间

```vue
<div class="result-content">
  <div class="query-info">
    <strong>查询内容:</strong>
    <p>{{ queryResult.query }}</p>
  </div>
  <div class="answer" v-if="queryResult.answer">
    <strong>回答:</strong>
    <p>{{ queryResult.answer }}</p>
  </div>
  <div class="sources">
    <strong>相关内容 ({{ queryResult.sources.length }} 条结果):</strong>
    <div v-for="(source, index) in queryResult.sources" :key="index" class="source-item">
      <div class="source-content">{{ source.content }}</div>
      <div class="source-meta">
        <span>文档: {{ source.metadata.title }}</span> |
        <span>相似度: {{ (source.similarity_score * 100).toFixed(1) }}%</span>
        <span v-if="source.metadata.page"> | 页码: {{ source.metadata.page }}</span>
      </div>
    </div>
  </div>
  <div class="timing">
    <small>
      检索时间: {{ queryResult.retrieval_time.toFixed(2) }}s |
      生成时间: {{ queryResult.generation_time.toFixed(2) }}s |
      总时间: {{ queryResult.total_time.toFixed(2) }}s
    </small>
  </div>
</div>
```

## 📝 修正文件

- `src/features/knowledge/types/knowledge.ts` - 类型定义
- `src/features/knowledge/components/KnowledgeBaseDetail.vue` - 查询结果显示
- `src/test-knowledge-api.ts` - 测试文件

## ✅ 修正验证

- [x] 更新了 `QueryResponse` 和 `QuerySource` 类型定义
- [x] 恢复了完整的查询结果显示功能
- [x] 更新了CSS样式以支持所有显示元素
- [x] TypeScript编译检查通过
- [x] 更新了测试文件以验证新格式

## 🎯 功能特性

### 查询结果包含：

1. **智能回答**：基于检索内容生成的AI回答
2. **原始内容**：检索到的相关文档片段
3. **元数据信息**：文档标题、类型、相似度等
4. **性能统计**：检索时间、生成时间、总时间

### 用户体验：

- 清晰的信息层次结构
- 详细的相似度和时间统计
- 完整的文档来源信息
- 响应式的查询结果展示

## 📊 API响应结构说明

```
查询响应
├── query (查询文本)
├── answer (AI生成的回答)
├── sources[] (相关内容数组)
│   ├── content (文档内容片段)
│   ├── similarity_score (相似度分数)
│   └── metadata (元数据)
│       ├── title (文档标题)
│       ├── source (来源)
│       ├── document_type (文档类型)
│       ├── document_id (文档ID)
│       └── file_path (文件路径)
├── retrieval_time (检索时间)
├── generation_time (生成时间)
└── total_time (总时间)
```

现在知识库查询功能完全适配实际的API响应格式，提供了完整的查询体验！🎉
