# 操作手册 (v2.1.0)

::: tip 版本说明
本操作手册基于 **v2.1.0** 版本编写。
:::

## 🚀 重大升级

### 全栈 UI 自动化体系升级

- 新增全栈 UI 自动化测试系统（Web 管理端 + 执行器）。
- 支持批量并发执行、执行器配置管理、执行记录按项目过滤。
- 新增 Playwright 执行追踪录制与可视化回放能力。


### LangGraph 与模型能力升级

- 新增多供应商 LLM 支持并集成通义千问（Qwen）。
- 新增项目作用域上下文注入能力（提示词自动拼装项目信息）。
- 聊天支持图表预览、HTML 预览与代码块可折叠预览。

### 部署与开箱体验升级

- 容器启动新增预置 Skills 自动初始化（`init_skills`）。
- Docker 本地开发支持挂载 bundled skills 自动同步。
- 新增 `run_local_compose.sh` 一键构建、启动、日志采集脚本。

## ✨ 新功能

### UI 自动化能力增强

- 新增 UI 自动化 Skill 工具集并优化元素采集策略（优先 `agent-browser-skill`）。
- 支持测试步骤变量动态替换。
- 批量执行详情新增步骤结果与错误信息展示。
- 支持删除执行记录并自动清理关联文件。
- UI 自动化菜单提升为顶级入口。
![alt text](./img_1.png)
![alt text](./img_8.png)
![alt text](./img_2.png)
![alt text](./img_3.png)
#### 操作步骤
1.创建一个模块
![alt text](./img_9.png)
2.创建一个页面
![alt text](./img_10.png)
3.添加页面元素
![alt text](./img_11.png)
![alt text](./img_12.png)
4.新增页面步骤
![alt text](./img_13.png)
5.添加步骤
![alt text](./img_14.png)
![alt text](./img_15.png)
6.创建环境配置
![alt text](./img_16.png)
7.启动执行器  
终端执行下面的命令
![alt text](./img_17.png)
![alt text](./img_18.png)
![alt text](./img_19.png)
![alt text](./img_20.png)
![alt text](./img_21.png)
8.创建测试用例
![alt text](./img_22.png)
9.执行测试用例
![alt text](./img_23.png)
![alt text](./img_24.png)
![alt text](./img_25.png)
![alt text](./img_26.png)
![alt text](./img_27.png)
### Agent 交互能力增强

- 工具消息支持头像与图片悬浮预览，支持拖动和关闭。
- 支持用户消息图片 URL 提取与工具结果图像 URL 展示。
- 工具审批弹窗支持分组折叠，并增强中断恢复上下文。
- 优化 MCP 工具输出解析与展示逻辑。
![alt text](./img_4.png)
### 测试用例管理增强

- 测试用例新增测试类型分类。
- 支持 Skill 工具批量执行。
- 支持按模块导出测试用例。
![alt text](./img_5.png)
![alt text](./img_6.png)
![alt text](./img_7.png)
### APP自动化MCP

1.下载platform-tools解压到本地并配置系统环境变量已保证adb命令正常使用
![alt text](./img_55.png)

2.双击mcp目录下的Windows 批处理文件启动mcp服务
![alt text](./img_54.png)
![alt text](./img_47.png)

3.将你的url填写到MCP配置中，ip是本机ip端口为8920。
![alt text](./img_60.png)
![alt text](./img_48.png)

4.打开模拟器，并进入开发者模式，这里演示的是mumu模拟器。
![alt text](./img_50.png)
![alt text](./img_51.png)

注意：这里连续点击7次版本号进入开发者模式

![alt text](./img_52.png)

5.cmd运行adb devices，监测模拟器是否连接成功
![alt text](./img_53.png)

6.在llm对话测试mcp是否连通
![alt text](./img_49.png)
## 🐛 问题修复

### 聊天与会话

- 修复 `tool_calls / tool_call_id` 历史配对异常问题。
- 修复会话 Token 统计更新时间缺失问题。
- 修复聊天侧边栏无效日期导致的时间显示异常。
- 清理会话启动时残留的停止信号。

### UI 自动化

- 修复模块树扁平化循环引用问题并切换树形 API。
- 修复搜索框清空后列表不刷新的问题。
- 优化编辑与查看详情时的数据加载与错误提示。
- 修复页面步骤按钮文案与列表列宽等交互问题。

### 系统稳定性

- 增强 persistent client 连接异常处理与日志记录。
- 中间件新增模型重试与异常处理，优化上下文限制逻辑。
- 修复数据库未就绪时的认证错误响应提示。
- 修复登录页原生密码显示按钮与自定义图标重复问题。

## 🔧 优化改进

- 移除内置 Diagram 工具，适配 MCP 响应格式。
- Draw.io 由自托管切换为官方在线版本。
- Docker 镜像构建纳入 `ui_automation`，并清理冗余产物。
- 默认禁用 `xinference` 服务，降低默认资源占用。
- 更新本地 compose 注释与开发体验文档。

## 📦 升级说明

1. 升级后请执行数据库迁移：`python manage.py migrate`。
2. Docker 本地开发建议使用：`./scripts/run_local_compose.sh docker-compose.local.yml`。
3. 若需启用 `xinference`，请在 compose 文件中手动开启对应服务。
4. 若依赖 Draw.io 自托管能力，请调整为官方在线模式或自行扩展代理方案。
5. 提示：此版本去掉了UI自动化脚本库，重构成了UI自动化模块，升级此版本会造成数据丢失，请提前备份。