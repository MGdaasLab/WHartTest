#!/usr/bin/env python
"""HTTPS 客户端证书支持的单元测试。

覆盖范围（仅单元测试，不做真实证书握手 —— 见文件末尾「已知缺口」）：
1. client_cert 纯函数：origin 归一化、路径解析、校验、camelCase dict 构造
2. PlaywrightExecutor._build_browser_context_options 的 ignore_https_errors 三态矩阵
3. 任务 origin 推导、证书配置幂等性、口令不泄漏
4. Config.load_from_toml / load_from_env（含三态解析与口令出环境）
5. consumer 的平台下发通道：字段白名单、日志脱敏、config.toml 往返

独立运行：python test_client_cert.py
"""

import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import client_cert
from client_cert import (
    build_client_certificates,
    normalize_origin,
    parse_origins,
    resolve_cert_path,
    validate_cert_files,
)
from executor import PageStepConfig, PlaywrightExecutor, TestCaseConfig
from main import Config, parse_tri_state_bool


# 一个明显的哨兵口令：任何日志里出现它都算泄漏
SECRET_PASSPHRASE = 'S3cr3t-Passphrase-Must-OnlyDanceInMemory'


def _write_file(path: Path, content: str = 'dummy') -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return path


class ActuatorTestCase(unittest.TestCase):
    """统一提供临时目录与执行器实例，避免污染工作区。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def make_executor(self, **overrides) -> PlaywrightExecutor:
        kwargs = {
            'user_data_dir': str(self.tmp / 'browser'),
            'screenshot_dir': str(self.tmp / 'shots'),
        }
        kwargs.update(overrides)
        return PlaywrightExecutor(**kwargs)

    def make_cert_files(self) -> dict:
        return {
            'pfx': _write_file(self.tmp / 'certs' / 'client.pfx', 'P12-BYTES'),
            'pfx2': _write_file(self.tmp / 'certs' / 'other.p12', 'P12-BYTES-2'),
            'cert': _write_file(self.tmp / 'certs' / 'client.crt', 'CERT-PEM'),
            'key': _write_file(self.tmp / 'certs' / 'client.key', 'KEY-PEM'),
        }


# ---------------------------------------------------------------------------
# 1. client_cert 纯函数
# ---------------------------------------------------------------------------

class NormalizeOriginTest(unittest.TestCase):
    def test_strips_path_query_and_fragment(self):
        self.assertEqual(
            normalize_origin('https://example.com/path?q=1#frag'),
            'https://example.com',
        )

    def test_keeps_non_default_port(self):
        self.assertEqual(
            normalize_origin('https://example.com:8443/x'),
            'https://example.com:8443',
        )

    def test_drops_explicit_default_port(self):
        # https://host:443 与 https://host 等价，统一成后者
        self.assertEqual(normalize_origin('https://example.com:443/x'), 'https://example.com')

    def test_rejects_non_https_and_schemeless(self):
        self.assertIsNone(normalize_origin('http://example.com'))
        self.assertIsNone(normalize_origin('example.com'))
        self.assertIsNone(normalize_origin('ftp://example.com'))

    def test_rejects_empty_and_none(self):
        self.assertIsNone(normalize_origin(''))
        self.assertIsNone(normalize_origin('   '))
        self.assertIsNone(normalize_origin(None))

    def test_drops_userinfo(self):
        self.assertEqual(
            normalize_origin('https://user:pw@example.com/x'),
            'https://example.com',
        )

    def test_keeps_ipv6_brackets(self):
        self.assertEqual(normalize_origin('https://[::1]:8443/x'), 'https://[::1]:8443')

    def test_is_idempotent(self):
        once = normalize_origin('https://example.com:8443/a?b=1')
        self.assertEqual(normalize_origin(once), once)


class ParseOriginsTest(unittest.TestCase):
    def test_splits_strips_and_dedupes_preserving_order(self):
        result = parse_origins('https://b.com, https://a.com ,https://b.com')
        self.assertEqual(result, ['https://b.com', 'https://a.com'])

    def test_merges_multiple_sources(self):
        result = parse_origins('https://a.com', 'https://b.com')
        self.assertEqual(result, ['https://a.com', 'https://b.com'])

    def test_drops_invalid_entries(self):
        result = parse_origins('http://plain.com, ,https://ok.com, notaurl')
        self.assertEqual(result, ['https://ok.com'])

    def test_empty_input_yields_empty_list(self):
        self.assertEqual(parse_origins(''), [])
        self.assertEqual(parse_origins(None), [])
        self.assertEqual(parse_origins(), [])


class ResolveCertPathTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_absolute_path_returned_as_is(self):
        absolute = self.tmp / 'certs' / 'client.pfx'
        self.assertEqual(resolve_cert_path(str(absolute), self.tmp), absolute)

    def test_relative_path_is_anchored_to_base_dir(self):
        self.assertEqual(
            resolve_cert_path('./certs/client.pfx', self.tmp),
            self.tmp / 'certs' / 'client.pfx',
        )
        # 不带 ./ 前缀同样成立
        self.assertEqual(
            resolve_cert_path('certs/client.pfx', self.tmp),
            self.tmp / 'certs' / 'client.pfx',
        )

    def test_dot_prefixed_path_is_not_treated_as_absolute(self):
        resolved = resolve_cert_path('./a.pfx', self.tmp)
        self.assertTrue(resolved.is_absolute())
        self.assertEqual(resolved.parent, self.tmp)

    def test_empty_returns_none(self):
        self.assertIsNone(resolve_cert_path(None, self.tmp))
        self.assertIsNone(resolve_cert_path('', self.tmp))
        self.assertIsNone(resolve_cert_path('   ', self.tmp))


class ValidateCertFilesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_files_produce_no_warning(self):
        pfx = _write_file(self.tmp / 'client.pfx')
        self.assertEqual(validate_cert_files(pfx_path=pfx), [])

    def test_unexpected_extension_warns_but_does_not_raise(self):
        weird = _write_file(self.tmp / 'client.txt')
        warnings = validate_cert_files(pfx_path=weird)
        self.assertEqual(len(warnings), 1)
        self.assertIn('.txt', warnings[0])

    def test_missing_file_warns(self):
        warnings = validate_cert_files(pfx_path=self.tmp / 'nope.pfx')
        self.assertEqual(len(warnings), 1)
        self.assertIn('不存在', warnings[0])

    def test_pem_extensions_accepted(self):
        cert = _write_file(self.tmp / 'client.crt')
        key = _write_file(self.tmp / 'client.key')
        self.assertEqual(validate_cert_files(cert_path=cert, key_path=key), [])


class BuildClientCertificatesTest(unittest.TestCase):
    """本组断言的核心是 camelCase 键名 —— 写错会被 Playwright 静默忽略。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.pfx = _write_file(self.tmp / 'client.pfx')
        self.cert = _write_file(self.tmp / 'client.crt')
        self.key = _write_file(self.tmp / 'client.key')

    def tearDown(self):
        self._tmp.cleanup()

    def test_pfx_entry_uses_camel_case_keys(self):
        entries = build_client_certificates(
            ['https://a.example.com'],
            pfx_path=self.pfx,
            passphrase='pw',
        )
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry['origin'], 'https://a.example.com')
        self.assertEqual(entry['pfxPath'], str(self.pfx))
        self.assertEqual(entry['passphrase'], 'pw')
        self.assertLessEqual(set(entry), {'origin', 'pfxPath', 'passphrase'})
        self.assertIn('pfxPath', entry)

    def test_snake_case_keys_are_absent(self):
        """防退化：Playwright 不做 snake_case -> camelCase 转换，写错会静默不生效。"""
        entry = build_client_certificates(['https://a.com'], pfx_path=self.pfx)[0]
        for wrong in ('pfx_path', 'cert_path', 'key_path', 'origin_url'):
            self.assertNotIn(wrong, entry)

    def test_pem_entry_uses_camel_case_keys(self):
        entry = build_client_certificates(
            ['https://a.com'],
            cert_path=self.cert,
            key_path=self.key,
        )[0]
        self.assertEqual(entry['certPath'], str(self.cert))
        self.assertEqual(entry['keyPath'], str(self.key))
        self.assertNotIn('cert', entry)
        self.assertNotIn('key', entry)

    def test_one_entry_per_origin(self):
        entries = build_client_certificates(
            ['https://a.com', 'https://b.com:8443', 'https://a.com'],
            pfx_path=self.pfx,
        )
        self.assertEqual(
            [e['origin'] for e in entries],
            ['https://a.com', 'https://b.com:8443'],
        )

    def test_origin_is_normalized(self):
        entry = build_client_certificates(
            ['https://a.com:443/login?x=1'],
            pfx_path=self.pfx,
        )[0]
        self.assertEqual(entry['origin'], 'https://a.com')

    def test_empty_passphrase_omits_key(self):
        """空口令必须不带 passphrase 键：Playwright 视空串为无效口令。"""
        for blank in (None, '', '   '):
            entry = build_client_certificates(
                ['https://a.com'], pfx_path=self.pfx, passphrase=blank
            )[0]
            self.assertNotIn('passphrase', entry, msg=f'passphrase={blank!r}')

    def test_passphrase_with_real_content_is_not_stripped(self):
        """含非空白字符的口令原样传递，避免破坏带前后空格的真实口令。"""
        entry = build_client_certificates(
            ['https://a.com'], pfx_path=self.pfx, passphrase='  p w  '
        )[0]
        self.assertEqual(entry['passphrase'], '  p w  ')

    def test_no_origins_returns_empty(self):
        self.assertEqual(build_client_certificates([], pfx_path=self.pfx), [])
        self.assertEqual(build_client_certificates([None, 'http://x.com'], pfx_path=self.pfx), [])

    def test_no_cert_material_returns_empty(self):
        self.assertEqual(build_client_certificates(['https://a.com']), [])
        # PEM 只给一半也不成立
        self.assertEqual(
            build_client_certificates(['https://a.com'], cert_path=self.cert),
            [],
        )

    def test_pfx_wins_over_pem(self):
        with self.assertLogs('actuator', level='WARNING'):
            entry = build_client_certificates(
                ['https://a.com'],
                pfx_path=self.pfx,
                cert_path=self.cert,
                key_path=self.key,
            )[0]
        self.assertEqual(entry['pfxPath'], str(self.pfx))
        self.assertNotIn('certPath', entry)


# ---------------------------------------------------------------------------
# 2. ignore_https_errors 三态矩阵
# ---------------------------------------------------------------------------

class ContextOptionsMatrixTest(ActuatorTestCase):
    def test_stealth_on_without_cert_matches_legacy_behaviour(self):
        executor = self.make_executor(stealth_enabled=True)
        options = executor._build_browser_context_options()
        self.assertIs(options['ignore_https_errors'], True)
        self.assertNotIn('client_certificates', options)

    def test_stealth_off_without_cert_omits_key(self):
        """回归保护：与改动前完全一致，stealth 关闭且无证书时不设置该键。"""
        executor = self.make_executor(stealth_enabled=False)
        options = executor._build_browser_context_options()
        self.assertNotIn('ignore_https_errors', options)

    def test_stealth_off_with_cert_enables_both(self):
        files = self.make_cert_files()
        executor = self.make_executor(stealth_enabled=False)
        executor.configure_client_cert(
            enabled=True,
            pfx_path=str(files['pfx']),
            origins='https://a.example.com',
        )
        executor.set_task_origins(['https://a.example.com'])

        options = executor._build_browser_context_options()
        self.assertIs(options['ignore_https_errors'], True)
        self.assertEqual(
            options['client_certificates'],
            [{'origin': 'https://a.example.com', 'pfxPath': str(files['pfx'])}],
        )

    def test_explicit_false_overrides_stealth_default(self):
        executor = self.make_executor(stealth_enabled=True, ignore_https_errors=False)
        options = executor._build_browser_context_options()
        self.assertNotIn('ignore_https_errors', options)

    def test_explicit_true_overrides_stealth_off(self):
        executor = self.make_executor(stealth_enabled=False, ignore_https_errors=True)
        options = executor._build_browser_context_options()
        self.assertIs(options['ignore_https_errors'], True)

    def test_explicit_auto_is_none(self):
        executor = self.make_executor(stealth_enabled=False, ignore_https_errors=None)
        options = executor._build_browser_context_options()
        self.assertNotIn('ignore_https_errors', options)

    def test_viewport_still_applied_when_stealth_off(self):
        """重构时把证书逻辑提到了早退分支之前，确认原视口行为未被破坏。"""
        executor = self.make_executor(stealth_enabled=False, viewport_width=1024, viewport_height=768)
        options = executor._build_browser_context_options()
        self.assertEqual(options['viewport'], {'width': 1024, 'height': 768})

    def test_stealth_on_chromium_uses_stealth_defaults(self):
        executor = self.make_executor(stealth_enabled=True, browser_type='chromium')
        options = executor._build_browser_context_options()
        # stealth 开启时使用伪装 UA；视口回退到节点默认视口（任务级未指定）
        self.assertIn('user_agent', options)
        self.assertEqual(options['viewport'], {'width': 1280, 'height': 720})

    def test_stealth_off_non_chromium_omits_user_agent(self):
        """非 chromium 且未配置 stealth_user_agent 时不注入 UA（与改动前一致）。"""
        executor = self.make_executor(stealth_enabled=True, browser_type='firefox')
        options = executor._build_browser_context_options()
        self.assertNotIn('user_agent', options)


class CertWarningDedupTest(ActuatorTestCase):
    def test_missing_origin_warning_logged_only_once(self):
        files = self.make_cert_files()
        executor = self.make_executor()
        executor.configure_client_cert(
            enabled=True,
            pfx_path=str(files['pfx']),
            origins=None,  # 不提供额外 origin
        )
        executor.set_task_origins([])

        with self.assertLogs('actuator', level='WARNING') as captured:
            first = executor._build_browser_context_options()
            second = executor._build_browser_context_options()

        self.assertNotIn('client_certificates', first)
        self.assertNotIn('client_certificates', second)

        matched = [r for r in captured.records if '未能推导出 https origin' in r.getMessage()]
        self.assertEqual(len(matched), 1, msg='告警应只出现一次，避免每个上下文都刷日志')

    def test_incomplete_material_warns(self):
        executor = self.make_executor()
        executor.configure_client_cert(enabled=True, origins='https://a.example.com')
        executor.set_task_origins(['https://a.example.com'])

        with self.assertLogs('actuator', level='WARNING') as captured:
            options = executor._build_browser_context_options()

        self.assertNotIn('client_certificates', options)
        self.assertTrue(
            any('未配置完整的证书文件' in r.getMessage() for r in captured.records)
        )

    def test_disabled_cert_never_warns_or_applies(self):
        executor = self.make_executor()
        executor.configure_client_cert(pfx_path='/nonexistent/client.pfx', origins='https://a.com')
        executor.set_task_origins(['https://a.com'])

        options = executor._build_browser_context_options()
        self.assertNotIn('client_certificates', options)


# ---------------------------------------------------------------------------
# 3. origin 推导 / 配置幂等 / 口令不泄漏
# ---------------------------------------------------------------------------

class TaskOriginsTest(ActuatorTestCase):
    def test_derives_from_env_config_and_page_urls(self):
        executor = self.make_executor()
        page_step = PageStepConfig(
            page_step_id=1,
            page_url='https://b.example.com:8443/login',
            page_name='登录页',
            env_config={'base_url': 'http://ignored.example.com'},
        )
        case = TestCaseConfig(
            case_id=1,
            case_name='登录用例',
            page_steps=[page_step],
            env_config={'base_url': 'https://a.example.com/x'},
        )

        self.assertEqual(
            executor._task_origins(case),
            ['https://a.example.com', 'https://b.example.com:8443'],
        )

    def test_http_base_url_is_dropped(self):
        executor = self.make_executor()
        case = TestCaseConfig(
            case_id=2, case_name='c', env_config={'base_url': 'http://insecure.example.com'}
        )
        self.assertEqual(executor._task_origins(case), [])

    def test_page_step_config_is_supported_directly(self):
        executor = self.make_executor()
        page_step = PageStepConfig(
            page_step_id=3, page_url='https://direct.example.com/path', page_name='p'
        )
        self.assertEqual(executor._task_origins(page_step), ['https://direct.example.com'])

    def test_extra_origins_are_merged(self):
        executor = self.make_executor()
        executor.configure_client_cert(origins='https://extra.example.com, https://a.example.com')
        case = TestCaseConfig(
            case_id=4, case_name='c', env_config={'base_url': 'https://a.example.com'}
        )
        self.assertEqual(
            executor._task_origins(case),
            ['https://a.example.com', 'https://extra.example.com'],
        )

    def test_accepts_plain_strings_and_multiple_configs(self):
        executor = self.make_executor()
        case_a = TestCaseConfig(case_id=5, case_name='a', env_config={'base_url': 'https://a.com'})
        case_b = TestCaseConfig(case_id=6, case_name='b', env_config={'base_url': 'https://b.com'})
        self.assertEqual(
            executor._task_origins(case_a, case_b),
            ['https://a.com', 'https://b.com'],
        )
        self.assertEqual(executor._task_origins('https://c.com/x'), ['https://c.com'])

    def test_no_configs_yields_empty(self):
        executor = self.make_executor()
        self.assertEqual(executor._task_origins(), [])


class SetTaskOriginsTest(ActuatorTestCase):
    def test_overwrites_instead_of_accumulating(self):
        executor = self.make_executor()
        executor.set_task_origins(['https://a.com'])
        executor.set_task_origins(['https://b.com'])
        self.assertEqual(executor._task_cert_origins, ['https://b.com'])

    def test_empty_clears(self):
        executor = self.make_executor()
        executor.set_task_origins(['https://a.com'])
        executor.set_task_origins([])
        self.assertEqual(executor._task_cert_origins, [])
        executor.set_task_origins(None)
        self.assertEqual(executor._task_cert_origins, [])

    def test_string_input_is_accepted(self):
        executor = self.make_executor()
        executor.set_task_origins('https://a.com, https://b.com')
        self.assertEqual(executor._task_cert_origins, ['https://a.com', 'https://b.com'])


class ConfigureClientCertTest(ActuatorTestCase):
    def test_only_passed_fields_are_updated(self):
        files = self.make_cert_files()
        executor = self.make_executor()
        executor.configure_client_cert(
            enabled=True,
            pfx_path=str(files['pfx']),
            passphrase=SECRET_PASSPHRASE,
            origins='https://a.com',
        )

        # 只更新 origins，其余保持不变
        executor.configure_client_cert(origins='https://b.com')

        self.assertTrue(executor._client_cert_enabled)
        self.assertEqual(executor._client_cert_pfx_path, str(files['pfx']))
        self.assertEqual(executor._client_cert_passphrase, SECRET_PASSPHRASE)
        self.assertEqual(executor._client_cert_origins, 'https://b.com')

    def test_relative_path_resolved_against_config_dir(self):
        files = self.make_cert_files()
        executor = self.make_executor()
        executor.configure_client_cert(
            enabled=True,
            pfx_path='certs/client.pfx',
            config_dir=str(self.tmp),
        )
        executor.set_task_origins(['https://a.com'])

        options = executor._build_browser_context_options()
        self.assertEqual(
            options['client_certificates'][0]['pfxPath'],
            str(files['pfx']),
        )

    def test_empty_string_clears_path(self):
        files = self.make_cert_files()
        executor = self.make_executor()
        executor.configure_client_cert(enabled=True, pfx_path=str(files['pfx']))
        executor.configure_client_cert(pfx_path='')
        self.assertIsNone(executor._client_cert_pfx_path)

    def test_reconfigure_invalidates_cached_resolution(self):
        files = self.make_cert_files()
        executor = self.make_executor()
        executor.configure_client_cert(enabled=True, pfx_path=str(files['pfx']))
        executor.set_task_origins(['https://a.com'])
        executor._build_browser_context_options()  # 触发缓存

        executor.configure_client_cert(pfx_path=None)
        executor.configure_client_cert(pfx_path=str(files['pfx2']))
        options = executor._build_browser_context_options()
        self.assertEqual(
            options['client_certificates'][0]['pfxPath'], str(files['pfx2'])
        )


class PassphraseLeakTest(ActuatorTestCase):
    """口令不能出现在任何日志里（含 record.args）。"""

    def test_passphrase_not_logged_anywhere(self):
        files = self.make_cert_files()
        executor = self.make_executor()

        with self.assertLogs('actuator', level='DEBUG') as captured:
            executor.configure_client_cert(
                enabled=True,
                pfx_path=str(files['pfx']),
                passphrase=SECRET_PASSPHRASE,
                origins='https://a.com, notaurl',
            )
            executor.set_task_origins(['https://a.com'])
            options = executor._build_browser_context_options()
            # 再走一遍，覆盖「已打印过指纹」的分支
            executor._build_browser_context_options()

        # 功能正常：口令确实被传给了 Playwright
        self.assertEqual(options['client_certificates'][0]['passphrase'], SECRET_PASSPHRASE)

        for record in captured.records:
            self.assertNotIn(SECRET_PASSPHRASE, record.getMessage())
            self.assertNotIn(SECRET_PASSPHRASE, str(record.args))
            self.assertNotIn(SECRET_PASSPHRASE, str(record.__dict__.get('exc_info')))

    def test_attach_log_contains_origin_and_path(self):
        files = self.make_cert_files()
        executor = self.make_executor()

        with self.assertLogs('actuator', level='INFO') as captured:
            executor.configure_client_cert(enabled=True, pfx_path=str(files['pfx']))
            executor.set_task_origins(['https://a.com'])
            executor._build_browser_context_options()

        attach = [r for r in captured.records if '客户端证书已启用' in r.getMessage()]
        self.assertEqual(len(attach), 1)
        self.assertIn('https://a.com', attach[0].getMessage())


# ---------------------------------------------------------------------------
# 4. Config 解析
# ---------------------------------------------------------------------------

class ParseTriStateBoolTest(unittest.TestCase):
    def test_none_and_auto_map_to_none(self):
        self.assertIsNone(parse_tri_state_bool(None))
        self.assertIsNone(parse_tri_state_bool('auto'))
        self.assertIsNone(parse_tri_state_bool('AUTO'))
        self.assertIsNone(parse_tri_state_bool(''))
        self.assertIsNone(parse_tri_state_bool('   '))

    def test_truthy_and_falsy_strings(self):
        for raw in ('true', 'TRUE', '1', 'yes', 'on'):
            self.assertIs(parse_tri_state_bool(raw), True, msg=raw)
        for raw in ('false', 'FALSE', '0', 'no', 'off'):
            self.assertIs(parse_tri_state_bool(raw), False, msg=raw)

    def test_booleans_pass_through(self):
        self.assertIs(parse_tri_state_bool(True), True)
        self.assertIs(parse_tri_state_bool(False), False)

    def test_unknown_string_falls_back_to_auto(self):
        self.assertIsNone(parse_tri_state_bool('maybe'))


class ConfigTomlTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _load(self, body: str) -> Config:
        path = self.tmp / 'config.toml'
        path.write_text(body, encoding='utf-8')
        config = Config()
        config.config_dir = self.tmp
        config.load_from_toml(str(path))
        return config

    def test_all_cert_keys_are_read(self):
        config = self._load(
            """
[browser]
client_cert_enabled = true
client_cert_pfx_path = "./certs/client.pfx"
client_cert_passphrase = "pw"
client_cert_cert_path = "./certs/client.crt"
client_cert_key_path = "./certs/client.key"
client_cert_origins = "https://a.example.com"
ignore_https_errors = true
"""
        )
        self.assertTrue(config.client_cert_enabled)
        self.assertEqual(config.client_cert_pfx_path, './certs/client.pfx')
        self.assertEqual(config.client_cert_passphrase, 'pw')
        self.assertEqual(config.client_cert_cert_path, './certs/client.crt')
        self.assertEqual(config.client_cert_key_path, './certs/client.key')
        self.assertEqual(config.client_cert_origins, 'https://a.example.com')
        self.assertIs(config.ignore_https_errors, True)

    def test_defaults_when_section_is_absent(self):
        config = self._load('[browser]\nbrowser_type = "chromium"\n')
        self.assertFalse(config.client_cert_enabled)
        self.assertIsNone(config.client_cert_pfx_path)
        self.assertIsNone(config.client_cert_passphrase)
        self.assertIsNone(config.ignore_https_errors)

    def test_ignore_https_errors_auto_in_toml(self):
        config = self._load('[browser]\nignore_https_errors = "auto"\n')
        self.assertIsNone(config.ignore_https_errors)

    def test_ignore_https_errors_explicit_false(self):
        config = self._load('[browser]\nignore_https_errors = false\n')
        self.assertIs(config.ignore_https_errors, False)

    def test_resolve_client_cert_paths_anchors_to_config_dir(self):
        _write_file(self.tmp / 'certs' / 'client.pfx')
        config = self._load('[browser]\nclient_cert_enabled = true\nclient_cert_pfx_path = "certs/client.pfx"\n')
        resolved = config.resolve_client_cert_paths()
        self.assertEqual(resolved['pfx'], self.tmp / 'certs' / 'client.pfx')

    def test_resolve_warns_when_file_missing(self):
        config = self._load('[browser]\nclient_cert_enabled = true\nclient_cert_pfx_path = "nope.pfx"\n')
        with self.assertLogs(level='WARNING') as captured:
            config.resolve_client_cert_paths()
        self.assertTrue(any('不存在' in r.getMessage() for r in captured.records))


class ConfigEnvTest(unittest.TestCase):
    ENV = {
        'WHARTTEST_ACTUATOR_CLIENT_CERT_ENABLED': 'true',
        'WHARTTEST_ACTUATOR_CLIENT_CERT_PFX_PATH': '  /app/certs/client.pfx  ',
        'WHARTTEST_ACTUATOR_CLIENT_CERT_PASSPHRASE': SECRET_PASSPHRASE,
        'WHARTTEST_ACTUATOR_CLIENT_CERT_CERT_PATH': '/app/certs/client.crt',
        'WHARTTEST_ACTUATOR_CLIENT_CERT_KEY_PATH': '/app/certs/client.key',
        'WHARTTEST_ACTUATOR_CLIENT_CERT_ORIGINS': 'https://a.example.com',
    }

    @patch.dict(os.environ, ENV, clear=True)
    def test_string_and_bool_env_are_applied(self):
        config = Config()
        config.load_from_env()

        self.assertTrue(config.client_cert_enabled)
        self.assertEqual(config.client_cert_pfx_path, '/app/certs/client.pfx')
        self.assertEqual(config.client_cert_cert_path, '/app/certs/client.crt')
        self.assertEqual(config.client_cert_key_path, '/app/certs/client.key')
        self.assertEqual(config.client_cert_origins, 'https://a.example.com')

    @patch.dict(os.environ, ENV, clear=True)
    def test_passphrase_is_removed_from_environment(self):
        config = Config()
        config.load_from_env()

        self.assertEqual(config.client_cert_passphrase, SECRET_PASSPHRASE)
        # 读完即从环境中移除，避免泄漏给后续启动的子进程
        self.assertNotIn('WHARTTEST_ACTUATOR_CLIENT_CERT_PASSPHRASE', os.environ)

    @patch.dict(
        os.environ,
        {'WHARTTEST_ACTUATOR_IGNORE_HTTPS_ERRORS': 'auto'},
        clear=True,
    )
    def test_ignore_https_errors_auto_is_none(self):
        config = Config()
        config.ignore_https_errors = 'sentinel-set-by-test'
        config.load_from_env()
        self.assertIsNone(config.ignore_https_errors)

    @patch.dict(os.environ, {'WHARTTEST_ACTUATOR_IGNORE_HTTPS_ERRORS': 'true'}, clear=True)
    def test_ignore_https_errors_true(self):
        config = Config()
        config.load_from_env()
        self.assertIs(config.ignore_https_errors, True)

    @patch.dict(os.environ, {'WHARTTEST_ACTUATOR_IGNORE_HTTPS_ERRORS': 'false'}, clear=True)
    def test_ignore_https_errors_false(self):
        config = Config()
        config.load_from_env()
        self.assertIs(config.ignore_https_errors, False)

    @patch.dict(os.environ, {}, clear=True)
    def test_unset_env_leaves_attribute_untouched(self):
        config = Config()
        config.load_from_env()
        self.assertIsNone(config.ignore_https_errors)


# ---------------------------------------------------------------------------
# 5. consumer 平台下发通道
# ---------------------------------------------------------------------------

class ConsumerConfigChannelTest(unittest.TestCase):
    def setUp(self):
        from consumer import TaskConsumer

        self.TaskConsumer = TaskConsumer

    def test_config_field_map_covers_cert_fields(self):
        mapping = self.TaskConsumer._CONFIG_FIELD_MAP
        for key in (
            'client_cert_enabled',
            'client_cert_pfx_path',
            'client_cert_cert_path',
            'client_cert_key_path',
            'client_cert_origins',
        ):
            self.assertIn(key, mapping)
            self.assertEqual(mapping[key], key)

    def test_config_field_map_excludes_passphrase(self):
        """口令绝不能进入平台下发通道（下发+持久化都走这张表）。"""
        mapping = self.TaskConsumer._CONFIG_FIELD_MAP
        self.assertNotIn('client_cert_passphrase', mapping)
        self.assertNotIn('client_cert_passphrase', set(mapping.values()))

    def test_redact_masks_sensitive_keys(self):
        redacted = self.TaskConsumer._redact(
            {
                'client_cert_passphrase': SECRET_PASSPHRASE,
                'api_password': 'p',
                'model_api_key': 'k',
                'client_cert_pfx_path': '/app/certs/client.pfx',
                'nested': {'passphrase': 'x'},
                'items': [{'secret': 'y'}],
            }
        )
        self.assertEqual(redacted['client_cert_passphrase'], '***')
        self.assertEqual(redacted['api_password'], '***')
        self.assertEqual(redacted['model_api_key'], '***')
        self.assertEqual(redacted['nested']['passphrase'], '***')
        self.assertEqual(redacted['items'][0]['secret'], '***')
        # 非敏感字段原样保留
        self.assertEqual(redacted['client_cert_pfx_path'], '/app/certs/client.pfx')

    def test_redact_keeps_empty_values(self):
        self.assertEqual(self.TaskConsumer._redact({'api_password': ''})['api_password'], '')

    def test_redact_passthrough_for_scalars(self):
        self.assertEqual(self.TaskConsumer._redact('plain'), 'plain')
        self.assertIsNone(self.TaskConsumer._redact(None))


class PersistConfigRoundTripTest(unittest.TestCase):
    """平台下发配置写回 config.toml 时，不能冲掉本机配置的证书口令。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.path = self.tmp / 'config.toml'

    def tearDown(self):
        self._tmp.cleanup()

    def _make_consumer(self):
        from consumer import TaskConsumer

        consumer = TaskConsumer.__new__(TaskConsumer)  # 跳过 __init__（会拉起网络/队列）
        consumer.config_path = str(self.path)
        return consumer

    def test_cert_keys_written_and_passphrase_preserved(self):
        import tomllib

        # 本机已有配置（含口令）
        self.path.write_text(
            f'[browser]\nclient_cert_passphrase = "{SECRET_PASSPHRASE}"\n',
            encoding='utf-8',
        )

        consumer = self._make_consumer()
        consumer._persist_config(
            {
                'client_cert_enabled': True,
                'client_cert_pfx_path': './certs/client.pfx',
                'client_cert_origins': 'https://a.example.com',
            }
        )

        with open(self.path, 'rb') as fh:
            data = tomllib.load(fh)

        browser = data['browser']
        self.assertTrue(browser['client_cert_enabled'])
        self.assertEqual(browser['client_cert_pfx_path'], './certs/client.pfx')
        self.assertEqual(browser['client_cert_origins'], 'https://a.example.com')
        # 关键：口令未被平台下发内容覆盖
        self.assertEqual(browser['client_cert_passphrase'], SECRET_PASSPHRASE)

    def test_none_values_are_skipped(self):
        import tomllib

        consumer = self._make_consumer()
        consumer._persist_config(
            {'client_cert_enabled': None, 'client_cert_pfx_path': '/app/certs/x.pfx'}
        )

        with open(self.path, 'rb') as fh:
            data = tomllib.load(fh)

        self.assertNotIn('client_cert_enabled', data['browser'])
        self.assertEqual(data['browser']['client_cert_pfx_path'], '/app/certs/x.pfx')

    def test_other_sections_survive(self):
        import tomllib

        self.path.write_text(
            '[server]\nws_url = "ws://backend:8000/ws/ui/actuator/"\n',
            encoding='utf-8',
        )
        consumer = self._make_consumer()
        consumer._persist_config({'client_cert_enabled': True})

        with open(self.path, 'rb') as fh:
            data = tomllib.load(fh)

        self.assertEqual(data['server']['ws_url'], 'ws://backend:8000/ws/ui/actuator/')


class ActuatorInfoReportingTest(unittest.TestCase):
    """执行器上报必须包含证书路径字段，否则平台编辑弹窗会提交空串把它清掉。"""

    def test_actuator_info_includes_cert_paths(self):
        import inspect

        from websocket_client import WebSocketClient

        source = inspect.getsource(WebSocketClient._send_actuator_info)
        for key in (
            'client_cert_enabled',
            'client_cert_pfx_path',
            'client_cert_cert_path',
            'client_cert_key_path',
            'client_cert_origins',
        ):
            self.assertIn(f"'{key}':", source, msg=f'上报字段缺少 {key}')
        # 口令绝不上报（注释里提及是允许的，所以断言的是「不是 dict 键」）
        self.assertNotIn("'client_cert_passphrase':", source)


class DjangoWhitelistConsistencyTest(unittest.TestCase):
    """证书字段必须同时存在于 6 个位置，漏掉任何一处都会被静默丢弃。

    这是本功能最容易出错的地方（已实际踩过一次：Django consumers 的 config_keys 白名单）。
    这里对源码做静态比对 —— 比拉起 Django 环境轻得多，且不需要数据库。
    """

    CERT_KEYS = (
        'client_cert_enabled',
        'client_cert_pfx_path',
        'client_cert_cert_path',
        'client_cert_key_path',
        'client_cert_origins',
    )

    def _read(self, relative: str) -> str:
        repo_root = Path(__file__).parent.parent
        path = repo_root / relative
        self.assertTrue(path.exists(), msg=f'找不到文件: {path}')
        return path.read_text(encoding='utf-8')

    def test_executor_side_field_map(self):
        from consumer import TaskConsumer

        for key in self.CERT_KEYS:
            self.assertIn(key, TaskConsumer._CONFIG_FIELD_MAP, msg=f'consumer 缺少 {key}')

    def test_django_views_whitelist_and_list_actuators(self):
        views = self._read('WHartTest_Django/ui_automation/views.py')
        for key in self.CERT_KEYS:
            self.assertIn(key, views, msg=f'Django views 缺少 {key}')
        # list_actuators 必须回填，否则前端以空串预填并覆盖执行器上的真实值
        for key in self.CERT_KEYS:
            self.assertIn(f"'{key}'", views, msg=f'Django views 未回填 {key}')

    def test_django_consumers_config_keys(self):
        """上报字段白名单：缺了它，执行器上报的证书路径不会被存储。"""
        consumers = self._read('WHartTest_Django/ui_automation/consumers.py')
        start = consumers.index('config_keys = (')
        end = consumers.index(')', start)
        block = consumers[start:end]
        for key in self.CERT_KEYS:
            self.assertIn(key, block, msg=f'Django consumers.config_keys 缺少 {key}')

    def test_vue_api_types_and_form(self):
        api_ts = self._read('WHartTest_Vue/src/features/ui-automation/api/index.ts')
        vue = self._read(
            'WHartTest_Vue/src/features/ui-automation/views/ActuatorList.vue'
        )
        for key in self.CERT_KEYS:
            self.assertIn(key, api_ts, msg=f'Vue api 类型缺少 {key}')
            self.assertIn(key, vue, msg=f'ActuatorList.vue 缺少 {key}')

    def test_django_whitelist_excludes_passphrase(self):
        views = self._read('WHartTest_Django/ui_automation/views.py')
        start = views.index('_ACTUATOR_CONFIG_FIELDS = frozenset({')
        end = views.index('})', start)
        self.assertNotIn('client_cert_passphrase', views[start:end])

    def test_django_report_whitelist_excludes_passphrase(self):
        consumers = self._read('WHartTest_Django/ui_automation/consumers.py')
        start = consumers.index('config_keys = (')
        end = consumers.index(')', start)
        self.assertNotIn('client_cert_passphrase', consumers[start:end])


if __name__ == '__main__':
    # 避免测试过程的日志被生产 handler 吞掉（assertLogs 需要真实生效）
    logging.getLogger('actuator').setLevel(logging.DEBUG)
    unittest.main(verbosity=2)
