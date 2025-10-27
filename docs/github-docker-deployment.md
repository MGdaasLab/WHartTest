# GitHub 自动构建 Docker 镜像部署指南

## 概述

本项目已配置 GitHub Actions 自动构建流程，可以自动将代码构建为 Docker 镜像并推送到 GitHub Container Registry (GHCR)。用户可以直接拉取预构建的镜像，无需本地构建。

## 工作流程

### 1. 自动构建触发条件

- 推送代码到 `main` 分支
- 创建版本标签 (如 `v1.0.0`)
- 创建 Pull Request

### 2. 构建的镜像

GitHub Actions 会自动构建并推送以下三个镜像：

- `ghcr.io/YOUR_USERNAME/wharttest-backend:latest` - Django 后端
- `ghcr.io/YOUR_USERNAME/wharttest-frontend:latest` - Vue 前端
- `ghcr.io/YOUR_USERNAME/wharttest-mcp:latest` - MCP 服务

### 3. 镜像标签策略

- `latest` - main 分支的最新版本
- `v1.0.0` - 具体版本号
- `main` - main 分支标签
- `pr-123` - Pull Request 标签

## 初次设置步骤

### 1. 启用 GitHub Packages

1. 进入你的 GitHub 仓库
2. 进入 **Settings** > **Actions** > **General**
3. 确保 **Workflow permissions** 设置为 **Read and write permissions**
4. 保存设置

### 2. 修改镜像地址

镜像地址已经配置为：

```yaml
services:
  backend:
    image: ghcr.io/mg-duan/wharttest-backend:latest
  frontend:
    image: ghcr.io/mg-duan/wharttest-frontend:latest
  mcp:
    image: ghcr.io/mg-duan/wharttest-mcp:latest
```

### 3. 设置镜像为公开（可选）

默认情况下，镜像是私有的。如果希望公开访问：

1. 进入 GitHub 仓库页面
2. 点击右侧的 **Packages**
3. 选择对应的包（backend/frontend/mcp）
4. 点击 **Package settings**
5. 滚动到 **Danger Zone**
6. 点击 **Change visibility** 设置为 **Public**

## 使用方式

### 开发环境（本地构建）

使用默认的 `docker-compose.yml`，会在本地构建镜像：

```bash
docker-compose up -d
```

### 生产环境（使用预构建镜像）

#### 方法一：使用 docker-compose.prod.yml

```bash
# 1. 复制环境变量配置
cp .env.example .env

# 2. 编辑 .env 文件，设置必要的环境变量
# 特别是 DJANGO_SECRET_KEY 和 DJANGO_ADMIN_PASSWORD

# 3. 使用生产配置启动
docker-compose -f docker-compose.prod.yml up -d
```

#### 方法二：修改 docker-compose.yml

在 `docker-compose.yml` 中注释掉 `build` 部分，取消注释 `image` 行：

```yaml
services:
  backend:
    # build:
    #   context: ./WHartTest_Django
    #   dockerfile: Dockerfile
    image: ghcr.io/your-github-username/wharttest-backend:latest
```

然后运行：

```bash
docker-compose up -d
```

### 使用特定版本

如果要使用特定版本而不是 `latest`：

```yaml
services:
  backend:
    image: ghcr.io/mg-duan/wharttest-backend:v1.0.0
```

## 验证部署

### 查看容器状态

```bash
docker-compose ps
```

### 查看日志

```bash
# 查看所有容器日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f mcp
```

### 访问服务

- 前端: http://localhost
- 后端 API: http://localhost:8000/api/
- Django Admin: http://localhost:8000/admin/
- MCP Tools: http://localhost:8006
- MS MCP API: http://localhost:8007

## 私有镜像认证

如果镜像是私有的，需要先登录 GitHub Container Registry：

```bash
# 1. 创建 Personal Access Token (PAT)
#    - 进入 GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
#    - 点击 "Generate new token (classic)"
#    - 选择 read:packages 权限
#    - 生成并复制 token

# 2. 使用 token 登录
echo YOUR_PAT_TOKEN | docker login ghcr.io -u mg-duan --password-stdin

# 3. 现在可以拉取私有镜像了
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

## 手动拉取最新镜像

如果 GitHub 已经构建了新版本，本地想更新：

```bash
# 拉取最新镜像
docker-compose -f docker-compose.prod.yml pull

# 重启容器
docker-compose -f docker-compose.prod.yml up -d
```

## 查看 GitHub Actions 构建状态

1. 进入 GitHub 仓库
2. 点击 **Actions** 标签
3. 查看 **Build and Push Docker Images** 工作流
4. 点击具体的运行记录查看详细日志

## 版本发布流程

### 发布新版本

```bash
# 1. 确保代码已提交
git add .
git commit -m "release: version 1.0.0"

# 2. 创建版本标签
git tag v1.0.0

# 3. 推送代码和标签
git push origin main
git push origin v1.0.0
```

GitHub Actions 会自动：
- 构建三个服务的 Docker 镜像
- 推送到 GHCR，包含 `latest` 和 `v1.0.0` 标签

## 故障排除

### 问题：拉取镜像失败

**原因**：镜像是私有的，需要认证

**解决**：按照"私有镜像认证"部分的步骤登录 GHCR

### 问题：GitHub Actions 构建失败

**检查**：
1. 进入 Actions 页面查看错误日志
2. 确认 Workflow permissions 设置正确
3. 检查 Dockerfile 是否有语法错误

### 问题：容器启动失败

**检查**：
```bash
# 查看容器日志
docker-compose logs backend
docker-compose logs frontend
docker-compose logs mcp

# 检查环境变量
cat .env
```

## 环境变量配置

生产环境必须修改的环境变量（在 `.env` 文件中）：

```env
# Django 配置
DJANGO_SECRET_KEY=your-secret-key-here  # 必须修改！
DJANGO_DEBUG=False
DJANGO_ADMIN_PASSWORD=your-secure-password  # 必须修改！
DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# CORS 配置
DJANGO_CORS_ALLOWED_ORIGINS=https://your-domain.com

# MCP 配置（如果使用）
WHARTTEST_API_KEY=your-api-key
```

## 清理资源

### 停止并删除容器

```bash
docker-compose down
```

### 删除镜像

```bash
docker image rm ghcr.io/your-github-username/wharttest-backend:latest
docker image rm ghcr.io/your-github-username/wharttest-frontend:latest
docker image rm ghcr.io/your-github-username/wharttest-mcp:latest
```

### 清理构建缓存

```bash
docker system prune -a
```

## 性能优化

### 使用多阶段构建缓存

GitHub Actions 已配置使用 GitHub Actions Cache 进行层缓存，加快构建速度。

### 镜像大小优化

所有 Dockerfile 已使用多阶段构建，生产镜像较小：
- Backend: ~200-300 MB
- Frontend: ~50-80 MB (nginx + 静态文件)
- MCP: ~150-200 MB

## 安全建议

1. **保护敏感信息**：不要在代码中硬编码密钥，使用环境变量
2. **定期更新依赖**：运行 `pip install --upgrade` 和 `npm update`
3. **使用版本标签**：生产环境避免使用 `latest`，使用具体版本号
4. **限制网络访问**：配置防火墙规则，只开放必要端口
5. **启用 HTTPS**：生产环境使用反向代理（如 Nginx）并配置 SSL 证书

## 相关文档

- [Docker Compose 文档](https://docs.docker.com/compose/)
- [GitHub Actions 文档](https://docs.github.com/actions)
- [GitHub Packages 文档](https://docs.github.com/packages)