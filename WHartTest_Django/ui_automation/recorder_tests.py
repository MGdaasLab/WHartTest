"""录制器后端单测：动作解析入库 + 会话管理 + REST 校验。"""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project, ProjectMember
from ui_automation.consumers import UiAutomationConsumer, SocketUserManager
from ui_automation.socket_models import NoticeType
from ui_automation.models import (
    UiElement, UiModule, UiPage, UiPageSteps, UiPageStepsDetailed, UiEnvironmentConfig, UiAuthState, UiTestCase,
)
from ui_automation.recorder.session_manager import (
    recorder_manager, RecorderSessionError,
)
from ui_automation.recorder_apply import apply_recorded_actions

STUB_NODE = r"""
const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
function send(msg) { process.stdout.write(JSON.stringify(msg) + '\n'); }
rl.on('line', (line) => {
  let msg;
  try { msg = JSON.parse(line); } catch (_) { return; }
  const { id, method, params } = msg;
  if (method === 'ping') send({ id, ok: true, state: { alive: true } });
  else if (method === 'start') send({ id, ok: true, state: { viewport: params.viewport } });
  else if (method === 'input') send({ id, ok: true });
  else if (method === 'assert') send({ id, ok: true, state: { action: 'assert_visible' } });
  else if (method === 'finish') send({ id, ok: true, state: { actions: [], script: '' } });
  else if (method === 'close') { send({ id, ok: true }); process.exit(0); }
  else send({ id, ok: false, error: 'unknown method ' + method });
});
"""


class RecorderSessionManagerTests(TestCase):
    """会话管理：spawn / JSON-RPC / 事件推送 / 关闭（使用 stub 脚本）。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.mkdtemp(prefix='recorder-skill-')
        (Path(cls._tmp) / 'package.json').write_text(
            json.dumps({'name': 'stub-skill', 'version': '1.0.0', 'dependencies': {}}),
            encoding='utf-8',
        )
        cls._stub_script = Path(cls._tmp) / 'stub_node.js'
        cls._stub_script.write_text(STUB_NODE, encoding='utf-8')
        os.environ['RECORDER_SERVER_SCRIPT'] = str(cls._stub_script)

    @classmethod
    def tearDownClass(cls):
        os.environ.pop('RECORDER_SERVER_SCRIPT', None)
        shutil.rmtree(cls._tmp, ignore_errors=True)
        super().tearDownClass()

    def _spawn(self):
        session = recorder_manager.create_session(
            user_id='u1',
            project_id=1,
            skill_dir=self._tmp,
        )
        return session

    def test_ping_request_close(self):
        session = self._spawn()
        session.start(timeout=15)
        self.assertTrue(session.alive)
        resp = session.request('ping', {}, timeout=10)
        self.assertTrue(resp['ok'])
        session.close()
        self.assertFalse(session.alive)

    def test_events_and_latest_frame(self):
        """事件推送（frame 只保留最新）与 drain。"""
        session = self._spawn()
        session.start(timeout=15)
        # stub 不推帧，这里直接注入模拟事件
        session._dispatch_event('frame', {'data': 'AAA'})
        session._dispatch_event('frame', {'data': 'BBB'})
        session._dispatch_event('actions', {'type': 'click', 'seq': 1})
        self.assertEqual(session.take_latest_frame()['data'], 'BBB')
        self.assertIsNone(session.take_latest_frame())
        events = session.drain_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'actions')
        session.close()

    def test_timeout_raises(self):
        session = self._spawn()
        session.start(timeout=15)
        with self.assertRaises(RecorderSessionError):
            session.request('unknown_method', {}, timeout=3)
        session.close()

    def test_close_is_idempotent(self):
        session = self._spawn()
        session.start(timeout=15)
        session.close()
        session.close()
        self.assertFalse(session.alive)


class RecorderApplyTests(TestCase):
    """动作列表 → 元素/步骤 入库解析。"""

    def setUp(self):
        self.user = User.objects.create_superuser(username='recorder', password='secret')
        self.project = Project.objects.create(name='Recorder Project')
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.module = UiModule.objects.create(project=self.project, name='M', creator=self.user)
        self.page = UiPage.objects.create(
            project=self.project, module=self.module, name='Page', url='/login', creator=self.user,
        )
        self.page_step = UiPageSteps.objects.create(
            project=self.project, page=self.page, module=self.module, name='Steps', creator=self.user,
        )

    def _actions(self):
        return [
            {'type': 'goto', 'url': 'https://example.com/page'},
            {'type': 'click', 'selector': {'locator_type': 'id', 'locator_value': 'login-btn', 'name': '登录'}},
            {'type': 'fill', 'selector': {'locator_type': 'name', 'locator_value': 'username', 'name': '用户名'}, 'value': 'admin'},
            {'type': 'press', 'selector': {'locator_type': 'placeholder', 'locator_value': '输入密码', 'name': '密码'}, 'key': 'Enter'},
            {'type': 'assert', 'mode': 'visible', 'selector': {'locator_type': 'text', 'locator_value': '登录成功', 'name': '登录成功'}},
        ]

    def test_apply_creates_elements_and_steps(self):
        stats = apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user, actions=self._actions())
        self.assertEqual(stats['elements_created'], 4)  # goto 无选择器
        self.assertEqual(stats['steps_created'], 5)
        self.assertEqual(UiElement.objects.filter(page=self.page).count(), 4)
        details = list(UiPageStepsDetailed.objects.filter(page_step=self.page_step).order_by('step_sort'))
        self.assertEqual([d.ope_key for d in details], ['goto', 'click', 'fill', 'press', 'assert_visible'])
        self.assertEqual([d.step_sort for d in details], [0, 1, 2, 3, 4])
        click_step = details[1]
        self.assertEqual(click_step.step_type, 0)
        self.assertEqual(click_step.element.locator_type, 'id')
        self.assertEqual(details[2].ope_value, {'value': 'admin'})
        self.assertEqual(details[3].ope_value, {'key': 'Enter'})
        assert_step = details[4]
        self.assertEqual(assert_step.step_type, 1)

    def test_apply_reuses_elements_by_locator(self):
        apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user, actions=self._actions())
        stats = apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user, actions=self._actions())
        # 第二次全部复用已有元素：不新建元素，步骤继续追加
        self.assertEqual(stats['elements_created'], 0)
        self.assertEqual(stats['elements_updated'], 4)
        self.assertEqual(stats['steps_created'], 5)
        self.assertEqual(UiElement.objects.filter(page=self.page).count(), 4)
        self.assertEqual(UiPageStepsDetailed.objects.filter(page_step=self.page_step).count(), 10)

    def test_apply_appends_after_existing_steps(self):
        UiPageStepsDetailed.objects.create(
            page_step=self.page_step, step_type=0, ope_key='click',
            element=None, step_sort=2,  # 已有 3 条（0,1,2），新步骤应从 3 开始
        )
        UiPageStepsDetailed.objects.create(
            page_step=self.page_step, step_type=0, ope_key='click', element=None, step_sort=0,
        )
        UiPageStepsDetailed.objects.create(
            page_step=self.page_step, step_type=0, ope_key='click', element=None, step_sort=1,
        )
        apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user, actions=self._actions())
        details = list(UiPageStepsDetailed.objects.filter(page_step=self.page_step).order_by('step_sort'))
        self.assertEqual(details[0].step_sort, 0)
        self.assertEqual(details[-1].step_sort, 7)  # 5 条新步骤从 3 开始：3..7

    def _selector_with_backups(self):
        # 录制端候选链：主定位 + 两个同 xpath 备用定位
        return {
            'locator_type': 'xpath',
            'locator_value': '//button[normalize-space()="登录"]',
            'name': '登录按钮',
            'locator_type_2': 'xpath',
            'locator_value_2': '//button[@id="login-btn"]',
            'locator_type_3': 'xpath',
            'locator_value_3': '/html/body/div[1]/button[1]',
        }

    def test_apply_persists_backup_locators(self):
        stats = apply_recorded_actions(
            page=self.page, page_step=self.page_step, user=self.user,
            actions=[{'type': 'click', 'selector': self._selector_with_backups()}],
        )
        self.assertEqual(stats['elements_created'], 1)
        element = UiElement.objects.get(page=self.page)
        self.assertEqual(element.locator_type, 'xpath')
        self.assertEqual(element.locator_value, '//button[normalize-space()="登录"]')
        self.assertEqual(element.locator_type_2, 'xpath')
        self.assertEqual(element.locator_value_2, '//button[@id="login-btn"]')
        self.assertEqual(element.locator_type_3, 'xpath')
        self.assertEqual(element.locator_value_3, '/html/body/div[1]/button[1]')

    def test_apply_reuse_fills_missing_backup_locators(self):
        # 老数据：仅主定位，无备用
        existing = UiElement.objects.create(
            page=self.page, name='登录按钮', creator=self.user,
            locator_type='xpath', locator_value='//button[normalize-space()="登录"]',
        )
        apply_recorded_actions(
            page=self.page, page_step=self.page_step, user=self.user,
            actions=[{'type': 'click', 'selector': self._selector_with_backups()}],
        )
        existing.refresh_from_db()
        self.assertEqual(existing.locator_type_2, 'xpath')
        self.assertEqual(existing.locator_value_2, '//button[@id="login-btn"]')
        self.assertEqual(existing.locator_type_3, 'xpath')
        self.assertEqual(existing.locator_value_3, '/html/body/div[1]/button[1]')

    def test_apply_persists_iframe_locator(self):
        sel = {
            'locator_type': 'xpath',
            'locator_value': '//input[@placeholder="邮箱账号或手机号码"]',
            'name': '邮箱账号',
            'is_iframe': True,
            'iframe_locator': '//div[@id="loginDiv"]/iframe',
        }
        apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user,
                               actions=[{'seq': 1, 'type': 'click', 'selector': sel}])
        element = UiElement.objects.get(page=self.page)
        self.assertTrue(element.is_iframe)
        self.assertEqual(element.iframe_locator, '//div[@id="loginDiv"]/iframe')

    def test_apply_reuse_fills_missing_iframe_flag(self):
        existing = UiElement.objects.create(
            page=self.page, name='邮箱账号', creator=self.user,
            locator_type='xpath', locator_value='//input[@placeholder="邮箱账号或手机号码"]',
        )
        sel = {
            'locator_type': 'xpath',
            'locator_value': '//input[@placeholder="邮箱账号或手机号码"]',
            'name': '邮箱账号',
            'is_iframe': True,
            'iframe_locator': '//div[@id="loginDiv"]/iframe',
        }
        apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user,
                               actions=[{'seq': 1, 'type': 'click', 'selector': sel}])
        existing.refresh_from_db()
        self.assertTrue(existing.is_iframe)
        self.assertEqual(existing.iframe_locator, '//div[@id="loginDiv"]/iframe')

    def test_apply_non_iframe_keeps_flag_off(self):
        sel = {'locator_type': 'xpath', 'locator_value': '//button[1]'}
        apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user,
                               actions=[{'seq': 1, 'type': 'click', 'selector': sel}])
        element = UiElement.objects.get(page=self.page)
        self.assertFalse(element.is_iframe)
        self.assertIsNone(element.iframe_locator)
    def test_serialize_page_step_for_recorder_includes_iframe(self):
        from ui_automation.views import _serialize_page_step_for_recorder
        el = UiElement.objects.create(
            page=self.page, name='163邮箱', creator=self.user,
            locator_type='xpath', locator_value='//input[@name="email"]',
            is_iframe=True, iframe_locator='//div[@id="loginDiv"]/iframe',
        )
        UiPageStepsDetailed.objects.create(
            page_step=self.page_step, step_type=0, ope_key='click',
            element=el, step_sort=0,
        )
        steps = _serialize_page_step_for_recorder(self.page_step)
        self.assertEqual(steps[0]['element']['is_iframe'], True)
        self.assertEqual(steps[0]['element']['iframe_locator'], '//div[@id="loginDiv"]/iframe')

    def test_serialize_page_step_for_recorder_plain_element(self):
        from ui_automation.views import _serialize_page_step_for_recorder
        el = UiElement.objects.create(
            page=self.page, name='普通', creator=self.user,
            locator_type='xpath', locator_value='//button[1]',
        )
        UiPageStepsDetailed.objects.create(
            page_step=self.page_step, step_type=0, ope_key='click',
            element=el, step_sort=0,
        )
        steps = _serialize_page_step_for_recorder(self.page_step)
        self.assertNotIn('is_iframe', steps[0]['element'])

    def test_apply_reuse_keeps_manual_backup_locators(self):
        # 已有备用定位时不得覆盖（手工维护优先）
        existing = UiElement.objects.create(
            page=self.page, name='登录按钮', creator=self.user,
            locator_type='xpath', locator_value='//button[normalize-space()="登录"]',
            locator_type_2='text', locator_value_2='登录',
        )
        apply_recorded_actions(
            page=self.page, page_step=self.page_step, user=self.user,
            actions=[{'type': 'click', 'selector': self._selector_with_backups()}],
        )
        existing.refresh_from_db()
        self.assertEqual(existing.locator_type_2, 'text')
        self.assertEqual(existing.locator_value_2, '登录')
        self.assertEqual(existing.locator_type_3, 'xpath')
        self.assertEqual(existing.locator_value_3, '/html/body/div[1]/button[1]')


class RecorderApiValidationTests(TestCase):
    """REST 层参数校验（不触发浏览器启动）。"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(username='recorder-api', password='secret')
        self.client.force_authenticate(user=self.user)
        self.project = Project.objects.create(name='Recorder API Project')
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.module = UiModule.objects.create(project=self.project, name='M', creator=self.user)
        self.page = UiPage.objects.create(
            project=self.project, module=self.module, name='Page', url='/login', creator=self.user,
        )
        self.page_step = UiPageSteps.objects.create(
            project=self.project, page=self.page, module=self.module, name='Steps', creator=self.user,
        )
        self.env = UiEnvironmentConfig.objects.create(
            project=self.project, name='Prod', base_url='https://example.com', creator=self.user,
        )
        self.base = '/api/ui-automation/recorder-sessions/'

    def test_missing_env_returns_400(self):
        resp = self.client.post(self.base, {
            'page_id': self.page.id,
            'page_step_id': self.page_step.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_page_not_in_project_returns_400(self):
        other_project = Project.objects.create(name='Other')
        other_module = UiModule.objects.create(project=other_project, name='X', creator=self.user)
        other_page = UiPage.objects.create(
            project=other_project, module=other_module, name='Other Page', url='/x', creator=self.user,
        )
        resp = self.client.post(self.base, {
            'env_config_id': self.env.id,
            'page_id': other_page.id,
            'page_step_id': self.page_step.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_page_step_not_matching_page_returns_400(self):
        other_page = UiPage.objects.create(
            project=self.project, module=self.module, name='Other Page', url='/x', creator=self.user,
        )
        other_step = UiPageSteps.objects.create(
            project=self.project, page=other_page, module=self.module, name='Other Steps', creator=self.user,
        )
        resp = self.client.post(self.base, {
            'env_config_id': self.env.id,
            'page_id': self.page.id,
            'page_step_id': other_step.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_unknown_session_returns_404(self):
        resp = self.client.post(f'{self.base}deadbeef/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_finish_unknown_session_returns_404(self):
        resp = self.client.post(f'{self.base}deadbeef/finish/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

class RecorderCoalesceTests(TestCase):
    """入库兜底：连续同元素 fill 合并为一条。"""

    def setUp(self):
        self.user = User.objects.create_superuser(username='coalesce', password='secret')
        self.project = Project.objects.create(name='Coalesce Project')
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.module = UiModule.objects.create(project=self.project, name='M', creator=self.user)
        self.page = UiPage.objects.create(
            project=self.project, module=self.module, name='Page', url='/login', creator=self.user,
        )
        self.page_step = UiPageSteps.objects.create(
            project=self.project, page=self.page, module=self.module, name='Steps', creator=self.user,
        )

    def test_consecutive_fills_coalesced(self):
        sel = {'locator_type': 'xpath', 'locator_value': '//input[@placeholder="账号"]', 'name': '账号'}
        actions = [
            {'seq': 1, 'type': 'click', 'selector': sel},
            {'seq': 2, 'type': 'fill', 'selector': sel, 'value': 'a'},
            {'seq': 3, 'type': 'fill', 'selector': sel, 'value': 'ad'},
            {'seq': 4, 'type': 'fill', 'selector': sel, 'value': 'adm'},
            {'seq': 5, 'type': 'fill', 'selector': sel, 'value': 'admin'},
            {'seq': 6, 'type': 'press', 'selector': sel, 'key': 'Enter'},
        ]
        stats = apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user, actions=actions)
        from ui_automation.models import UiPageStepsDetailed
        details = list(UiPageStepsDetailed.objects.filter(page_step=self.page_step).order_by('step_sort'))
        fill_steps = [d for d in details if d.ope_key == 'fill']
        self.assertEqual(len(fill_steps), 1)
        self.assertEqual(fill_steps[0].ope_value, {'value': 'admin'})
        self.assertEqual(stats['steps_created'], 3)  # click + fill + press

    def test_different_element_fills_not_coalesced(self):
        sel_a = {'locator_type': 'xpath', 'locator_value': '//input[@placeholder="A"]', 'name': 'A'}
        sel_b = {'locator_type': 'xpath', 'locator_value': '//input[@placeholder="B"]', 'name': 'B'}
        actions = [
            {'seq': 1, 'type': 'fill', 'selector': sel_a, 'value': '1'},
            {'seq': 2, 'type': 'fill', 'selector': sel_b, 'value': '2'},
        ]
        apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user, actions=actions)
        from ui_automation.models import UiPageStepsDetailed
        self.assertEqual(
            UiPageStepsDetailed.objects.filter(page_step=self.page_step, ope_key='fill').count(),
            2,
        )


class RecorderWaitApplyTests(TestCase):
    """等待动作入库：无元素 wait 步骤，timeout 毫秒入 ope_value。"""

    def setUp(self):
        self.user = User.objects.create_superuser(username='wait-rec', password='secret')
        self.project = Project.objects.create(name='Wait Project')
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.module = UiModule.objects.create(project=self.project, name='M', creator=self.user)
        self.page = UiPage.objects.create(
            project=self.project, module=self.module, name='Page', url='/login', creator=self.user,
        )
        self.page_step = UiPageSteps.objects.create(
            project=self.project, page=self.page, module=self.module, name='Steps', creator=self.user,
        )

    def test_wait_action_apply(self):
        sel = {'locator_type': 'text', 'locator_value': '提交', 'name': '提交'}
        actions = [
            {'seq': 1, 'type': 'click', 'selector': sel},
            {'seq': 2, 'type': 'wait', 'seconds': 3},
            {'seq': 3, 'type': 'assert', 'mode': 'visible', 'selector': sel},
        ]
        apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user, actions=actions)
        from ui_automation.models import UiPageStepsDetailed
        details = list(UiPageStepsDetailed.objects.filter(page_step=self.page_step).order_by('step_sort'))
        wait_step = details[1]
        self.assertEqual(wait_step.ope_key, 'wait')
        self.assertEqual(wait_step.ope_value, {'timeout': 3})
        self.assertIsNone(wait_step.element)


class BatchDeleteApiTests(TestCase):
    """元素 / 步骤明细批量删除接口。"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(username='batch-del', password='secret')
        self.client.force_authenticate(user=self.user)
        self.project = Project.objects.create(name='Batch Project')
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.module = UiModule.objects.create(project=self.project, name='M', creator=self.user)
        self.page = UiPage.objects.create(
            project=self.project, module=self.module, name='Page', url='/login', creator=self.user,
        )
        self.page_step = UiPageSteps.objects.create(
            project=self.project, page=self.page, module=self.module, name='Steps', creator=self.user,
        )

    def test_element_batch_delete_blocked_by_usage(self):
        el = UiElement.objects.create(page=self.page, name='E1', locator_type='xpath',
                                      locator_value='//button[1]', creator=self.user)
        UiPageStepsDetailed.objects.create(page_step=self.page_step, element=el,
                                           ope_key='click', step_sort=0)
        resp = self.client.post('/api/ui-automation/elements/batch-delete/',
                                {'ids': [el.id]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('引用', resp.data['error'])

    def test_element_batch_delete_ok(self):
        el = UiElement.objects.create(page=self.page, name='E1', locator_type='xpath',
                                      locator_value='//button[1]', creator=self.user)
        resp = self.client.post('/api/ui-automation/elements/batch-delete/',
                                {'ids': [el.id]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['deleted'], 1)
        self.assertFalse(UiElement.objects.filter(id=el.id).exists())

    def test_step_detail_batch_delete(self):
        d1 = UiPageStepsDetailed.objects.create(page_step=self.page_step, ope_key='click', step_sort=0)
        d2 = UiPageStepsDetailed.objects.create(page_step=self.page_step, ope_key='fill', step_sort=1)
        resp = self.client.post('/api/ui-automation/page-steps-detailed/batch-delete/',
                                {'ids': [d1.id, d2.id]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['deleted'], 2)
        self.assertEqual(UiPageStepsDetailed.objects.filter(page_step=self.page_step).count(), 0)


class ElementNamingTests(TestCase):
    """元素命名：录制端语义名优先 + 同页面唯一去重。"""

    def setUp(self):
        self.user = User.objects.create_superuser(username='naming', password='secret')
        self.project = Project.objects.create(name='Naming Project')
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.module = UiModule.objects.create(project=self.project, name='M', creator=self.user)
        self.page = UiPage.objects.create(
            project=self.project, module=self.module, name='Page', url='/login', creator=self.user,
        )
        self.page_step = UiPageSteps.objects.create(
            project=self.project, page=self.page, module=self.module, name='Steps', creator=self.user,
        )

    def test_semantic_name_from_recorder(self):
        sel = {'locator_type': 'xpath', 'locator_value': '//input[1]', 'name': '用户名输入框'}
        apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user,
                               actions=[{'seq': 1, 'type': 'fill', 'selector': sel, 'value': 'x'}])
        el = UiElement.objects.get(page=self.page)
        self.assertEqual(el.name, '用户名输入框')

    def test_same_name_elements_get_suffix(self):
        sel_a = {'locator_type': 'xpath', 'locator_value': '//button[1]', 'name': '提交按钮'}
        sel_b = {'locator_type': 'xpath', 'locator_value': '//button[2]', 'name': '提交按钮'}
        apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user,
                               actions=[{'seq': 1, 'type': 'click', 'selector': sel_a},
                                        {'seq': 2, 'type': 'click', 'selector': sel_b}])
        names = sorted(UiElement.objects.filter(page=self.page).values_list('name', flat=True))
        self.assertEqual(names, ['提交按钮', '提交按钮 2'])

    def test_fallback_name_without_semantic(self):
        sel = {'locator_type': 'xpath', 'locator_value': '//div[3]'}
        apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user,
                               actions=[{'seq': 1, 'type': 'click', 'selector': sel}])
        el = UiElement.objects.get(page=self.page)
        self.assertEqual(el.name, '点击-//div[3]')


class ExecFrameAndBatchTests(TestCase):
    """执行画面帧转发 + 批量强制无头。"""

    def setUp(self):
        SocketUserManager._web_users.clear()
        self.addCleanup(SocketUserManager._web_users.clear)

    def test_exec_frame_forwarded_to_initiator(self):
        captured = {}

        class FakeWebUser:
            async def send_json(self, data):
                captured['data'] = data

        SocketUserManager._web_users['alice'] = FakeWebUser()
        consumer = UiAutomationConsumer()

        async def run():
            await consumer.handle_exec_frame(
                {'case_id': 42, 'page_step_id': 0, 'frame': {'w': 1280, 'h': 720, 'data': 'AAAA'}},
                'alice',
            )

        asyncio.run(run())
        msg = captured['data']
        self.assertEqual(msg.data.func_name, 'u_exec_frame')
        self.assertEqual(msg.data.func_args['case_id'], 42)
        self.assertEqual(msg.data.func_args['frame'], {'w': 1280, 'h': 720, 'data': 'AAAA'})
        self.assertEqual(msg.is_notice, NoticeType.WEB)
        self.assertEqual(msg.user, 'alice')

    def test_exec_frame_dropped_when_initiator_offline(self):
        consumer = UiAutomationConsumer()

        async def run():
            # 发起人不在线：不抛错、不落库（无 DB 交互）、无消息
            await consumer.handle_exec_frame({'case_id': 1, 'frame': {'data': 'BBBB'}}, 'ghost')

        asyncio.run(run())
        self.assertEqual(SocketUserManager._web_users, {})

    def test_force_batch_headless(self):
        args = {
            'case_ids': [1, 2],
            'run_options': {'browser': 'chromium', 'headless': False},
            'effective_runtime': {'browser': 'chromium', 'headless': False, 'actuator_id': 9},
        }
        UiAutomationConsumer._force_batch_headless(args)
        self.assertIs(args['run_options']['headless'], True)
        self.assertIs(args['effective_runtime']['headless'], True)

    def test_force_batch_headless_ignores_missing_keys(self):
        args = {'case_ids': [1], 'run_options': None}
        UiAutomationConsumer._force_batch_headless(args)
        self.assertIsNone(args['run_options'])


class RecorderLoginInjectTests(TestCase):
    """录制器注入已保存登录态（勾选开关 → storageState 注入 start 参数）。"""

    def setUp(self):
        from unittest.mock import AsyncMock
        from types import SimpleNamespace
        self._AsyncMock = AsyncMock
        self._SimpleNamespace = SimpleNamespace
        self.user = User.objects.create_superuser(username='rec-login', password='secret')
        self.project = Project.objects.create(name='Recorder Login Project')
        self.module = UiModule.objects.create(project=self.project, name='M', creator=self.user)
        self.page = UiPage.objects.create(
            project=self.project, module=self.module, name='Page', url='/login', creator=self.user,
        )
        self.env = UiEnvironmentConfig.objects.create(
            project=self.project, name='测试环境', base_url='http://e.local', creator=self.user,
        )
        self._meta = None

    def _start(self, *, bound_auth_id):
        from unittest.mock import patch
        from ui_automation.views import _start_recorder_session
        from ui_automation.recorder.session_manager import RecorderSessionMeta
        from ui_automation.models import UiEnvironmentConfig

        env = UiEnvironmentConfig.objects.create(
            project=self.project, name='环境A', base_url='http://env.local', creator=self.user,
        )
        # 环境存在启用中的登录态：新语义下未显式绑定也绝不注入
        UiAuthState.objects.create(
            env_config=env, is_active=True, name='环境生效登录态',
            state_json={'cookies': [{'name': 'S', 'value': 'x', 'domain': '.env.local', 'path': '/'}]},
            creator=self.user,
        )
        meta = RecorderSessionMeta(
            user_id='u1', project_id=self.project.id, page_id=self.page.id, page_step_id=1,
            create_elements=True, create_steps=True, base_url='http://env.local',
            viewport={'width': 1400, 'height': 900}, kind='record', env_config_id=env.id,
            auth_state_id=bound_auth_id,
        )
        from unittest.mock import Mock
        session = Mock()
        session.start = Mock(return_value=None)
        session.request = Mock(return_value={
            'ok': True, 'state': {'viewport': {'width': 1400, 'height': 900}},
        })
        with patch('ui_automation.recorder.session_manager.recorder_manager') as rm:
            rm.create_session.return_value = session
            _start_recorder_session(
                env_config=env, page=self.page, base_url='http://env.local',
                skill_dir='/tmp/x', request=self._SimpleNamespace(user=self._SimpleNamespace(username='u1')),
                meta=meta,
            )
        return session.request.call_args_list[0].args[1]

    def test_bound_auth_injected(self):
        from ui_automation.models import UiAuthState
        bound = UiAuthState.objects.create(
            env_config=self.env, name='绑定登录态',
            state_json={'cookies': [{'name': 'B', 'value': 'y'}]}, creator=self.user,
        )
        params = self._start(bound_auth_id=bound.id)
        self.assertEqual(params['storage_state']['cookies'][0]['name'], 'B')

    def test_unbound_never_injected_even_with_active_state(self):
        # 环境有启用中的登录态，但选择框未绑定 → 无痕启动
        params = self._start(bound_auth_id=None)
        self.assertNotIn('storage_state', params)

    def test_invalid_bound_id_no_injection(self):
        params = self._start(bound_auth_id=999999)
        self.assertNotIn('storage_state', params)


class RecorderUploadApplyTests(TestCase):
    """上传动作入库：ope_key=upload + file_id，元素按选择器创建。"""

    def setUp(self):
        self.user = User.objects.create_superuser(username='up-rec', password='secret')
        self.project = Project.objects.create(name='Up Project')
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.module = UiModule.objects.create(project=self.project, name='M', creator=self.user)
        self.page = UiPage.objects.create(
            project=self.project, module=self.module, name='Page', url='/upload', creator=self.user,
        )
        self.page_step = UiPageSteps.objects.create(
            project=self.project, page=self.page, module=self.module, name='Steps', creator=self.user,
        )

    def test_upload_action_apply(self):
        sel = {'locator_type': 'xpath', 'locator_value': '//input[@type="file"]', 'name': '附件上传'}
        actions = [{'seq': 1, 'type': 'upload', 'selector': sel, 'file_id': 88, 'file_name': '报告.xlsx'}]
        stats = apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user, actions=actions)
        from ui_automation.models import UiPageStepsDetailed
        detail = UiPageStepsDetailed.objects.get(page_step=self.page_step)
        self.assertEqual(detail.ope_key, 'upload')
        self.assertEqual(detail.ope_value, {'file_id': 88, 'value': 'file_id:88', 'file_name': '报告.xlsx'})
        self.assertIsNotNone(detail.element)
        self.assertEqual(detail.element.locator_value, '//input[@type="file"]')
        self.assertEqual(stats['steps_created'], 1)

    def test_upload_missing_file_id_ok(self):
        sel = {'locator_type': 'xpath', 'locator_value': '//input[@type="file"]', 'name': '附件上传'}
        apply_recorded_actions(page=self.page, page_step=self.page_step, user=self.user,
                               actions=[{'seq': 1, 'type': 'upload', 'selector': sel}])
        from ui_automation.models import UiPageStepsDetailed
        detail = UiPageStepsDetailed.objects.get(page_step=self.page_step)
        self.assertEqual(detail.ope_value, {})


class RecorderBrowserExecTests(TestCase):
    """录制器浏览器（本地虚拟执行器）：步骤调试 / 单用例执行。"""

    def setUp(self):
        from asgiref.sync import async_to_sync
        self._run = async_to_sync
        self.user = User.objects.create_superuser(username='rec-exec', password='secret')
        self.project = Project.objects.create(name='Recorder Exec Project')
        ProjectMember.objects.create(project=self.project, user=self.user, role='admin')
        self.module = UiModule.objects.create(project=self.project, name='M', creator=self.user)
        self.page = UiPage.objects.create(
            project=self.project, module=self.module, name='Page', url='/login', creator=self.user,
        )
        self.page_step = UiPageSteps.objects.create(
            project=self.project, page=self.page, module=self.module, name='Steps', creator=self.user,
        )
        UiPageStepsDetailed.objects.create(
            page_step=self.page_step, step_type=0, ope_key='click', step_sort=0,
        )
        self.env = UiEnvironmentConfig.objects.create(
            project=self.project, name='环境', base_url='http://env.local', creator=self.user,
        )
        self.case = UiTestCase.objects.create(
            project=self.project, module=self.module, name='用例', creator=self.user,
        )
        from ui_automation.models import UiCaseStepsDetailed
        UiCaseStepsDetailed.objects.create(test_case=self.case, page_step=self.page_step, case_sort=0)

    def _consumer_env(self):
        from unittest.mock import patch
        from ui_automation.consumers import UiAutomationConsumer, SocketUserManager
        SocketUserManager._web_users.clear()
        self.addCleanup(SocketUserManager._web_users.clear)

        received = []

        class FakeWebUser:
            async def send_json(self, data):
                received.append(data)

        SocketUserManager._web_users['alice'] = FakeWebUser()

        class FakeSession:
            session_id = 'fake-sess-1'

            def __init__(self):
                self.requests = []

            def start(self, timeout=120):
                pass

            def request(self, method, params=None, timeout=None):
                if params is None:
                    params = {}
                self.requests.append((method, params))
                if method == 'start':
                    return {'ok': True, 'state': {'viewport': {'width': 1400, 'height': 900}}}
                if method == 'run_steps':
                    steps = params.get('steps', [])
                    return {'ok': True, 'state': {'executed': len(steps), 'failed': False}}
                return {'ok': True, 'state': {}}

        session = FakeSession()
        rm_patch = patch('ui_automation.recorder.session_manager.recorder_manager')
        rm = rm_patch.start()
        rm.create_session.return_value = session
        self.addCleanup(rm_patch.stop)
        skill_patch = patch('ui_automation.views._resolve_recorder_skill_dir', return_value='/tmp/skill')
        skill_patch.start()
        self.addCleanup(skill_patch.stop)

        consumer = UiAutomationConsumer()

        async def capture_send_json(data):
            received.append(data)

        consumer.send_json = capture_send_json

        class _FakeLayer:
            def __init__(self):
                self.sent = []

            async def group_send(self, group, data):
                self.sent.append(data)

        layer = _FakeLayer()
        consumer.channel_layer = layer
        return consumer, session, received, layer

    def test_page_steps_exec_via_recorder(self):
        consumer, session, received, _layer = self._consumer_env()
        async def scenario():
            await consumer.handle_execute_page_steps({'page_step_id': self.page_step.id, 'env_config_id': self.env.id, 'actuator_id': 'recorder-browser'}, 'alice')
            if consumer._recorder_exec_task is not None:
                await asyncio.wait_for(consumer._recorder_exec_task, timeout=15)
        self._run(scenario)()
        # 执行已改为独立任务：等待其完成（结果回传后再断言）
        if consumer._recorder_exec_task is not None:
            self._run(lambda: consumer._recorder_exec_task)()
        # run_steps 被调用且首条为 goto
        run_calls = [p for m, p in session.requests if m == 'run_steps']
        self.assertEqual(len(run_calls), 1)
        self.assertEqual(run_calls[0]['steps'][0]['ope_key'], 'goto')
        # 回执生效运行时（headless=false）→ 前端据此打开执行画布
        eff = [m for m in received if m.data.func_name == 'effective_runtime']
        self.assertEqual(len(eff), 1)
        self.assertIs(eff[0].data.func_args['headless'], False)
        # 结果回传（goto 导航步骤不计数：库里 1 条明细 + 1 条 goto 拼接 → 统计 1）
        msg = received[-1]
        self.assertEqual(msg.data.func_name, 'u_page_step_result')
        self.assertEqual(msg.data.func_args['status'], 'success')
        self.assertEqual(msg.data.func_args['total_steps'], 1)
        # 步骤状态已更新
        self.page_step.refresh_from_db()
        self.assertEqual(self.page_step.status, 2)

    def test_case_exec_via_recorder_saves_record(self):
        from ui_automation.models import UiExecutionRecord
        consumer, session, received, layer = self._consumer_env()
        async def scenario():
            await consumer.handle_execute_test_case({
                'case_id': self.case.id,
                'env_config_id': self.env.id,
                'actuator_id': 'recorder-browser',
                'execution_request_id': 'hybrid-request-1',
            }, 'alice')
            if consumer._recorder_exec_task is not None:
                await asyncio.wait_for(consumer._recorder_exec_task, timeout=15)
        self._run(scenario)()
        acknowledgements = [m for m in received if m.data and m.data.func_name == 'u_test_case_ack']
        self.assertEqual(len(acknowledgements), 1)
        self.assertEqual(acknowledgements[0].data.func_args['execution_request_id'], 'hybrid-request-1')
        # 用例结果广播（与执行器 handle_case_result 同路径）+ 执行记录落库
        # （goto 导航步骤不计数：用例含 1 组 1 条明细 → 统计 1）
        case_broadcasts = [d for d in layer.sent if d.get('data', {}).get('func_name') == 'u_case_result']
        self.assertEqual(len(case_broadcasts), 1)
        self.assertEqual(case_broadcasts[0]['data']['args']['status'], 'success')
        self.assertEqual(case_broadcasts[0]['data']['args']['execution_request_id'], 'hybrid-request-1')
        self.assertEqual(case_broadcasts[0]['data']['args']['total_steps'], 1)
        self.assertEqual(case_broadcasts[0]['data']['args']['passed_steps'], 1)
        record = UiExecutionRecord.objects.get(test_case=self.case)
        self.assertEqual(record.status, 2)
        self.assertEqual(record.executor_name if hasattr(record, 'executor_name') else 'recorder-browser', 'recorder-browser')

    def test_case_auth_upward_inherit_skips_context_switch(self):
        """未绑定步骤"向上匹配"最近绑定的登录态：绑定 A/无/B/无 的用例只在
        第 3 步切换一次上下文（注入 B），第 2/4 步沿用不清空（与执行器同语义）。"""
        from ui_automation.models import UiCaseStepsDetailed, UiAuthState, UiTestCase
        env_a = self.env
        auth_a = UiAuthState.objects.create(
            env_config=env_a, name='登录态A', state_json={'cookies': [{'name': 'A'}]}, creator=self.user,
        )
        auth_b = UiAuthState.objects.create(
            env_config=env_a, name='登录态B', state_json={'cookies': [{'name': 'B'}]}, creator=self.user,
        )
        # 独立用例（不复用 setUp 的 self.case）：4 个页面步骤 1绑A、2未绑、3绑B、4未绑
        case = UiTestCase.objects.create(
            project=self.project, module=self.module, name='双账号用例', creator=self.user,
        )
        for i, auth in enumerate([auth_a, None, auth_b, None]):
            ps = UiPageSteps.objects.create(
                project=self.project, page=self.page, module=self.module,
                name=f'向上匹配步骤{i + 1}', creator=self.user, auth_state=auth,
            )
            UiPageStepsDetailed.objects.create(
                page_step=ps, step_type=0, ope_key='click', step_sort=0,
            )
            UiCaseStepsDetailed.objects.create(test_case=case, page_step=ps, case_sort=i)

        consumer, session, received, layer = self._consumer_env()

        async def scenario():
            await consumer.handle_execute_test_case(
                {'case_id': case.id, 'env_config_id': self.env.id, 'actuator_id': 'recorder-browser'},
                'alice',
            )
            if consumer._recorder_exec_task is not None:
                await asyncio.wait_for(consumer._recorder_exec_task, timeout=15)

        self._run(scenario)()
        switches = [(p.get('storage_state') or {}).get('cookies') for m, p in session.requests if m == 'switch_context']
        # 仅第 3 步触发一次切换，且注入的是登录态 B
        self.assertEqual(len(switches), 1)
        self.assertEqual(switches[0], [{'name': 'B'}])
        # 4 组全部执行成功
        run_calls = [p for m, p in session.requests if m == 'run_steps']
        self.assertEqual(len(run_calls), 4)
        broadcasts = [d for d in layer.sent if d.get('data', {}).get('func_name') == 'u_case_result']
        self.assertEqual(broadcasts[0]['data']['args']['status'], 'success')

    def test_case_all_unbound_never_switches_context(self):
        """全部步骤未绑定登录态：无痕启动后全程不切换上下文。"""
        from ui_automation.models import UiCaseStepsDetailed
        consumer, session, received, layer = self._consumer_env()

        async def scenario():
            await consumer.handle_execute_test_case(
                {'case_id': self.case.id, 'env_config_id': self.env.id, 'actuator_id': 'recorder-browser'},
                'alice',
            )
            if consumer._recorder_exec_task is not None:
                await asyncio.wait_for(consumer._recorder_exec_task, timeout=15)

        self._run(scenario)()
        self.assertEqual([m for m, _p in session.requests if m == 'switch_context'], [])
        broadcasts = [d for d in layer.sent if d.get('data', {}).get('func_name') == 'u_case_result']
        self.assertEqual(broadcasts[0]['data']['args']['status'], 'success')


    def test_page_steps_recorder_error_reports_failed(self):
        consumer, session, received, _layer = self._consumer_env()
        async def scenario():
            await consumer.handle_execute_page_steps({'page_step_id': 999999, 'env_config_id': self.env.id, 'actuator_id': 'recorder-browser'}, 'alice')
            if consumer._recorder_exec_task is not None:
                await asyncio.wait_for(consumer._recorder_exec_task, timeout=15)
        self._run(scenario)()
        # 执行已改为独立任务：等待其完成（结果回传后再断言）
        if consumer._recorder_exec_task is not None:
            self._run(lambda: consumer._recorder_exec_task)()
        msg = received[-1]
        self.assertEqual(msg.data.func_name, 'u_page_step_result')
        self.assertEqual(msg.data.func_args['status'], 'failed')

    def test_close_canvas_interrupts_recorder_exec(self):
        import threading
        gate = threading.Event()

        class BlockingSession:
            session_id = 'fake-sess-stop'

            def start(self, timeout=120):
                pass

            def request(self, method, params=None, timeout=None):
                if method == 'start':
                    return {'ok': True, 'state': {'viewport': {'width': 1400, 'height': 900}}}
                if method == 'run_steps':
                    gate.wait(2)  # 模拟长执行：run_steps 挂起，等待中断
                    return {'ok': True, 'state': {'executed': 1, 'failed': False}}
                return {'ok': True, 'state': {}}

        session = BlockingSession()
        from unittest.mock import patch
        rm_patch = patch('ui_automation.recorder.session_manager.recorder_manager')
        rm = rm_patch.start()
        rm.create_session.return_value = session
        self.addCleanup(rm_patch.stop)
        skill_patch = patch('ui_automation.views._resolve_recorder_skill_dir', return_value='/tmp/skill')
        skill_patch.start()
        self.addCleanup(skill_patch.stop)

        from ui_automation.consumers import UiAutomationConsumer, SocketUserManager
        SocketUserManager._web_users.clear()
        self.addCleanup(SocketUserManager._web_users.clear)
        received = []

        class FakeWebUser:
            async def send_json(self, data):
                received.append(data)

        SocketUserManager._web_users['alice'] = FakeWebUser()
        consumer = UiAutomationConsumer()

        async def _noop_send(**kwargs):
            pass

        consumer.send = _noop_send  # 单测桩：stop 回执走 send_json → send

        async def scenario():
            task = asyncio.ensure_future(consumer.handle_execute_page_steps(
                {'page_step_id': self.page_step.id, 'env_config_id': self.env.id,
                 'actuator_id': 'recorder-browser'},
                'alice',
            ))
            await asyncio.sleep(0.05)
            # 前端关闭执行画布 → u_stop_execution
            await consumer.handle_stop_execution({}, 'alice')
            if consumer._recorder_exec_task is not None:
                await asyncio.wait_for(consumer._recorder_exec_task, timeout=3)
            # 中断后不再产生新的执行结果消息
            await asyncio.sleep(0.1)

        # 用 async_to_sync 驱动（自动管理事件循环与 DB 连接，避免测试库残留）
        self._run(scenario)()
        # 中断结果按 failed 回传（"执行已中断"）
        self.assertTrue(received)
        msg = received[-1]
        self.assertEqual(msg.data.func_name, 'u_page_step_result')
        self.assertEqual(msg.data.func_args['status'], 'failed')
        self.assertIn('中断', msg.data.func_args['message'])
        # 任务引用已清理
        self.assertIsNone(consumer._recorder_exec_task)
    def test_serialize_upload_step_resolves_local_path(self):
        from unittest.mock import patch
        from ui_automation.views import _serialize_page_step_for_recorder
        detail = UiPageStepsDetailed.objects.create(
            page_step=self.page_step, step_type=0, ope_key='upload',
            ope_value={'file_id': 9, 'file_name': 'a.txt'}, step_sort=0,
        )
        fake_file = {'path': '/shared/a.txt', 'name': 'a.txt', 'mime_type': 'text/plain'}
        with patch('file_management.services.validate_file_ids', return_value=[fake_file]), \
             patch('file_management.services.serialize_file_for_runtime', return_value=fake_file):
            steps = _serialize_page_step_for_recorder(self.page_step)
        upload = next(s for s in steps if s['ope_key'] == 'upload')
        self.assertEqual(upload['ope_value']['file_path'], '/shared/a.txt')
        self.assertEqual(upload['ope_value']['value'], '/shared/a.txt')

    def test_serialize_upload_step_without_file_id_keeps_raw(self):
        from ui_automation.views import _serialize_page_step_for_recorder
        step = UiPageStepsDetailed.objects.create(
            page_step=self.page_step, step_type=0, ope_key='upload',
            ope_value={'file_name': 'x.txt'}, step_sort=1,
        )
        steps = _serialize_page_step_for_recorder(self.page_step)
        upload_step = next(s for s in steps if s['ope_key'] == 'upload')
        self.assertNotIn('file_path', upload_step['ope_value'])

    def test_serialize_upload_step_without_file_id_keeps_raw(self):
        from ui_automation.views import _serialize_page_step_for_recorder
        step = UiPageStepsDetailed.objects.create(
            page_step=self.page_step, step_type=0, ope_key='upload',
            ope_value={'file_name': 'x.txt'}, step_sort=1,
        )
        steps = _serialize_page_step_for_recorder(self.page_step)
        upload_step = next(s for s in steps if s['ope_key'] == 'upload')
        self.assertNotIn('file_path', upload_step['ope_value'])


class PageStepsListSerializerAuthStateTests(TestCase):
    """列表序列化器携带 auth_state_id：详情抽屉按列表行数据直接回显绑定。"""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from projects.models import Project
        self.user = get_user_model().objects.create_superuser(username='list-auth', password='secret')
        self.project = Project.objects.create(name='List Auth Project')
        self.module = UiModule.objects.create(project=self.project, name='M', creator=self.user)
        self.page = UiPage.objects.create(
            project=self.project, module=self.module, name='Page', url='/login', creator=self.user,
        )
        self.env = UiEnvironmentConfig.objects.create(
            project=self.project, name='Env', base_url='http://e.local', creator=self.user,
        )
        self.auth = UiAuthState.objects.create(
            env_config=self.env, name='录制登录态', state_json={'cookies': []}, creator=self.user,
        )

    def test_list_serializer_includes_auth_state_id(self):
        from ui_automation.serializers import UiPageStepsListSerializer
        bound = UiPageSteps.objects.create(
            project=self.project, page=self.page, module=self.module,
            name='已绑定', creator=self.user, auth_state=self.auth,
        )
        unbound = UiPageSteps.objects.create(
            project=self.project, page=self.page, module=self.module,
            name='未绑定', creator=self.user,
        )
        bound_data = UiPageStepsListSerializer(bound).data
        unbound_data = UiPageStepsListSerializer(unbound).data
        self.assertEqual(bound_data['auth_state_id'], self.auth.id)
        self.assertIsNone(unbound_data['auth_state_id'])
