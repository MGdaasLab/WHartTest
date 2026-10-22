# UI 自动化 WebSocket 认证配置指南

`/ws/ui/web/`（前端）与 `/ws/ui/actuator/`（执行器）两个 WebSocket 端点此前完全匿名，
存在执行器抢注截获任务载荷、伪造执行结果等漏洞。修复引入两层防护：

- 第一层：ASGI 认证中间件（`wharttest_django/websocket_auth.py`）
- 第二层：consumer 内防抢注 + 结果回传来源校验（`ui_automation/consumers.py`）

## 配置变量

| 变量 | 作用 | 默认值 |
|---|---|---|
| `UI_WS_ACTUATOR_TOKEN` | 执行器连接共享密钥，须与执行器侧 `ws_token` 一致 | 空（compose 部署自动生成） |
| `UI_WS_AUTH_STRICT` | `1` = 未认证连接一律拒绝（close 4401） | 代码内 `0`（本地开发）；`.env.example`/compose `1`（新部署默认严格） |

模式行为：

| 连接方式 | 兼容模式（STRICT=0） | 严格模式（STRICT=1） |
|---|---|---|
| 匿名（不带 token） | 放行（启动日志有 WARNING） | 拒绝 4401 |
| 带错误/过期 token | 拒绝 4401 | 拒绝 4401 |
| 有效凭据（前端 JWT / 执行器密钥） | 放行，连接带真实身份 | 放行 |

**为什么两处默认值不同**：compose 部署的内置前端与执行器随同一份源码构建，均内置
认证能力，新部署默认严格即开箱即安全；本地手动开发环境可能有旧版前端/执行器在跑，
代码内默认保持兼容，需要时手动设 `UI_WS_AUTH_STRICT=1`。存量部署（升级前已生成
`.env`）不受 `.env.example` 变更影响，需手动补该变量。

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

### 4. 严格模式

`.env.example` 与 compose 默认已开启（`UI_WS_AUTH_STRICT=1`）：全新部署启动即严格，
密钥由 `run_compose.sh` 自动生成，内置前端/执行器自动带凭据，无需任何手工步骤。

存量部署升级或本地手动环境：确认所有执行器已配置 `ws_token` 后，在 `.env` 补
`UI_WS_AUTH_STRICT=1` 并重启。日志出现 `UI WS 认证失败` 且路径为 actuator，
说明还有执行器没带凭据被拒——升级该执行器或临时置 0 过渡。

回滚：把 `UI_WS_AUTH_STRICT` 改回 `0` 重启即可，兼容模式不会拒绝任何合法旧客户端。

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
