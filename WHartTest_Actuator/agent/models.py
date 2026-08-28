"""AI Agent 模块用到的数据结构。"""

from dataclasses import dataclass


@dataclass
class AgentModelConfig:
    """AI 模型配置（用于 step_type=10「AI操作」步骤）。"""

    api_url: str
    api_key: str
    model: str
    provider: str = "openai_compatible"
    supports_vision: bool = False
    context_limit: int = 100000
    max_steps: int = 25
    temperature: float = 0.0
    # 上下文管理（可选，有默认值不破坏现有消费方）
    token_budget_ratio: float = 0.60   # 预算 = context_limit * 该比例
    hard_message_cap: int = 40        # 消息条数硬上限
    keep_recent: int = 32            # 裁剪时保留的最近消息条数


@dataclass
class ObservationResult:
    """对当前页面的一次观察结果。"""

    url: str
    title: str
    text: str  # 文本快照（非 VLM）或简短页面信息（VLM）
    screenshot_data_url: str | None = None  # VLM 模式下的 base64 data URL
    has_image: bool = False