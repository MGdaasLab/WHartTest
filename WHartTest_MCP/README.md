# MCP 测试工具部署文档

## 项目概述

本项目包含两个 MCP (Model Context Protocol) 工具服务：

- **ms_mcp_api.py** - MS测试用例工具，提供与MS测试平台的API交互功能
- **WHartTest_tools.py** - WHartTest 测试用例工具，提供本地测试用例管理功能

## 环境要求

- Python 3.8+
- 网络连接（用于API调用）

## 安装部署

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置说明

#### WHartTest Tools (WHartTest_tools.py) ✨ 开箱即用

- **服务端口**: 8006
- **后端地址**: `WHARTTEST_BACKEND_URL`（默认：http://backend:8000）
- **API密钥**: `WHARTTEST_API_KEY`（安全：固定演示密钥已废除，请配置后台创建的密钥）

**🎉 零配置启动：**
```bash
cp .env.example .env  # 已包含默认API Key
docker-compose up -d   # 直接启动，无需手动配置
```

**⚠️ 生产环境安全提示：**
- `init_admin` 会自动创建随机命名的默认 API Key，并在 stdout 打印一次
- 开发环境可直接使用
- 生产环境请登录后台删除默认Key并创建新的安全密钥

#### MS测试用例工具 (ms_mcp_api.py)

- **服务端口**: 8007
- **API地址**: 通过环境变量 `MS_API_HOST` 配置
- **认证信息**: 通过环境变量 `MS_ACCESS_KEY` 和 `MS_SECRET_KEY` 配置

### 3. 启动服务

#### 启动MS测试用例工具

```bash
python ms_mcp_api.py
```

服务将在 `http://127.0.0.1:8007` 启动

#### 启动测试用例工具

```bash
python WHartTest_tools.py
```

服务将在 `http://0.0.0.0:8006` 启动

## 功能说明

### MS测试用例工具功能

- 获取项目名称和ID
- 获取模块名称和ID
- 获取用例等级信息
- 生成测试用例步骤数据
- 保存功能测试用例

### 测试用例工具功能

- 获取项目列表
- 获取模块信息
- 获取用例等级
- 获取用例列表和详情
- 保存操作截图
- 保存功能测试用例

## MCP 集成

这些工具基于 FastMCP 框架构建，可以与支持 MCP 协议的客户端集成使用。

### 连接配置

在 MCP 客户端中配置连接：

```json
{
  "mcpServers": {
    "ms-testcase-tools": {
      "command": "python",
      "args": ["path/to/ms_mcp_api.py"],
      "env": {}
    },
    "testauto-tools": {
      "command": "python",
      "args": ["path/to/WHartTest_tools.py"],
      "env": {}
    }
  }
}
```

## 注意事项

1. 确保目标API服务可访问
2. 检查防火墙设置，确保端口8006和8007可用
3. 如需修改配置，请直接编辑源码中的配置参数
4. 建议在生产环境中使用环境变量管理敏感信息

## 故障排除

- 如果服务启动失败，检查端口是否被占用
- 如果API调用失败，检查网络连接和API地址
- 查看控制台输出获取详细错误信息