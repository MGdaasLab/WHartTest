---
title: 后端架构
---

# 后端架构 (WHartTest_Django)

后端基于 Django 和 Django REST Framework (DRF) 构建，是一个强大的 API 服务器，负责处理业务逻辑、数据持久化，并集成了先进的 AI 能力。

## 2.1. 技术选型

| 类别 | 技术 | 说明 |
| :--- | :--- | :--- |
| **核心框架** | Django & DRF | 提供了一个健壮、安全且可扩展的 Web API 开发框架。 |
| **数据库** | SQLite / PostgreSQL | 开发时使用 SQLite，生产环境推荐使用 PostgreSQL。 |
| **认证授权** | Simple JWT & API Key | 提供 JWT (JSON Web Token) 用于前端用户认证，同时支持 API Key 用于外部工具或服务的认证。 |
| **AI 引擎** | LangChain & LangGraph | 作为 AI 核心，用于构建和运行复杂的大语言模型 (LLM) 应用，如对话系统和测试用例生成。 |
| **知识库** | ChromaDB & HuggingFace | 使用 ChromaDB 作为向量数据库，结合 HuggingFace 的 `BGE-M3` 等嵌入模型，实现高效的 RAG (检索增强生成)。 |
| **API 文档** | drf-spectacular | 自动生成符合 OpenAPI 3.0 规范的 API 文档 (Swagger UI, ReDoc)。 |
| **异步任务** | (待定) | 可通过 Celery 等工具实现异步任务处理，如文档向量化。 |

## 2.2. 应用模块 (Apps)

项目采用模块化的设计，每个 Django App 负责一个明确的功能领域：

- **`accounts`**: 负责用户注册、登录和认证，基于 Django 内置的 `User` 模型。
- **`projects`**: 管理项目和项目成员，实现了项目级别的数据隔离和基于角色的访问控制 (Owner, Admin, Member)。
- **`testcases`**: 负责测试用例的 CRUD，支持多级模块、测试步骤和截图管理。
- **`knowledge`**: **知识库核心**。管理知识库、文档上传（支持 PDF, DOCX 等），并调用服务进行文档解析、分块和向量化，最终存入 ChromaDB。
- **`langgraph_integration`**: **AI 对话核心**。管理 LLM 配置，并提供与 LangGraph 交互的接口，实现 AI 对话、上下文管理和流式响应。
- **`mcp_tools`**: 负责与外部工具通过模型上下文协议 (MCP) 进行集成，管理远程 MCP 服务器配置。
- **`api_keys`**: 提供 API Key 的生成和管理功能，用于保护需要程序化访问的端点。
- **`prompts`**: (规划中) 用于管理和版本化与 LLM 交互的提示词。
- **`requirements`**: (规划中) 负责需求文档的管理和智能评审。

## 2.3. 核心机制

- **API 架构**:
  - **视图集 (ViewSets)**: 广泛使用 DRF 的 `ModelViewSet` 结合 `DefaultRouter` 快速构建遵循 RESTful 风格的 CRUD API。
  - **序列化器 (Serializers)**: `ModelSerializer` 用于模型的验证、数据转换和 JSON 格式化。
  - **统一响应格式**: 通过自定义的 `UnifiedResponseRenderer`，所有 API 响应都遵循 `{ "status": "success/error", "code": 200, "message": "...", "data": ... }` 的标准格式。
- **数据库模型**:
  - 核心模型包括 `Project`, `User`, `TestCase`, `KnowledgeBase`, `Document` 等。
  - 模型之间通过外键 (ForeignKey) 和多对多 (ManyToManyField) 关系构建了清晰的数据结构，例如：一个 `Project` 可以有多个 `TestCase` 和 `KnowledgeBase`。
- **认证与权限**:
  - **双重认证**: API 请求可以通过 `Authorization: Bearer <JWT>` 或 `Authorization: Api-Key <KEY>` 进行认证。
  - **分层权限**: 实现了基于 Django `ModelPermissions` 和项目角色的自定义权限系统。视图集会根据 `action` (如 `list`, `create`, `destroy`) 动态应用不同的权限检查，确保用户只能在授权范围内操作数据。
- **AI 与 RAG 集成**:
  - 当用户在 AI 对话中提问时，`langgraph_integration` 应用会接收请求。
  - 它会调用 `knowledge` 应用的服务，将问题向量化并在 ChromaDB 中检索相关的文档片段（Chunks）。
  - 检索到的上下文会与用户的原始问题、系统提示词一起被整合，并发送给 LangGraph 中定义的大语言模型。
  - LLM 基于增强的上下文生成更精准的回答，最终通过流式响应返回给前端。
