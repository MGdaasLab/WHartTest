"""自愈会话守护（generation_mode=self_heal）单元测试。

覆盖：
1. detect_generation_mode 对 self_heal 标记的识别（含多标记优先级与无标记）；
2. SelfHealGuardMiddleware 对删除/结构级创建/接口自动化动作的拦截与修复类动作放行；
3. SELF_HEAL_INSTRUCTION 与默认模板注册同源。
"""
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from orchestrator_integration.generation_guard import (
    GENERATION_MODE_INTERFACE_CASE,
    GENERATION_MODE_SELF_HEAL,
    GENERATION_MODE_UI_CASE,
    SELF_HEAL_FORBIDDEN_TOOL_HINTS,
    SelfHealGuardMiddleware,
    detect_generation_mode,
)
from orchestrator_integration.self_heal_instructions import (
    SELF_HEAL_INSTRUCTION,
    SELF_HEAL_PROMPT_NAME,
)


def _make_request(command: str, tool_name: str = "execute_skill_script"):
    tool_call = {"name": tool_name, "args": {"command": command}, "id": "call_1"}
    request = MagicMock()
    request.tool_call = tool_call
    request.override.return_value = request
    return request


class DetectGenerationModeTests(SimpleTestCase):
    def test_detects_self_heal_marker(self):
        message = "<!-- wharttest:generation_mode=self_heal -->\n自愈任务"
        self.assertEqual(detect_generation_mode(message), GENERATION_MODE_SELF_HEAL)

    def test_interface_case_marker_has_priority(self):
        message = (
            "<!-- wharttest:generation_mode=self_heal -->\n"
            "<!-- wharttest:generation_mode=interface_case -->"
        )
        self.assertEqual(detect_generation_mode(message), GENERATION_MODE_INTERFACE_CASE)

    def test_ui_case_marker_still_detected(self):
        message = "<!-- wharttest:generation_mode=ui_case -->"
        self.assertEqual(detect_generation_mode(message), GENERATION_MODE_UI_CASE)

    def test_no_marker_returns_none(self):
        self.assertIsNone(detect_generation_mode("普通消息"))
        self.assertIsNone(detect_generation_mode(None))


class SelfHealGuardMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.middleware = SelfHealGuardMiddleware()

    def test_blocks_delete_action(self):
        request = _make_request(
            "python ui_automation_tools.py --action delete_element --element_id 3"
        )
        result = self.middleware.wrap_tool_call(request, lambda req: "executed")
        self.assertEqual(result.status, "error")
        self.assertIn("update_element", result.content)
        self.assertEqual(self.middleware.drift_count, 1)

    def test_blocks_structural_create_actions(self):
        for action in ("create_testcase", "create_page_step", "set_case_steps", "create_page"):
            request = _make_request(
                f"python ui_automation_tools.py --action {action} --payload '{{}}'"
            )
            result = self.middleware.wrap_tool_call(request, lambda req: "executed")
            self.assertEqual(result.status, "error", action)

    def test_blocks_interface_tool_drift(self):
        request = _make_request("python api_tools.py --action run_interface_case --case_id 1")
        result = self.middleware.wrap_tool_call(request, lambda req: "executed")
        self.assertEqual(result.status, "error")
        self.assertIn("execute_testcase", result.content)

    def test_allows_repair_and_query_actions(self):
        executed = []

        def handler(req):
            executed.append(req)
            return "executed"

        for command in (
            "python ui_automation_tools.py --action get_elements --page_id 1",
            "python ui_automation_tools.py --action get_execution_record --record_id 9",
            "python ui_automation_tools.py --action update_element --element_id 3 "
            "--payload '{\"locator_type\": \"css\", \"locator_value\": \".btn\"}'",
            "python ui_automation_tools.py --action set_step_details --step_detail_id 5 "
            "--payload '{\"element\": 3}'",
            "python ui_automation_tools.py --action execute_testcase --case_id 7 "
            "--actuator_id recorder-browser --wait_result",
            "python ui_automation_tools.py --action create_element --payload '{\"name\": \"新元素\"}'",
        ):
            request = _make_request(command)
            self.assertEqual(self.middleware.wrap_tool_call(request, handler), "executed", command)

        self.assertEqual(len(executed), 6)
        self.assertEqual(self.middleware.drift_count, 0)

    async def test_async_path_blocks_delete_action(self):
        request = _make_request(
            "python ui_automation_tools.py --action delete_testcase --case_id 7"
        )
        result = await self.middleware.awrap_tool_call(request, self._async_handler)
        self.assertEqual(result.status, "error")

    @staticmethod
    async def _async_handler(request):
        return "executed"

    def test_non_skill_tool_passes_through(self):
        request = _make_request("ls -la", tool_name="bash")
        self.assertEqual(
            self.middleware.wrap_tool_call(request, lambda req: "executed"),
            "executed",
        )

    def test_forbidden_hints_all_non_empty(self):
        for action, hint in SELF_HEAL_FORBIDDEN_TOOL_HINTS.items():
            self.assertTrue(hint.strip(), action)


class SelfHealInstructionSourceTests(SimpleTestCase):
    def test_default_template_registered_with_same_constant(self):
        # zh 模板模块顶层引用 Django 模型，pytest 直跑时需先完成 apps 初始化
        import django

        if not django.apps.apps.ready:
            django.setup()

        from prompts.default_templates import zh

        registered = [p for p in zh.DEFAULT_PROMPTS if p.get("name") == SELF_HEAL_PROMPT_NAME]
        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["content"], SELF_HEAL_INSTRUCTION)
