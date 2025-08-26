# 后端组件依赖

## 技术栈概览

WHartTest 后端基于 Django REST Framework 构建，采用 Python 生态的现代化技术栈，提供高性能、可扩展的 RESTful API 服务。

## 版本控制说明

在依赖管理中，我们使用以下版本控制符号：

- **==**: 精确版本匹配（如 `Django==5.2`）
- **>=**: 大于或等于指定版本
- **^**: 兼容版本（主版本号不变，次版本号和修订号可以升级）
- **~**: 近似版本（次版本号不变，修订号可以升级）

## 核心框架

### Django
- **版本**: 5.2
- **作用**: 高级 Python Web 框架，遵循 MTV 架构模式
- **特点**: 
  - 内置 ORM、认证系统、管理后台
  - 强大的中间件支持
  - 完善的文档和社区
- **开源协议**: BSD License

### Django REST Framework
- **版本**: 3.16.0
- **作用**: Django 的 RESTful API 扩展框架
- **特点**:
  - 序列化/反序列化
  - 认证和权限控制
  - 视图集和路由
  - 内置 API 文档
- **开源协议**: BSD License

## 身份认证

### Django REST Framework Simple JWT
- **版本**: 5.3.1
- **作用**: JWT 认证支持
- **开源协议**: MIT License

## API 文档

### DRF Spectacular
- **版本**: 0.28.0
- **作用**: API Schema 生成和文档
- **开源协议**: BSD License

## 跨域支持

### Django CORS Headers
- **版本**: 4.3.1
- **作用**: CORS 跨域支持
- **开源协议**: MIT License

## 环境配置

### Python Dotenv
- **版本**: 1.1.1
- **作用**: 环境变量加载
- **开源协议**: BSD License

## MCP 工具支持

### FastMCP
- **版本**: 2.4.0
- **作用**: MCP 工具框架
- **开源协议**: MIT License

## 网络请求

### HTTPX
- **版本**: 0.28.1
- **作用**: 异步 HTTP 客户端
- **开源协议**: BSD License

### OpenAI
- **版本**: 1.79.0
- **作用**: OpenAI API 客户端
- **开源协议**: MIT License

## 数据过滤

### Django Filter
- **版本**: 25.1
- **作用**: Django 查询过滤
- **开源协议**: BSD License

## 路由扩展

### DRF Nested Routers
- **版本**: 0.94.2
- **作用**: 嵌套路由支持
- **开源协议**: BSD License

## AI 和机器学习

### LangGraph
- **版本**: 0.4.5
- **作用**: 语言模型应用编排框架
- **开源协议**: MIT License

### LangChain 相关组件
- **langchain-openai** (0.3.17): OpenAI 集成
- **langchain-anthropic** (0.2.4): Anthropic/Claude 支持
- **langchain-google-genai** (2.0.8): Google Generative AI 支持
- **langchain-ollama** (0.2.2): Ollama 本地模型支持
- **langchain-mistralai** (0.2.4): Mistral AI 支持
- **langchain-cohere** (0.3.5): Cohere AI 支持
- **langchain-fireworks** (0.2.7): Fireworks AI 支持
- **langchain-core** (0.3.60): 核心功能
- **langgraph-checkpoint-sqlite** (2.0.10): SQLite 检查点存储
- **langchain-mcp-adapters** (0.1.7): MCP 适配器
- **开源协议**: MIT License

### AI 服务客户端
- **anthropic** (0.48.0): Anthropic API 客户端
- **cohere** (5.15.0): Cohere API 客户端
- **fireworks-ai** (0.15.12): Fireworks AI 客户端
- **google-ai-generativelanguage** (0.6.15): Google AI 生成语言 API
- **google-api-core** (2.24.1): Google API 核心库
- **google-api-python-client** (2.162.0): Google API 客户端
- **google-auth** (2.38.0): Google 认证库
- **google-generativeai** (0.8.4): Google 生成式 AI
- **ollama** (0.4.7): Ollama 客户端
- **开源协议**: MIT/Apache 2.0 License

### LangChain 社区组件
- **langchain-community** (0.3.24): 社区扩展
- **langchain-text-splitters** (0.3.8): 文本分割器
- **langchain-chroma** (0.2.4): ChromaDB 集成
- **langchain-huggingface** (0.2.0): HuggingFace 嵌入模型集成
- **开源协议**: MIT License

## 文档处理

### 文档格式支持
- **openpyxl** (3.1.5): Excel 文件处理
- **pypdf** (5.6.0): PDF 处理
- **python-docx** (1.1.2): Word 文档处理
- **python-pptx** (1.0.2): PowerPoint 文档处理
- **docx2txt** (0.9): Word 文档文本提取
- **unstructured** (0.17.2): 非结构化数据处理
- **beautifulsoup4** (4.13.3): HTML/XML 解析
- **开源协议**: MIT License (除 beautifulsoup4 为 MIT License)

### HuggingFace 模型依赖
- **sentence-transformers** (4.1.0): 句子转换模型 (~90MB模型，需要网络下载)
- **torch** (2.7.1): PyTorch 框架 (修复 CVE-2025-32434 安全漏洞)
- **transformers** (4.52.4): HuggingFace transformers 库
- **huggingface-hub** (0.32.4): HuggingFace 模型下载
- **开源协议**: Apache License 2.0

