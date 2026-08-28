---
name: api-automation
description: WHartTest 接口自动化管理工具。用于按真实后端接口管理接口模块、数据库配置、环境与变量、自定义函数、接口定义与调试、单接口用例 ApiInterfaceCase、场景用例 ApiTestCase、任务套件、执行报告与同步配置。当需要创建、查询、修改、执行 API 自动化资源，区分单接口测试和场景用例，或排查执行、同步、任务套件问题时使用。
---

# WHartTest 接口自动化管理

## 先遵守这些

- **以当前代码为准**：动作清单以 `api_automation_tools.py` 的 `ACTIONS` 为准；字段语义以 Django 的 models/serializers/views 为准。不要按旧 skill 或记忆猜字段。
- **先查后建**：创建模块、环境、接口、用例、套件前，先 `list_*` / `get_*`，避免重复。
- **不要混用两个用例概念**：
  - **单接口用例**是 `ApiInterfaceCase`，接口路径是 `api-interface-cases`，CLI 动作用 `*_interface_case`。
  - **场景用例**是 `ApiTestCase`，接口路径是 `api-testcases`，CLI 动作用 `*_testcase`。
- **同步只支持场景步骤**：`ApiSyncConfig.step` 绑定的是 `ApiTestCaseStep`，不是 `ApiInterfaceCaseStep`。
- **复杂 JSON 用文件**：`--payload "@payload.json"` 和 `--params "@params.json"` 都支持从文件读取 JSON。PowerShell 下必须给 `@文件` 加引号，否则会被当作 splatting 语法。
- **所有动作返回 JSON**：成功通常是 `{"status":"success","data":...}`；失败是 `{"status":"error",...}`。

## CLI 用法

```bash
python api_automation_tools.py --action <action_name> --project_id <project_id>
python api_automation_tools.py --action create_interface --project_id 1 --payload "@interface.json"
python api_automation_tools.py --action list_interfaces --project_id 1 --params '{"page":1,"page_size":50}'
```

可覆盖默认服务地址和 API Key：

```bash
python api_automation_tools.py --action list_modules --project_id 1 --base_url http://127.0.0.1:8000 --api_key wharttest-default-mcp-key-2025
```

## 用例概览

接口自动化测试中，**用例管理**分为两个页签，对应两种不同的用例类型：

| 维度 | 单接口用例（接口用例页签） | 场景用例（场景用例页签） |
|------|--------------------------|------------------------|
| **模型** | `ApiInterfaceCase` | `ApiTestCase` |
| **API 路径** | `api-interface-cases` | `api-testcases` |
| **CLI 动作前缀** | `*_interface_case` | `*_testcase` |
| **用途** | 针对**单个接口**进行测试，比如验证登录接口的各种入参组合 | 编排**多接口业务流程**，比如"登录→查询个人资料→修改资料" |
| **步骤结构** | 一个 `role=main` 的主步骤（绑定被测接口）+ 可选 `role=precondition` 的前置步骤 | 多个 `role` 无区别的步骤，每步绑定一个接口，按 `order` 顺序执行 |
| **主接口绑定** | 创建时顶层传 `interface_id`，后端自动生成主步骤 | 无顶层绑定，每步各自指定 `interface_id` |
| **批量执行** | 通过任务套件（`task_suite.interface_cases`） | 通过 `batch_run_testcases` 或任务套件（`task_suite.test_cases`） |
| **报告模型** | `ApiInterfaceCaseReport` | `ApiTestReport` |
| **同步配置** | 不支持 | 支持（`ApiSyncConfig` 绑定场景步骤） |

> **工作流提示**：先用 `quick_debug_interface` 或 `run_interface` 验证接口定义，再沉淀为接口用例或场景用例步骤。

## 真实概念边界

### 接口定义

`ApiInterface` 是保存的接口定义，支持 HTTP 和 SQL。先用 `quick_debug_interface` 或 `run_interface` 验证接口定义，再沉淀为单接口用例或场景用例步骤。

HTTP 的 `headers`、`params` 可以传对象或 key-value 数组，后端会规范化为数组。`body.type` 支持 `none`、`form-data`、`x-www-form-urlencoded`、`raw`、`binary`。

### 提取变量

`extract` 是变量名到 JMESPath 表达式的映射。`extract_meta` 是同名变量的元信息，支持 `variable_type: "temporary" | "project"` 和 `source: "response" | "request"`。

- 省略 `source` 时按 `response` 处理。
- `source: "response"` 从响应对象提取，继续使用现有写法，例如 `body.data.token`。
- `source: "request"` 从实际发出的请求快照提取，可用根字段是 `method`、`url`、`headers`、`params`、`cookies`、`body`、`json`、`data`，例如 `method`、`url`、`headers.Authorization`、`body.username`。
- `source` 只决定从请求还是响应提取；是否持久化到项目变量仍由 `variable_type: "project"` 决定。
- 接口定义的 serializer 只保留变量名同时存在于 `extract` 的 `extract_meta` 项。
- 同步配置的 `extract` 字段当前只同步提取表达式，不同步 `extract_meta`；如果改了请求/响应来源，要同步后手动检查场景步骤里的 `extract_meta`。

### 断言规则

`validators` 是断言规则数组，支持 `{"eq": ["status_code", 200]}` 和 `{"check": "status_code", "expect": 200}` 两种格式。`check` 默认按响应对象解析，可直接断言 `status_code`、`headers`、`cookies`、`body`。

断言没有独立的 `source` 或 `validators_meta` 字段。需要断言请求内容时，先用 `extract` + `extract_meta.source: "request"` 把请求字段提取成临时变量，再在同一步或后续步骤的 `validators` 里用 `$变量名` 断言。后端执行顺序是先提取、再断言。

接口定义执行器 `InterfaceRunner` 当前支持这些 comparator：`eq`、`ne`、`lt`、`le`、`lte`、`gt`、`ge`、`gte`、`str_eq`、`contains`、`contained_by`、`type_match`、`regex_match`、`startswith`、`endswith`、`length_equal`、`length_greater_than`、`length_less_than`、`length_greater_or_equals`、`length_less_or_equals`。

场景用例和单接口用例当前复用 `TestCaseRunner`，步骤断言实际映射的 comparator 是：`eq`、`ne`、`lt`、`le`、`gt`、`ge`、`str_eq`、`contains`、`contained_by`、`type_match`、`regex_match`。不要在场景步骤或单接口步骤里假设 `lte`、`gte`、`startswith`、`endswith`、`length_*` 会被执行，除非代码里的 `api_testcases.runner.TestCaseRunner` 已同步映射。

### 单接口用例（接口用例页签）

`ApiInterfaceCase` 用于"一个被测主接口"的测试。创建时顶层必须传 `interface_id`，后端会自动生成一个 `role=main` 的主步骤，主步骤绑定这个 `interface_id` 对应的接口。

`steps_info` 可选，用来补前置步骤；前置步骤 `role` 为 `precondition`。如果显式传 `role=main`，后端仍只保留一个主步骤，并按"前置步骤在前，主步骤最后"的顺序重建步骤。

单接口用例没有独立的批量执行接口。需要批量或混合执行时，把单接口用例加入任务套件的 `interface_cases`。

### 场景用例（场景用例页签）

`ApiTestCase` 是多步骤业务场景用例。创建或更新步骤使用 `steps_info`，新步骤需要 `interface_id`。每一步落库为 `ApiTestCaseStep`，可以覆盖 `interface_data` 中的请求、断言、提取、变量、hooks 等字段。

`get_group_testcases` 当前只返回分组下的场景用例；标签统计 `get_tag_statistics` 当前也只统计场景用例。

### 任务套件

`ApiTestTaskSuite` 可以同时包含场景用例和单接口用例：

- 创建/更新套件 payload 用 `test_cases` 表示场景用例 ID 列表。
- 创建/更新套件 payload 用 `interface_cases` 表示单接口用例 ID 列表。
- 向已有套件追加用例用 `testcase_ids` 和 `interface_case_ids`。
- 套件内用例类型是 `case_type: "scenario" | "interface"`。

## 常用枚举

- 数据库类型：`mysql`、`postgresql`、`sqlite`、`oracle`、`sqlserver`
- 环境变量类型：`string`、`integer`、`float`、`boolean`、`json`、`list`、`dict`
- 接口类型：`http`、`sql`
- HTTP 方法：`GET`、`POST`、`PUT`、`DELETE`、`PATCH`
- SQL 方法：`fetchone`、`fetchmany`、`fetchall`、`insert`、`update`、`delete`
- 提取变量类型：`temporary`、`project`
- 提取来源：`response`、`request`
- 用例/套件优先级：`P0`、`P1`、`P2`、`P3`
- 单接口步骤角色：`precondition`、`main`
- 任务套件用例类型：`scenario`、`interface`
- 执行状态：报告 `success`、`failure`、`error`；任务执行 `pending`、`running`、`completed`、`failed`、`canceled`；套件用例结果 `pending`、`running`、`success`、`failure`、`error`、`skipped`
- 同步字段：`method`、`url`、`headers`、`params`、`body`、`setup_hooks`、`teardown_hooks`、`variables`、`validators`、`extract`
- 同步模式：`manual`、`auto`

## 可用动作

### 基础资源

| Action | 说明 |
|---|---|
| `list_modules` / `get_module` / `create_module` / `update_module` / `delete_module` | 接口模块 CRUD |
| `get_module_tree` / `search_modules` / `move_module` | 模块树、搜索与移动 |
| `list_database_configs` / `get_database_config` / `create_database_config` / `update_database_config` / `delete_database_config` | 数据库配置 CRUD |
| `test_database_connection` / `test_saved_database_connection` | 测试临时或已保存数据库连接 |
| `list_environments` / `get_environment` / `create_environment` / `update_environment` / `delete_environment` | 环境 CRUD |
| `clone_environment` | 克隆环境及变量 |
| `list_environment_variables` / `get_environment_variable` / `create_environment_variable` / `update_environment_variable` / `delete_environment_variable` | 环境变量 CRUD |
| `batch_create_environment_variables` / `batch_update_environment_variables` | 批量维护环境变量 |
| `list_global_headers` / `get_global_header` / `create_global_header` / `update_global_header` / `delete_global_header` | 全局请求头 CRUD |
| `list_functions` / `get_function` / `create_function` / `update_function` / `delete_function` | 自定义函数 CRUD |
| `generate_debugtalk` / `execute_function` | 生成 debugtalk 或试运行函数代码 |

### 接口定义与调试

| Action | 说明 |
|---|---|
| `list_interfaces` / `get_interface` / `create_interface` / `update_interface` / `delete_interface` | 接口定义 CRUD |
| `duplicate_interface` | 复制接口定义 |
| `quick_debug_interface` | 不落库快速调试接口 |
| `run_interface` | 执行已保存接口 |
| `list_interface_results` / `get_interface_result` | 查询接口调试/执行结果 |

### 接口用例页签（单接口用例 ApiInterfaceCase）

| Action | 说明 |
|---|---|
| `list_interface_cases` / `get_interface_case` / `create_interface_case` / `update_interface_case` / `delete_interface_case` | 单接口用例 CRUD |
| `copy_interface_case` | 复制单接口用例 |
| `run_interface_case` | 执行单接口用例 |
| `get_interface_case_history_reports` | 查看某个单接口用例历史报告 |
| `list_interface_case_reports` / `get_interface_case_report` | 查询单接口用例报告 |

**查询参数说明**：`list_interface_cases` 支持通过 `--params` 传入以下过滤参数：
- `interface_id` — 按接口 ID 过滤
- `module_id` — 按接口所属模块 ID 过滤（通过接口的 module 关联）
- `no_module` — 过滤未分类的接口用例（`true` / `1`）

### 场景用例页签（场景用例 ApiTestCase）

| Action | 说明 |
|---|---|
| `list_testcases` / `get_testcase` / `create_testcase` / `update_testcase` / `delete_testcase` | 场景用例 CRUD |
| `get_available_interfaces` | 获取可引用接口列表 |
| `get_referenced_interfaces` | 查看场景用例引用的接口 |
| `copy_testcase` | 复制场景用例 |
| `run_testcase` | 执行单个场景用例 |
| `batch_run_testcases` | 批量执行场景用例 |
| `update_testcase_step` / `delete_testcase_step` / `reorder_testcase_steps` | 维护场景用例步骤 |
| `get_history_reports` | 查看某个场景用例历史报告 |
| `list_test_reports` / `get_test_report` | 查询场景用例报告 |

### 标签与分组（两个页签共用）

| Action | 说明 |
|---|---|
| `list_testcase_tags` / `get_testcase_tag` / `create_testcase_tag` / `update_testcase_tag` / `delete_testcase_tag` | 用例标签 CRUD |
| `get_tag_statistics` | 标签使用统计（当前统计场景用例） |
| `list_testcase_groups` / `get_testcase_group` / `create_testcase_group` / `update_testcase_group` / `delete_testcase_group` | 用例分组 CRUD |
| `get_testcase_group_tree` | 分组树 |
| `get_group_testcases` | 某分组下的场景用例 |

> 标签和分组由**接口用例**和**场景用例**共用。`get_group_testcases` 只返回场景用例；接口用例的分组查询可通过 `list_interface_cases` 配合 `--params '{"group_id": N}'` 实现。

### 同步配置

| Action | 说明 |
|---|---|
| `list_sync_configs` / `get_sync_config` / `create_sync_config` / `update_sync_config` / `delete_sync_config` | 场景步骤同步配置 CRUD |
| `sync_now` / `batch_sync` | 立即同步或批量同步 |
| `list_sync_histories` / `get_sync_history` / `rollback_sync_history` | 同步历史与回滚 |
| `list_global_sync_configs` / `get_global_sync_config` / `create_global_sync_config` / `update_global_sync_config` / `delete_global_sync_config` | 全局同步配置 CRUD |
| `set_active_global_sync_config` / `get_current_global_sync_config` | 设置或读取当前生效全局同步配置 |

### 任务套件

| Action | 说明 |
|---|---|
| `list_task_suites` / `get_task_suite` / `create_task_suite` / `update_task_suite` / `delete_task_suite` | 任务套件 CRUD |
| `add_suite_testcases` | 向套件追加场景用例和/或单接口用例 |
| `remove_suite_testcase` | 从套件移除场景用例，兼容旧路径 |
| `remove_suite_interface_case` | 从套件移除单接口用例 |
| `remove_suite_case` | 按 `case_type` + `case_id` 从套件移除任意类型用例 |
| `list_task_executions` / `get_task_execution` | 查询任务执行 |
| `execute_task_suite` | 发起套件执行 |
| `get_task_case_results` | 查看某次套件执行的每条用例结果 |
| `cancel_task_execution` | 取消待执行/执行中的任务 |

## 常见 Payload

### 移动模块

`drop_position` 取值：`-1` 表示移到目标模块前，`1` 表示移到目标模块后，`0` 表示移入目标模块。`target_id` 为 `null` 时只能移动到根层级，且 `drop_position` 不能为 `0`。

```json
{"target_id": 10, "drop_position": 0}
```

### 创建数据库配置

数据库配置 serializer 暴露字段是 `type`，映射到模型字段 `db_type`。

```json
{
  "name": "sqlite-dev",
  "type": "sqlite",
  "host": "local",
  "port": 0,
  "username": "tester",
  "password": "secret",
  "database": "/tmp/demo.sqlite3",
  "charset": "utf8mb4",
  "verify_ssl": false,
  "is_active": true
}
```

临时测试连接使用 `db_type`：

```json
{"db_type": "sqlite", "database": "/tmp/demo.sqlite3"}
```

### 创建环境与变量

```json
{
  "name": "dev",
  "base_url": "https://dev.example.com",
  "database_config": 8,
  "verify_ssl": false,
  "description": "开发环境"
}
```

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
  "headers": {"Content-Type": "application/json"},
  "params": [],
  "body": {"type": "raw", "content": {"username": "admin", "password": "123456"}},
  "variables": {},
  "validators": [
    {"eq": ["status_code", 200]},
    {"eq": ["$login_request_method", "POST"]},
    {"contains": ["$login_request_method", "O"]},
    {"regex_match": ["$login_request_method", "^POST$"]},
    {"length_equal": ["$login_request_method", 4]}
  ],
  "extract": {
    "token": "body.data.token",
    "login_request_method": "method",
    "login_username": "body.username"
  },
  "extract_meta": {
    "token": {"variable_type": "project", "source": "response"},
    "login_request_method": {"variable_type": "temporary", "source": "request"},
    "login_username": {"variable_type": "temporary", "source": "request"}
  },
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

### 创建单接口用例（接口用例页签）

顶层 `interface_id` 是被测主接口。下面示例包含一个登录前置步骤；如果没有前置步骤，`steps_info` 可以省略或传空数组。

```json
{
  "name": "查询个人资料",
  "description": "登录后调用个人资料接口",
  "priority": "P1",
  "group": 3,
  "tags": [1, 2],
  "interface_id": 20,
  "config": {},
  "steps_info": [
    {
      "name": "登录前置",
      "role": "precondition",
      "order": 1,
      "interface_id": 19,
      "interface_data": {
        "extract": {
          "token": "body.data.token",
          "login_request_method": "method"
        },
        "extract_meta": {
          "token": {"variable_type": "temporary", "source": "response"},
          "login_request_method": {"variable_type": "temporary", "source": "request"}
        },
        "validators": [
          {"eq": ["$login_request_method", "POST"]}
        ]
      }
    }
  ]
}
```

执行：

```bash
python api_automation_tools.py --action run_interface_case --project_id 1 --interface_case_id 88 --payload '{"environment_id":10}'
```

### 创建场景用例（场景用例页签）

`create_testcase` 用于多接口业务流程，不用于单接口用例。

```json
{
  "name": "登录后查询个人资料",
  "description": "多接口业务流程",
  "priority": "P0",
  "group": 3,
  "tags": [1, 2],
  "config": {},
  "steps_info": [
    {
      "name": "调用登录接口",
      "order": 1,
      "interface_id": 19,
      "interface_data": {
        "extract": {
          "token": "body.data.token",
          "login_request_method": "method"
        },
        "extract_meta": {
          "token": {"variable_type": "temporary", "source": "response"},
          "login_request_method": {"variable_type": "temporary", "source": "request"}
        },
        "validators": [
          {"eq": ["status_code", 200]},
          {"eq": ["$login_request_method", "POST"]}
        ]
      }
    },
    {
      "name": "查询个人资料",
      "order": 2,
      "interface_id": 20,
      "interface_data": {
        "headers": [{"key": "Authorization", "value": "Bearer $token", "enabled": true}],
        "validators": [{"eq": ["status_code", 200]}]
      }
    }
  ]
}
```

### 创建和维护任务套件

```json
{
  "name": "接口回归套件",
  "description": "混合执行场景用例与单接口用例",
  "priority": "P1",
  "fail_fast": false,
  "test_cases": [101, 102],
  "interface_cases": [201, 202]
}
```

追加用例：

```bash
python api_automation_tools.py --action add_suite_testcases --project_id 1 --task_suite_id 6 --payload '{"testcase_ids":[101],"interface_case_ids":[201]}'
```

移除用例：

```bash
python api_automation_tools.py --action remove_suite_testcase --project_id 1 --task_suite_id 6 --testcase_id 101
python api_automation_tools.py --action remove_suite_interface_case --project_id 1 --task_suite_id 6 --interface_case_id 201
python api_automation_tools.py --action remove_suite_case --project_id 1 --task_suite_id 6 --case_type interface --case_id 201
```

执行套件：

```bash
python api_automation_tools.py --action execute_task_suite --project_id 1 --payload '{"task_suite_id":6,"environment_id":10}'
python api_automation_tools.py --action get_task_case_results --project_id 1 --task_execution_id 88
```

### 创建同步配置

同步配置只用于场景用例步骤：

`sync_fields` 里填 `extract` 时只同步 `interface.extract`，当前后端 `api_sync` 没有同步 `extract_meta`；依赖 `source: "request"` 的提取规则同步后要检查步骤来源元信息。

```json
{
  "name": "登录接口同步配置",
  "description": "保持场景步骤与接口定义一致",
  "interface": 20,
  "testcase": 101,
  "step": 301,
  "sync_fields": ["url", "headers", "body", "validators", "extract"],
  "sync_enabled": true,
  "sync_mode": "manual",
  "sync_trigger": {}
}
```

## 推荐工作流

### 按页签分步操作

1. **基础准备**：`get_module_tree`、`list_environments`、`list_interfaces`，先确认基础资源。
2. **接口定义**：新接口先 `create_interface`，再 `quick_debug_interface` 或 `run_interface` 验证。
3. **接口用例页签**：用户要"单个接口测试"时，走**接口用例页签** → 使用 `create_interface_case`（不是 `create_testcase`）。
4. **场景用例页签**：用户要"业务流程/多接口编排/场景"时，走**场景用例页签** → 使用 `create_testcase`。
5. **执行**：单接口用例用 `run_interface_case`；场景用例用 `run_testcase` 或 `batch_run_testcases`。
6. **混合批量执行**：创建任务套件，使用 `test_cases` + `interface_cases` 混合编排。
7. **同步**：只有场景用例步骤需要接口定义同步时，才创建 `ApiSyncConfig` 并执行 `sync_now` / `batch_sync`。

### 快速判断

| 用户说的是 | 对应的页签 | 创建动作 | 执行动作 |
|-----------|-----------|---------|---------|
| "测试登录接口"、"单个接口验证" | 接口用例页签 | `create_interface_case` | `run_interface_case` |
| "登录后查询资料"、"业务流程" | 场景用例页签 | `create_testcase` | `run_testcase` / `batch_run_testcases` |
| "批量执行回归" | 任务套件 | `create_task_suite` | `execute_task_suite` |

## 排查提示

| 问题 | 处理建议 |
|---|---|
| `401 Unauthorized` / `403 Forbidden` | 检查 `--api_key` 与项目权限 |
| `404 Not Found` | 检查 `project_id` 和资源 ID 是否属于同一项目 |
| JSON 解析失败 | 使用合法 JSON，复杂结构改用 `"@文件.json"`；PowerShell 下不要省略引号 |
| 创建单接口用例失败 | 确认顶层 `interface_id` 存在且属于当前项目 |
| 单接口用例没有主步骤 | 后端应自动创建 `role=main`；检查创建响应中的 `main_step` |
| 场景步骤创建失败 | 新步骤必须提供有效 `interface_id`，或更新已有步骤时提供 `step_id` |
| 套件用例类型不对 | 场景用例放 `test_cases`/`testcase_ids`，单接口用例放 `interface_cases`/`interface_case_ids` |
| 同步配置不生效 | 确认目标是 `ApiTestCaseStep`；单接口用例步骤当前不支持同步配置 |