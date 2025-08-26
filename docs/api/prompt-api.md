# 提示词管理API文档

## 概述

提示词管理系统提供用户级别的提示词管理功能，支持创建、编辑、删除和管理个人提示词。每个用户可以设置默认提示词，在AI对话中会优先使用用户的提示词。

## 基础信息

- **基础URL**: `/api/prompts/`
- **认证方式**: JWT Bearer Token
- **响应格式**: 统一JSON响应格式

## 提示词优先级机制

系统采用智能提示词优先级机制：
```
用户指定提示词 > 用户默认提示词 > 全局LLM配置 > 无提示词
```

1. **用户指定提示词**: 在对话API中通过`prompt_id`参数指定
2. **用户默认提示词**: 用户设置的默认提示词
3. **全局LLM配置**: 管理员配置的system_prompt
4. **无提示词**: 使用模型默认行为

## API接口列表

### 1. 获取用户提示词列表

**接口**: `GET /api/prompts/user-prompts/`

**描述**: 获取当前用户的所有提示词列表，支持分页、搜索和过滤。

**请求参数**:
```
Query Parameters:
- page: 页码 (可选, 默认: 1)
- page_size: 每页数量 (可选, 默认: 20)
- search: 搜索关键词 (可选, 搜索名称和描述)
- is_default: 是否为默认提示词 (可选, true/false)
- is_active: 是否启用 (可选, true/false)
- ordering: 排序字段 (可选, 如: -created_at, name)
```

**响应示例**:
```json
{
  "status": "success",
  "code": 200,
  "message": "操作成功",
  "data": {
    "count": 5,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": 1,
        "name": "技术专家",
        "description": "专业技术问答提示词",
        "is_default": true,
        "is_active": true,
        "created_at": "2025-07-02T10:30:00Z",
        "updated_at": "2025-07-02T10:30:00Z"
      }
    ]
  },
  "errors": null
}
```

### 2. 获取默认提示词

**接口**: `GET /api/prompts/user-prompts/default/`

**描述**: 获取当前用户的默认提示词。

**响应示例**:
```json
{
  "status": "success",
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 1,
    "name": "技术专家",
    "content": "你是一个资深的技术专家...",
    "description": "专业技术问答提示词",
    "is_default": true,
    "is_active": true,
    "created_at": "2025-07-02T10:30:00Z",
    "updated_at": "2025-07-02T10:30:00Z"
  },
  "errors": null
}
```

**无默认提示词时**:
```json
{
  "status": "success",
  "code": 200,
  "message": "用户暂无默认提示词",
  "data": null,
  "errors": null
}
```

### 3. 获取单个提示词详情

**接口**: `GET /api/prompts/user-prompts/{id}/`

**描述**: 获取指定提示词的详细信息。

**路径参数**:
- `id`: 提示词ID

**响应示例**:
```json
{
  "status": "success",
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 1,
    "name": "技术专家",
    "content": "你是一个资深的技术专家，专门解答编程、架构和技术问题。请用专业但易懂的语言回答。",
    "description": "专业技术问答提示词",
    "is_default": true,
    "is_active": true,
    "created_at": "2025-07-02T10:30:00Z",
    "updated_at": "2025-07-02T10:30:00Z"
  },
  "errors": null
}
```

### 4. 创建新提示词

**接口**: `POST /api/prompts/user-prompts/`

**描述**: 创建新的用户提示词。

**请求体**:
```json
{
  "name": "创意助手",
  "content": "你是一个富有创意的助手，擅长头脑风暴、创意写作和艺术创作。",
  "description": "创意写作提示词",
  "is_default": false,
  "is_active": true
}
```

**字段说明**:
- `name`: 提示词名称 (必填, 2-255字符, 用户内唯一)
- `content`: 提示词内容 (必填, 10-10000字符)
- `description`: 描述 (可选)
- `is_default`: 是否设为默认 (可选, 默认false)
- `is_active`: 是否启用 (可选, 默认true)

**响应示例**:
```json
{
  "status": "success",
  "code": 201,
  "message": "操作成功",
  "data": {
    "id": 2,
    "name": "创意助手",
    "content": "你是一个富有创意的助手...",
    "description": "创意写作提示词",
    "is_default": false,
    "is_active": true,
    "created_at": "2025-07-02T11:00:00Z",
    "updated_at": "2025-07-02T11:00:00Z"
  },
  "errors": null
}
```

### 5. 更新提示词

**接口**: `PUT /api/prompts/user-prompts/{id}/` 或 `PATCH /api/prompts/user-prompts/{id}/`

**描述**: 更新指定的提示词信息。

**路径参数**:
- `id`: 提示词ID

**请求体** (PATCH支持部分更新):
```json
{
  "name": "高级技术专家",
  "content": "你是一个资深的高级技术专家...",
  "description": "更新后的描述"
}
```

**响应示例**:
```json
{
  "status": "success",
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 1,
    "name": "高级技术专家",
    "content": "你是一个资深的高级技术专家...",
    "description": "更新后的描述",
    "is_default": true,
    "is_active": true,
    "created_at": "2025-07-02T10:30:00Z",
    "updated_at": "2025-07-02T11:15:00Z"
  },
  "errors": null
}
```

### 6. 删除提示词

**接口**: `DELETE /api/prompts/user-prompts/{id}/`

**描述**: 删除指定的提示词。

**路径参数**:
- `id`: 提示词ID

**响应示例**:
```json
{
  "status": "success",
  "code": 200,
  "message": "删除操作成功完成",
  "data": null,
  "errors": null
}
```

### 7. 设置默认提示词

**接口**: `POST /api/prompts/user-prompts/{id}/set_default/`

**描述**: 将指定提示词设置为用户的默认提示词。

**路径参数**:
- `id`: 提示词ID

**响应示例**:
```json
{
  "status": "success",
  "code": 200,
  "message": "默认提示词设置成功",
  "data": {
    "id": 2,
    "name": "创意助手",
    "content": "你是一个富有创意的助手...",
    "description": "创意写作提示词",
    "is_default": true,
    "is_active": true,
    "created_at": "2025-07-02T11:00:00Z",
    "updated_at": "2025-07-02T11:20:00Z"
  },
  "errors": null
}
```

### 8. 清除默认提示词设置

**接口**: `POST /api/prompts/user-prompts/clear_default/`

**描述**: 清除用户的默认提示词设置。

**响应示例**:
```json
{
  "status": "success",
  "code": 200,
  "message": "已清除默认提示词设置，影响1条记录",
  "data": {
    "updated_count": 1
  },
  "errors": null
}
```

### 9. 复制提示词

**接口**: `POST /api/prompts/user-prompts/{id}/duplicate/`

**描述**: 复制指定的提示词，创建一个副本。

**路径参数**:
- `id`: 要复制的提示词ID

**响应示例**:
```json
{
  "status": "success",
  "code": 201,
  "message": "提示词复制成功",
  "data": {
    "id": 3,
    "name": "技术专家 (副本)",
    "content": "你是一个资深的技术专家...",
    "description": "复制自: 专业技术问答提示词",
    "is_default": false,
    "is_active": true,
    "created_at": "2025-07-02T11:25:00Z",
    "updated_at": "2025-07-02T11:25:00Z"
  },
  "errors": null
}
```

## 在对话中使用提示词

### 对话API集成

在现有的对话API中，新增了`prompt_id`参数来指定使用的提示词。**重要：所有原有参数保持不变，完全向后兼容。**

#### 标准对话接口

**接口**: `POST /api/langgraph/chat/`

**完整参数列表**:
```json
{
  // 必填参数
  "message": "请帮我解释一下微服务架构",     // string, 用户消息
  "project_id": "project123",            // string, 项目ID

  // 可选参数
  "session_id": "session456",            // string, 会话ID
  "prompt_id": 2,                        // 🆕 integer, 指定提示词ID

  // 知识库参数（原有功能）
  "knowledge_base_id": "kb789",          // string, 知识库ID
  "use_knowledge_base": true,            // boolean, 是否使用知识库
  "similarity_threshold": 0.7,           // float, 相似度阈值
  "top_k": 5                             // integer, 检索数量
}
```

#### 流式对话接口

**接口**: `POST /api/langgraph/chat/stream/`

**参数**: 与标准对话接口完全相同，支持所有参数包括`prompt_id`

#### 提示词优先级机制

```
1. 用户指定提示词 (prompt_id参数)     ← 最高优先级
   ↓
2. 用户默认提示词 (is_default=true)
   ↓
3. 全局LLM配置 (system_prompt)
   ↓
4. 无提示词 (使用模型默认行为)        ← 最低优先级
```

#### 使用场景示例

**场景1: 普通对话（使用默认提示词）**
```json
{
  "message": "你好",
  "project_id": "project123"
}
```

**场景2: 指定技术专家提示词**
```json
{
  "message": "请设计一个微服务架构",
  "project_id": "project123",
  "prompt_id": 2
}
```

**场景3: 结合知识库和提示词**
```json
{
  "message": "Django有什么特点？",
  "project_id": "project123",
  "prompt_id": 2,
  "knowledge_base_id": "django_docs",
  "use_knowledge_base": true
}
```

> 📖 **详细集成指南**: 请参考 `docs/prompts_chat_integration.md` 获取完整的前后端集成示例和最佳实践。

## 错误响应

### 常见错误码

**400 Bad Request**:
```json
{
  "status": "error",
  "code": 400,
  "message": "请求参数有误或处理失败",
  "data": null,
  "errors": {
    "name": ["提示词名称不能为空"],
    "content": ["提示词内容至少需要10个字符"]
  }
}
```

**401 Unauthorized**:
```json
{
  "status": "error",
  "code": 401,
  "message": "认证失败",
  "data": null,
  "errors": {
    "detail": "未提供认证凭据"
  }
}
```

**404 Not Found**:
```json
{
  "status": "error",
  "code": 404,
  "message": "请求的资源不存在",
  "data": null,
  "errors": {
    "detail": "未找到"
  }
}
```

## 使用示例

### JavaScript/Fetch示例

```javascript
// 获取提示词列表
const getPrompts = async () => {
  const response = await fetch('/api/prompts/user-prompts/', {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  return response.json();
};

// 创建新提示词
const createPrompt = async (promptData) => {
  const response = await fetch('/api/prompts/user-prompts/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(promptData)
  });
  return response.json();
};

// 在对话中使用指定提示词
const chatWithPrompt = async (message, projectId, promptId) => {
  const response = await fetch('/api/langgraph/chat/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      message,
      project_id: projectId,
      prompt_id: promptId
    })
  });
  return response.json();
};
```

### Python/Requests示例

```python
import requests

# 设置认证头
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# 获取默认提示词
response = requests.get(
    'http://localhost:8000/api/prompts/user-prompts/default/',
    headers=headers
)
default_prompt = response.json()

# 创建新提示词
prompt_data = {
    'name': '数据分析师',
    'content': '你是一个专业的数据分析师，擅长数据处理和可视化。',
    'description': '数据分析专用提示词',
    'is_default': False,
    'is_active': True
}

response = requests.post(
    'http://localhost:8000/api/prompts/user-prompts/',
    headers=headers,
    json=prompt_data
)
new_prompt = response.json()
```

## 注意事项

1. **权限控制**: 用户只能管理自己的提示词，无法访问其他用户的提示词
2. **默认提示词**: 每个用户只能有一个默认提示词，设置新默认时会自动取消原默认
3. **名称唯一性**: 提示词名称在同一用户内必须唯一
4. **内容验证**: 提示词内容不能为空，且有长度限制
5. **软删除**: 删除提示词是硬删除，请谨慎操作
6. **对话兼容**: 不指定prompt_id时，系统会自动使用用户默认提示词或全局配置
