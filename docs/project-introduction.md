# 项目介绍

WHartTest 是基于 Django REST Framework 与现代大模型技术打造的 AI 驱动测试自动化平台。
平台聚合自然语言理解、知识库检索与嵌入搜索能力，结合 LangChain 与 MCP（Model Context Protocol）工具调用，实现从需求到可执行测试用例的自动化生成与管理，帮助测试团队提升效率与覆盖率。

## 核心价值
- 智能用例生成：从需求或对话中自动生成结构化测试用例（测试步骤、前置条件、输入、期望结果、优先级等）。
- 知识感知：支持从文档、API 文档与知识库抽取上下文，使用嵌入增强模型的理解与检索精度。
- 自动评审与建议：基于模型的需求评审与风险提示，辅助测试策略制定与优先级判断。
- 用例管理与执行：集中管理用例、执行记录、自动截屏与执行结果上报，便于审计与回溯。
- 可扩展与可定制：支持接入自定义模型、第三方服务与扩展工具链（LangChain、HuggingFace 等）。

## 技术栈
- 后端：Django, Django REST Framework
- AI：大语言模型（LLM）、LangChain、HuggingFace 嵌入
- 存储：示例使用 SQLite，可切换为 PostgreSQL / MySQL
- 前端：Vue + Vite（详见 `WHartTest_Vue`）

## 快速上手（简要）
1. 克隆仓库并进入项目根目录。
2. 进入 `WHartTest_Django`，创建虚拟环境并安装依赖：参见 `requirements.txt`。
3. 执行数据库迁移并启动服务：
   - python manage.py migrate
   - python manage.py runserver
4. 浏览器打开 http://127.0.0.1:8000 查看界面（具体配置与部署请参阅根目录 README）。

## 界面与功能预览
以下截图展示了平台的典型界面与功能，供快速浏览：

### 登录页面
![登录页面](/img/image.png)

### 知识库提取与管理
![知识库管理](/img/image-1.png)

### AI 对话与测试用例生成
![AI 对话与测试用例生成](/img/image-2.png)

### 测试用例管理
![测试用例管理](/img/image-3.png)

### 生成用例详情
![生成用例详情](/img/image-4.png)

### 测试执行与自动截屏
![测试执行与自动截屏](/img/image-6.png)

### 执行结果与报告
![执行结果](/img/image-7.png)

### 报告详情
![报告详情](/img/image-8.png)

### AI 驱动的需求评审与报告
![AI 需求评审](/img/image-9.png)

### 报告打分与建议
![报告打分与建议](/img/image-11.png)

### 报告详情
![报告详情](/img/image-10.png)

（更多细节、API 与部署说明请查阅仓库中的 docs 目录及各模块 README）

