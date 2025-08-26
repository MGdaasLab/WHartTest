# CLAUDE.md

此文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 开发命令

- **启动开发服务器**: `npm run dev`
- **生产环境构建**: `npm run build` (包含 TypeScript 编译 vue-tsc)
- **预览生产构建**: `npm run preview`

## 项目架构

### 技术栈
- **前端**: Vue 3 + TypeScript + Vite
- **UI 框架**: Arco Design Vue
- **样式**: TailwindCSS + Wired Elements
- **状态管理**: Pinia
- **HTTP 客户端**: Axios
- **Markdown**: Marked + DOMPurify
- **工具库**: VueUse

### 后端集成
- Django 后端 API 地址: `http://localhost:8000`
- Vite 代理配置 `/api` 路由
- 基于 Token 的身份验证和路由守卫

### 项目结构
```
src/
├── features/           # 功能模块
│   ├── knowledge/      # 知识库管理
│   ├── langgraph/      # AI 聊天与 LLM 集成
│   ├── prompts/        # 提示词管理
│   └── requirements/   # 需求管理
├── components/         # 可复用组件
├── views/             # 页面级组件
├── services/          # API 服务层
├── store/             # Pinia 状态存储
├── router/            # Vue Router 配置
├── layouts/           # 布局组件
└── utils/             # 工具函数
```

### 核心功能
- **身份验证**: 基于 JWT 的路由守卫
- **多租户**: 组织和项目管理
- **测试管理**: 测试用例和模块管理
- **AI 集成**: LangGraph 聊天支持流式输出
- **知识库**: 文档上传和管理
- **需求管理**: 文档分析和评审报告

### 代码规范
- 使用 Composition API 和 `<script setup>`
- 按功能划分文件夹结构（而非按文件类型）
- 组件使用 PascalCase，组合式函数使用 camelCase
- 对象类型优先使用 TypeScript interface
- 函数式和声明式编程风格
- 组件超过 500 行时拆分为更小单元

### 身份验证流程
- 登录/注册路由为公开路由
- 其他路由需要身份验证 (`meta: { requiresAuth: true }`)
- 身份状态在 `authStore.ts` 中管理
- 路由守卫在 `router/index.ts` 中处理重定向

### API 集成
- `src/services/` 中的服务处理 API 调用
- Axios 配置基础 URL 和拦截器
- 通过 `authErrorHandler.ts` 处理错误
- `utils/request.ts` 中的请求工具

### 组件架构
- 大型组件拆分为小单元（参见 `features/langgraph/components/README.md`）
- 组件间通过 props 和 events 通信
- 使用 scoped 样式避免冲突
- 所有 props 和 events 使用 TypeScript 类型

### 状态管理
- Pinia 存储全局状态
- 功能特定的存储（auth、project）
- 组合式函数用于可复用逻辑

### 开发注意事项
- 修改前务必阅读整个文件
- 使用现有模式和库
- 遵循安全最佳实践
- 实现适当的加载和错误状态
- 使用环境变量进行配置