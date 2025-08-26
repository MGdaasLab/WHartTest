# 需求评审管理API文档

## 概述

需求评审管理模块提供了完整的需求文档管理和AI评审功能，类似传统需求评审会的数字化版本。

## 核心功能

### 🎯 主要特性
- ✅ **需求文档管理** - 支持多种格式文档上传和版本管理
- ✅ **AI智能拆分** - 自动识别功能模块边界
- ✅ **用户调整界面** - 支持手动优化AI拆分结果
- ✅ **专业评审分析** - 规范性、清晰度、完整性、一致性四维度评审
- ✅ **项目级隔离** - 基于项目权限的数据隔离
- ✅ **评审报告** - 专业的问题分级和改进建议

## API接口

### 基础URL
```
/api/requirements/
```

### 认证方式
JWT Bearer Token

## 1. 需求文档管理

### 1.1 获取文档列表
```http
GET /api/requirements/documents/
```

**查询参数**:
- `project`: 项目ID过滤
- `status`: 状态过滤 (uploaded, processing, module_split, user_reviewing, ready_for_review, reviewing, review_completed, failed)
- `document_type`: 文档类型 (pdf, docx, pptx, txt, md, html)
- `search`: 搜索关键词
- `ordering`: 排序字段

**响应示例**:
```json
{
  "status": "success",
  "code": 200,
  "data": {
    "count": 10,
    "results": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "用户管理系统需求文档",
        "description": "包含用户注册、登录、权限管理等功能需求",
        "document_type": "pdf",
        "status": "ready_for_review",
        "version": "1.0",
        "project": "project-uuid",
        "project_name": "电商平台",
        "uploader_name": "张三",
        "uploaded_at": "2024-01-20T10:00:00Z",
        "modules_count": 5
      }
    ]
  }
}
```

### 1.2 上传需求文档
```http
POST /api/requirements/documents/
Content-Type: multipart/form-data
```

**请求参数**:
```
title: 文档标题
description: 文档描述 (可选)
document_type: 文档类型
project: 项目ID
file: 文档文件 (与content二选一)
content: 文档内容 (与file二选一)
```

### 1.3 获取文档详情
```http
GET /api/requirements/documents/{id}/
```

**响应包含**:
- 文档基本信息
- 模块列表
- 评审报告列表
- 最新评审结果

### 1.4 AI智能模块拆分
```http
POST /api/requirements/documents/{id}/split-modules/
```

**功能**: AI自动识别文档中的功能模块边界

**响应示例**:
```json
{
  "status": "success",
  "message": "AI模块拆分完成",
  "data": {
    "modules": [
      {
        "id": "module-uuid",
        "title": "用户管理模块",
        "content": "用户注册、登录、权限管理相关需求...",
        "start_page": 1,
        "end_page": 3,
        "order": 1,
        "confidence_score": 0.85,
        "is_auto_generated": true
      }
    ],
    "status": "user_reviewing"
  }
}
```

### 1.5 用户调整模块拆分
```http
PUT /api/requirements/documents/{id}/adjust-modules/
```

**请求体**:
```json
{
  "modules": [
    {
      "title": "用户管理模块",
      "content": "调整后的模块内容...",
      "start_page": 1,
      "end_page": 4,
      "order": 1
    }
  ]
}
```

### 1.6 开始需求评审
```http
POST /api/requirements/documents/{id}/start-review/
```

**请求体**:
```json
{
  "analysis_type": "comprehensive",
  "parallel_processing": true,
  "priority_modules": ["module-uuid-1"],
  "custom_requirements": "重点关注数据安全相关需求"
}
```

**响应**:
```json
{
  "status": "success",
  "data": {
    "message": "评审任务已启动",
    "task_id": "task-uuid",
    "report_id": "report-uuid",
    "estimated_duration": "5-10分钟"
  }
}
```

### 1.7 查询评审进度
```http
GET /api/requirements/documents/{id}/review-progress/
```

**响应示例**:
```json
{
  "status": "success",
  "data": {
    "task_id": "task-uuid",
    "overall_progress": 80,
    "status": "running",
    "current_step": "正在分析订单管理模块...",
    "estimated_remaining_time": "2分钟",
    "modules_progress": [
      {
        "module_name": "用户管理模块",
        "status": "completed",
        "progress": 100,
        "issues_found": 3
      }
    ]
  }
}
```

## 2. 评审报告管理

### 2.1 获取评审报告列表
```http
GET /api/requirements/reports/
```

### 2.2 获取评审报告详情
```http
GET /api/requirements/reports/{id}/
```

**响应包含**:
- 评审概览信息
- 问题列表 (按优先级分类)
- 模块评审结果
- 改进建议

## 3. 评审问题管理

### 3.1 获取问题列表
```http
GET /api/requirements/issues/
```

**查询参数**:
- `report`: 报告ID
- `module`: 模块ID
- `issue_type`: 问题类型 (specification, clarity, completeness, consistency, feasibility)
- `priority`: 优先级 (high, medium, low)
- `is_resolved`: 是否已解决

### 3.2 标记问题已解决
```http
PATCH /api/requirements/issues/{id}/
```

```json
{
  "is_resolved": true,
  "resolution_note": "已在v1.1版本中修复"
}
```

## 4. 权限控制

### 权限层级
1. **项目成员** - 可查看项目内的需求文档和评审报告
2. **文档上传者** - 可编辑自己上传的文档
3. **项目管理员** - 可管理项目内所有需求文档
4. **超级管理员** - 拥有所有权限

### 数据隔离
- 所有数据按项目隔离
- 用户只能访问自己是成员的项目的数据
- 支持多角色协作评审

## 5. 状态流转

```
uploaded → module_split → user_reviewing → ready_for_review → reviewing → review_completed
    ↓
  failed (任何阶段都可能失败)
```

## 6. 支持的文档格式

- PDF (.pdf)
- Word文档 (.docx)
- PowerPoint (.pptx)
- 文本文件 (.txt)
- Markdown (.md)
- HTML (.html)

## 7. 错误码说明

- `400` - 请求参数错误或文档状态不允许操作
- `401` - 未认证
- `403` - 权限不足
- `404` - 资源不存在
- `500` - 服务器内部错误

## 8. 使用示例

### 完整的需求评审流程

```javascript
// 1. 上传需求文档
const uploadResponse = await fetch('/api/requirements/documents/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN'
  },
  body: formData
});

// 2. AI模块拆分
const splitResponse = await fetch(`/api/requirements/documents/${docId}/split-modules/`, {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN'
  }
});

// 3. 用户调整模块 (可选)
const adjustResponse = await fetch(`/api/requirements/documents/${docId}/adjust-modules/`, {
  method: 'PUT',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ modules: adjustedModules })
});

// 4. 开始评审
const reviewResponse = await fetch(`/api/requirements/documents/${docId}/start-review/`, {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ analysis_type: 'comprehensive' })
});

// 5. 查询进度
const progressResponse = await fetch(`/api/requirements/documents/${docId}/review-progress/`, {
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN'
  }
});
```

这就是需求评审管理模块的完整API文档！🚀
