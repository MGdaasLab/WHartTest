"""录制器后端单测：动作解析入库 + 会话管理 + REST 校验。"""

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
from ui_automation.models import (
    UiElement, UiModule, UiPage, UiPageSteps, UiPageStepsDetailed, UiEnvironmentConfig,
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