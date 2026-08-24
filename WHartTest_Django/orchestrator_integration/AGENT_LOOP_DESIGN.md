# Agent Loop 架构设计

## 问题背景

当前 LangGraph agent 在执行多步骤任务时，每次工具调用的结果都累积在 `messages` 状态中，导致：
- Token 快速增长（特别是 Playwright 的 DOM 快照）
- 超出模型上下文限制后任务失败

## 解决方案：Agent Loop + Blackboard

### 核心思路

将"一次长对话"拆分为"多次短对话"，通过 Blackboard 传递状态：

```
原来：
用户请求 → AI思考 → 工具1 → 结果累积 → AI思考 → 工具2 → 结果累积 → ... → 💥Token爆炸

新架构：
用户请求 → Orchestrator 启动循环 → {
  Step 1: 构建精简上下文 → AI决策 → 执行 → 保存到Blackboard → 清空上下文
  Step 2: 构建精简上下文 → AI决策 → 执行 → 保存到Blackboard → 清空上下文
  ...
} → 最终汇总响应
```

### 架构组件

```
┌─────────────────────────────────────────────────────────────┐
│                         用户请求                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      AgentOrchestrator                       │
│  - 判断是否需要工具调用（轻量模式 vs 完整模式）                   │
│  - 控制 Agent Loop                                           │
│  - 管理 Blackboard                                           │
│  - 汇总最终结果                                                │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
       ┌──────────┐    ┌──────────┐    ┌──────────┐
       │  Step 1  │    │  Step 2  │    │  Step N  │
       │ AI 决策  │ →  │ AI 决策  │ →  │ AI 决策  │
       │ 工具执行  │    │ 工具执行  │    │ 工具执行  │
       └──────────┘    └──────────┘    └──────────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Blackboard                             │
│  {                                                          │
│    "goal": "用户原始请求",                                    │
│    "history_summary": ["Step1: xxx", "Step2: yyy"],         │
│    "current_state": {...},                                  │
│    "tool_results": [...],                                   │
│    "completed": false                                       │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

### 数据模型

```python
# models.py
class AgentTask(models.Model):
    """Agent 任务"""
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE)
    goal = models.TextField()  # 用户原始请求
    status = models.CharField(max_length=20, choices=[
        ('pending', '待处理'),
        ('running', '执行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)

class AgentStep(models.Model):
    """Agent 单步执行记录"""
    task = models.ForeignKey(AgentTask, on_delete=models.CASCADE, related_name='steps')
    step_number = models.IntegerField()
    input_summary = models.TextField()  # 输入上下文摘要
    ai_decision = models.TextField()  # AI 的决策（要调用什么工具）
    tool_name = models.CharField(max_length=100, null=True)  # 调用的工具
    tool_input = models.JSONField(null=True)  # 工具输入
    tool_output_summary = models.TextField(null=True)  # 工具输出摘要（非完整内容）
    ai_response = models.TextField(null=True)  # AI 的回复
    token_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class Blackboard(models.Model):
    """任务黑板（状态共享）"""
    task = models.OneToOneField(AgentTask, on_delete=models.CASCADE)
    history_summary = models.JSONField(default=list)  # 历史摘要列表
    current_state = models.JSONField(default=dict)  # 当前状态
    tool_results_refs = models.JSONField(default=list)  # 工具结果引用（ID列表，完整结果存文件/对象存储）
```

### Orchestrator 核心逻辑

```python
class AgentOrchestrator:
    """Agent 编排器"""
    
    MAX_STEPS = 50  # 最大步骤数，防止无限循环
    
    async def execute(self, user_request: str, session: ChatSession) -> dict:
        """执行 Agent 任务"""
        
        # 1. 创建任务和 Blackboard
        task = await self._create_task(user_request, session)
        blackboard = await self._create_blackboard(task)
        
        # 2. Agent Loop
        step_count = 0
        while step_count < self.MAX_STEPS:
            step_count += 1
            
            # 2.1 构建精简上下文（从 Blackboard 读取）
            context = self._build_step_context(blackboard, user_request)
            
            # 2.2 调用 AI（独立上下文，不累积历史）
            ai_result = await self._call_ai_step(context)
            
            # 2.3 判断是否需要工具调用
            if ai_result.get('tool_call'):
                tool_result = await self._execute_tool(ai_result['tool_call'])
                # 2.4 工具结果摘要（不是完整内容）
                summary = self._summarize_tool_result(tool_result)
                blackboard.history_summary.append(f"Step {step_count}: {summary}")
                blackboard.save()
            
            # 2.5 判断任务是否完成
            if ai_result.get('completed') or ai_result.get('final_response'):
                task.status = 'completed'
                task.save()
                return {
                    'response': ai_result.get('final_response'),
                    'steps': step_count,
                    'history': blackboard.history_summary
                }
        
        # 超过最大步骤
        task.status = 'failed'
        task.save()
        return {'error': 'Max steps exceeded'}
    
    def _build_step_context(self, blackboard: Blackboard, goal: str) -> dict:
        """构建单步上下文（精简版）"""
        return {
            'goal': goal,
            'history': blackboard.history_summary[-10:],  # 只最近10条
            'current_state': blackboard.current_state,
        }
    
    def _summarize_tool_result(self, result: dict) -> str:
        """工具结果摘要"""
        # 对于 Playwright 这类大结果，只保留关键信息
        if result.get('type') == 'page_snapshot':
            return f"页面快照: {result.get('url')}, 元素数: {len(result.get('elements', []))}"
        return str(result)[:200]  # 默认截断
```

### 与现有架构的集成点

1. **入口**：`ChatAPIView.post()` 和 `AgentLoopStreamAPIView.post()`
2. **判断模式**：
   - 如果请求简单（无工具调用），走现有路径
   - 如果请求复杂（需要工具），走 AgentOrchestrator
3. **前端兼容**：
   - 返回格式保持不变
   - 增加 `steps` 和 `history` 字段供调试

### 实现计划

1. **Phase 1: 数据模型**
   - 创建 AgentTask, AgentStep, Blackboard 模型
   - Migration

2. **Phase 2: Orchestrator**
   - 实现 AgentOrchestrator 核心逻辑
   - 工具结果摘要逻辑

3. **Phase 3: 集成**
   - 修改 ChatAPIView/AgentLoopStreamAPIView
   - 添加模式判断逻辑

4. **Phase 4: 优化**
   - 流式输出支持
   - 前端进度显示

---

**待确认问题：**
1. Blackboard 存储位置：数据库 vs Redis？
2. 工具结果完整内容存哪里？数据库 JSONField vs 文件存储？
3. 是否需要支持任务中断和恢复？
