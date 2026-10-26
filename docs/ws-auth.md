# UI 自动化 WebSocket 认证配置指南

`/ws/ui/web/`（前端）与 `/ws/ui/actuator/`（执行器）两个 WebSocket 端点此前完全匿名，
存在执行器抢注截获任务载荷、伪造执行结果等漏洞。修复引入两层防护：

- 第一层：ASGI 认证中间件（`wharttest_django/websocket_auth.py`）
- 第二层：consumer 内防抢注 + 结果回传来源校验（`ui_automation/consumers.py`）

## 配置变量

| 变量 | 作用 | 默认值 |
|---|---|---|
| `UI_WS_ACTUATOR_TOKEN` | 执行器连接共享密钥，须与执行器侧 `ws_token` 一致 | 空（compose 部署由 run_compose.sh 自动生成并同步） |

**WS 认证为硬性安全要求，不存在开关**：未认证连接一律拒绝（4401），不提供兼容
模式。历史版本的 `UI_WS_AUTH_STRICT` 环境变量已废弃、不再被读取。密钥未配置时
执行器连接同样被拒（fail-closed），`run_compose.sh` 会自动生成并同步到本机执行器
的 `config.toml`，正常部署无需手工配置。

## 部署步骤

### 1. 密钥生成与分发（compose 部署全自动，无需手工填写）

`run_compose.sh` 首次启动时会自动生成随机密钥并回写 `.env`：

- `UI_WS_ACTUATOR_TOKEN` → 注入 backend 容器；
- `WHARTTEST_ACTUATOR_WS_TOKEN` → 自动取同值，注入内置 actuator 容器。

即"复制 .env.example 后直接执行"开箱即用，两边密钥自动保持一致。
手动部署（不经 compose/脚本）时才需要自行生成并分别配置：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 后端：写入根 .env 或导出为环境变量
UI_WS_ACTUATOR_TOKEN=<生成的密钥>
# 执行器：config.toml [server] ws_token 或环境变量
WHARTTEST_ACTUATOR_WS_TOKEN=<同值>
```

### 2. 外置执行器（不在 compose 内自行部署的）

按上面的手动方式配置 `ws_token`（TOML）或 `WHARTTEST_ACTUATOR_WS_TOKEN`（环境变量，
读取后从环境中移除）。值与后端 `UI_WS_ACTUATOR_TOKEN` 一致。

### 3. 前端（无需配置）

前端 `websocket.ts` 已自动从 `localStorage` 读取登录 access token 附加到连接 URL，
收到 4401 时自动刷新 token 重连一次。无需额外配置。

### 4. 严格模式（恒开，无需操作）

WS 认证严格模式为系统硬性行为，无开关、不可关闭。`run_compose.sh` 每次运行都会
校验并同步密钥（根 `.env` 与本机 `WHartTest_Actuator/config.toml`），升级部署后
本地执行器直接启动即可。若日志出现 `UI_WS_ACTUATOR_TOKEN 未配置` 或执行器反复
4401，运行一次 `run_compose.sh` 即可自动修复。

## 安全验证

```bash
# 单元测试（PG/SQLite 均可）
cd WHartTest_Django
.venv/bin/python manage.py test ui_automation.test_ws_auth -v 1

# 平台侧冒烟（对运行实例，参数：<port> <strict:0|1> <secret>）
.venv/bin/python scripts/ws_auth_smoke.py 8000 0 <secret>
```

浏览器控制台快速验证：

```js
// 伪造 token → 应立即关闭，code 4401
new WebSocket('ws://<host>/ws/ui/web/?token=forged')
// 登录后有效 token → 收到 {"code":200,"user":"<用户名>"}
new WebSocket(`ws://<host>/ws/ui/web/?token=${localStorage.getItem('auth-accessToken')}`)
```

## 已知边界

- token 经查询参数传递（浏览器 WebSocket API 不支持自定义握手头）；生产请走
  HTTPS/WSS，避免 token 落入中间代理日志。
- **任务来源强校验已端到端生效**：后端下发任务时在 `func_args` 附带一次性
  `task_token` 并登记归属（执行器 + 发起人）；执行器 `_route_task` 摘取，
  `send_result` 对所有结果消息（逐步结果/画面帧/汇总）自动回显；后端
  `verify_result_source` 强校验 token 与发起人一致（非消费式，同一任务多条
  结果复用），并在校验后从 args 剥离（不随结果入库/广播）。旧版执行器不回显
  token 时退化为"claimed_user 命中近期下发记录"的次级校验，严格模式下同样
  拒绝未登记来源。
- 来源登记为进程内状态：多 worker 部署时执行器回传必须命中同一 worker 的
  登记（执行器与单个 worker 保持长连接，天然满足；若未来引入跨 worker 结果
  路由，需把登记迁到 Redis）。
- 严格模式下未带凭据的旧版执行器会被拒绝，升级执行器前不要开启。
