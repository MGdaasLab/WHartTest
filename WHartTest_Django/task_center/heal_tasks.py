"""
Celery 任务 - 定时任务失败用例自动自愈

链路：批次完结（部分失败/全部失败）→ consumers 事件投递本任务 →
串行单会话逐用例调 agent-loop（非流式）自愈 → 会话中断重试（同 session_id 续跑）→ 总结落执行记录日志。

设计约束（对应需求文档 docs/ui-case-self-heal.md 第 8 章）：
- 仅 module=ui_automation 且 auto_heal_enabled=True 的定时任务触发；
- 单次任务自愈用例数受 heal_case_limit 上限约束，超出者列入待人工清单；
- 同一 session_id 串行追加消息（复测通道 recorder-browser 单槽、避免并行改同一元素、会话记忆复用）；
- 会话中断（网络/LLM 异常）按 retry_count/retry_interval 同一 session_id 重试续跑；
- 过程写入 ChatSession/ChatMessage（module_key=testcase_execution），AI 对话页可回看。
"""
import json
import logging
import uuid

import requests
from celery import shared_task
from django.conf import settings as django_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)

# agent-loop 非流式调用超时（秒）。自愈含多轮工具调用与复测，取较长超时。
AGENT_LOOP_TIMEOUT_SECONDS = 30 * 60
# 单条失败现场 message 的报错截断长度
_FAILURE_MESSAGE_MAX = 400
# 进入自愈消息的步骤流水条数上限
_STEP_HISTORY_LIMIT = 20


def _build_auth_headers(user) -> dict:
    """构造任务创建者身份的认证头（JWT，与 trigger-batch 同模式）。

    agent-loop 视图是 Django View，手动认证只解析 Bearer JWT（不支持 X-API-Key），
    因此这里始终签发带当前 session_version 的 JWT，不使用 API Key。
    （API Key 仅适用于 skill 工具回调的 DRF 路径，两者认证入口不同。）
    """
    token = RefreshToken.for_user(user).access_token
    from accounts.models import UserLoginState

    state, _ = UserLoginState.objects.get_or_create(user=user)
    token['session_version'] = state.session_version
    return {'Authorization': f'Bearer {token}'}


def _truncate(text: str, max_length: int) -> str:
    text = (text or '').strip()
    if len(text) <= max_length:
        return text
    head = text[: int(max_length * 0.7)]
    tail = text[-int(max_length * 0.3):]
    return f"{head}...(过长已省略)...{tail}"


def _collect_failed_cases(batch, limit: int) -> list:
    """取批次内失败用例（按执行记录创建时间升序），截取前 limit 个。

    同一用例在批次内可能有多条失败记录（复测等），按用例去重后仍按首次失败时间排序。
    """
    from ui_automation.models import UiExecutionRecord

    failed_records = (
        UiExecutionRecord.objects
        .filter(batch=batch, status=3)
        .select_related('test_case')
        .order_by('created_at')
    )
    seen, ordered_cases = set(), []
    for record in failed_records:
        if record.test_case_id in seen:
            continue
        seen.add(record.test_case_id)
        ordered_cases.append(record)
    return ordered_cases[:limit]


def _build_failure_message(task, case_record, project_id: int) -> str:
    """组装单个用例的自愈指令（与手动自愈 uiSelfHeal.ts 同构，服务端版）。"""
    from ui_automation.models import UiExecutionRecord

    record = UiExecutionRecord.objects.filter(id=case_record.id).first()
    case = case_record.test_case

    steps = record.step_results if record and isinstance(record.step_results, list) else []
    clean_steps = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        message = step.get('message') or step.get('error') or ''
        clean_steps.append({
            'step_id': step.get('step_id'),
            'status': step.get('status'),
            'description': step.get('description'),
            'message': _truncate(' '.join(str(message).split()), _FAILURE_MESSAGE_MAX) if message else '',
        })
    recent_steps = clean_steps[-_STEP_HISTORY_LIMIT:]

    failed_step = None
    for step in reversed(clean_steps):
        if step['status'] in (3, 'failed'):
            failed_step = step
            break

    lines = [
        '<!-- wharttest:generation_mode=self_heal -->',
        '',
        '【UI 自动化用例执行失败 - 定时任务自动自愈】',
        '请按自愈规范诊断该 UI 自动化用例的失败根因，修复用例资产后自动复测验证。',
        '',
        '## 目标用例（只允许修复该用例相关资产）',
        f'项目 ID：{project_id}',
        f'UI 用例 ID：{case.id}',
        f'用例名称：{case.name}',
    ]
    if getattr(case, 'module', None):
        lines.append(f'所属模块 ID：{case.module_id}')

    lines += [
        '',
        '## 执行失败现场（本次定时任务批次中的失败执行记录）',
        f'执行记录 ID：{case_record.id}',
        f'定时任务：{task.name}（ID: {task.id}）',
    ]
    if record and record.error_message:
        lines.append(f'整体报错：{_truncate(" ".join(str(record.error_message).split()), _FAILURE_MESSAGE_MAX * 2)}')

    if failed_step:
        status_text = '成功' if failed_step['status'] in (2, 'success') else '失败'
        desc = failed_step.get('description') or f"步骤 {failed_step.get('step_id')}"
        lines += ['', '## 失败步骤', f"[{status_text}] {desc} - {failed_step.get('message') or ''}"]

    if recent_steps:
        lines += ['', '## 步骤执行流水（按执行顺序）']
        for idx, step in enumerate(recent_steps):
            status_text = '成功' if step['status'] in (2, 'success') else '失败'
            desc = step.get('description') or f"步骤 {step.get('step_id') or idx + 1}"
            message = f" - {step['message']}" if step.get('message') else ''
            lines.append(f"[{status_text}] {desc}{message}")

    lines += ['', '自愈完成后请按规范输出总结（根因、修改点、复测结果）。']
    return '\n'.join(lines)


def _sync_heal_session_messages(session_id: str, user_id: int, project_id: int):
    """把自愈会话的 checkpointer 消息增量同步到 ChatMessage 表。

    agent-loop 路径自身不做该同步（消息只在 LangGraph checkpointer 里），
    对话页会话列表读的是 ChatMessage 表——不同步则用户在 LLM 对话看不到自愈过程。
    每个用例的自愈调用结束后调用一次，实现准实时可见。
    """
    try:
        from langgraph_integration.models import ChatSession
        from langgraph_integration.views import sync_chat_messages_from_checkpointer

        chat_session = ChatSession.objects.filter(session_id=session_id).first()
        if chat_session:
            thread_id = f"{user_id}_{project_id}_{session_id}"
            sync_chat_messages_from_checkpointer(chat_session, chat_session.user, thread_id)
    except Exception:
        logger.warning("[自愈] 自愈会话消息同步到 ChatMessage 失败", exc_info=True)


def _ensure_heal_session_title(session_id: str, task_name: str, case_name: str):
    """给自愈会话设置可读标题（默认标题取 message 头部含守护标记，可读性差）。"""
    try:
        from langgraph_integration.models import ChatSession

        title = f"定时任务自愈 - {task_name} - {case_name}"
        ChatSession.objects.filter(session_id=session_id, title__startswith='新对话').update(title=title)
    except Exception:
        logger.debug("[自愈] 自愈会话标题设置失败", exc_info=True)


def _publish_heal_event(session_id: str, payload: dict) -> None:
    """把自愈流事件转发到通道层，供对话页 WS 订阅实时渲染（打字机效果）。

    委托公共桥接 orchestrator_integration.stream_bridge（best-effort：
    通道层不可用时静默跳过，对话页退化为轮询兜底）。
    """
    from orchestrator_integration.stream_bridge import publish_stream_event

    publish_stream_event(session_id, payload)


def _call_agent_loop_stream(headers: dict, payload: dict) -> dict:
    """流式调用 agent-loop（SSE），收集事件并返回与非流式一致的结构。

    使用 stream=True 的事件流路径：会话状态实时写入 LangGraph checkpointer，
    结束后再同步 ChatMessage，用户可在 AI 对话页看到自愈全过程。
    每个事件同时转发到通道层（打字机实时渲染，best-effort）。
    网络/超时异常向上抛出由调用方判定是否续跑。
    """
    payload = {**payload, 'stream': True}
    final_content = ""
    final_session_id = payload['session_id']
    error_message = None
    error_code = 500
    error_details = None

    with requests.post(
        f"{django_settings.BASE_URL}/api/orchestrator/agent-loop/",
        json=payload,
        headers={**headers, 'Accept': 'text/event-stream'},
        timeout=(30, AGENT_LOOP_TIMEOUT_SECONDS),
        stream=True,
    ) as resp:
        if resp.status_code >= 400:
            retriable = resp.status_code not in (401, 403)
            try:
                detail = resp.json().get('message') or resp.text
            except ValueError:
                detail = resp.text
            raise AgentLoopCallError(f"agent-loop 调用失败 HTTP {resp.status_code}: {detail}", retriable=retriable)

        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line or not str(raw_line).startswith('data: '):
                continue
            data_str = str(raw_line)[6:].strip()
            if data_str == '[DONE]':
                break
            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            event_type = event.get('type')
            if event_type == 'start':
                final_session_id = event.get('session_id', final_session_id)
            elif event_type == 'stream':
                final_content += event.get('data', '')
            elif event_type == 'error':
                error_message = event.get('message', 'Unknown error')
                error_code = event.get('code', 500)
                error_details = event.get('errors')
            # 实时转发给对话页（打字机效果）；step/tool 事件一并转发
            _publish_heal_event(final_session_id, {
                'type': event_type or 'unknown',
                'data': event.get('data'),
                'message': event.get('message'),
                'summary': event.get('summary'),
                'tool_name': event.get('tool_name'),
                'step': event.get('step'),
                'session_id': final_session_id,
            })

    if error_message:
        raise AgentLoopCallError(f"agent-loop 执行错误: {error_message}", retriable=True)
    return {'session_id': final_session_id, 'content': final_content, 'code': error_code, 'errors': error_details}


def _call_agent_loop(headers: dict, payload: dict) -> dict:
    """同步调用 agent-loop 非流式接口。网络/超时异常向上抛出由调用方判定是否续跑。"""
    resp = requests.post(
        f"{django_settings.BASE_URL}/api/orchestrator/agent-loop/",
        json=payload,
        headers=headers,
        timeout=AGENT_LOOP_TIMEOUT_SECONDS,
    )
    if resp.status_code >= 400:
        # 401/403 属于认证/权限问题，重试同会话无法恢复，标记为不可续跑
        retriable = resp.status_code not in (401, 403)
        try:
            detail = resp.json().get('error') or resp.json().get('detail') or resp.text
        except ValueError:
            detail = resp.text
        raise AgentLoopCallError(f"agent-loop 调用失败 HTTP {resp.status_code}: {detail}", retriable=retriable)

    data = resp.json().get('data') or {}
    if data.get('error'):
        # 业务执行错误（LLM 限流/超时等）：同一会话可续跑
        raise AgentLoopCallError(f"agent-loop 执行错误: {data.get('error')}", retriable=True)
    return data


class AgentLoopCallError(Exception):
    """agent-loop 调用异常；retriable=True 表示同会话续跑可能恢复。"""

    def __init__(self, message: str, retriable: bool = True):
        super().__init__(message)
        self.retriable = retriable


@shared_task(bind=True, name='task_center.tasks.heal_failed_cases')
def heal_failed_cases(self, batch_id: int):
    """批次失败用例自动自愈入口（事件驱动，由批次完结判定处投递）。"""
    from ui_automation.models import UiBatchExecutionRecord

    try:
        batch = UiBatchExecutionRecord.objects.select_related(
            'scheduled_task', 'scheduled_task__creator', 'scheduled_task__project',
        ).get(id=batch_id)
    except UiBatchExecutionRecord.DoesNotExist:
        logger.warning(f"[自愈] 批次 {batch_id} 不存在，跳过自愈")
        return {'status': 'skipped', 'message': f'批次 {batch_id} 不存在'}

    task = batch.scheduled_task
    if task is None:
        logger.info(f"[自愈] 批次 {batch_id} 未关联定时任务，跳过自愈")
        return {'status': 'skipped', 'message': '批次未关联定时任务'}
    if not getattr(task, 'auto_heal_enabled', False):
        logger.info(f"[自愈] 任务 [{task.name}] 未开启失败自愈，跳过")
        return {'status': 'skipped', 'message': '任务未开启失败自愈'}

    creator = task.creator
    if creator is None:
        logger.error(f"[自愈] 任务 [{task.name}] 无创建人，无法发起自愈会话")
        return {'status': 'error', 'message': '任务无创建人'}

    limit = task.heal_case_limit or 5
    failed_records = _collect_failed_cases(batch, limit)
    if not failed_records:
        logger.info(f"[自愈] 批次 {batch_id} 未找到失败用例，跳过")
        return {'status': 'skipped', 'message': '无失败用例'}

    skipped_count = batch.failed_cases - len(failed_records)
    healed, unresolved, interrupted = [], [], []
    # 单会话串行：全部用例共用一个 session_id，会话记忆跨用例复用
    session_id = uuid.uuid4().hex
    headers = _build_auth_headers(creator)
    project_id = task.project_id

    log_lines = [
        f"[{timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')}] 自愈任务启动: "
        f"批次 {batch_id} 失败用例 {batch.failed_cases} 个，本轮自愈 {len(failed_records)} 个"
        + (f"（受上限 {limit} 约束，{skipped_count} 个列入待人工清单）" if skipped_count > 0 else ''),
    ]

    for record in failed_records:
        case = record.test_case
        message = _build_failure_message(task, record, project_id)
        payload = {
            'message': message,
            'project_id': str(project_id),
            'module_key': 'testcase_execution',
            'use_knowledge_base': False,
            'session_id': session_id,
        }
        try:
            data = _call_agent_loop_stream(headers, payload)
            summary = ' '.join(str(data.get('content') or '').split())
            healed.append({'case_id': case.id, 'case_name': case.name, 'summary': summary[:200]})
            log_lines.append(
                f"[{timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')}] "
                f"用例 [{case.name}]（ID: {case.id}）自愈完成: {summary[:200] or '详见 AI 对话页'}"
            )
        except AgentLoopCallError as exc:
            # 无论中断与否，先把已产生的会话消息刷进 ChatMessage，保证对话页能看到已发生的自愈过程
            _sync_heal_session_messages(session_id, task.creator_id, project_id)
            if exc.retriable and self.request.retries < (task.retry_count or 3):
                # 会话中断：同一 session_id 续跑（LangGraph checkpointer 保留会话状态）
                log_lines.append(
                    f"[{timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"自愈会话中断: {exc}，将于 {task.retry_interval} 分钟后以同一会话续跑"
                )
                _append_heal_log(batch, log_lines)
                raise self.retry(
                    exc=exc,
                    countdown=(task.retry_interval or 2) * 60,
                    max_retries=task.retry_count or 3,
                )
            interrupted.append({'case_id': case.id, 'case_name': case.name, 'error': str(exc)})
            log_lines.append(
                f"[{timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')}] "
                f"用例 [{case.name}]（ID: {case.id}）自愈中断且不再续跑: {exc}"
            )
            break
        except Exception as exc:  # noqa: BLE001 - 单用例异常不阻断整体总结
            logger.exception(f"[自愈] 用例 [{case.name}] 自愈异常")
            _sync_heal_session_messages(session_id, task.creator_id, project_id)
            interrupted.append({'case_id': case.id, 'case_name': case.name, 'error': str(exc)})
            log_lines.append(
                f"[{timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')}] "
                f"用例 [{case.name}]（ID: {case.id}）自愈异常: {exc}"
            )
            break
        else:
            _ensure_heal_session_title(session_id, task.name, case.name)
            _sync_heal_session_messages(session_id, task.creator_id, project_id)

    # 汇总待人工清单：本轮未自愈的失败用例（超上限/中断剩余）
    healed_ids = {item['case_id'] for item in healed} | {item['case_id'] for item in interrupted}
    manual_required = [
        {'case_id': r.test_case_id, 'case_name': r.test_case.name}
        for r in failed_records
        if r.test_case_id not in healed_ids
    ]

    log_lines.append(
        f"[{timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')}] 自愈总结: "
        f"已处理 {len(healed)} 个，中断 {len(interrupted)} 个，待人工确认 {len(manual_required) + skipped_count} 个"
        f"（自愈会话 session_id={session_id}，可在 AI 对话页回看）"
    )

    # 方案B（执行记录状态翻转）：定时任务因批次失败被置 failed，若本轮自愈把
    # 该批次全部失败用例都修复成功（无中断、无超上限裁剪、无待人工），则把该执行
    # 记录翻转为 success——自愈的成功让定时任务的最终结果恢复为通过。
    # 仅定时任务触发的自愈链路（本函数）会执行此翻转：手动自愈/双模自愈不走这里，
    # 天然不涉及任务中心执行记录。
    # 判定依据是落库的执行记录真实状态（复测回执），而非模型流程完成与否——
    # agent-loop 正常返回 ≠ 自愈成功（模型可能因复测通道故障得出失败结论但流程无异常）
    all_healed = (
        len(healed) > 0
        and not interrupted
        and not manual_required
        and skipped_count == 0
        and _all_failed_cases_passed(batch)
    )
    if all_healed:
        if _flip_execution_record_to_success(batch, len(healed)):
            log_lines.append(
                f"[{timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')}] "
                f"执行记录状态已翻转为成功（自愈全部成功）"
            )
            logger.info(
                f"[自愈] 批次 {batch_id} 全部失败用例自愈成功，执行记录状态已翻转为成功"
            )

    _append_heal_log(batch, log_lines)

    # 任务结束：清除活跃标记（前端 task-session 接口 active=False → 停止订阅/轮询、按钮复位）
    try:
        from orchestrator_integration.stream_bridge import clear_active_session

        clear_active_session(session_id)
    except Exception:
        pass

    return {
        'status': 'completed' if not interrupted else 'interrupted',
        'batch_id': batch_id,
        'session_id': session_id,
        'healed': healed,
        'interrupted': interrupted,
        'manual_required': manual_required,
    }


def _append_heal_log(batch, log_lines: list):
    """把自愈过程摘要追加到批次关联的任务中心执行记录日志中。"""
    from .models import TaskExecution

    try:
        # 按批次精确关联：同"最新一条"取法会把日志写到自愈期间新产生的其他执行记录上
        execution = (
            batch.scheduled_task.executions
            .filter(batch_record=batch)
            .order_by('-started_at')
            .first()
        )
        if execution:
            append_text = '\n'.join(log_lines)
            TaskExecution.objects.filter(id=execution.id).update(
                log=((execution.log + '\n') if execution.log else '') + append_text
            )
    except Exception:
        logger.warning("[自愈] 自愈日志写入执行记录失败", exc_info=True)

def _all_failed_cases_passed(batch) -> bool:
    """核对批次内全部失败用例的最新执行记录是否都已通过（status=2）。

    自愈复测会为每个用例生成新的执行记录；以落库回执为准判定自愈是否真实成功，
    防止"模型流程走完但复测实际失败"时误翻转执行记录状态。
    """
    from ui_automation.models import UiExecutionRecord

    failed_case_ids = list(
        UiExecutionRecord.objects
        .filter(batch=batch, status=3)
        .values_list('test_case_id', flat=True)
        .distinct()
    )
    if not failed_case_ids:
        return False
    for case_id in failed_case_ids:
        latest = (
            UiExecutionRecord.objects
            .filter(test_case_id=case_id, status__in=(2, 3))
            .order_by('-created_at')
            .first()
        )
        if latest is None or latest.status != 2:
            return False
    return True


def _flip_execution_record_to_success(batch, healed_count: int) -> bool:
    """自愈全部成功时，把批次关联的任务中心执行记录 failed → success。

    条件更新（仅 failed 行），与并发回写互斥；finished_at 保持不变
    （记录任务的触发完成时间，不因状态翻转改变）；翻转原因追加到日志。
    返回是否发生了翻转。
    """
    from .models import TaskExecution

    try:
        # 按批次精确关联（batch_record=batch）：自愈期间同任务可能被手动触发或
        # 再调度产生其他执行记录，取"最新一条"会把状态翻到错误的记录上
        execution = (
            TaskExecution.objects
            .filter(batch_record=batch, status=TaskExecution.ExecutionStatus.FAILED)
            .order_by('-started_at')
            .first()
        )
        if execution is None:
            return False
        flip_note = (
            f"\n[{timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')}] "
            f"自愈成功：批次 {batch.id} 的全部 {healed_count} 个失败用例已修复并复测通过，"
            f"执行记录状态翻转为成功"
        )
        updated = TaskExecution.objects.filter(
            id=execution.id,
            status=TaskExecution.ExecutionStatus.FAILED,
        ).update(
            status=TaskExecution.ExecutionStatus.SUCCESS,
            log=((execution.log or '') + flip_note),
        )
        return updated > 0
    except Exception:
        logger.warning("[自愈] 执行记录状态翻转失败", exc_info=True)
        return False
