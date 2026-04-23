# 项目介绍

**WHartTest** （/wɑːtest/）是由 **山东麦港数据系统有限公司** 旗下**麦港实验室（MGdaas Lab）** 推出的开源项目，隶属于 **WHart** 系列。该系列聚焦于为开源社区贡献优质产品与组件，旨在通过技术共享赋能行业生态，推动相关领域的技术创新与应用发展。

**WHartTest** 是基于 **Django 5.2 + DRF** 与现代大模型技术打造的 **AI 驱动智能测试平台**。平台采用前后端分离的 Monorepo 架构，由 6 个子项目组成，聚合自然语言理解、知识库检索与嵌入搜索能力，结合 **LangChain/LangGraph** 与 **MCP（Model Context Protocol）** 工具调用，实现从需求到可执行测试用例的自动化生成、管理与执行，帮助测试团队提升效率与覆盖率。

## 架构总览

| 子项目 | 技术栈 | 说明 |
|---|---|---|
| `WHartTest_Django` | Django 5.2 + DRF + Celery + LangChain/LangGraph + Channels | 后端 API 服务 |
| `WHartTest_Vue` | Vue 3 + TypeScript + Vite + Arco Design Vue + TailwindCSS | 前端 SPA |
| `WHartTest_Actuator` | Python + Playwright (async) + WebSocket | UI 自动化执行器 |
| `WHartTest_MCP` | Python + FastMCP | MCP 工具服务 |
| `WHartTest_Skills` | 多技术栈（Python/Node.js） | 可扩展 Agent 技能库 |
| `docx-editor` | Django + Vue 3 + ONLYOFFICE | 在线文档编辑器 |

**依赖关系：**
```
WHartTest_Vue (前端 SPA)
  ↓ REST API + WebSocket
WHartTest_Django (后端核心)
  ├── ↔ Redis (Celery Broker / Cache)
  ├── → PostgreSQL (关系数据)
  ├── → Qdrant (向量存储)
  ├── ↔ WHartTest_MCP (MCP 工具，streamable-http)
  ├── ↔ WHartTest_Actuator (WebSocket 双向通信)
  ├── ↔ docx-editor (iframe 嵌入)
  └── → 外部 LLM API (OpenAI/Azure/Ollama/Xinference)
```

## 核心功能

### AI 智能测试用例生成
基于大语言模型（LLM）技术，实现从需求到测试用例的智能转化：
- **多源输入**：支持需求文档、AI 对话、知识库检索等多种输入方式
- **结构化输出**：自动生成包含测试步骤、前置条件、输入数据、期望结果、优先级（P0-P3）的完整用例
- **流式对话**：LangGraph 驱动的流式 AI 对话，支持上下文摘要压缩与 Token 用量统计
- **多模型支持**：OpenAI、Azure OpenAI、Ollama、Xinference 等 OpenAI 兼容格式 LLM

### 智能编排（Orchestrator）
AI 驱动的端到端测试生成流水线：
- **需求→知识库检索→AI 分析→测试用例生成**的自动化编排
- 交互式执行计划，支持 Agent Loop 分步执行
- 人工审批中间件（HITL），关键节点可人工介入

### 知识库管理与文档理解
构建项目级知识库，为 AI 生成提供精准上下文：
- **多格式支持**：PDF、Word、Excel、PPT、Markdown、网页链接
- **智能分块**：RecursiveCharacterTextSplitter 文档分块，支持图片提取（PDF 用 PyMuPDF，DOCX 用 python-docx）
- **混合检索**：Dense + BM25 Sparse 稀疏-稠密混合检索 + RRF 融合排序
- **Reranker 精排**：可配置重排序模型提升检索精度
- **多模态嵌入**：支持文档图片的多模态向量化

### MCP 工具集成
通过 Model Context Protocol 实现 AI 与测试工具的无缝对接：
- **远程服务管理**：streamable-http、SSE 等传输协议，支持多服务器配置
- **工具发现与同步**：自动从 MCP 服务器发现并同步可用工具
- **HITL 人工审批**：工具级别的敏感操作人工确认机制
- **内置工具集**：WHartTest 自身 MCP 工具（项目/模块/用例 CRUD）及第三方平台集成

### 需求评审与风险分析
AI 驱动的需求质量评估，提前识别潜在风险：
- **六维评分体系**：完整度、清晰度、一致性、可测性、可行性、逻辑性
- **状态流转**：上传→处理→模块拆分→用户调整→待评审→评审中→完成
- **专项分析报告**：8 种分析维度的独立报告（通用对话/完整性/一致性/可测性/可行性/清晰度/逻辑性/图表生成）
- **在线文档编辑**：集成 ONLYOFFICE 文档编辑器，支持 AI 补全与 AI 分析插件

### 测试用例管理
全生命周期的测试用例管理能力：
- **5 级模块树**：灵活的用例组织结构
- **7 种测试类型**：覆盖功能、接口、性能、安全等测试场景
- **用例审核**：待审核、通过、优化、不可用等状态流转
- **测试套件**：灵活组合用例，支持并发执行配置
- **Excel 导入/导出**：可配置字段映射的模板系统，支持多种步骤解析模式
- **批量操作**：用例的批量创建、编辑、移动、删除

### UI 自动化测试
低代码 UI 自动化，降低自动化测试门槛：
- **可视化编排**：5 级模块 → 页面管理 → 元素定位 → 步骤编排 → 用例组装
- **9 种定位策略**：CSS、XPath、Text、Role、Label、Placeholder、AltText、Title、TestId
- **6 种步骤类型**：元素操作、断言、SQL 查询、自定义变量、条件判断、Python 代码
- **多浏览器支持**：Chromium / Firefox / WebKit，支持持久化浏览器上下文
- **Trace 追踪**：完整的截图、Trace 录制与回放

### APP 自动化测试
集成 mobile-mcp，支持移动端应用自动化测试：
- **多平台支持**：Android、iOS 设备自动化
- **元素交互**：点击、滑动、输入、手势操作
- **屏幕操作**：截图、录屏、亮度/音量调节

### Skill 智能技能系统
可扩展的 Agent 技能管理框架：
- **多来源导入**：ZIP 文件上传、Git 仓库导入
- **SKILL.md 规范**：标准化的技能描述文件
- **内置技能**：浏览器自动化（Playwright/agent-browser）、图表生成（Draw.io）、知识库查询、平台 CLI 工具
- **安全隔离**：技能文件独立存储，防止路径穿越攻击

### UI 自动化执行器（Actuator）
独立部署的测试执行客户端：
- 通过 WebSocket 与后端实时双向通信
- Playwright 异步执行引擎，支持 Trace 录制与截图回传
- 支持 PyInstaller 打包为 Windows EXE 桌面客户端
- 自动重连、变量替换、参数化数据处理

### 任务中心
定时/周期任务调度：
- **4 种调度策略**：一次性 / 每小时 / 每天 / 每周
- 关联 UI 自动化或测试套件执行
- 失败重试策略，基于 Celery Beat 数据库调度器

### 项目与权限管理
- 多项目隔离，项目级 RBAC（Owner / Admin / Member）
- JWT + API Key 双认证模式
- 项目凭据管理（被测系统地址/账密）

### 微信集成
- 扫码登录会话管理
- 微信机器人账号绑定与消息转发

## 技术栈

| 层级 | 技术 |
|------|------|
| **后端框架** | Django 5.2、Django REST Framework、Daphne (ASGI)、Channels (WebSocket) |
| **任务调度** | Celery + Redis Broker + django-celery-beat |
| **AI/LLM** | LangChain、LangGraph、多种 LLM (OpenAI/Azure/Ollama/Xinference)、多种嵌入服务 |
| **向量存储** | Qdrant (Dense + BM25 Sparse 混合检索) |
| **关系数据库** | PostgreSQL |
| **缓存/消息** | Redis |
| **前端框架** | Vue 3 (Composition API) + TypeScript + Vite |
| **前端 UI** | Arco Design Vue + TailwindCSS |
| **状态管理** | Pinia |
| **自动化引擎** | Playwright (async，Chromium/Firefox/WebKit) |
| **文档编辑** | ONLYOFFICE Document Server |
| **MCP 协议** | FastMCP (streamable-http/SSE) |
| **部署** | Docker Compose、Supervisor |

## 快速上手

1. 克隆仓库并进入项目根目录：
   ```bash
   git clone https://github.com/MGdaasLab/WHartTest.git
   cd WHartTest
   ```
2. 使用 Docker Compose 启动所有服务：
   ```bash
   docker-compose up -d
   ```
3. 等待服务启动完成后，访问以下地址：
   - 前端界面：http://localhost:8913
   - 默认管理员账号：admin / admin123456
4. 如需自定义配置（如数据库密码、管理员账号等），请在项目根目录创建 `.env` 文件进行设置。

> 详细配置与部署说明请参阅根目录 README。

## 界面与功能预览

### 登录页面
![登录页面](/img/image-a1.png)

### 知识库管理
![知识库管理](/img/image-a18.png)

### AI 对话与测试用例生成
![AI 对话与测试用例生成](/img/image-a6.png)

### 测试用例管理
![测试用例管理](/img/image-a7.png)

### 生成用例详情
![生成用例详情](/img/image-a8.png)

### 测试执行与自动截屏
![测试执行](/img/image-a19.png)
![自动截屏](/img/image-a20.png)

### UI 自动化测试
![执行结果](/img/image-a22.png)
![报告详情](/img/image-a23.png)

### AI 驱动的需求评审与报告
![AI 需求评审](/img/image-a15.png)
![报告打分与建议](/img/image-a5.png)

（更多细节、API 与部署说明请查阅仓库中的 docs 目录及各模块 README）
