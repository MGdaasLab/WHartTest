# 🏢 后端生产环境部署指南

本指南将引导您完成 WHartTest 后端服务的生产环境部署。系统已改为使用API方式调用嵌入模型，无需本地下载模型文件。


## 🚀 部署方案

我们提供多种部署方案以适应不同环境的需求。

### 🐳 方案一：使用 Docker 部署 (推荐)

Docker 提供了环境一致性，是生产环境部署的首选方案。

#### 1. 构建 Docker 镜像
```bash
# 在项目根目录 (WHartTest_Django/) 下执行
docker build -t wharttest-django .
```

#### 2. 运行 Docker 容器

您可以使用 `.env` 文件来管理环境变量，这是最推荐的方式。

```bash
# 确保 .env 文件在项目根目录中
# 运行容器，并将 .env 文件传递给容器
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  -v ./whart_data:/app/data \
  wharttest-django
```
*   `-v ./whart_data:/app/data` 将容器内的数据目录挂载到宿主机，用于持久化存储，例如 SQLite 数据库、上传的文件等。

#### 3. 使用 Docker Compose
为了更方便地管理服务，您可以使用 `docker-compose.yml`。

```yaml
version: '3.8'
services:
  web:
    build: .
  container_name: wharttest_backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./whart_data:/app/data
      - ./.cache:/app/.cache  # 挂载模型缓存目录
```
*   **注意**: 确保您的 `.env` 文件中包含了所有必要的环境变量。

### 🛠️ 方案二：手动部署 (以 Ubuntu 为例)

此方案适用于您希望对部署环境有完全控制权的场景。

#### 1. 系统准备
```bash
sudo apt update
sudo apt install python3-pip python3-venv git nginx
```

#### 2. 克隆项目
```bash
git clone <your-repo-url>
cd WHartTest_Django
```

#### 3. 创建并激活虚拟环境
```bash
python3 -m venv venv
source venv/bin/activate
```

#### 4. 安装依赖
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 5. 配置 AI 模型 API
系统现已改为使用API方式调用嵌入模型，请在环境变量中配置相应的API密钥。
```bash
# 在 .env 文件中配置API密钥
# 具体配置请参考环境变量配置部分
```

#### 6. 数据库配置
```bash
# 生成迁移文件
python manage.py makemigrations

# 执行迁移
python manage.py migrate

# 创建超级管理员用户
python manage.py createsuperuser
```

#### 7. 收集静态文件
```bash
python manage.py collectstatic --noinput
```

#### 8. 使用 Gunicorn 启动服务
```bash
# 安装 gunicorn
pip install gunicorn

# 启动服务
gunicorn WHartTest_Django.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --timeout 120 \
  --preload
```
*   `--preload` 会在启动时预加载模型，减少首次请求的延迟。

### 🔌 方案三：离线部署

适用于无法直接访问互联网的生产服务器。

#### 步骤 1: 在有网机器上准备物料

1.  **下载 Python 依赖包**
    ```bash
    pip download -r requirements.txt -d /path/to/packages
    ```
2.  **配置 API 密钥**
    ```bash
    # 在项目目录中配置 .env 文件
    # 添加必要的API密钥配置
    ```
3.  **打包所有文件**
    ```bash
    # 打包项目代码
    tar -czf project.tar.gz .
    # 打包依赖包
    tar -czf packages.tar.gz /path/to/packages
    # 打包模型文件
    tar -czf models.tar.gz .cache
    ```

#### 步骤 2: 在生产服务器上部署

1.  **传输并解压文件**
    将 `project.tar.gz`, `packages.tar.gz`, `models.tar.gz` 上传到服务器并解压。

2.  **安装依赖**
    ```bash
    # 进入解压后的项目目录
    pip install --no-index --find-links=/path/to/packages -r requirements.txt
    ```

3.  **恢复模型文件**
    将解压后的 `.cache` 文件夹移动到项目根目录。

4.  **完成后续步骤**
    参考**方案二**中的数据库配置、静态文件收集和 Gunicorn 启动步骤。

## ⚙️ 环境配置

### 环境变量 (`.env` 文件)
在项目根目录创建 `.env` 文件是管理配置的最佳实践。

```dotenv
# --- 基础配置 ---
# 生产环境必须设置为 False
DEBUG=False
# 生产环境必须设置一个长且随机的字符串
SECRET_KEY=your-super-strong-and-random-secret-key
# 允许访问的域名或IP，用逗号分隔
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# --- 数据库配置 ---
# 推荐使用 PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/whartdb

# --- AI 模型 API 配置 ---
# 配置嵌入模型 API 密钥
EMBEDDING_API_KEY=your-embedding-api-key
EMBEDDING_API_BASE_URL=https://api.your-provider.com

# --- CORS 跨域配置 ---
# 允许您的前端应用访问后端API
DJANGO_CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com,http://localhost:3000

# --- LLM API Keys ---
# 根据您使用的模型提供商配置
OPENAI_API_KEY=sk-your-openai-key
# ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
```

### Nginx 反向代理
使用 Nginx 作为反向代理可以提高性能和安全性。

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 强制跳转到 HTTPS
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    # SSL 证书路径
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location /static/ {
        alias /path/to/your/WHartTest_Django/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

## 🛡️ 安全配置

### 防火墙 (UFW on Ubuntu)
```bash
# 只开放必要的端口
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp   # HTTP (用于SSL证书续期)
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### SSL 证书 (Let's Encrypt)
```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 获取并自动配置 SSL 证书
sudo certbot --nginx -d your-domain.com
```

## 🔍 部署验证

### 1. 验证 API 连接
启动服务后，检查日志输出，确认嵌入模型 API 连接正常。
```log
🚀 正在初始化嵌入模型API...
✅ 嵌入模型API连接成功
🧪 API测试成功，服务正常
🤖 向量存储管理器初始化完成:
   ✅ 实际使用的嵌入模型: API嵌入服务
```

### 2. API 健康检查
```bash
# 检查项目 API 是否正常 (需要有效的 JWT Token)
curl -X GET http://your-domain.com/api/projects/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 3. 知识库功能测试
通过 API 创建一个知识库，上传文档并进行搜索，验证整个流程是否正常。

## ✅ 生产环境检查清单

- [ ] `DEBUG` 设置为 `False`
- [ ] `SECRET_KEY` 已更换为强密钥
- [ ] 使用 `Gunicorn` 或其他 WSGI 服务器
- [ ] 配置 `Nginx` 作为反向代理
- [ ] 数据库已从 SQLite 切换到 `PostgreSQL`
- [ ] 嵌入模型 API 已配置并连接正常
- [ ] 静态文件已通过 `collectstatic` 收集并由 Nginx 服务
- [ ] `SSL/TLS` 证书已配置，强制 HTTPS
- [ ] 防火墙已启用，只开放必要端口
- [ ] 备份策略已制定（数据库和用户上传文件）
- [ ] 日志记录和监控已配置
