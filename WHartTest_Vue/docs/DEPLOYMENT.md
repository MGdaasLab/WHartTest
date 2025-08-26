# 部署指南

## 🚀 部署配置说明

### 当前问题
您遇到的问题是：前端部署在服务器上，但API请求仍然指向 `localhost`，导致用户从自己电脑访问时无法正确请求到服务器的后端API。

### 解决方案

#### 方案1：使用反向代理（推荐）

**配置步骤：**

1. **修改生产环境配置**
   ```bash
   # .env.production 已配置为：
   VITE_API_BASE_URL=/api
   ```

2. **重新打包**
   ```bash
   npx vite build
   ```

3. **配置Nginx反向代理**
   ```nginx
   server {
       listen 8088;
       server_name your_server_ip;

       # 前端静态文件
       location / {
           root /path/to/your/dist;
           index index.html;
           # 关键配置：所有路由都返回 index.html，解决SPA刷新404问题
           try_files $uri $uri/ /index.html;
       }

       # API反向代理
       location /api/ {
           proxy_pass http://127.0.0.1:8000/api/;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

**优点：**
- 用户访问时，前端和后端都是同一个域名
- 避免跨域问题
- 配置简单，维护方便

#### 方案2：直接指定后端地址

**配置步骤：**

1. **修改 `.env.production`**
   ```bash
   # 将 YOUR_SERVER_IP 替换为您的实际服务器IP
   VITE_API_BASE_URL=http://YOUR_SERVER_IP:8000/api
   ```

2. **重新打包**
   ```bash
   npx vite build
   ```

**缺点：**
- 需要处理跨域问题
- IP变更时需要重新打包
- 不够灵活

### 🔧 快速修复当前问题

如果您想立即解决问题，请按以下步骤操作：

1. **修改 `.env.production` 文件**
   ```bash
   # 将下面的 192.168.1.100 替换为您的实际服务器IP
   VITE_API_BASE_URL=http://192.168.1.100:8000/api
   ```

2. **重新打包**
   ```bash
   npx vite build
   ```

3. **重新部署 `dist/` 目录到服务器**

### 📝 环境变量说明

- **`.env`** - 开发环境配置（使用 localhost）
- **`.env.production`** - 生产环境配置（使用服务器地址或相对路径）

### 🌐 访问示例

假设您的服务器IP是 `192.168.1.100`：

- **前端访问地址**: `http://192.168.1.100:8088`
- **后端API地址**: `http://192.168.1.100:8000/api`

用户从自己电脑访问 `http://192.168.1.100:8088` 时，前端会正确请求到 `http://192.168.1.100:8000/api`。

### ⚠️ 注意事项

1. **跨域配置**：如果使用方案2，需要在后端配置CORS允许前端域名
2. **防火墙**：确保服务器的8000和8088端口都已开放
3. **HTTPS**：生产环境建议使用HTTPS

## 🚨 解决SPA刷新404问题

### 问题描述
- **正常跳转**: 点击菜单跳转正常 ✅
- **刷新页面**: 在 `/dashboard` 等路由刷新时出现404 ❌

### 原因分析
Vue Router 使用 `history` 模式，路由如 `/dashboard` 是前端路由，不是真实服务器文件。刷新时浏览器直接请求服务器，服务器找不到对应文件返回404。

### 解决方案

#### Nginx 配置（推荐）
```nginx
server {
    listen 8088;

    location / {
        root /path/to/dist;
        index index.html;
        # 关键：所有路由都fallback到index.html
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
    }
}
```

#### Apache 配置
在 `dist/` 目录创建 `.htaccess` 文件：
```apache
<IfModule mod_rewrite.c>
  RewriteEngine On
  RewriteBase /
  RewriteRule ^index\.html$ - [L]
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteCond %{REQUEST_FILENAME} !-d
  RewriteRule . /index.html [L]
</IfModule>
```

#### Node.js Express 配置
```javascript
const express = require('express');
const path = require('path');
const app = express();

// 静态文件
app.use(express.static(path.join(__dirname, 'dist')));

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist/index.html'));
});
```

### 🔧 核心配置说明

**关键配置**: `try_files $uri $uri/ /index.html;`

**工作原理**:
1. 先尝试找真实文件 `$uri`
2. 再尝试找目录 `$uri/`
3. 都找不到就返回 `index.html`
4. Vue Router 接管路由处理
