# 批量执行测试用例使用指南

本文档说明如何使用基于Celery的批量测试用例执行功能。

## 系统架构

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   前端/API  │─────>│ Django Server│─────>│   Redis     │
└─────────────┘      └──────────────┘      └─────────────┘
                            │                      │
                            │                      ▼
                            │              ┌─────────────┐
                            └─────────────>│Celery Worker│
                                           └─────────────┘
                                                   │
                                                   ▼
                                           ┌─────────────┐
                                           │ MCP执行引擎 │
                                           └─────────────┘
```

## 核心概念

### 1. TestSuite (测试套件)
- 包含多个测试用例的集合
- 支持按优先级排序执行
- 可复用于多次执行

### 2. TestExecution (测试执行)
- 代表一次测试套件的执行实例
- 记录执行状态、统计信息
- 关联Celery任务ID,支持取消操作

### 3. TestCaseResult (用例结果)
- 单个测试用例的执行结果
- 包含详细日志、截图、错误信息
- 支持执行时间统计

## 启动服务

### 1. 启动Redis (消息队列)
```bash
# Windows
redis-server

# Linux/Mac
redis-server /etc/redis/redis.conf
```

### 2. 启动Celery Worker
```bash
# 进入项目目录
cd C:\Code\wharttest\WHartTest_Django

# 启动Worker (Windows使用solo模式)
uv run celery -A wharttest_django worker --loglevel=info --pool=solo

# Linux/Mac可以使用默认模式
uv run celery -A wharttest_django worker --loglevel=info
```

### 3. 启动Django服务器
```bash
uv run python manage.py runserver
```

## API使用

### 1. 创建测试套件

**请求:**
```http
POST /api/projects/{project_id}/test-suites/
Authorization: Bearer {your_token}
Content-Type: application/json

{
  "name": "登录功能回归测试",
  "description": "包含所有登录相关的测试用例",
  "testcase_ids": [1, 2, 3, 4, 5]
}
```

**响应:**
```json
{
  "status": "success",
  "code": 201,
  "message": "创建成功",
  "data": {
    "id": 1,
    "name": "登录功能回归测试",
    "description": "包含所有登录相关的测试用例",
    "testcase_count": 5,
    "project": 1,
    "creator": 1,
    "created_at": "2025-10-23T14:00:00Z"
  }
}
```

### 2. 查看测试套件列表

**请求:**
```http
GET /api/projects/{project_id}/test-suites/
Authorization: Bearer {your_token}
```

**响应:**
```json
{
  "status": "success",
  "code": 200,
  "data": {
    "count": 10,
    "results": [
      {
        "id": 1,
        "name": "登录功能回归测试",
        "testcase_count": 5,
        "created_at": "2025-10-23T14:00:00Z"
      }
    ]
  }
}
```

### 3. 启动批量执行

**请求:**
```http
POST /api/projects/{project_id}/test-executions/
Authorization: Bearer {your_token}
Content-Type: application/json

{
  "suite_id": 1
}
```

**响应:**
```json
{
  "status": "success",
  "code": 201,
  "message": "测试执行已创建",
  "data": {
    "id": 1,
    "suite": {
      "id": 1,
      "name": "登录功能回归测试"
    },
    "status": "pending",
    "total_count": 5,
    "passed_count": 0,
    "failed_count": 0,
    "celery_task_id": "abc123-def456-ghi789",
    "created_at": "2025-10-23T14:05:00Z"
  }
}
```

### 4. 查看执行状态

**请求:**
```http
GET /api/projects/{project_id}/test-executions/{execution_id}/
Authorization: Bearer {your_token}
```

**响应:**
```json
{
  "status": "success",
  "code": 200,
  "data": {
    "id": 1,
    "status": "running",
    "started_at": "2025-10-23T14:05:10Z",
    "total_count": 5,
    "passed_count": 3,
    "failed_count": 1,
    "skipped_count": 0,
    "error_count": 0,
    "pass_rate": 75.0,
    "duration": null
  }
}
```

### 5. 查看详细结果

**请求:**
```http
GET /api/projects/{project_id}/test-executions/{execution_id}/results/
Authorization: Bearer {your_token}
```

**响应:**
```json
{
  "status": "success",
  "code": 200,
  "data": [
    {
      "id": 1,
      "testcase": {
        "id": 1,
        "name": "用户名密码登录"
      },
      "status": "pass",
      "execution_time": 5.23,
      "screenshots": [
        "/media/screenshots/login_success.png"
      ],
      "completed_at": "2025-10-23T14:05:15Z"
    },
    {
      "id": 2,
      "testcase": {
        "id": 2,
        "name": "错误密码登录"
      },
      "status": "fail",
      "error_message": "未显示错误提示信息",
      "execution_time": 3.45,
      "completed_at": "2025-10-23T14:05:20Z"
    }
  ]
}
```

### 6. 生成测试报告

**请求:**
```http
GET /api/projects/{project_id}/test-executions/{execution_id}/report/
Authorization: Bearer {your_token}
```

**响应:**
```json
{
  "status": "success",
  "code": 200,
  "data": {
    "execution_id": 1,
    "suite": {
      "name": "登录功能回归测试"
    },
    "status": "completed",
    "duration": 125.5,
    "statistics": {
      "total": 5,
      "passed": 4,
      "failed": 1,
      "skipped": 0,
      "error": 0,
      "pass_rate": 80.0
    },
    "results": [...]
  }
}
```

### 7. 取消执行

**请求:**
```http
POST /api/projects/{project_id}/test-executions/{execution_id}/cancel/
Authorization: Bearer {your_token}
```

**响应:**
```json
{
  "status": "success",
  "code": 200,
  "message": "测试执行取消请求已发送"
}
```

## 执行状态说明

| 状态 | 说明 |
|------|------|
| `pending` | 等待执行 |
| `running` | 执行中 |
| `completed` | 已完成 |
| `failed` | 执行失败 |
| `cancelled` | 已取消 |

## 用例结果状态

| 状态 | 说明 |
|------|------|
| `pending` | 等待执行 |
| `running` | 执行中 |
| `pass` | 通过 |
| `fail` | 失败 |
| `skip` | 跳过 |
| `error` | 错误 |

## 配置说明

### Celery配置

在 `wharttest_django/settings.py` 中:

```python
# Redis连接配置
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# 任务超时设置
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30分钟
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25分钟
```

### 环境变量

可以在 `.env` 文件中配置:

```bash
# Redis配置
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## 监控和调试

### 1. 查看Celery日志
Celery Worker会输出详细的执行日志,包括:
- 任务接收
- 任务开始
- 任务完成/失败
- 错误堆栈

### 2. Redis监控
```bash
# 连接Redis
redis-cli

# 查看所有keys
KEYS *

# 查看任务队列
LLEN celery

# 查看结果
GET celery-task-meta-{task_id}
```

### 3. Django Admin
可以在Django Admin中查看和管理:
- 测试套件
- 测试执行记录
- 用例结果

## 集成MCP执行引擎

目前 `testcases/tasks.py` 中的 `execute_single_testcase()` 函数是占位实现。

要集成实际的MCP执行,需要修改该函数:

```python
def execute_single_testcase(result: TestCaseResult):
    """执行单个测试用例"""
    from mcp_tools.persistent_client import get_mcp_client
    
    testcase = result.testcase
    result.status = 'running'
    result.started_at = timezone.now()
    result.save()
    
    try:
        # 获取MCP客户端
        mcp_client = get_mcp_client(result.execution.executor)
        
        # 执行测试步骤
        for step in testcase.steps.all().order_by('step_number'):
            # 使用自然语言执行操作
            response = mcp_client.execute_action(step.description)
            
            # 捕获截图
            screenshot = mcp_client.take_screenshot()
            result.screenshots.append(screenshot)
            
            # 验证预期结果
            if not verify_result(response, step.expected_result):
                result.status = 'fail'
                result.error_message = f"步骤{step.step_number}验证失败"
                break
        else:
            result.status = 'pass'
            
    except Exception as e:
        result.status = 'error'
        result.error_message = str(e)
        result.stack_trace = traceback.format_exc()
    
    finally:
        result.completed_at = timezone.now()
        result.execution_time = (
            result.completed_at - result.started_at
        ).total_seconds()
        result.save()
```

## 常见问题

### Q: Windows下Celery启动后报错"PermissionError: [WinError 5] 拒绝访问"?

**A: 这是Celery在Windows上的已知兼容性问题。我已经通过修改 `wharttest_django/celery.py` 文件自动修复了此问题。**

**解决方案**:
1.  **停止** 当前的Celery Worker (`Ctrl+C`)。
2.  **重启** Celery Worker:
    ```bash
    uv run celery -A wharttest_django worker --loglevel=info
    ```
    配置文件会自动在Windows上使用稳定的 `solo` 模式,无需手动添加 `--pool=solo` 参数。

### Q: Celery Worker启动失败?
A: 检查Redis是否正常运行,端口是否被占用。

### Q: 任务一直pending不执行?
A: 确认Celery Worker是否正常运行,查看Worker日志。

### Q: 如何查看任务执行进度?
A: 轮询 `/api/projects/{id}/test-executions/{id}/` 接口查看状态。

## 性能优化建议

1. **并行执行**: 可以启动多个Celery Worker实现并行执行
2. **任务优先级**: 设置不同优先级的任务队列
3. **结果缓存**: 使用Redis缓存频繁查询的结果
4. **截图压缩**: 对截图进行压缩以节省存储空间
5. **日志清理**: 定期清理过期的执行记录和日志

## 下一步扩展

- [ ] 支持定时执行(Celery Beat)
- [ ] 支持并行执行多个用例
- [ ] 邮件通知执行结果
- [ ] WebSocket实时推送执行进度
- [ ] 测试报告导出(PDF/HTML)
- [ ] 失败用例自动重试
- [ ] 执行历史对比分析