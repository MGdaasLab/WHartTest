---
name: ui-automation
description: WHartTest UI 自动化管理工具。用于创建、编辑、删除 UI 测试模块、页面、元素、页面步骤和测试用例。支持执行记录查询和错误分析。当需要将浏览器技能获取到的页面元素保存到平台、创建 UI 自动化用例、执行测试或分析执行结果时使用。元素采集默认优先 browser-use，无法覆盖时再用 playwright-skill 兜底。
---

# WHartTest UI 自动化管理

## 生命周期概览

```
┌─────────────────────────────────────────────────────────────────┐
│                    UI 自动化完整生命周期                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 设计阶段          2. 构建阶段           3. 执行阶段          │
│  ┌──────────┐        ┌──────────┐         ┌──────────┐         │
│  │ 查询模块  │        │ 查询页面  │         │ 执行用例  │         │
│  │ (是否存在)│        │ (是否存在)│         │ (运行)   │         │
│  └────┬─────┘        └────┬─────┘         └──────────┘         │
│       │ 不存在则创建        │ 不存在则创建        │               │
│       ↓                   ↓                    ↓               │
│  ┌──────────┐        ┌──────────┐         ┌──────────┐         │
│  │ 创建/复用 │        │ 添加元素  │         │ 查看记录  │         │
│  │ 模块/环境 │        │ (定位器) │         │ (状态)   │         │
│  └──────────┘        └──────────┘         └──────────┘         │
│                           │                    │               │
│                           ↓                    ↓               │
│                      ┌──────────┐         ┌──────────┐         │
│                      │ 创建步骤  │         │ 分析错误  │         │
│                      │ (操作)   │         │ (定位)   │         │
│                      └──────────┘         └──────────┘         │
│                           │                    │               │
│                           ↓                    ↓               │
│                      ┌──────────┐         ┌──────────┐         │
│                      │ 组装用例  │←────────│ 修复重试  │         │
│                      │ (P0-P3) │         │ (迭代)   │         │
│                      └──────────┘         └──────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 阶段说明

| 阶段 | 操作 | 说明 |
|------|------|------|
| **设计** | `get_ui_modules` → `create_ui_module` (可选) → `get_env_configs` → `create_env_config` (可选) | 先查询现有资源，按需创建 |
| **构建** | `get_ui_pages` → `create_ui_page` → `create_element` → `create_page_step` → `create_testcase` | 先查后建，逐层构建 |
| **执行** | `get_testcase_execute_data` → 执行 → `get_execution_records` → 分析修复 | 执行并迭代优化 |

**重要原则：先查后建**
- 创建任何资源前，必须先使用对应的 `get_*` 操作查询是否已存在
- 如果已存在合适的资源，直接使用其 ID，避免重复创建

## 快速开始

```bash
# 执行操作
python ui_automation_tools.py --action <action_name> [--参数名 参数值]
```

## 元素采集策略（强制）

### 技术路线优先级

1. 默认使用 `browser-use` 进行页面访问、元素抓取与识别（CDP / 可访问性树）。
2. 仅当 `browser-use` 无法稳定获取目标元素时，才使用 `playwright-skill` 兜底。
3. `ui-automation-skill` 负责将已确认的元素表达式入库并组装步骤/用例。

### 元素表达式质量标准（必须满足）

1. 唯一性：元素表达式在当前目标页面必须唯一匹配（期望匹配数为 `1`）。
2. 客观性：优先依赖页面客观稳定属性，不依赖主观描述和截图猜测。
3. 可维护性：优先选择改版后仍相对稳定的属性组合，避免脆弱路径。
4. 简约性：在满足唯一性的前提下，表达式尽量短且语义清晰。

### 推荐的定位优先级

1. `test_id` / `data-testid` / 业务稳定 id
2. `role + name`（可访问性语义）
3. `name` / `label` / `placeholder`（稳定时）
4. `css`（稳定属性组合）
5. `xpath`（仅在上面都不适用时）

### 反模式（避免）

1. 纯索引路径：如 `:nth-child()` 深层链、绝对 XPath（`/html/body/...`）
2. 易变 class：构建产物 hash class、运行时动态 class
3. 易变文本：时间戳、数量、用户名、随机文案

## 与 browser-use / playwright-skill 协作流程

```
browser-use                    playwright-skill                 ui-automation-skill
       │                             │                                  │
       │ 1. 默认：CDP/可访问性树抓取元素 │                                  │
       ├─────────────────────────────┼─────────────────────────────────→│ 2. 保存元素 (create_element)
       │                             │                                  │ 3. 创建步骤 (create_page_step)
       │ 1.1 若无法稳定获取元素       │ 1.2 兜底：获取选择器/结构信息        │ 4. 组装用例 (create_testcase)
       └─────────────失败时切换──────→├─────────────────────────────────→│
                                     │                                  │ 5. 执行并查看记录 (get_execution_records)
                                     │                                  │ 6. 分析错误并修复
                                     │                                  │ 7. 重新执行
                                     ↓                                  ↓
```

### AI 错误分析流程

当执行失败时，AI 应按以下流程定位问题：

```bash
# 1. 获取最近失败的执行记录
python ui_automation_tools.py --action get_execution_records --status 3 --limit 1

# 2. 从 step_results 中定位失败步骤
#    - status: "failed" 的步骤
#    - message: 包含具体错误信息（超时、元素未找到等）
#    - element_found: false 表示定位器失效

# 3. 常见错误及解决方案：
#    - "Timeout exceeded": 元素定位器失效，需更新 locator_value
#    - "element not found": 页面结构变化，需重新获取元素（先 browser-use，再 playwright 兜底）
#    - "Target page closed": 前序步骤导致页面关闭

# 4. 更新元素定位器
python ui_automation_tools.py --action update_element --element_id <id> --locator_value "<新选择器>"
```

---

## 可用操作

### 模块管理

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `get_ui_modules` | 获取 UI 模块树 | `--project_id` | - |
| `create_ui_module` | 创建模块 | `--project_id`, `--name` | `--parent_id` |
| `update_ui_module` | 更新模块 | `--module_id`, `--name` | - |
| `delete_ui_module` | 删除模块 | `--module_id` | - |

### 页面管理

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `get_ui_pages` | 获取页面列表 | `--project_id` | `--module_id` |
| `get_ui_page` | 获取页面详情（含元素） | `--page_id` | - |
| `create_ui_page` | 创建页面 | `--project_id`, `--module_id`, `--name` | `--url`, `--description` |
| `update_ui_page` | 更新页面 | `--page_id` | `--name`, `--url`, `--description` |
| `delete_ui_page` | 删除页面 | `--page_id` | - |

### 元素管理

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `get_elements` | 获取页面元素列表 | `--page_id` | - |
| `create_element` | 创建元素 | `--page_id`, `--name`, `--locator_type`, `--locator_value` | `--locator_type_2`, `--locator_value_2`, `--wait_time`, `--description` |
| `update_element` | 更新元素 | `--element_id` | `--name`, `--locator_type`, `--locator_value`, 等 |
| `delete_element` | 删除元素 | `--element_id` | - |
| `batch_create_elements` | 批量创建元素 | `--page_id`, `--elements` (JSON) | - |

**定位类型（locator_type）可选值：**
- `css` - CSS 选择器
- `xpath` - XPath
- `text` - 文本
- `role` - Role
- `label` - Label
- `placeholder` - Placeholder
- `test_id` - Test ID
- `id` - ID
- `name` - Name

### 页面步骤管理

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `get_page_steps` | 获取页面步骤列表 | `--project_id` | `--page_id`, `--module_id` |
| `get_page_step` | 获取页面步骤详情 | `--step_id` | - |
| `create_page_step` | 创建页面步骤 | `--project_id`, `--page_id`, `--module_id`, `--name` | `--description` |
| `update_page_step` | 更新页面步骤 | `--step_id` | `--name`, `--description` |
| `delete_page_step` | 删除页面步骤 | `--step_id` | - |
| `set_step_details` | 设置步骤详情（批量） | `--step_id`, `--steps` (JSON) | - |

**步骤类型（step_type）可选值：**
- `0` - 元素操作
- `1` - 断言操作
- `2` - SQL 操作
- `3` - 自定义变量
- `4` - 条件判断
- `5` - Python 代码

### 测试用例管理

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `get_testcases` | 获取用例列表（精简版） | `--project_id` | `--module_id`, `--level`, `--limit` (默认50) |
| `get_testcase` | 获取用例详情 | `--testcase_id` | - |
| `create_testcase` | 创建测试用例 | `--project_id`, `--module_id`, `--name` | `--description`, `--level` |
| `update_testcase` | 更新测试用例 | `--testcase_id` | `--name`, `--description`, `--level` |
| `delete_testcase` | 删除测试用例 | `--testcase_id` | - |
| `set_case_steps` | 设置用例步骤（批量） | `--testcase_id`, `--page_step_ids` (逗号分隔) | - |

**用例等级（level）可选值：** `P0`, `P1`, `P2`, `P3`

**注意：** `get_testcases` 返回精简数据（id, name, level, status 等），详情请使用 `get_testcase`

### 公共数据管理

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `get_public_data` | 获取公共数据列表 | `--project_id` | - |
| `create_public_data` | 创建公共数据 | `--project_id`, `--key`, `--value` | `--type`, `--description` |
| `update_public_data` | 更新公共数据 | `--data_id` | `--key`, `--value`, `--is_enabled` |
| `delete_public_data` | 删除公共数据 | `--data_id` | - |

### 执行记录管理

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `get_execution_records` | 获取执行记录列表 | - | `--testcase_id`, `--status`, `--limit` |
| `get_execution_record` | 获取执行记录详情 | `--record_id` | - |
| `get_execution_trace` | 获取 Trace 数据 | `--record_id` | `--refresh` |
| `delete_execution_record` | 删除执行记录 | `--record_id` | - |

**执行状态（status）可选值：**
- `0` - 未执行
- `1` - 执行中
- `2` - 成功
- `3` - 失败
- `4` - 取消

### 批量执行记录管理

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `get_batch_records` | 获取批量执行记录列表 | - | `--status`, `--limit` |
| `get_batch_record` | 获取批量执行记录详情 | `--batch_id` | - |
| `delete_batch_record` | 删除批量执行记录 | `--batch_id` | - |

### 环境配置管理

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `get_env_configs` | 获取环境配置列表 | `--project_id` | - |
| `create_env_config` | 创建环境配置 | `--project_id`, `--name` | `--base_url`, `--browser`, `--headless`, `--viewport_width`, `--viewport_height`, `--timeout`, `--is_default` |
| `update_env_config` | 更新环境配置 | `--config_id` | 同上 |
| `delete_env_config` | 删除环境配置 | `--config_id` | - |

**浏览器类型（browser）可选值：** `chromium`, `firefox`, `webkit`

### 执行器管理

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `get_actuators` | 获取在线执行器列表 | - | - |
| `get_actuator_status` | 获取执行器状态统计 | - | - |

### 执行数据获取

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `get_testcase_execute_data` | 获取用例完整执行数据 | `--testcase_id` | - |
| `get_page_step_execute_data` | 获取页面步骤执行数据 | `--step_id` | - |

### 执行用例

| Action | 描述 | 必填参数 | 可选参数 |
|--------|------|----------|----------|
| `execute_testcase` | 执行测试用例 | `--testcase_id` | `--config_id`, `--actuator_id`, `--wait_result`, `--exec_timeout` |
| `execute_page_steps` | 执行页面步骤（调试） | `--step_id` | `--config_id`, `--actuator_id` |

**执行参数说明：**
- `--config_id` - 环境配置 ID（不传使用默认配置）
- `--actuator_id` - 执行器 ID（不传自动选择可用执行器）
- `--wait_result` - 是否等待执行结果（默认否，传此参数则等待）
- `--exec_timeout` - 等待超时时间（秒，默认 120）

**注意：** 执行前需确保有执行器在线（通过 `get_actuators` 查询）

---

## 使用示例

### 获取模块树

```bash
python ui_automation_tools.py --action get_ui_modules --project_id 1
```

### 创建页面

```bash
python ui_automation_tools.py --action create_ui_page \
  --project_id 1 \
  --module_id 5 \
  --name "登录页面" \
  --url "http://example.com/login" \
  --description "用户登录页面"
```

### 创建元素（优先基于 browser-use，失败时使用 playwright-skill）

```bash
# 单个元素
python ui_automation_tools.py --action create_element \
  --page_id 10 \
  --name "用户名输入框" \
  --locator_type css \
  --locator_value "#username" \
  --locator_type_2 xpath \
  --locator_value_2 "//input[@placeholder='请输入用户名']" \
  --description "登录页用户名输入框"

# 批量创建元素
python ui_automation_tools.py --action batch_create_elements \
  --page_id 10 \
  --elements '[
    {"name": "用户名输入框", "locator_type": "css", "locator_value": "#username"},
    {"name": "密码输入框", "locator_type": "css", "locator_value": "#password"},
    {"name": "登录按钮", "locator_type": "css", "locator_value": "button[type=submit]"}
  ]'
```

### 创建页面步骤

```bash
# 创建步骤
python ui_automation_tools.py --action create_page_step \
  --project_id 1 \
  --page_id 10 \
  --module_id 5 \
  --name "输入登录信息" \
  --description "输入用户名和密码"

# 设置步骤详情
python ui_automation_tools.py --action set_step_details \
  --step_id 20 \
  --steps '[
    {"step_type": 0, "element": 101, "ope_key": "fill", "ope_value": {"value": "admin"}},
    {"step_type": 0, "element": 102, "ope_key": "fill", "ope_value": {"value": "password123"}},
    {"step_type": 0, "element": 103, "ope_key": "click", "ope_value": {}}
  ]'
```

### 创建测试用例

```bash
# 创建用例
python ui_automation_tools.py --action create_testcase \
  --project_id 1 \
  --module_id 5 \
  --name "登录功能测试" \
  --description "验证用户登录功能" \
  --level P0

# 设置用例步骤（引用已创建的页面步骤）
python ui_automation_tools.py --action set_case_steps \
  --testcase_id 50 \
  --page_step_ids "20,21,22"
```

---

## 常用操作方法（ope_key）

| 方法 | 描述 | 参数示例 |
|------|------|----------|
| `click` | 点击元素 | `{}` |
| `fill` | 填充输入框 | `{"value": "文本内容"}` |
| `type` | 逐字输入 | `{"value": "文本内容"}` |
| `clear` | 清空输入框 | `{}` |
| `select_option` | 下拉选择 | `{"value": "选项值"}` |
| `check` | 勾选复选框 | `{}` |
| `uncheck` | 取消勾选 | `{}` |
| `hover` | 鼠标悬停 | `{}` |
| `double_click` | 双击 | `{}` |
| `right_click` | 右键点击 | `{}` |
| `press` | 按键 | `{"key": "Enter"}` |
| `wait` | 等待时间 | `{"timeout": 3000}` |
| `screenshot` | 截图 | `{"filename": "step1.png"}` |
| `assert_visible` | 断言可见 | `{}` |
| `assert_text` | 断言文本 | `{"expected": "预期文本"}` |

---

## 输出格式

成功返回：
```json
{"status": "success", "data": {...}}
```

失败返回：
```json
{"status": "error", "message": "错误信息"}
```

---

## 完整生命周期示例

以下是 AI 使用 ui-automation-skill 的完整工作流程：

### Phase 1: 设计阶段

```bash
# 1.1 先查询现有模块（检查是否已存在）
python ui_automation_tools.py --action get_ui_modules --project_id 1
# 如果已有合适的模块，直接使用其 id，无需创建

# 1.2 如果需要，创建新模块
python ui_automation_tools.py --action create_ui_module \
  --project_id 1 --name "用户模块"

# 1.3 查询现有环境配置（检查是否已存在）
python ui_automation_tools.py --action get_env_configs --project_id 1
# 如果已有合适的环境，直接使用，无需创建

# 1.4 如果需要，创建新环境配置
python ui_automation_tools.py --action create_env_config \
  --project_id 1 --name "开发环境" \
  --base_url "http://dev.example.com" \
  --browser chromium --headless false --timeout 30000
```

### Phase 2: 构建阶段

```bash
# 2.1 查询现有页面（检查是否已存在同名页面）
python ui_automation_tools.py --action get_ui_pages --project_id 1 --module_id 10

# 2.2 如果需要，创建页面
python ui_automation_tools.py --action create_ui_page \
  --project_id 1 --module_id 10 --name "登录页面" --url "/login"

# 2.3 批量创建元素（基于元素采集策略：browser-use 优先，playwright 兜底）
python ui_automation_tools.py --action batch_create_elements \
  --page_id 20 \
  --elements '[
    {"name": "用户名", "locator_type": "css", "locator_value": "#username"},
    {"name": "密码", "locator_type": "css", "locator_value": "#password"},
    {"name": "登录按钮", "locator_type": "css", "locator_value": "button[type=submit]"}
  ]'

# 2.3 创建页面步骤
python ui_automation_tools.py --action create_page_step \
  --project_id 1 --page_id 20 --module_id 10 --name "执行登录"

# 2.4 设置步骤详情（定义操作序列）
python ui_automation_tools.py --action set_step_details \
  --step_id 30 \
  --steps '[
    {"step_type": 0, "element": 100, "ope_key": "fill", "ope_value": {"value": "${{username}}"}},
    {"step_type": 0, "element": 101, "ope_key": "fill", "ope_value": {"value": "${{password}}"}},
    {"step_type": 0, "element": 102, "ope_key": "click", "ope_value": {}}
  ]'

# 2.5 创建测试用例
python ui_automation_tools.py --action create_testcase \
  --project_id 1 --module_id 10 --name "登录成功测试" --level P0

# 2.6 设置用例步骤（引用页面步骤）
python ui_automation_tools.py --action set_case_steps \
  --testcase_id 40 --page_step_ids "30"

# 2.7 创建公共数据（测试账号）
python ui_automation_tools.py --action create_public_data \
  --project_id 1 --key "username" --value "admin"
python ui_automation_tools.py --action create_public_data \
  --project_id 1 --key "password" --value "admin123"
```

### Phase 3: 执行阶段

```bash
# 3.1 检查执行器是否在线
python ui_automation_tools.py --action get_actuators
# 确保至少有一个执行器 is_open: true

# 3.2 获取用例执行数据（用于调试验证）
python ui_automation_tools.py --action get_testcase_execute_data --testcase_id 40

# 3.3 执行用例（不等待结果）
python ui_automation_tools.py --action execute_testcase --testcase_id 40

# 3.4 执行用例（等待结果，最多120秒）
python ui_automation_tools.py --action execute_testcase --testcase_id 40 --wait_result --exec_timeout 120

# 3.5 查看执行记录
python ui_automation_tools.py --action get_execution_records --testcase_id 40 --limit 5

# 3.6 查看执行详情（分析结果）
python ui_automation_tools.py --action get_execution_record --record_id 100
```

### Phase 4: 错误分析与修复

```bash
# 4.1 获取失败的执行记录
python ui_automation_tools.py --action get_execution_records --status 3 --limit 1
# 返回数据中的 step_results 包含每个步骤的执行结果：
# - status: "success" | "failed"
# - message: 具体错误信息（超时、元素未找到、断言失败等）
# - element_found: 是否找到元素

# 4.2 根据错误信息修复
# 常见错误及修复方法：

# 错误1: Timeout exceeded - 元素定位器失效
python ui_automation_tools.py --action update_element \
  --element_id 100 --locator_value "#new-username-selector"

# 错误2: 断言失败 - 更新预期值
python ui_automation_tools.py --action set_step_details \
  --step_id 30 \
  --steps '[{"step_type": 1, "element": 105, "ope_key": "assert_text", "ope_value": {"expected": "新的预期文本"}}]'

# 4.3 重新执行验证
python ui_automation_tools.py --action execute_testcase --testcase_id 40 --wait_result
```

---

## 故障排除

### API 错误

| 问题 | 解决方案 |
|------|----------|
| 401 Unauthorized | 检查 API_KEY 是否正确设置 |
| 404 Not Found | 确认资源 ID 是否存在 |
| 400 Bad Request | 检查必填参数是否完整 |
| 连接失败 | 确认后端服务是否启动 |

### 执行错误分析

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| `Timeout exceeded` | 元素定位器失效或页面加载慢 | 更新 `locator_value` 或增加 `timeout` |
| `element not found` | 页面 DOM 结构变化 | 先使用 browser-use 重新采集，必要时用 playwright-skill 兜底 |
| `Target page closed` | 前序步骤导致页面关闭/跳转 | 检查页面导航逻辑 |
| `Assertion failed` | 实际值与预期不符 | 更新 `ope_value.expected` |
| `locator resolved to X elements` | 定位器匹配多个元素 | 调整为唯一定位器（匹配数必须为 1） |

### 从执行记录快速定位问题

```python
# AI 可以按以下逻辑分析 get_execution_records 返回的数据：

record = get_execution_records(status=3, limit=1)[0]

# 1. 检查整体状态
print(f"执行结果: {record['log']}")  # "用例执行失败: 通过 2/8"
print(f"总耗时: {record['duration']}秒")

# 2. 遍历步骤找到失败点
for step in record['step_results']:
    if step['status'] == 'failed':
        print(f"失败步骤 ID: {step['step_id']}")
        print(f"错误信息: {step['message']}")
        print(f"元素是否找到: {step['element_found']}")
        # 根据 message 内容判断修复方案

# 3. 常见修复动作
# - element_found=False → update_element 更新定位器
# - Timeout → 增加等待时间或检查页面状态
# - Assertion failed → 更新断言预期值
```
