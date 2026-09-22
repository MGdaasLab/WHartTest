# UI自动化执行器 (WHartTest Actuator)

独立的UI自动化执行器服务，通过WebSocket连接Django后端，接收并执行自动化测试任务。

## 架构设计


```
┌─────────────┐     WebSocket      ┌──────────────────┐
│   Django    │ ◄────────────────► │   Actuator       │
│   Backend   │                    │   (执行器)        │
│             │                    │                  │
│ - Consumer  │ ◄─ 发送任务 ────── │ - WebSocketClient│
│ - 任务分发   │ ◄─ 返回结果 ────── │ - TaskConsumer   │
└─────────────┘                    │ - Executor       │
                                   └──────────────────┘
                                          │
                                          ▼
                                   ┌──────────────────┐
                                   │  Playwright      │
                                   │  (浏览器自动化)   │
                                   └──────────────────┘
```

## 通信协议

### 消息格式 (SocketDataModel)
```json
{
    "code": 200,
    "msg": "success",
    "user": "username",
    "is_notice": 2,
    "data": {
        "func_name": "u_test_case",
        "func_args": {
            "case_id": 1
        }
    }
}
```

### 支持的任务类型
- `u_page_steps` - 执行页面步骤
- `u_test_case` - 执行测试用例
- `u_test_case_batch` - 批量执行用例
- `u_stop_execution` - 停止执行
- `u_step_result` - 步骤执行结果
- `u_case_result` - 用例执行结果

## 安装

```bash
cd WHartTest_Actuator
pip install -r requirements.txt
```

## 使用

### 基本启动
```bash
python main.py
```

### 指定服务器地址
```bash
python main.py --server ws://192.168.1.100:8000/ws/ui/actuator/
```

### 指定执行器ID
```bash
python main.py --id actuator-01 --server ws://localhost:8000/ws/ui/actuator/
```

### 完整参数
```bash
python main.py \
    --server ws://localhost:8000/ws/ui/actuator/ \
    --api http://localhost:8000 \
    --id my-actuator \
    --log-level DEBUG
```

## 参数说明

| 参数 | 短参数 | 默认值 | 说明 |
|------|--------|--------|------|
| --server | -s | ws://localhost:8000/ws/ui/actuator/ | WebSocket服务器地址 |
| --api | -a | http://localhost:8000 | API服务器地址 |
| --id | -i | actuator-{pid} | 执行器唯一标识 |
| --log-level | -l | INFO | 日志级别 |

## 工作流程

1. **连接服务器**: 执行器启动后通过WebSocket连接Django后端
2. **等待任务**: 监听来自服务器的执行任务
3. **获取详情**: 通过REST API获取用例/步骤详细信息
4. **生成脚本**: 将步骤配置转换为Playwright代码
5. **执行测试**: 调用Playwright执行浏览器自动化
6. **返回结果**: 通过WebSocket将执行结果发送回服务器

## 打包成独立 EXE

执行器支持打包成独立可执行文件，方便分发部署。

### 安装打包依赖

```bash
# 使用 uv
uv pip install pyinstaller

# 或使用 pip
pip install pyinstaller
```

### 执行打包

```bash
cd WHartTest_Actuator
uv run python build_exe.py
```

### 输出目录

```
dist/WHartTest_Actuator/
├── WHartTest_Actuator.exe  # 主程序
├── config.toml             # 配置文件
├── start.bat               # GUI模式启动脚本
├── start_no_gui.bat        # 无GUI模式启动脚本
├── browsers/               # Playwright浏览器（首次运行自动下载）
└── data/                   # 数据目录
    ├── browser/            # 浏览器用户数据
    ├── screenshots/        # 截图
    └── traces/             # Trace文件
```

### 使用说明

1. 将 `dist/WHartTest_Actuator/` 目录复制到目标机器
2. 编辑 `config.toml` 配置服务器地址和账号
3. 双击 `start.bat` 启动（GUI模式）或 `start_no_gui.bat`（无GUI模式）

**首次运行**：
- 首次运行会自动下载 Chromium 浏览器（约 150MB）
- 浏览器会下载到 `browsers/` 目录
- 后续运行无需重复下载

## 分布式部署

执行器支持分布式部署，多个执行器可以同时连接到一个Django后端：

```bash
# 机器A
python main.py --id actuator-machine-a --server ws://server:8000/ws/ui/actuator/

# 机器B  
python main.py --id actuator-machine-b --server ws://server:8000/ws/ui/actuator/

# 机器C
python main.py --id actuator-machine-c --server ws://server:8000/ws/ui/actuator/
```

服务器会自动将任务分发给可用的执行器。

## HTTPS 客户端证书（双向 TLS 站点）

访问要求**客户端证书**的 HTTPS 站点（内网自签名双向 TLS 等）时，在执行器本机配置证书即可，
证书不会经过平台传输。

### 配置方式

`config.toml` 的 `[browser]` 段：

```toml
[browser]
client_cert_enabled = true
# PKCS#12（.pfx/.p12）；相对路径以 config.toml 所在目录为基准
client_cert_pfx_path = "./certs/client.pfx"
# 或 PEM 方案（cert + key），与 pfx 二选一（同时配置时优先 pfx）
# client_cert_cert_path = "./certs/client.crt"
# client_cert_key_path = "./certs/client.key"
# 一张证书覆盖多个域名时补充（逗号分隔）
# client_cert_origins = "https://a.example.com,https://b.example.com:8443"
# auto（默认）/ true / false
# ignore_https_errors = "auto"
```

或使用环境变量（优先级高于配置文件）：

```bash
export WHARTTEST_ACTUATOR_CLIENT_CERT_ENABLED=true
export WHARTTEST_ACTUATOR_CLIENT_CERT_PFX_PATH=/app/certs/client.pfx
export WHARTTEST_ACTUATOR_CLIENT_CERT_PASSPHRASE=your-passphrase   # 读完即从环境移除
export WHARTTEST_ACTUATOR_CLIENT_CERT_ORIGINS=https://a.example.com
export WHARTTEST_ACTUATOR_IGNORE_HTTPS_ERRORS=auto
```

**口令建议只用环境变量注入**，不要写进 `config.toml`（会明文落盘）。口令不会被上报到平台，
也不会写入日志。

### 生效规则（务必了解）

1. **origin 必须精确匹配**，Playwright 不支持通配。执行器会从用例的 `base_url` 与页面地址
   自动推导 origin，因此通常无需手工配置；只有「一张证书用于多个域名」时才需要
   `client_cert_origins`。
2. **origin 不匹配时证书会被静默丢弃**：不报错，也不发送证书。若访问双向 TLS 站点报握手失败，
   先核对执行器日志里打印的「生效 origin」与页面实际 origin 是否完全一致（含端口）。
3. 证书文件在创建浏览器上下文时才读取，路径写错会在日志中给出 `不存在` 告警。
4. 已启用证书且 `ignore_https_errors` 为 `auto` 时，会自动容忍 HTTPS 证书错误
   （这类站点通常同时使用自签名服务端证书）。需严格校验时显式设为 `false`。
5. 平台「执行器配置」弹窗可编辑证书路径与 origin，但**不包含口令** —— 口令只能在本机配置。

### 部署示例

- **Windows exe**：把 `client.pfx` 放到 exe 同级的 `certs\` 目录，配置里写 `./certs/client.pfx`。
- **Docker**：
  ```bash
  docker run -v ./certs:/app/certs:ro \
    -e WHARTTEST_ACTUATOR_CLIENT_CERT_PFX_PATH=/app/certs/client.pfx \
    -e WHARTTEST_ACTUATOR_CLIENT_CERT_PASSPHRASE=your-passphrase \
    wharttest-actuator
  ```

## 文件说明

```
WHartTest_Actuator/
├── main.py              # 主入口，启动执行器
├── models.py            # 消息模型定义
├── websocket_client.py  # WebSocket客户端
├── consumer.py          # 任务消费者
├── executor.py          # Playwright执行引擎
├── client_cert.py       # HTTPS 客户端证书解析（纯函数）
├── browser_installer.py # 浏览器安装检查模块
├── build_exe.py         # 打包脚本
├── actuator.spec        # PyInstaller配置
├── requirements.txt     # 依赖
└── README.md            # 说明文档
```
