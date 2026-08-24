"""智能编排任务数据模型"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator

User = get_user_model()


class OrchestratorTask(models.Model):
    """智能编排任务"""
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('planning', '规划中'),
        ('waiting_confirmation', '等待确认'),
        ('executing', '执行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('cancelled', '已取消'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orchestrator_tasks')
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        verbose_name='所属项目',
        help_text='任务必须关联到项目,用于数据隔离'
    )
    chat_session = models.ForeignKey('langgraph_integration.ChatSession', on_delete=models.SET_NULL,
                                     null=True, blank=True, verbose_name='关联对话会话',
                                     help_text='任务源自的对话会话')
    
    # 输入
    requirement = models.TextField(verbose_name='需求描述')
    # ❌ 移除 knowledge_base_ids,Brain自动访问项目下所有知识库
    
    # 状态
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    
    # 交互式执行相关
    execution_plan = models.JSONField(null=True, blank=True, verbose_name='执行计划')
    execution_history = models.JSONField(default=list, blank=True, verbose_name='执行历史')
    current_step = models.IntegerField(default=0, verbose_name='当前步骤')
    waiting_for = models.CharField(max_length=50, blank=True, verbose_name='等待对象')
    user_notes = models.TextField(blank=True, verbose_name='用户备注')
    
    # 输出
    requirement_analysis = models.JSONField(null=True, blank=True, verbose_name='需求分析结果')
    knowledge_docs = models.JSONField(default=list, blank=True, verbose_name='检索的知识文档')
    testcases = models.JSONField(default=list, blank=True, verbose_name='生成的测试用例')
    
    # 执行记录(保留兼容性)
    execution_log = models.JSONField(default=list, blank=True, verbose_name='执行日志(旧)')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    
    # 时间
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'orchestrator_task'
        ordering = ['-created_at']
        verbose_name = '智能编排任务'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"Task {self.id}: {self.requirement[:50]}"


class AgentTask(models.Model):
    """Agent Loop 任务 - 用于分步执行的任务管理"""
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('running', '执行中'),
        ('paused', '已暂停'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    
    session = models.ForeignKey(
        'langgraph_integration.ChatSession',
        on_delete=models.CASCADE,
        related_name='agent_tasks',
        verbose_name='关联会话'
    )
    goal = models.TextField(verbose_name='任务目标（用户原始请求）')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    max_steps = models.IntegerField(default=500, verbose_name='最大步骤数')
    current_step = models.IntegerField(default=0, verbose_name='当前步骤')
    final_response = models.TextField(blank=True, verbose_name='最终响应')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'agent_task'
        ordering = ['-created_at']
        verbose_name = 'Agent任务'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"AgentTask {self.id}: {self.goal[:50]}"


class AgentStep(models.Model):
    """Agent 单步执行记录"""
    
    task = models.ForeignKey(
        AgentTask,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name='所属任务'
    )
    step_number = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='步骤序号'
    )
    
    # 输入
    input_context = models.JSONField(default=dict, verbose_name='输入上下文（精简版）')
    
    # AI 决策
    ai_thinking = models.TextField(blank=True, verbose_name='AI思考过程')
    ai_decision = models.TextField(blank=True, verbose_name='AI决策')
    
    # 工具调用
    tool_name = models.CharField(max_length=100, blank=True, verbose_name='工具名称')
    tool_input = models.JSONField(null=True, blank=True, verbose_name='工具输入')
    tool_output_summary = models.TextField(blank=True, verbose_name='工具输出摘要')
    tool_output_full_ref = models.CharField(max_length=200, blank=True, verbose_name='完整输出引用')
    
    # AI 响应
    ai_response = models.TextField(blank=True, verbose_name='AI响应')
    is_final = models.BooleanField(default=False, verbose_name='是否为最终响应')
    
    # 统计
    token_input = models.IntegerField(default=0, verbose_name='输入Token数')
    token_output = models.IntegerField(default=0, verbose_name='输出Token数')
    duration_ms = models.IntegerField(default=0, verbose_name='耗时(毫秒)')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'agent_step'
        ordering = ['task', 'step_number']
        unique_together = ['task', 'step_number']
        verbose_name = 'Agent步骤'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"Step {self.step_number} of Task {self.task_id}"


class AgentBlackboard(models.Model):
    """Agent 黑板 - 任务执行过程中的状态共享"""
    
    MAX_HISTORY_LENGTH = 100  # 历史摘要最大条数
    
    task = models.OneToOneField(
        AgentTask,
        on_delete=models.CASCADE,
        related_name='blackboard',
        verbose_name='所属任务'
    )
    
    # 历史摘要（精简版，供 AI 参考）
    history_summary = models.JSONField(default=list, verbose_name='历史摘要列表')
    
    # 当前状态（如当前页面 URL、已完成的子任务等）
    current_state = models.JSONField(default=dict, verbose_name='当前状态')
    
    # 工具结果引用列表（完整结果的存储位置）
    tool_results_refs = models.JSONField(default=list, verbose_name='工具结果引用')
    
    # 上下文变量（可供工具使用的变量）
    context_variables = models.JSONField(default=dict, verbose_name='上下文变量')
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'agent_blackboard'
        verbose_name = 'Agent黑板'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"Blackboard for Task {self.task_id}"
    
    def add_history(self, summary: str):
        """添加历史摘要"""
        history = list(self.history_summary or [])
        history.append(str(summary))
        # 限制历史长度
        if len(history) > self.MAX_HISTORY_LENGTH:
            history = history[-self.MAX_HISTORY_LENGTH:]
        self.history_summary = history
        self.save(update_fields=['history_summary', 'updated_at'])
    
    def update_state(self, key: str, value):
        """更新当前状态"""
        state = dict(self.current_state or {})
        state[key] = value
        self.current_state = state
        self.save(update_fields=['current_state', 'updated_at'])
    
    def get_recent_history(self, count: int = 10) -> list:
        """获取最近的历史摘要"""
        return (self.history_summary or [])[-count:]
    
    def compress_old_history(self, context_limit: int = 128000, model_name: str = "gpt-4o") -> bool:
        """AI智能压缩:在token达到90%时,让AI总结历史,相当于新开对话"""
        import logging
        logger = logging.getLogger(__name__)
        
        history = list(self.history_summary or [])
        logger.info(f"[Compression] 当前历史条数: {len(history)}")
        
        # ⭐ Token超限就压缩,不判断条数(即使1条超长记录也要总结)
        if not history:
            logger.warning(f"[Compression] 历史为空,无需压缩")
            return False
        
        # 分离已压缩摘要和原始记录
        summary_prefix = "[历史压缩]"
        existing_summary = None
        if history[0].startswith(summary_prefix):
            existing_summary = history.pop(0)
            logger.info(f"[Compression] 发现旧摘要,已分离。剩余原始记录: {len(history)}条")
        
        # 调用AI总结所有原始记录
        try:
            logger.info(f"[Compression] 开始调用AI总结历史...")
            from langgraph_integration.models import LLMConfig
            from langgraph_integration.views import create_llm_instance
            
            active_config = LLMConfig.objects.get(is_active=True)
            llm = create_llm_instance(active_config)
            logger.info(f"[Compression] LLM实例创建成功,模型: {active_config.name}")
            
            content_text = '\n'.join([f"- {str(entry)[:200]}..." for entry in history])  # ⭐ 限制每条显示长度
            logger.info(f"[Compression] 待总结内容长度: {len(content_text)} 字符")
            
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content="你是Agent历史记录总结助手。"),
                HumanMessage(content=f"""当前Agent执行历史即将超过上下文限制,请总结关键信息:

{content_text}

请用2-3句话总结:
1. **已完成**:做了什么操作(如查询知识库、生成用例)
2. **正在做**:当前任务进展
3. **下一步计划**:接下来要做什么

要求:简洁明了,100字以内。""")
            ]
            
            logger.info(f"[Compression] 正在调用LLM生成摘要...")
            response = llm.invoke(messages)
            summary_content = response.content if hasattr(response, 'content') else str(response)
            summary_text = f"{summary_prefix} {summary_content.strip()}"
            logger.info(f"[Compression] AI摘要生成成功: {summary_text[:100]}...")
            
            # ⭐ 压缩策略:总结ALL→1条摘要,保留最近1条原始
            # 例如:5条历史→总结5条成1摘要+保留最后1条=2条总长度(压缩60%)
            keep_recent = 1
            if len(history) <= 1:
                # 只有1条,直接压缩
                self.history_summary = [summary_text]
                logger.info(f"[Compression Done] 将{len(history)}条历史全部压缩为1条摘要")
            else:
                # 总结所有,保留最后1条原始(提供最新上下文)
                recent_history = history[-keep_recent:]
                self.history_summary = [summary_text] + recent_history
                logger.info(f"[Compression Done] 总结{len(history)}条历史为摘要,额外保留最近{keep_recent}条原始")
            
            self.save(update_fields=['history_summary', 'updated_at'])
            return True
            
        except Exception as e:
            logger = __import__('logging').getLogger(__name__)
            logger.error(f"AI压缩失败: {e}", exc_info=True)
            # 失败时至少保留最近10条
            self.history_summary = history[-10:]
            self.save(update_fields=['history_summary', 'updated_at'])
            return False