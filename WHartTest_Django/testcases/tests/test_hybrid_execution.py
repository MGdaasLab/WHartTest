from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from projects.models import Project
from testcases.models import TestCase as TestCaseModel, TestCaseModule, TestCaseStep
from ui_automation.models import UiModule, UiPage, UiElement, UiPageSteps, UiPageStepsDetailed, UiTestCase, UiCaseStepsDetailed, UiExecutionRecord


class HybridExecutionAndBindingTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="testuser",
            password="password",
            email="test@example.com",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(
            name="Test Project",
            description="Test Description",
            creator=self.user,
        )
        self.module = TestCaseModule.objects.create(
            project=self.project,
            name="Test Module",
            creator=self.user,
        )
        self.testcase = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="功能测试用例1",
            precondition="前置条件1",
            creator=self.user,
            review_status="pending_review",
        )
        TestCaseStep.objects.create(
            test_case=self.testcase,
            step_number=1,
            description="点击登录按钮",
            expected_result="成功跳转首页",
            creator=self.user,
        )

        # 创建 UI 自动化资产
        self.ui_module = UiModule.objects.create(
            project=self.project,
            name="UI模块",
            creator=self.user,
        )
        self.ui_page = UiPage.objects.create(
            project=self.project,
            module=self.ui_module,
            name="登录页",
            creator=self.user,
        )
        self.ui_element = UiElement.objects.create(
            page=self.ui_page,
            name="登录按钮",
            locator_type="xpath",
            locator_value="//button[@id='old-login-btn']",
            creator=self.user,
        )
        self.ui_page_step = UiPageSteps.objects.create(
            project=self.project,
            page=self.ui_page,
            module=self.ui_module,
            name="点击登录步骤",
            creator=self.user,
        )
        UiPageStepsDetailed.objects.create(
            page_step=self.ui_page_step,
            step_type=0,
            element=self.ui_element,
            ope_key="click",
            step_sort=1,
        )
        self.ui_testcase = UiTestCase.objects.create(
            project=self.project,
            module=self.ui_module,
            name="UI登录自动化用例",
            creator=self.user,
        )
        UiCaseStepsDetailed.objects.create(
            test_case=self.ui_testcase,
            page_step=self.ui_page_step,
            case_sort=1,
        )

    def test_bind_ui_testcase_success(self):
        """测试绑定 UI 自动化用例接口"""
        url = f"/api/projects/{self.project.id}/testcases/{self.testcase.id}/bind-ui-testcase/"
        response = self.client.post(
            url,
            {
                "ui_test_case_id": self.ui_testcase.id,
                "execution_mode": "hybrid",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.testcase.refresh_from_db()
        self.assertEqual(self.testcase.ui_test_case_id, self.ui_testcase.id)
        self.assertEqual(self.testcase.execution_mode, "hybrid")
        self.assertIsNotNone(response.data.get("ui_test_case_detail"))
        self.assertEqual(response.data["ui_test_case_detail"]["id"], self.ui_testcase.id)

    def test_unbind_ui_testcase_success(self):
        """测试解绑 UI 自动化用例"""
        self.testcase.ui_test_case = self.ui_testcase
        self.testcase.save()

        url = f"/api/projects/{self.project.id}/testcases/{self.testcase.id}/bind-ui-testcase/"
        response = self.client.post(
            url,
            {"ui_test_case_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.testcase.refresh_from_db()
        self.assertIsNone(self.testcase.ui_test_case)

    def test_diagnose_failure_rule_fallback(self):
        """测试失败诊断接口在无外部 LLM 时的规则回退诊断能力"""
        self.testcase.ui_test_case = self.ui_testcase
        self.testcase.save()

        # 创建一条失败的 UI 执行记录
        record = UiExecutionRecord.objects.create(
            test_case=self.ui_testcase,
            executor=self.user,
            status=3,  # 失败
            error_message="Timeout 5000ms waiting for locator //button[@id='old-login-btn']",
            step_results=[
                {
                    "step_id": 1,
                    "status": 3,
                    "error_message": "Timeout 5000ms waiting for locator //button[@id='old-login-btn']",
                }
            ],
        )

        url = f"/api/projects/{self.project.id}/testcases/{self.testcase.id}/diagnose-failure/"
        response = self.client.post(
            url,
            {"ui_execution_record_id": record.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("root_cause_type", response.data)
        self.assertEqual(response.data["root_cause_type"], "SCRIPT_DEFECT")
        self.assertTrue(response.data["healing_suggestion"]["can_self_heal"])

    def test_apply_healing_to_element(self):
        """测试一键应用自愈建议更新 UI 元素定位"""
        self.testcase.ui_test_case = self.ui_testcase
        self.testcase.save()

        url = f"/api/projects/{self.project.id}/testcases/{self.testcase.id}/apply-healing/"
        response = self.client.post(
            url,
            {
                "element_id": self.ui_element.id,
                "suggested_locator_type": "xpath",
                "suggested_locator_value": "//button[text()='登录']",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ui_element.refresh_from_db()
        self.assertEqual(self.ui_element.locator_value, "//button[text()='登录']")
        self.assertEqual(self.ui_element.locator_value_2, "//button[@id='old-login-btn']")
