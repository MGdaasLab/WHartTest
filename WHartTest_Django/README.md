# WhartTest - AI驱动的智能测试用例生成平台

## 项目简介

WhartTest 是一个基于 Django REST Framework 构建的AI驱动测试自动化平台，核心功能是通过AI智能生成测试用例。平台集成了 LangChain、MCP（Model Context Protocol）工具调用、项目管理、测试用例管理以及先进的知识库管理和文档理解功能。利用大语言模型和多种嵌入服务（OpenAI、Azure OpenAI、Ollama等）的能力，自动化生成高质量的测试用例，并结合知识库提供更精准的测试辅助，为测试团队提供一个完整的智能测试管理解决方案。

## 核心特性

### 🤖 AI智能测试用例生成
- 基于大语言模型的智能测试用例自动生成
 - 支持 OpenAI 兼容的 LLM 供应商（如 OpenAI、部分自建代理等），可灵活配置
- 通过 MCP 工具调用，实现测试用例的智能分析和生成，支持自定义工具集
- 自然语言描述转换为结构化测试用例，结合知识库提升准确性
- 支持测试步骤、预期结果的自动生成，并可进行AI辅助优化
- 支持多种嵌入服务（OpenAI、Azure OpenAI、Ollama等），增强语义理解

### 💬 智能对话系统
- 基于 LangChain 和 LangGraph 的 AI 对话功能
- 支持流式响应和聊天历史管理
- 与测试用例生成深度集成

### 📋 项目管理
- 多项目支持，实现数据隔离
- 基于角色的权限控制（Owner、Admin、Member）
- 项目成员管理和权限分配
- 项目级别的资源访问控制

### 🧪 智能测试用例管理
- AI生成的测试用例自动保存和管理
- 完整的测试用例 CRUD 操作
- 支持用例模块分类管理
- 嵌套式用例步骤管理
- 用例导出功能（Excel 格式）
- 基于项目的用例隔离
- 测试用例质量评估和优化建议
- 与知识库联动，生成更贴合业务场景的测试用例

### 🔧 MCP 工具集成
- 支持多种 MCP 传输方式（stdio、HTTP、SSE）
- 远程 MCP 服务器连接
- 工具调用日志和监控
- 与 AI 测试用例生成系统深度集成
- 提供测试用例生成专用工具集

### 🧠 知识库管理
- 支持创建和管理多个知识库，基于项目隔离
- 文档导入与自动分片、向量化处理（支持PDF, DOCX, TXT等多种格式）
- 多种嵌入服务支持：OpenAI、Azure OpenAI、Ollama
- 基于语义的高效检索和相似度匹配
- 与AI对话和测试用例生成深度集成，提供上下文感知能力
- 知识库内容管理与更新

### 🔧 MCP 工具集成
- 支持多种 MCP 传输方式（stdio、HTTP、SSE）
- 远程 MCP 服务器连接
- 工具调用日志和监控
- 与 AI 测试用例生成系统深度集成
- 提供测试用例生成专用工具集

### � 安全认证
- JWT 令牌认证
- API Key 认证支持
- 细粒度权限控制
- 用户和组管理

## 技术架构

### 后端技术栈
- **框架**: Django 5.2.1 + Django REST Framework
- **数据库**: SQLite（开发）/ PostgreSQL（生产）
- **认证**: JWT + API Key 双重认证
- **AI引擎**: LangChain + LangGraph（测试用例生成核心）
- **知识库引擎**: LangChain + Qdrant + 多种嵌入服务（OpenAI/Azure/Ollama等）
- **MCP集成**: FastMCP + langchain-mcp-adapters（工具调用）
- **API文档**: drf-spectacular (OpenAPI 3.0)
- **环境变量管理**: python-dotenv

### 核心依赖
```
# 核心框架与Web服务
django==5.2.1
djangorestframework
djangorestframework-simplejwt
drf-spectacular
django-cors-headers
python-dotenv
gunicorn # 生产环境WSGI服务器

# AI与LangChain相关
langchain-core
langchain-openai
langchain-community # 包含多种LLM集成和工具
langgraph
langgraph-checkpoint-sqlite # LangGraph状态持久化
fastmcp>=2.3.0
langchain-mcp-adapters

# 知识库相关
langchain-text-splitters
langchain-qdrant # Qdrant向量数据库集成
fastembed # BM25稀疏向量（混合检索）
# 注意：现使用CustomAPIEmbeddings通过API调用嵌入模型，无需以下本地模型依赖
# langchain-huggingface # HuggingFace嵌入模型支持 (已弃用)
# sentence-transformers # HuggingFace句子转换模型 (已弃用，约1GB+)
# torch # PyTorch (已弃用，约800MB+)
# transformers # HuggingFace Transformers库 (已弃用)
# huggingface-hub # HuggingFace模型下载 (已弃用)

# 文档处理
pypdf
python-docx
python-pptx
docx2txt
unstructured
beautifulsoup4 # HTML解析

# 数据库与工具
django-filter # DRF列表过滤
drf-nested-routers # DRF嵌套路由
openpyxl # Excel导出
httpx # HTTP客户端 (例如调用外部API)
openai # OpenAI官方SDK
# psycopg2-binary # PostgreSQL驱动 (生产环境可选)
```

## 应用模块

### 1. accounts - 用户管理
- 用户注册、登录、权限管理
- 用户组和权限分配
- JWT 令牌管理

### 2. projects - 项目管理
- 项目 CRUD 操作
- 项目成员管理
- 基于项目的权限控制

### 3. testcases - 测试用例管理
- 测试用例和用例步骤管理
- 用例模块分类
- 用例导出功能

- 用例导出功能

### 4. knowledge - 知识库管理 (新增)
- 知识库 CRUD 操作
- 文档上传、向量化处理与索引构建
- 知识库内容检索与管理
- 与AI对话、测试用例生成模块联动

### 5. langgraph_integration - AI测试用例生成引擎
- LLM 配置管理
- AI 智能测试用例生成
- 自然语言到测试用例的转换
- AI 对话接口
- 聊天历史管理
- 流式响应支持

- 流式响应支持

### 6. mcp_tools - MCP 工具管理
- MCP 服务器配置
- 工具调用管理
- 远程 MCP 连接

- 远程 MCP 连接

### 7. api_keys - API 密钥管理
- LLM 供应商 API 密钥管理
- API Key 认证支持

## API 接口

### 认证接口
- `POST /api/token/` - 获取 JWT 令牌
- `POST /api/token/refresh/` - 刷新 JWT 令牌

### 用户管理
- `GET /api/accounts/users/` - 用户列表
- `POST /api/accounts/register/` - 用户注册
- `GET /api/accounts/me/` - 当前用户信息

### 项目管理
- `GET /api/projects/` - 项目列表
- `POST /api/projects/` - 创建项目
- `GET /api/projects/{id}/` - 项目详情
- `POST /api/projects/{id}/add_member/` - 添加成员

### 测试用例管理
- `GET /api/projects/{project_id}/testcases/` - 用例列表
- `POST /api/projects/{project_id}/testcases/` - 创建用例
- `GET /api/projects/{project_id}/testcases/{id}/` - 用例详情
- `GET /api/projects/{project_id}/testcase-modules/` - 项目的用例模块列表
- `POST /api/projects/{project_id}/testcase-modules/` - 为项目创建用例模块

### AI 测试用例生成
- `POST /api/lg/chat/` - AI 智能生成测试用例
- `POST /api/lg/chat/stream/` - 流式测试用例生成
- `GET /api/lg/chat/history/` - 生成历史记录

### MCP 工具
- `GET /api/mcp_tools/configs/` - MCP 配置列表
- `POST /api/mcp_tools/configs/` - 创建 MCP 配置

- `POST /api/mcp_tools/configs/` - 创建 MCP 配置

### API密钥管理
- `GET /api/api_keys/` - API密钥列表 (示例, 具体根据api_keys.urls)
- `POST /api/api_keys/` - 创建API密钥 (示例, 具体根据api_keys.urls)

### 知识库管理 (新增)
- `GET /api/knowledge/kbs/` - 知识库列表 (示例, 具体根据knowledge.urls)
- `POST /api/knowledge/kbs/` - 创建知识库 (示例, 具体根据knowledge.urls)
- `POST /api/knowledge/kbs/{kb_id}/upload_docs/` - 上传文档到知识库 (示例)
- `GET /api/knowledge/kbs/{kb_id}/search_docs/` - 检索知识库文档 (示例)

### API Schema与文档 (新增)
- `GET /api/schema/` - 获取 OpenAPI 3.0 Schema
- `GET /api/schema/swagger-ui/` - Swagger UI 界面
- `GET /api/schema/redoc/` - ReDoc UI 界面

## 快速开始

### 环境要求
- Python 3.8+ (推荐 3.10+)
- Django 5.2.1
- SQLite/PostgreSQL
- Pip (包管理器)
- Git (版本控制)

### 系统依赖（Linux/Ubuntu）
```bash
# 旧版Word文档(.doc)解析支持
sudo apt-get install antiword catdoc
```

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/MGdaasLab/WHartTest.git
cd WhartTest_django
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **数据库迁移**
```bash
python manage.py makemigrations
python manage.py migrate
```

4. **创建超级用户**
```bash
python manage.py createsuperuser
```

5. **启动服务**
```bash
python manage.py runserver
```

### 配置说明

#### 环境变量配置

| 变量名 | 必填 | 默认值 | 示例值 | 说明 |
|--------|------|--------|--------|------|
| `DJANGO_DEBUG` | 否 | `False` | `True` | 调试模式开关，开发环境设为 `True`，生产环境设为 `False` |
| `DJANGO_SECRET_KEY` | 建议设置 | 开发默认值 | `your-production-secret-key-here` | Django 密钥，生产环境必须设置强密钥 |
| `DJANGO_ALLOWED_HOSTS` | 生产必填 | 开发默认 | `yourdomain.com,localhost,127.0.0.1` | 允许的主机列表，用逗号分隔 |
| `DJANGO_SUPERUSER_USERNAME` | 否 | `admin` | `admin` | Docker 容器启动时自动创建的超级用户名 |
| `DJANGO_SUPERUSER_PASSWORD` | 否 | `123456` | `123456` | Docker 容器启动时自动创建的超级用户密码 |
| `DJANGO_SUPERUSER_EMAIL` | 否 | `admin@qq.com` | `admin@qq.com` | Docker 容器启动时自动创建的超级用户邮箱 |
| `DJANGO_CORS_ALLOWED_ORIGINS` | 否 | 开发默认 | `http://localhost:3000,http://127.0.0.1:3000` | CORS 允许的源，用逗号分隔 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 否 | 开发默认 | `http://localhost:3000,http://127.0.0.1:3000` | CSRF 信任的源，用逗号分隔 |
| `USER_AGENT` | 否 | `WHartTest/2.6.0-ce` | `WHartTest/2.6.0-ce` | HTTP 请求的用户代理标识 |
| `FILE_MANAGEMENT_MAX_FILE_SIZE` | 否 | `104857600` | `209715200` | 文件管理单文件上传大小限制，单位：字节，默认 100MB |
| `FILE_MANAGEMENT_LLM_MAX_CHARS_PER_FILE` | 否 | `0` | `0` | LLM 附件单文件解析文本字符数限制；`0` 表示不限制，超限会报错且不会截断 |
| `DATABASE_URL` | 否 | SQLite | `postgresql://user:pass@localhost/dbname` | 数据库连接 URL（生产环境推荐 PostgreSQL） |
| `OPENAI_API_KEY` | 否 | - | `sk-...` | OpenAI API 密钥（如果使用 OpenAI 模型） |
| `ANTHROPIC_API_KEY` | 否 | - | `sk-ant-...` | Anthropic API 密钥（注：项目当前默认只支持 OpenAI 兼容格式，如需启用 Anthropic/Claude，请按需安装依赖并修改配置） |

#### LLM 配置
在管理后台或通过 API 配置 LLM 供应商和 API 密钥。

#### MCP 配置
配置 MCP 服务器连接信息，支持本地和远程服务器。

## 权限系统

### 权限层级
1. **用户认证** - 确保用户已登录
2. **模型权限** - Django 模型级别权限
3. **项目权限** - 基于项目成员身份的权限

### 角色定义
- **Owner** - 项目拥有者，拥有所有权限
- **Admin** - 项目管理员，可管理项目和成员
- **Member** - 项目成员，可访问项目资源

## 开发指南

### 代码结构
```
wharttest_django/
├── accounts/          # 用户管理
├── projects/          # 项目管理
├── testcases/         # 测试用例管理
├── knowledge/         # 知识库管理 (新增)
├── langgraph_integration/  # AI 对话集成
├── mcp_tools/         # MCP 工具管理
├── api_keys/          # API 密钥管理
├── llm_config/        # LLM 配置管理 (可能存在, 根据实际情况调整)
├── wharttest_django/   # 项目配置
├── docs/              # 文档
├── logs/              # 日志文件
└── templates/         # 模板文件
```

### 开发规范
- 所有视图集继承自 `BaseModelViewSet`
- 使用统一的响应格式 `UnifiedResponseRenderer`
- 遵循 RESTful API 设计原则
- 完善的权限控制和数据隔离
- 注释规范统一遵循 [`docs/code_comment_rules.md`](./docs/code_comment_rules.md)

### 注释规范

为避免配置注释与逻辑注释风格混用，项目按以下规则执行（详细示例见 [`docs/code_comment_rules.md`](./docs/code_comment_rules.md)）：

1. 配置文件（如 `settings.py`）统一使用行尾注释，强调“用途/影响”，且同一列表/字典全量一致。
2. 业务逻辑文件（`views/services/tasks/permissions`）统一使用上方细粒度注释，说明“条件 -> 动作 -> 结果”或“为什么这么做”。
3. 同一配置块保持同一风格；新增/修改配置时同步补注释；注释不得与代码语义冲突。

## 部署指南

### 🐳 Docker 部署

#### 构建镜像
```bash
# 构建 Docker 镜像
docker build -t wharttest-django .
```

#### 运行容器
```bash
# 使用环境变量运行
docker run -d \n  -p 8000:8000 \n  -e DJANGO_DEBUG=False \n  -e DJANGO_SECRET_KEY=your-production-secret-key \n  -e DJANGO_ALLOWED_HOSTS=yourdomain.com,localhost \n  wharttest-django

# 使用 .env 文件运行
docker run -d -p 8000:8000 --env-file .env wharttest-django
```

#### Docker Compose
```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DJANGO_DEBUG=False
      - DJANGO_SECRET_KEY=${SECRET_KEY}
      - DJANGO_ALLOWED_HOSTS=yourdomain.com,localhost
    volumes:
      - ./data:/app/data
```

### 🚀 快速部署

#### 开发环境部署
```bash
# 1. 克隆项目
git clone https://github.com/MGdaasLab/WHartTest.git
cd wharttest-django

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 数据库迁移
python manage.py makemigrations
python manage.py migrate

# 5. 创建超级用户
python manage.py createsuperuser

# 6. 启动开发服务器
python manage.py runserver
```

#### 生产环境部署

##### 方案1: Ubuntu服务器自动部署（推荐）
```bash
# 1. 系统准备
sudo apt update
sudo apt install python3-pip python3-venv git

# 2. 克隆项目
git clone https://github.com/MGdaasLab/WHartTest.git
cd wharttest-django

# 3. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 4. 安装完整依赖
pip install --upgrade pip
pip install -r requirements.txt

# 5. 配置嵌入服务（使用API）
export OPENAI_API_KEY=your-api-key
# 或者使用其他嵌入服务，如Azure OpenAI、Ollama等

# 6. 数据库配置
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser

# 7. 收集静态文件
python manage.py collectstatic --noinput

# 8. 启动生产服务器（支持 WebSocket）
uvicorn wharttest_django.asgi:application --host 0.0.0.0 --port 8000 --workers 4
```

##### 方案2: Docker Compose部署（推荐）
```bash
# 创建docker-compose.yml  
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  # Django应用
  django-app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=your-api-key
      # 或使用其他嵌入服务配置
    restart: unless-stopped
EOF

# 启动服务
docker-compose up -d
```

### 🔧 环境配置

#### 环境变量配置
创建 `.env` 文件：
```bash
# 基础配置
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=your-domain.com,your-ip-address

# 数据库配置（生产环境推荐PostgreSQL）
DATABASE_URL=postgresql://user:password@localhost/dbname

# 文件管理配置
# 单文件上传大小限制，单位：字节，默认 100MB
FILE_MANAGEMENT_MAX_FILE_SIZE=104857600
# LLM 附件单文件解析文本字符数限制；0 表示不限制，超限会报错且不会截断
FILE_MANAGEMENT_LLM_MAX_CHARS_PER_FILE=0

# LLM API Keys (根据实际使用的模型配置)
OPENAI_API_KEY=your_openai_api_key_here
# ANTHROPIC_API_KEY=your_anthropic_api_key_here (注：默认未启用 / 如需 Anthropic 支持，请取消注释并安装对应依赖)
# ... 其他 LLM API Keys

# CORS配置
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:3000,https://your-frontend-domain.com
```

#### 数据库配置
```python
# settings.py - 生产环境数据库配置
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'wharttest_db',
        'USER': 'wharttest_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 🌐 Web服务器配置

#### Nginx配置
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    location /static/ {
        alias /path/to/your/static/files/;
        expires 30d;
    }

    location /media/ {
        alias /path/to/your/media/files/;
        expires 30d;
    }
}
```

#### SSL证书配置
```bash
# 使用Let's Encrypt免费SSL证书
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```



### 📊 性能优化

#### 嵌入服务选择对比
| 服务类型 | 精度 | 成本 | 部署复杂度 | 数据隐私 |
|---------|------|------|-----------|---------|
| OpenAI API | 90-95% | 按量付费 | 简单 | 云端 |
| Azure OpenAI | 90-95% | 企业定价 | 简单 | 企业级 |
| Ollama本地 | 80-90% | 免费 | 中等 | 完全私有 |

#### 生产环境优化建议
1. **选择合适嵌入服务**: 根据精度、成本、隐私要求选择
2. **配置Gunicorn**: 多进程处理提升并发性能
3. **启用Nginx缓存**: 静态文件缓存减少服务器负载
4. **数据库优化**: 使用PostgreSQL并配置连接池
5. **监控配置**: 配置日志和性能监控
6. **服务预热**: 启动时预加载嵌入服务减少首次查询延迟

### 🔍 部署验证

#### 验证嵌入服务状态
启动服务后，查看日志确认嵌入服务连接正常：
```bash
# OpenAI API服务的日志
🚀 初始化OpenAI嵌入模型: text-embedding-ada-002
✅ 嵌入模型测试成功: openai_text-embedding-ada-002, 维度: 1536
🎉 说明: 使用OpenAI嵌入API服务
```

#### 服务健康检查
```bash
# 检查Django API
curl http://localhost:8000/api/knowledge/embedding-services/  

# 检查知识库系统
python manage.py check_knowledge_system --verbose
```

#### 功能测试
```bash
# 测试API接口
curl -X GET http://localhost:8000/api/projects/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 测试AI对话功能
curl -X POST http://localhost:8000/api/lg/chat/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"message": "帮我生成一个登录功能的测试用例", "project_id": 1}'
```

### 🛡️ 安全配置

#### 防火墙设置
```bash
# Ubuntu UFW防火墙配置
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

#### 安全检查清单
- [ ] 更改默认密码和密钥
- [ ] 配置HTTPS/SSL证书
- [ ] 设置防火墙规则
- [ ] 配置数据库访问权限
- [ ] 启用日志监控
- [ ] 定期备份数据

### 📝 部署检查清单

#### 基础环境
- [ ] Python 3.8+ 已安装
- [ ] 虚拟环境已创建并激活
- [ ] requirements.txt 依赖已安装
- [ ] 数据库已配置并迁移
- [ ] 超级用户已创建

#### AI功能
- [ ] HuggingFace模型已下载（生产环境）
- [ ] 向量模型加载状态已验证
- [ ] 知识库功能测试通过
- [ ] AI对话接口测试通过

#### 生产环境
- [ ] 环境变量已配置
- [ ] 静态文件已收集
- [ ] Web服务器已配置
- [ ] SSL证书已安装
- [ ] 防火墙已设置
- [ ] 监控和日志已配置
- [ ] 备份策略已实施

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

## 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

### 协议说明
- ✅ **商业使用** - 可用于商业项目
- ✅ **修改** - 可以修改源代码
- ✅ **分发** - 可以分发原始或修改后的代码
- ❗ **责任** - 作者不承担责任
- ❗ **保证** - 不提供任何保证

### 使用要求
使用本项目时，请在您的项目中包含以下内容：
- 保留原始的版权声明
- 保留MIT许可证全文

### 第三方依赖
本项目使用的主要依赖库及其协议：
- Django (BSD-3-Clause)
- Django REST Framework (MIT)
- LangChain系列 (MIT)
- OpenAI SDK (MIT)
- 其他依赖库详见 [requirements.txt](requirements.txt)

所有依赖库均为宽松开源协议，与MIT协议完全兼容。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 Issue
- 项目讨论区

---

**WhartTest** - AI驱动测试用例生成，让测试更智能，让开发更高效！
