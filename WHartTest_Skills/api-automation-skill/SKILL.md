---
name: api-automation
description: WHartTest 接口自动化管理工具。用于管理接口模块、数据库配置、环境与变量、自定义函数、接口调试、测试用例、同步配置、任务套件与执行结果。当需要创建接口自动化资源、调试接口、编排用例、执行测试或排查同步问题时使用。
---

# WHartTest 接口自动化管理

## 生命周期概览

```text
基础资源准备 → 接口调试验证 → 用例编排 → 执行与报告 → 套件批量执行 → 同步与回滚

1. 模块/数据库/环境/变量/函数
2. 接口定义与 quick_debug / run
3. 测试用例、步骤、标签、分组
4. 单用例执行 / 批量执行 / 历史报告
5. 任务套件执行 / 查看 case_results / 取消执行
6. 接口-步骤同步 / 立即同步 / 批量同步 / 历史回滚
```

## 关键原则

- **先查后建**：创建模块、环境、接口、用例前，优先先查现有资源，避免重复。
- **先调试后编排**：接口定义好后先用 `quick_debug_interface` 或 `run_interface` 验证，再写入测试用例。
- **复杂 JSON 用 `@文件`**：`--payload` 和 `--params` 都支持 `@绝对或相对路径.json`，适合长 JSON。
- **统一返回 JSON**：所有动作都返回 JSON，成功时通常包含 `status/data`，失败时返回 `status=error`。

## 快速开始

```bash
# 基本调用
python api_automation_tools.py --action <action_name> --project_id <project_id>

# 带请求体
python api_automation_tools.py --action <action_name> --project_id 1 --payload '{"name":"示例"}'

# 从文件读取 JSON
python api_automation_tools.py --action create_interface --project_id 1 --payload @payload.json

# 带查询参数
python api_automation_tools.py --action list_interfaces --project_id 1 --params '{"module_id":10,"page":1,"page_size":50}'
```

## 常用枚举值

### 数据库类型

- `mysql`
- `postgresql`
- `sqlite`
- `oracle`
- `sqlserver`

### 环境变量类型

- `string`
- `integer`
- `float`
- `boolean`
- `json`
- `list`
- `dict`

### 接口类型与方法

- 接口类型：`http`、`sql`
- HTTP 方法：`GET`、`POST`、`PUT`、`DELETE`、`PATCH`
- SQL 方法：`fetchone`、`fetchmany`、`fetchall`、`insert`、`update`、`delete`

### 用例/任务优先级

- `P0`
- `P1`
- `P2`
- `P3`

### 同步配置

- `sync_mode`：`manual`、`auto`
- `sync_fields` 可选：`method`、`url`、`headers`、`params`、`body`、`setup_hooks`、`teardown_hooks`、`variables`、`validators`、`extract`

### 执行状态

- 用例报告：`success`、`failure`、`error`
- 任务执行：`pending`、`running`、`completed`、`failed`、`canceled`
- 套件用例结果：`pending`、`running`、`success`、`failure`、`error`、`skipped`

## 可用动作

### 模块管理

| Action | 说明 |
|---|---|
| `list_modules` | 列出模块 |
| `get_module` | 获取模块详情 |
| `create_module` | 创建模块 |
| `update_module` | 更新模块 |
| `delete_module` | 删除模块 |
| `get_module_tree` | 获取模块树 |
| `search_modules` | 按关键字搜索模块 |

### 数据库配置

| Action | 说明 |
|---|---|
| `list_database_configs` / `get_database_config` | 查询数据库配置 |
| `create_database_config` / `update_database_config` / `delete_database_config` | 维护数据库配置 |
| `test_database_connection` | 用临时参数测试数据库连接 |
| `test_saved_database_connection` | 测试已保存的数据库配置 |

### 环境与变量

| Action | 说明 |
|---|---|
| `list_environments` / `get_environment` | 查询环境 |
| `create_environment` / `update_environment` / `delete_environment` | 维护环境 |
| `clone_environment` | 克隆环境及其变量 |
| `list_environment_variables` | 查询环境变量 |
| `create_environment_variable` / `update_environment_variable` / `delete_environment_variable` | 维护单个变量 |
| `batch_create_environment_variables` | 批量创建环境变量 |
| `batch_update_environment_variables` | 批量更新环境变量 |
| `list_global_headers` / `get_global_header` | 查询全局请求头 |
| `create_global_header` / `update_global_header` / `delete_global_header` | 维护全局请求头 |

### 自定义函数

| Action | 说明 |
|---|---|
| `list_functions` / `get_function` | 查询自定义函数 |
| `create_function` / `update_function` / `delete_function` | 维护自定义函数 |
| `generate_debugtalk` | 生成项目级 `debugtalk.py` 内容 |
| `execute_function` | 测试执行函数代码 |

### 接口定义与调试

| Action | 说明 |
|---|---|
| `list_interfaces` / `get_interface` | 查询接口 |
| `create_interface` / `update_interface` / `delete_interface` | 维护接口 |
| `run_interface` | 执行已保存接口 |
| `quick_debug_interface` | 不落库快速调试接口 |
| `list_interface_results` / `get_interface_result` | 查询接口调试/运行结果 |

### 用例标签、分组、用例与报告

| Action | 说明 |
|---|---|
| `list_testcase_tags` / `get_testcase_tag` | 查询标签 |
| `create_testcase_tag` / `update_testcase_tag` / `delete_testcase_tag` | 维护标签 |
| `get_tag_statistics` | 获取标签使用统计 |
| `list_testcase_groups` / `get_testcase_group` | 查询分组 |
| `create_testcase_group` / `update_testcase_group` / `delete_testcase_group` | 维护分组 |
| `get_testcase_group_tree` | 获取分组树 |
| `get_group_testcases` | 获取某分组下的用例 |
| `list_testcases` / `get_testcase` | 查询测试用例 |
| `create_testcase` / `update_testcase` / `delete_testcase` | 维护测试用例 |
| `get_available_interfaces` | 获取可引用接口列表 |
| `get_referenced_interfaces` | 查看用例引用的接口 |
| `copy_testcase` | 复制测试用例 |
| `run_testcase` | 执行单个测试用例 |
| `batch_run_testcases` | 批量执行多个用例 |
| `delete_testcase_step` | 删除用例中的某个步骤 |
| `update_testcase_step` | 更新某个步骤 |
| `reorder_testcase_steps` | 重排步骤顺序 |
| `get_history_reports` | 查看某用例历史报告 |
| `list_test_reports` / `get_test_report` | 查询测试报告 |

### 同步配置与回滚

| Action | 说明 |
|---|---|
| `list_sync_configs` / `get_sync_config` | 查询同步配置 |
| `create_sync_config` / `update_sync_config` / `delete_sync_config` | 维护同步配置 |
| `sync_now` | 立即触发单条同步 |
| `batch_sync` | 批量触发同步 |
| `list_sync_histories` / `get_sync_history` | 查询同步历史 |
| `rollback_sync_history` | 回滚某条同步历史 |
| `list_global_sync_configs` / `get_global_sync_config` | 查询全局同步配置 |
| `create_global_sync_config` / `update_global_sync_config` / `delete_global_sync_config` | 维护全局同步配置 |
| `set_active_global_sync_config` | 将某个全局同步配置设为当前生效 |
| `get_current_global_sync_config` | 获取当前生效的全局同步配置 |

### 任务套件与批量执行

| Action | 说明 |
|---|---|
| `list_task_suites` / `get_task_suite` | 查询任务套件 |
| `create_task_suite` / `update_task_suite` / `delete_task_suite` | 维护任务套件 |
| `add_suite_testcases` | 向任务套件批量添加用例 |
| `remove_suite_testcase` | 从套件中移除某个用例 |
| `list_task_executions` / `get_task_execution` | 查询任务执行 |
| `execute_task_suite` | 发起套件执行 |
| `get_task_case_results` | 查看某次套件执行下的每条用例结果 |
| `cancel_task_execution` | 取消待执行/执行中的任务 |

## 常见 Payload 结构

### 创建数据库配置

```json
{
	"name": "mysql-dev",
	"type": "mysql",
	"host": "127.0.0.1",
	"port": 3306,
	"username": "root",
	"password": "123456",
	"database": "demo",
	"charset": "utf8mb4",
	"verify_ssl": false,
	"is_active": true,
	"description": "开发环境 MySQL"
}
```

### 创建环境

```json
{
	"name": "dev",
	"base_url": "https://dev.example.com",
	"verify_ssl": false,
	"description": "开发环境",
	"is_active": true
}
```

### 批量创建环境变量

```json
{
	"environment_id": 10,
	"variables": [
		{"name": "token", "value": "demo-token", "type": "string"},
		{"name": "tenant_id", "value": "1001", "type": "integer"}
	]
}
```

### 创建 HTTP 接口

```json
{
	"name": "登录接口",
	"type": "http",
	"module": 5,
	"method": "POST",
	"url": "/api/login",
	"headers": [{"key": "Content-Type", "value": "application/json"}],
	"params": [],
	"body": {"type": "json", "content": {"username": "admin", "password": "123456"}},
	"variables": {},
	"validators": [{"eq": ["status_code", 200]}],
	"extract": {"token": "body.data.token"},
	"setup_hooks": [],
	"teardown_hooks": []
}
```

### 快速调试 SQL 接口

```json
{
	"name": "查询用户",
	"type": "sql",
	"method": "fetchone",
	"sql": "select id, username from user where id = 1",
	"sql_params": {},
	"environment_id": 10
}
```

### 创建测试用例

```json
{
	"name": "登录成功用例",
	"description": "验证登录接口返回 token",
	"priority": "P0",
	"group": 3,
	"tags": [1, 2],
	"config": {},
	"steps_info": [
		{
			"name": "调用登录接口",
			"order": 1,
			"interface_id": 20,
			"interface_data": {
				"extract": {"token": "body.data.token"},
				"validators": [{"eq": ["status_code", 200]}],
				"variables": {},
				"setup_hooks": [],
				"teardown_hooks": []
			}
		}
	]
}
```

### 创建任务套件

```json
{
	"name": "登录回归套件",
	"description": "登录相关接口回归",
	"priority": "P1",
	"fail_fast": false,
	"test_cases": [101, 102, 103]
}
```

### 创建同步配置

```json
{
	"name": "登录接口同步配置",
	"description": "保持步骤与接口定义一致",
	"interface": 20,
	"testcase": 101,
	"step": 301,
	"sync_fields": ["url", "headers", "body", "validators", "extract"],
	"sync_enabled": true,
	"sync_mode": "manual",
	"sync_trigger": {}
}
```

## 使用示例

### 1. 获取模块树

```bash
python api_automation_tools.py --action get_module_tree --project_id 1
```

### 2. 创建数据库配置并测试连接

```bash
python api_automation_tools.py --action create_database_config --project_id 1 --payload @db.json
python api_automation_tools.py --action test_saved_database_connection --project_id 1 --database_config_id 8
```

### 3. 创建环境并批量写入变量

```bash
python api_automation_tools.py --action create_environment --project_id 1 --payload '{"name":"dev","base_url":"https://dev.example.com"}'
python api_automation_tools.py --action batch_create_environment_variables --project_id 1 --payload @env-vars.json
```

### 4. 创建接口并快速调试

```bash
python api_automation_tools.py --action create_interface --project_id 1 --payload @login-interface.json
python api_automation_tools.py --action quick_debug_interface --project_id 1 --payload @quick-debug.json
python api_automation_tools.py --action run_interface --project_id 1 --interface_id 20 --payload '{"environment_id":10}'
```

### 5. 创建用例并执行

```bash
python api_automation_tools.py --action create_testcase --project_id 1 --payload @testcase.json
python api_automation_tools.py --action run_testcase --project_id 1 --testcase_id 101 --payload '{"environment_id":10}'
python api_automation_tools.py --action get_history_reports --project_id 1 --testcase_id 101 --params '{"page":1,"page_size":20}'
```

### 6. 批量执行多个用例

```bash
python api_automation_tools.py --action batch_run_testcases --project_id 1 --payload '{"testcase_ids":[101,102,103],"environment_id":10}'
```

### 7. 创建并执行任务套件

```bash
python api_automation_tools.py --action create_task_suite --project_id 1 --payload @suite.json
python api_automation_tools.py --action add_suite_testcases --project_id 1 --task_suite_id 6 --payload '{"testcase_ids":[101,102]}'
python api_automation_tools.py --action execute_task_suite --project_id 1 --payload '{"task_suite_id":6,"environment_id":10}'
python api_automation_tools.py --action get_task_case_results --project_id 1 --task_execution_id 88
```

### 8. 创建同步配置并立即同步

```bash
python api_automation_tools.py --action create_sync_config --project_id 1 --payload @sync-config.json
python api_automation_tools.py --action sync_now --project_id 1 --sync_config_id 15
python api_automation_tools.py --action batch_sync --project_id 1 --payload '{"config_ids":[15,16]}'
```

### 9. 回滚同步历史

```bash
python api_automation_tools.py --action list_sync_histories --project_id 1 --params '{"config_id":15}'
python api_automation_tools.py --action rollback_sync_history --project_id 1 --sync_history_id 99
```

## 故障排查

| 问题 | 处理建议 |
|---|---|
| `401 Unauthorized` / `403 Forbidden` | 检查文件内默认 `API Key` 或命令行传入的 `--api_key` 是否正确，确认当前用户对项目有权限 |
| `404 Not Found` | 检查 `project_id` 和各类资源 ID 是否正确，确认资源属于当前项目 |
| `JSON 解析失败` | 检查 `--payload` / `--params` 是否为合法 JSON，复杂结构建议用 `@文件` |
| 数据库连接失败 | 优先用 `test_database_connection` 或 `test_saved_database_connection` 验证 |
| 接口执行失败 | 先用 `quick_debug_interface` 缩小问题，再检查环境变量、请求头、body、validators |
| 用例执行失败 | 查看 `get_test_report` 或 `get_history_reports`，定位失败步骤和报告详情 |
| 套件执行卡住 | 用 `get_task_execution` 查看状态，必要时 `cancel_task_execution` |
| 同步结果不符合预期 | 先查 `list_sync_histories`，再决定是否 `rollback_sync_history` |

## 建议工作流

1. `get_module_tree` / `list_environments` / `list_interfaces`
2. 如需新增资源，先 `create_*`
3. 接口优先 `quick_debug_interface`
4. 验证通过后再 `create_testcase`
5. 先 `run_testcase`，再考虑 `execute_task_suite`
6. 若接口定义变更，再通过 `sync_now` / `batch_sync` 更新用例步骤
7. 若同步异常，查看 `list_sync_histories` 并按需 `rollback_sync_history`
