"""CE 线 LLM 运行时适配层（评审失败诚实化同步配套）。

master-pe 的 requirements 模块通过两套系统解析运行时 LLM 配置：

- langgraph_integration.bundle_runtime（LLM 配置包/槽位轮转）
- langgraph_integration.llm_quota（Token 配额控制）

两者均为商业版功能，CE 开源线不包含（langgraph_integration 的
BUNDLE_RUNTIME_AVAILABLE 守卫即为此设计）。本次同步的评审失败诚实化
（master-pe ee10c495）在 tasks/views/services 中按上述调用签名编写，
其回归测试亦按该签名 mock（patch "requirements.services.resolve_llm_config"
与 "requirements.views.resolve_llm_config"）。

为保持与 PE 调用结构一致、避免大改同步过来的代码与测试，这里提供
同名同签名的最小实现：

- resolve_llm_config(user, module_key, pinned_bundle_id)：返回当前激活的
  LLMConfig（与 CE 既有行为一致），bundle 恒为 None、source 恒为 "active"；
- LLMQuotaExceeded：CE 无配额系统，该异常不会被抛出，定义仅为让调用方的
  except 分支可导入、可编译。
"""

from typing import Any, Optional


class LLMQuotaExceeded(Exception):
    """CE 适配占位异常：CE 线无 Token 配额系统，运行时不会抛出。"""

    def __init__(self, message: str = "", status: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status = status


class SimpleLLMResolution:
    """resolve_llm_config 的返回值：对齐 PE ResolvedLLMRuntimeConfig 的使用面。

    仅暴露 requirements 模块实际读取的三个属性：
    runtime_config（激活的 LLMConfig）、bundle（恒 None）、source（恒 "active"）。
    """

    def __init__(self, runtime_config):
        self.runtime_config = runtime_config
        self.bundle = None
        self.source = "active"


def resolve_llm_config(user=None, module_key=None, pinned_bundle_id=None):
    """解析运行时 LLM 配置（CE 最小实现）。

    与 PE 的 bundle_runtime.resolve_llm_config 同签名，便于上层代码与测试
    无差别复用；CE 语义与历史行为一致：取当前激活的 LLMConfig，
    无可用配置时抛出异常。user/module_key/pinned_bundle_id 参数仅为
    签名兼容，CE 无槽位/绑定包概念，直接忽略。
    """
    # 延迟导入避免 app 加载顺序问题
    from langgraph_integration.models import LLMConfig

    active_config = LLMConfig.objects.filter(is_active=True).first()
    if not active_config:
        raise Exception("没有可用的LLM配置")
    return SimpleLLMResolution(active_config)
