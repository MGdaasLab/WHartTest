"""
UI自动化 WebSocket 消息模型
"""

from enum import IntEnum
from typing import Any, Optional
from pydantic import BaseModel


class NoticeType(IntEnum):
    """通知类型"""
    WEB = 1        # 发送给前端
    ACTUATOR = 2   # 发送给执行器


class ResponseCode(IntEnum):
    """响应状态码"""
    SUCCESS = 200
    ERROR = 400
    NOT_FOUND = 404
    SERVER_ERROR = 500


class UiSocketEnum:
    """UI自动化Socket端点枚举"""
    PAGE_STEPS = 'u_page_steps'           # 执行页面步骤
    PAGE_STEP_RESULT = 'u_page_step_result'  # 页面步骤执行结果
    TEST_CASE = 'u_test_case'             # 执行测试用例
    TEST_CASE_BATCH = 'u_test_case_batch' # 批量执行用例
    STOP_EXECUTION = 'u_stop_execution'   # 停止执行
    STEP_RESULT = 'u_step_result'         # 步骤执行结果
    CASE_RESULT = 'u_case_result'         # 用例执行结果
    SET_ACTUATOR_INFO = 't_set_actuator_info'  # 设置执行器信息
    SET_ACTUATOR_CONFIG = 't_set_actuator_config'  # 平台下发执行器配置


class QueueModel(BaseModel):
    """任务队列消息模型"""
    func_name: str              # 函数名，用于路由
    func_args: dict[str, Any]   # 函数参数


class SocketDataModel(BaseModel):
    """Socket消息模型"""
    code: int = ResponseCode.SUCCESS
    msg: str = 'success'
    user: Optional[str] = None
    is_notice: int = NoticeType.WEB
    data: Optional[QueueModel] = None
    
    def success_response(self, msg: str = 'success', data: Optional[QueueModel] = None) -> 'SocketDataModel':
        """创建成功响应"""
        return SocketDataModel(
            code=ResponseCode.SUCCESS,
            msg=msg,
            user=self.user,
            is_notice=self.is_notice,
            data=data
        )
    
    def error_response(self, msg: str = 'error') -> 'SocketDataModel':
        """创建错误响应"""
        return SocketDataModel(
            code=ResponseCode.ERROR,
            msg=msg,
            user=self.user,
            is_notice=self.is_notice,
            data=None
        )


class StepResultModel(BaseModel):
    """步骤执行结果"""
    step_id: int
    status: str              # success, failed, skipped
    message: str = ''
    screenshot: Optional[str] = None  # 截图路径
    duration: float = 0      # 执行时长(秒)
    element_found: bool = True


class CaseResultModel(BaseModel):
    """用例执行结果"""
    case_id: int
    status: str              # success, failed, skipped
    message: str = ''
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    duration: float = 0
    steps: list[StepResultModel] = []


class ExecutionTaskModel(BaseModel):
    """执行任务模型"""
    task_id: str                          # 任务唯一ID
    task_type: str                        # page_steps, test_case, batch
    case_id: Optional[int] = None
    page_step_id: Optional[int] = None
    case_ids: Optional[list[int]] = None  # 批量执行时的用例ID列表
    env_config_id: Optional[int] = None   # 环境配置ID
    user: Optional[str] = None            # 发起执行的用户
