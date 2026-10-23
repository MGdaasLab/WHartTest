# -*- coding: utf-8 -*-
"""
功能测试用例 - UI 自动化失败 AI 介入诊断与自愈服务
"""

import json
import logging
import re
from typing import Any, Dict, Optional
from django.utils import timezone
from langchain_core.messages import HumanMessage, SystemMessage

from langgraph_integration.models import LLMConfig
from langgraph_integration.views import create_llm_instance
from ui_automation.models import UiTestCase, UiExecutionRecord, UiElement, UiCaseStepsDetailed

logger = logging.getLogger(__name__)

DIAGNOSIS_SYSTEM_PROMPT = """你是一名资深自动化测试架构师与 AI 测试排障专家。
你的任务是对 UI 自动化执行失败的现场数据进行多模态/结构化深度分析，输出标准 JSON 格式的根因诊断报告和自愈建议。

请严格遵守以下输出格式，只输出纯 JSON，不要包含任何额外的自然语言解释或 Markdown 格式（如果使用代码块请使用 ```json ... ```）：
{
  "root_cause_type": "SCRIPT_DEFECT" | "BUG" | "ENV_ISSUE" | "UNKNOWN",
  "root_cause_label": "元素定位失效" | "业务缺陷(Bug)" | "环境或网络异常" | "未知原因",
  "confidence": 0.95,
  "summary": "一句话总结失败根因",
  "detailed_analysis": "详细技术与业务层面的失败原因分析，指出为何失败、哪一步受阻",
  "failure_step_info": {
    "step_sort": 1,
    "page_name": "页面名称",
    "element_name": "元素名称",
    "operation_type": "操作类型",
    "error_message": "原始错误信息"
  },
  "healing_suggestion": {
    "can_self_heal": true,
    "element_id": null,
    "element_name": "",
    "current_locator_type": "",
    "current_locator_value": "",
    "suggested_locator_type": "xpath" | "css" | "text" | "role" | "test_id" | "id",
    "suggested_locator_value": "推荐的新定位表达式",
    "explanation": "自愈定位推荐理由及替换建议"
  },
  "defect_report": {
    "is_real_bug": false,
    "title": "缺陷标题建议",
    "severity": "High" | "Medium" | "Low",
    "reproduction_summary": "复现步骤概要",
    "expected_vs_actual": "预期与实际差异"
  }
}
"""


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """从 LLM 返回文本中提取 JSON 对象"""
    if not text:
        return None
    cleaned = text.strip()
    # 匹配 ```json ... ```
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if json_match:
        cleaned = json_match.group(1).strip()
    try:
        return json.loads(cleaned)
    except Exception as e:
        logger.warning(f"直接解析 JSON 失败: {e}, 尝试粗略截取花括号")
        # 尝试寻找第一个 { 和最后一个 }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except Exception:
                pass
    return None


def _fallback_rule_diagnosis(
    testcase,
    ui_record: Optional[UiExecutionRecord],
    failure_info: Dict[str, Any],
) -> Dict[str, Any]:
    """基于规则的兜底诊断生成"""
    error_msg = failure_info.get("error_message", "") or ""
    step_info = failure_info.get("failure_step", {})

    root_cause_type = "UNKNOWN"
    root_cause_label = "执行异常"
    summary = "UI 自动化执行未达到预期"
    can_self_heal = False

    if any(k in error_msg.lower() for k in ["timeout", "waiting for locator", "element not found", "no element", "locator.click"]):
        root_cause_type = "SCRIPT_DEFECT"
        root_cause_label = "元素定位失效/超时"
        summary = f"步骤「{step_info.get('element_name', '目标元素')}」定位超时，页面结构或元素定位表达式可能已发生变更"
        can_self_heal = True
    elif any(k in error_msg.lower() for k in ["assertion", "expect", "assert", "not equal", "mismatch"]):
        root_cause_type = "BUG"
        root_cause_label = "业务断言不符 (疑似Bug)"
        summary = f"步骤断言校验失败：预期结果与实际页面状态不一致"
    elif any(k in error_msg.lower() for k in ["login", "auth", "502", "503", "504", "net::err", "connection refused"]):
        root_cause_type = "ENV_ISSUE"
        root_cause_label = "环境/网络或登录态异常"
        summary = f"网络连接或服务环境异常导致执行中断"

    return {
        "root_cause_type": root_cause_type,
        "root_cause_label": root_cause_label,
        "confidence": 0.85,
        "summary": summary,
        "detailed_analysis": f"用例【{testcase.name}】在执行绑定的 UI 自动化脚本时，第 {step_info.get('step_sort', 1)} 步发生失败。\n错误详情：{error_msg[:300]}",
        "failure_step_info": {
            "step_sort": step_info.get("step_sort", 1),
            "page_name": step_info.get("page_name", ""),
            "element_name": step_info.get("element_name", ""),
            "operation_type": step_info.get("operation_type", ""),
            "error_message": error_msg,
        },
        "healing_suggestion": {
            "can_self_heal": can_self_heal,
            "element_id": step_info.get("element_id"),
            "element_name": step_info.get("element_name", ""),
            "current_locator_type": step_info.get("locator_type", "xpath"),
            "current_locator_value": step_info.get("locator_value", ""),
            "suggested_locator_type": "xpath",
            "suggested_locator_value": step_info.get("locator_value", ""),
            "explanation": "建议检查页面对应元素的 XPath/CSS 定位或使用文本/role 定位替代。",
        },
        "defect_report": {
            "is_real_bug": root_cause_type == "BUG",
            "title": f"【UI自动化失败】{testcase.name} - {root_cause_label}",
            "severity": "Medium",
            "reproduction_summary": f"执行用例 {testcase.name} 时，在步骤 {step_info.get('step_sort', 1)} 发生失败。",
            "expected_vs_actual": f"预期操作成功，实际报错: {error_msg[:150]}",
        },
    }


def extract_failure_context(
    testcase,
    ui_record: Optional[UiExecutionRecord] = None,
) -> Dict[str, Any]:
    """从执行记录和用例中提取结构化失败上下文"""
    if not ui_record and testcase.ui_test_case:
        ui_record = UiExecutionRecord.objects.filter(
            test_case=testcase.ui_test_case
        ).order_by("-id").first()

    step_results = ui_record.step_results if ui_record else []
    failed_step_data = None
    step_sort = 1
    steps_history = []
    dom_snapshot = ""

    if step_results and isinstance(step_results, list):
        for idx, res in enumerate(step_results):
            step_status = res.get("status")
            msg = res.get("message") or res.get("error_message") or res.get("error") or ""
            step_desc = res.get("description") or f"步骤 {idx + 1}"

            status_text = "成功" if step_status in [2, "success", "passed", True] else "失败"
            steps_history.append(f"步骤 {idx + 1} [{status_text}]: {step_desc} - {msg[:160] if msg else '无详细消息'}")

            # 抓取页面快照
            if "Actual value:" in msg:
                try:
                    dom_part = msg.split("Actual value:", 1)[1]
                    if "Error:" in dom_part:
                        dom_part = dom_part.split("Error:", 1)[0]
                    dom_snapshot = dom_part.strip()
                except Exception:
                    pass

            # 判定失败步骤
            is_failed = (
                step_status in [3, "fail", "failed", False]
                or "Error:" in msg
                or "Locator." in msg
                or "not found" in msg
                or "Timeout" in msg
            )
            if is_failed and not failed_step_data:
                failed_step_data = res
                step_sort = idx + 1

        if not failed_step_data and len(step_results) > 0:
            failed_step_data = step_results[-1]
            step_sort = len(step_results)

    # 提取错误信息：优先使用具体步骤中的真实报错堆栈
    error_msg = ""
    if failed_step_data:
        error_msg = failed_step_data.get("message") or failed_step_data.get("error_message") or failed_step_data.get("error") or ""
    if not error_msg and ui_record:
        error_msg = ui_record.error_message or ui_record.log or ""

    # 获取关联的步骤、元素详细信息
    element_id = None
    element_name = ""
    locator_type = ""
    locator_value = ""
    page_name = ""
    operation_type = ""
    ope_value = None
    step_description = failed_step_data.get("description", "") if failed_step_data else ""
    step_id_val = failed_step_data.get("step_id") if failed_step_data else None

    # 1. 优先通过 step_id 精准反查 UiPageStepsDetailed
    if step_id_val:
        from ui_automation.models import UiPageStepsDetailed
        detailed_step = UiPageStepsDetailed.objects.filter(id=step_id_val).select_related(
            "element", "page_step", "page_step__page"
        ).first()
        if detailed_step:
            operation_type = detailed_step.ope_key or ""
            ope_value = detailed_step.ope_value
            if detailed_step.page_step and detailed_step.page_step.page:
                page_name = detailed_step.page_step.page.name
            if detailed_step.element:
                element_id = detailed_step.element.id
                element_name = detailed_step.element.name
                locator_type = detailed_step.element.locator_type
                locator_value = detailed_step.element.locator_value
            if not step_description:
                step_description = detailed_step.description or (detailed_step.page_step.name if detailed_step.page_step else "")

    # 2. 如果未找到元素，尝试根据用例步骤序号兜底匹配
    if not element_id and testcase.ui_test_case:
        case_steps = list(testcase.ui_test_case.case_steps.all().select_related(
            "page_step", "page_step__page"
        ).order_by("case_sort"))
        if 0 <= step_sort - 1 < len(case_steps):
            target_step = case_steps[step_sort - 1]
            if target_step.page_step and target_step.page_step.page:
                page_name = page_name or target_step.page_step.page.name
            details = list(target_step.page_step.step_details.all().select_related("element").order_by("step_sort"))
            if details:
                first_detail = details[0]
                operation_type = operation_type or first_detail.ope_key or ""
                ope_value = ope_value or first_detail.ope_value
                if first_detail.element:
                    element_id = first_detail.element.id
                    element_name = first_detail.element.name
                    locator_type = first_detail.element.locator_type
                    locator_value = first_detail.element.locator_value

    # 3. 收集项目或当前页面中已有的其他候选元素库，供自愈参考
    available_elements = []
    if testcase.project_id:
        from ui_automation.models import UiElement
        elements_qs = UiElement.objects.filter(page__project_id=testcase.project_id).select_related("page")
        if page_name:
            page_elements = list(elements_qs.filter(page__name=page_name)[:15])
            other_elements = list(elements_qs.exclude(page__name=page_name)[:10])
            all_elements = page_elements + other_elements
        else:
            all_elements = list(elements_qs[:20])

        for el in all_elements:
            available_elements.append(
                f"- [ID: {el.id}] 【{el.page.name if el.page else '公共'}】{el.name}: [{el.locator_type}] {el.locator_value}"
            )

    screenshots = []
    if ui_record and ui_record.screenshots:
        screenshots = ui_record.screenshots

    return {
        "ui_record_id": ui_record.id if ui_record else None,
        "error_message": error_msg,
        "screenshots": screenshots,
        "log": ui_record.log if ui_record else "",
        "steps_history": steps_history,
        "dom_snapshot": dom_snapshot,
        "available_elements": available_elements,
        "failure_step": {
            "step_sort": step_sort,
            "step_description": step_description,
            "page_name": page_name,
            "element_id": element_id,
            "element_name": element_name,
            "locator_type": locator_type,
            "locator_value": locator_value,
            "operation_type": operation_type,
            "operation_value": json.dumps(ope_value, ensure_ascii=False) if ope_value else "",
        },
    }


def diagnose_execution_failure(
    testcase,
    ui_record_id: Optional[int] = None,
    user=None,
) -> Dict[str, Any]:
    """
    对功能用例执行失败进行 AI 智能归因与自愈诊断
    """
    ui_record = None
    if ui_record_id:
        ui_record = UiExecutionRecord.objects.filter(id=ui_record_id).first()
        if not ui_record:
            raise ValueError(f"未找到指定的 UI 执行记录 (ID: {ui_record_id})")
        if testcase.ui_test_case and ui_record.test_case_id != testcase.ui_test_case_id:
            raise ValueError(f"指定的执行记录 (ID: {ui_record_id}) 不属于当前测试用例关联的 UI 自动化用例")
    elif testcase.ui_test_case:
        ui_record = UiExecutionRecord.objects.filter(
            test_case=testcase.ui_test_case
        ).order_by("-id").first()
    else:
        raise ValueError("当前测试用例尚未关联 UI 自动化用例且未提供有效的执行记录")

    failure_info = extract_failure_context(testcase, ui_record)

    # 组装 Prompt
    steps_desc = "\n".join([
        f"步骤 {s.step_number}: {s.description} (预期结果: {s.expected_result})"
        for s in testcase.steps.all().order_by("step_number")
    ])

    steps_history_str = "\n".join(failure_info.get("steps_history", [])) or "无"
    elements_str = "\n".join(failure_info.get("available_elements", [])) or "无候选元素"
    dom_snapshot_str = failure_info.get("dom_snapshot", "")

    user_prompt = f"""【待诊断的功能测试用例】
用例ID: {testcase.id}
用例名称: {testcase.name}
前置条件: {testcase.precondition or '无'}
功能步骤定义:
{steps_desc or '无详细步骤'}

【绑定的 UI 自动化资产】
UI用例ID: {testcase.ui_test_case_id or '未绑定'}
UI用例名称: {testcase.ui_test_case.name if testcase.ui_test_case else '无'}

【执行步骤完整流水】
{steps_history_str}

【执行失败现场上下文】
失败步骤序号: 第 {failure_info['failure_step']['step_sort']} 步 ({failure_info['failure_step']['step_description']})
失败页面/元素: {failure_info['failure_step']['page_name'] or '未知页面'} -> {failure_info['failure_step']['element_name'] or '未知元素'} (元素ID: {failure_info['failure_step']['element_id'] or '空'})
当前定位配置: [{failure_info['failure_step']['locator_type'] or '无'}] {failure_info['failure_step']['locator_value'] or '无'}
操作方法及参数: {failure_info['failure_step']['operation_type']} {failure_info['failure_step']['operation_value']}

【真实错误堆栈 / Playwright 报错信息】
{failure_info['error_message'] or '无详细报错'}
"""

    if dom_snapshot_str:
        user_prompt += f"""
【失败现场页面结构快照 (Accessibility Tree / DOM)】
{dom_snapshot_str}
"""

    user_prompt += f"""
【系统资产库中的已有元素参考】
{elements_str}

请针对上述失败现场、错误堆栈和页面 DOM 快照，给出准确的失败归因（是元素定位失效/资产配置错位、真实业务Bug还是环境网络异常），并给出定位自愈建议和缺陷报告建议。
特别提示：如果错误是因为在非输入框元素上执行了输入操作（例如对按钮进行了 fill），或者定位表达式失效，请结合页面快照给出正确的输入框定位自愈建议。
"""

    diagnosis_result = None

    try:
        active_config = LLMConfig.objects.filter(is_active=True).first()
        if active_config:
            llm = create_llm_instance(active_config, temperature=0.2)
            messages = [
                SystemMessage(content=DIAGNOSIS_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
            response = llm.invoke(messages)
            content_text = getattr(response, "content", "")
            if isinstance(content_text, list):
                content_text = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in content_text])
            diagnosis_result = _extract_json_from_text(str(content_text))
            if diagnosis_result:
                diagnosis_result["diagnosed_by"] = "llm"
                diagnosis_result["model_name"] = active_config.name
    except Exception as e:
        logger.error(f"调用 LLM 诊断失败: {e}", exc_info=True)

    if not diagnosis_result:
        diagnosis_result = _fallback_rule_diagnosis(testcase, ui_record, failure_info)
        diagnosis_result["diagnosed_by"] = "rule_fallback"

    diagnosis_result["diagnosed_at"] = timezone.now().isoformat()
    diagnosis_result["ui_execution_record_id"] = ui_record.id if ui_record else None

    return diagnosis_result


def apply_healing_to_element(
    testcase,
    healing_data: Dict[str, Any],
    user=None,
) -> Dict[str, Any]:
    """
    一键应用 AI 自愈建议，回写 UI 元素定位配置
    """
    element_id = healing_data.get("element_id")
    suggested_type = healing_data.get("suggested_locator_type")
    suggested_value = healing_data.get("suggested_locator_value")

    if not element_id:
        element_name = healing_data.get("element_name")
        if element_name and testcase.ui_test_case:
            elem = UiElement.objects.filter(
                page__project_id=testcase.project_id,
                name=element_name
            ).first()
            if elem:
                element_id = elem.id

    if not element_id or not suggested_value:
        raise ValueError("缺少待修复的元素 ID 或新的定位表达式")

    element = UiElement.objects.get(id=element_id, page__project_id=testcase.project_id)

    old_locator_type = element.locator_type
    old_locator_value = element.locator_value

    if old_locator_value and old_locator_value != suggested_value:
        element.locator_type_2 = old_locator_type
        element.locator_value_2 = old_locator_value

    element.locator_type = suggested_type or old_locator_type or "xpath"
    element.locator_value = suggested_value
    element.save()

    logger.info(
        f"成功自愈更新元素 [{element.name} (ID: {element.id})]: "
        f"{old_locator_type}='{old_locator_value}' -> {element.locator_type}='{element.locator_value}'"
    )

    return {
        "success": True,
        "element_id": element.id,
        "element_name": element.name,
        "old_locator": f"[{old_locator_type}] {old_locator_value}",
        "new_locator": f"[{element.locator_type}] {element.locator_value}",
        "updated_at": timezone.now().isoformat(),
    }
