# MCP 测试工具部署文档

## 项目概述

本项目包含两个 MCP (Model Context Protocol) 工具服务：

- **ms_mcp_api.py** - MS测试用例工具，提供与MS测试平台的API交互功能
- **testauto_tools.py** - 测试用例工具，提供本地测试用例管理功能

## 环境要求

- Python 3.8+
- 网络连接（用于API调用）

## 安装部署

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置说明

#### MS测试用例工具 (ms_mcp_api.py)

- **服务端口**: 8007
- **API地址**: http://msxxxxxxxxx.com
- **认证信息**: 已内置在代码中

#### 测试用例工具 (testauto_tools.py)

- **服务端口**: 8006
- **API地址**: http://127.0.0.1:8000
- **API密钥**: 已内置在代码中

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