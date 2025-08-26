# 🖼️ 前端生产环境部署指南

本指南将引导您完成 WHartTest 前端应用的生产环境部署。我们将涵盖从构建应用到配置 Web 服务器的完整流程。

## 📦 环境准备

在开始之前，请确保您的开发和部署环境满足以下要求：

- **Node.js**: 版本 18 或更高。
- **包管理器**: `npm` 或 `yarn`。
- **Web 服务器**: `Nginx` (推荐), `Apache`, 或其他支持静态文件托管和反向代理的服务器。

## 🚀 部署步骤

### 1. 获取项目代码

首先，从代码仓库克隆最新的前端项目代码。

```bash
# 克隆仓库
git clone https://github.com/MGdaasLab/WHartTest.git

# 进入项目目录
cd WHartTest_Vue
```

### 2. 安装依赖

进入项目目录后，使用 `npm` 或 `yarn` 安装项目所需的依赖项。

```bash
npm install
```

### 3. 构建生产版本

安装完依赖后，运行构建命令来生成用于生产环境的优化版本。

```bash
npm run build
```

此命令会在项目根目录下创建一个 `dist` 文件夹，其中包含了所有构建好的静态文件（HTML, CSS, JavaScript 等）。

### 4. 配置 Web 服务器

部署前端应用的核心是将构建产物（`dist` 目录下的文件）托管起来，并通过 Web 服务器对外提供访问。同时，需要配置反向代理将 API 请求转发到后端服务。

以下是一个推荐的 `Nginx` 配置示例：

```nginx
server {
    listen 80;
    server_name your-frontend-domain.com; # 替换为您的前端域名

    # 前端静态文件根目录
    root /path/to/your/WHartTest_Vue/dist; # 替换为 dist 目录的绝对路径
    index index.html;

    # 处理前端路由（History 模式）
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 请求反向代理到后端服务
    location /api/ {
        proxy_pass http://your-backend-api-server.com; # 替换为您的后端 API 地址
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # 可以选择性地为其他静态资源（如 media）配置缓存策略
    location ~* \.(?:jpg|jpeg|gif|png|ico|css|js)$ {
        expires 7d;
        add_header Cache-Control "public";
    }
}
```

**配置说明:**

- `listen 80;`: 监听 80 端口。
- `server_name`: 配置您的访问域名。
- `root`: 指向您项目中 `dist` 文件夹的绝对路径。
- `location /`: 这是处理单页应用（SPA）路由的关键。当用户访问一个前端路由时，Nginx 会返回 `index.html`，由 Vue Router接管后续的路由逻辑。
- `location /api/`: 将所有以 `/api/` 开头的请求代理到后端 API 服务器。**请务必将 `proxy_pass` 的地址修改为您的实际后端服务地址**。

### 5. 启动和验证

保存 Nginx 配置后，重新加载或重启 Nginx 服务。

```bash
# 测试 Nginx 配置是否正确
sudo nginx -t

# 重新加载 Nginx
sudo nginx -s reload
```

现在，您应该可以通过浏览器访问您配置的域名 (`your-frontend-domain.com`) 来查看并使用 WHartTest 应用了。

## 🔍 预览生产构建 (可选)

如果您想在部署前本地预览生产构建的效果，可以运行以下命令：

```bash
npm run preview
```

该命令会启动一个本地静态文件服务器，让您可以在本地环境中检查 `dist` 文件夹的内容是否按预期工作。
