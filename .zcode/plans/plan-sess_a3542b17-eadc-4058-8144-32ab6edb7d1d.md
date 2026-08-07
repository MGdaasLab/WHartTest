# 修复 SQL 前置钩子变量未引用的三个 Bug

## 背景
接口管理添加 HTTP 接口后，在前置钩子加 SQL 控制器（变量名 `name`，SQL `SELECT name FROM students WHERE student_no = '2024001'`），body 引用 `$name`，调试后 body 仍为字面量 `$name`。根因是三个叠加 Bug，现一次性修复。

## Bug ①：SQL 前置钩子从不执行 SQL（致命）
- **文件**：`WHartTest_Django/httprunner/step_request.py`，`execute_sql_hook` 函数（第 131-338 行）
- **根因**：第 184、228 行 `from utils.db_utils import get_database_connection / execute_sql` 引用了仓库中**根本不存在**的模块，必然抛 `ImportError`，第 197-201 行捕获后 `return`，SQL 一句没跑，`step_variables[var_name]` 从未赋值。
- **修复**：删除两处对 `utils.db_utils` 的导入，改用现成机制：
  - 用 `ApiDatabaseConfig.objects.get(id=db_id, is_active=True)` 查配置（用 `runner.interface_data.get('project_id')` 做 project 作用域过滤，取不到 project_id 则不限定）。
  - 用其 `.connection_string` 属性（已在 `api_database_configs/models.py:65-94` 按 db_type 构造好 SQLAlchemy URI）。
  - 用现成的 `DBEngine`（`httprunner/database/engine.py`）执行：`fetch_type == "one"` -> `db_engine.fetchone(sql)`；否则 -> `db_engine.fetchall(sql)`。非 SELECT 语句 `DBEngine` 自动返回 `{"rowcount": ...}`。
  - **结果处理逻辑（第 276-301 行）无需改动**：`fetchone` 返回 `{"name":"张三"}`（命中第 278 行 dict 单键提取），`fetchall` 返回 `[{"name":"张三"}]`（命中第 284 行 list 单行单列提取），与现有提取逻辑完全吻合。
  - 注意 `fetchone` 在 0 行时会因 `dict(None)` 抛 `TypeError`，需 try/except 包裹并当作"无结果"处理（不赋值变量，记 warning），避免静默崩溃。
  - 保留现有的 SQLite SQL 前缀剥离逻辑（第 206-224 行）和丰富的日志输出。
- **导入补充**：在文件顶部或函数内加 `from api_database_configs.models import ApiDatabaseConfig` 和 `from httprunner.database.engine import DBEngine`（函数内惰性导入，避免循环导入风险，与现有代码风格一致）。

## Bug ②：请求 body 在前置钩子之前就被渲染，之后不重新渲染
- **文件**：`WHartTest_Django/httprunner/step_request.py`，`run_step_request` 函数（第 512-633 行）
- **根因**：第 530 行 `parsed_request_dict = runner.parser.parse_data(...)` 渲染 body（此时 `name` 不在变量池，`parser.py:255-258` 静默保留 `$name`）；第 595-596 行才运行 `call_hooks` 写入 `step_variables["name"]`；第 604/633 行用第 530 行已冻结的 body 发请求，中间无重新渲染。
- **修复**：在 `call_hooks` 返回后（第 596 行之后）、提取 body 发请求（第 604 行）之前，对 `parsed_request_dict` 中受变量影响的字段（`req_json`、`data`、`headers`、`params`、`url`）重新执行一次 `runner.parser.parse_data(..., step_variables)`，让前置钩子产生的变量生效。
  - 为避免对无需替换的请求做无谓深拷贝，仅当本轮 setup hooks 存在时才重新解析（`if step.setup_hooks:` 块内）。
  - 重新解析后再次用 `_collect_unresolved_placeholders` 检测，若仍有未解析占位符记 warning（用于诊断）。
  - `headers` 此前已在第 551-590 行被 pop 出来单独处理，重新解析时需对 `request_headers` 同样做一次 `parse_data`（或对 `parsed_request_dict` 整体重解析后再重新 pop headers），保持一致。
  - 注意 `url` 在第 601 行才 `pop`，重解析时机放在 pop 之前，确保 url 中的 `$var` 也能被前置钩子变量替换。

## Bug ③（方案 B）：接口 runner 把 dict hook 序列化成字符串，导致进不了 SQL 分支
- **文件**：`WHartTest_Django/api_interfaces/runner.py`，`_add_hooks_to_step`（第 168-177 行）
- **根因**：对 dict hook 做了 `json.dumps` 再 `setup_hook(hook_json)`，而 `call_hooks` 只在 `isinstance(hook, Dict)` 分支路由 SQL hook；字符串 hook 落入 `Text` 分支被当函数调用，SQL hook 永远到不了 `execute_sql_hook`。
- **修复**：改为与 `api_testcases/runner.py:136-137` 一致--dict 直接 `setup_hook(hook)`，不再 `json.dumps`；非 dict（函数 ID 字符串）保持原样。已验证安全性：`setup_hook` builder（`step_request.py:973-979`）内部只 `append(hook)` 不调用字符串方法；`TStep.setup_hooks: Hooks` 类型接受 `Union[Text, Dict]`；前端 `getHooks()` 对 SQL hook 返回对象、函数 hook 返回字符串 ID，正好匹配。

## 验证
- 语法检查：`python -m py_compile` 三个改动文件。
- 相关单测：运行 `WHartTest_Django` 下涉及 runner / step_request 的测试（若有），确认无回归。
- 手动场景复现：按用户场景（SQL 前置钩子设 `name`，body 引用 `$name`，调试）验证 body 中 `$name` 被正确替换为查询结果。

## 改动文件清单
1. `WHartTest_Django/httprunner/step_request.py` — Bug ①（`execute_sql_hook` 改用 `ApiDatabaseConfig` + `DBEngine`）+ Bug ②（`run_step_request` 在 setup hooks 后重新解析请求）
2. `WHartTest_Django/api_interfaces/runner.py` — Bug ③（`_add_hooks_to_step` 去掉 dict 的 `json.dumps`）

不改前端、不改数据库、不改模型。