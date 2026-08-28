"""
UI自动化执行器 - 消息模型
与Django后端共享的消息定义
"""

from enum import IntEnum
from typing import Any, Optional
from pydantic import BaseModel


class NoticeType(IntEnum):
    """通知类型"""
    WEB = 1
    ACTUATOR = 2


class ResponseCode(IntEnum):
    """响应状态码"""
    SUCCESS = 200
    ERROR = 400
    NOT_FOUND = 404
    SERVER_ERROR = 500


class UiSocketEnum:
    """UI自动化Socket端点枚举"""
    PAGE_STEPS = 'u_page_steps'
    TEST_CASE = 'u_test_case'
    TEST_CASE_BATCH = 'u_test_case_batch'
    STOP_EXECUTION = 'u_stop_execution'
    STEP_RESULT = 'u_step_result'
    CASE_RESULT = 'u_case_result'
    SET_ACTUATOR_INFO = 't_set_actuator_info'  # 设置执行器信息
    SET_ACTUATOR_CONFIG = 't_set_actuator_config'  # 平台下发执行器配置


class QueueModel(BaseModel):
    """任务队列消息模型"""
    func_name: str
    func_args: dict[str, Any]


class SocketDataModel(BaseModel):
    """Socket消息模型"""
    code: int = ResponseCode.SUCCESS
    msg: str = 'success'
    user: Optional[str] = None
    is_notice: int = NoticeType.WEB
    data: Optional[QueueModel] = None


class StepResultModel(BaseModel):
    """步骤执行结果"""
    step_id: int
    status: str
    message: str = ''
    description: str = ''  # 步骤描述/元素名称
    screenshot: Optional[str] = None
    duration: float = 0
    element_found: bool = True


class CaseResultModel(BaseModel):
    """用例执行结果"""
    case_id: int
    status: str
    message: str = ''
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    duration: float = 0
    steps: list[StepResultModel] = []
    trace_path: Optional[str] = None  # Playwright Trace 文件路径
