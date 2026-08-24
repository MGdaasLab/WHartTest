#!/usr/bin/env node
'use strict';

/**
 * WHartTest UI 自动化录制器服务
 *
 * 协议：stdin/stdout 行分隔 JSON
 * 请求：   { id, method, params }
 * 响应：   { id, ok, error?, state? }
 * 事件推送：{ "event": "frame"|"actions", data: {...} }   （无 id，主动推送）
 *
 * 方法：
 *   - ping
 *   - start { url, viewport: {width, height} }  启动无头浏览器并注入录制捕获脚本
 *   - input { type: 'mouse'|'wheel'|'key', ... } 回放前端转发来的浏览器输入
 *   - assert { mode: 'visible'|'contain_text'|'enabled'|'url' } 对"悬停元素"记录断言动作
 *   - finish  停止帧推流，返回动作列表 + 生成的可读 playwright JS 脚本
 *   - close   关闭浏览器并退出
 *
 * 录制动作来源：页面注入脚本上报（click/fill/press/check/uncheck）+ 主 frame 导航（goto）+
 * 前端断言命令（assert）。动作点击目标自动生成 UiElement 兼容的选择器
 * （id/name/placeholder/test_id→css/text/role/xpath）。
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const Module = require('module');
const { execSync } = require('child_process');

// ---------------------------------------------------------------------------
// 基础
// ---------------------------------------------------------------------------

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + '\n');
}

function pushEvent(event, data) {
  send({ event, data });
}

function serverLog(...args) {
  try {
    process.stderr.write('[recorder_server] ' + args.map(String).join(' ') + '\n');
  } catch (_) {}
}

function parseCli(argv) {
  const out = { skillDir: '' };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--skill-dir') {
      out.skillDir = argv[i + 1] || '';
      i++;
    }
  }
  return out;
}

function checkPlaywrightInstalled(requireFromSkill) {
  try {
    requireFromSkill.resolve('playwright');
    return true;
  } catch (_) {
    return false;
  }
}

function installPlaywright(skillDir) {
  const allow = (process.env.PLAYWRIGHT_AUTO_INSTALL || 'true').toLowerCase() !== 'false';
  if (!allow) return false;
  serverLog('Playwright not found in skill dir, installing...');
  try {
    execSync('npm install', { stdio: 'inherit', cwd: skillDir });
    serverLog('npm install done');
    return true;
  } catch (e) {
    serverLog('npm install failed:', e && e.message ? e.message : String(e));
    return false;
  }
}

// ---------------------------------------------------------------------------
// 页面注入的录制捕获脚本（运行在浏览器页面中）
// ---------------------------------------------------------------------------

const INIT_SCRIPT = `
(function () {
  if (window.__whart) return;
  window.__whart = { hovered: null, describe: null };

  function cleanText(s, max) {
    return (s || '').replace(/\\s+/g, ' ').trim().slice(0, max || 40);
  }

  function buildXPath(el) {
    if (el.id) return '//*[@id="' + String(el.id).replace(/["']/g, '') + '"]';
    var nm = el.getAttribute && el.getAttribute('name');
    if (nm) return '//*[@name="' + String(nm).replace(/["']/g, '') + '"]';
    var parts = [];
    var node = el;
    while (node && node.nodeType === 1 && node !== document.documentElement) {
      var idx = 1;
      var sib = node.previousElementSibling;
      while (sib) {
        if (sib.tagName === node.tagName) idx++;
        sib = sib.previousElementSibling;
      }
      parts.unshift(node.tagName.toLowerCase() + '[' + idx + ']');
      node = node.parentElement;
    }
    return '/html/' + parts.join('/');
  }

  function describe(el) {
    if (!el || el.nodeType !== 1) return null;
    if (el === document.documentElement || el === document.body) return null;
    var attrs = {};
    if (el.getAttribute) {
      attrs.id = el.getAttribute('id') || '';
      attrs.name = el.getAttribute('name') || '';
      attrs.placeholder = el.getAttribute('placeholder') || '';
      attrs.testId = el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-test-id') || '';
      attrs.role = el.getAttribute('role') || '';
    }
    var text = cleanText(el.textContent, 40);
    var label = text || attrs.id || attrs.name || attrs.placeholder || 'element';

    if (attrs.testId) {
      return { locator_type: 'css', locator_value: '[data-testid="' + attrs.testId + '"]', name: label.slice(0, 24) };
    }
    if (attrs.id) {
      return { locator_type: 'id', locator_value: attrs.id, name: label.slice(0, 24) };
    }
    if (attrs.name) {
      return { locator_type: 'name', locator_value: attrs.name, name: label.slice(0, 24) };
    }
    if (attrs.placeholder) {
      return { locator_type: 'placeholder', locator_value: attrs.placeholder, name: label.slice(0, 24) };
    }
    var tag = el.tagName || '';
    var clickableText = (tag === 'BUTTON' || tag === 'A' || tag === 'LABEL' || tag === 'SUMMARY' ||
      attrs.role === 'button' || attrs.role === 'link' || attrs.role === 'tab') && text;
    if (clickableText) {
      return { locator_type: 'text', locator_value: text, name: text.slice(0, 24) };
    }
    if (attrs.role) {
      return { locator_type: 'role', locator_value: attrs.role, name: label.slice(0, 24) };
    }
    return { locator_type: 'xpath', locator_value: buildXPath(el), name: label.slice(0, 24) };
  }

  window.__whart.describe = describe;

  document.addEventListener('pointermove', function (e) {
    if (e.target && e.target.nodeType === 1) {
      window.__whart.hovered = e.target;
    }
  }, true);

  document.addEventListener('click', function (e) {
    var el = e.target;
    if (!el || el.nodeType !== 1) return;
    var d = window.__whart.describe(el);
    if (!d) return;
    if (window.__whartReport) {
      window.__whartReport({ t: 'click', el: d });
    }
  }, true);

  document.addEventListener('input', function (e) {
    var el = e.target;
    if (!el || el.nodeType !== 1) return;
    var tag = el.tagName || '';
    if (tag === 'CHECKBOX' || tag === 'RADIO') return;
    if (tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') return;
    if (el.type === 'checkbox' || el.type === 'radio') return;
    var d = window.__whart.describe(el);
    if (!d) return;
    if (window.__whartReport) {
      window.__whartReport({ t: 'fill', el: d, value: String(el.value || '').slice(0, 2000) });
    }
  }, true);

  document.addEventListener('change', function (e) {
    var el = e.target;
    if (!el || el.nodeType !== 1) return;
    var tag = el.tagName || '';
    var d = window.__whart.describe(el);
    if (!d) return;
    if (window.__whartReport) {
      if (tag === 'SELECT') {
        window.__whartReport({ t: 'fill', el: d, value: String(el.value || '') });
      } else if (el.type === 'checkbox' || el.type === 'radio') {
        window.__whartReport({ t: el.checked ? 'check' : 'uncheck', el: d });
      }
    }
  }, true);

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter') return;
    var el = document.activeElement || e.target;
    if (!el || el.nodeType !== 1) return;
    var d = window.__whart.describe(el);
    if (!d) return;
    if (window.__whartReport) {
      window.__whartReport({ t: 'press', el: d, key: 'Enter' });
    }
  }, true);
})();
`;

// ---------------------------------------------------------------------------
// 录制状态
// ---------------------------------------------------------------------------

const state = {
  browser: null,
  context: null,
  page: null,
  viewport: { width: 1400, height: 900 },
  running: false,
  frameTimer: null,
  capturing: false,
  startedUrl: '',
  lastNavUrl: '',
  navReady: false,
  recorded: [],
  seq: 0,
  lastClick: { sel: '', ts: 0 },
  lastFill: { sel: '', value: '', ts: 0 },
  lastPress: { sel: '', ts: 0 },
  finished: false,
};

function recordAction(action) {
  state.seq += 1;
  const entry = Object.assign({ seq: state.seq }, action);
  state.recorded.push(entry);
  if (state.recorded.length > 1000) {
    state.recorded.splice(0, state.recorded.length - 1000);
  }
  pushEvent('actions', entry);
}

function handleReport(payload) {
  if (!state.running || !payload || !payload.t) return;
  const now = Date.now();
  try {
    if (payload.t === 'click') {
      const selKey = JSON.stringify(payload.el);
      if (selKey === state.lastClick.sel && now - state.lastClick.ts < 400) return;
      state.lastClick = { sel: selKey, ts: now };
      recordAction({ type: 'click', selector: payload.el });
    } else if (payload.t === 'fill') {
      const selKey = JSON.stringify(payload.el);
      if (selKey === state.lastFill.sel && payload.value === state.lastFill.value && now - state.lastFill.ts < 500) return;
      state.lastFill = { sel: selKey, value: payload.value, ts: now };
      recordAction({ type: 'fill', selector: payload.el, value: payload.value });
    } else if (payload.t === 'check' || payload.t === 'uncheck') {
      recordAction({ type: payload.t, selector: payload.el });
    } else if (payload.t === 'press') {
      const selKey = JSON.stringify(payload.el);
      if (selKey === state.lastPress.sel && now - state.lastPress.ts < 600) return;
      state.lastPress = { sel: selKey, ts: now };
      recordAction({ type: 'press', selector: payload.el, key: payload.key || 'Enter' });
    }
  } catch (e) {
    serverLog('handleReport error:', e && e.message ? e.message : String(e));
  }
}

function recordNavigation(url) {
  if (!state.running || state.finished) return;
  if (!url || !url.startsWith('http')) return;
  if (url === state.lastNavUrl) return;
  const prev = state.lastNavUrl || state.startedUrl || '';
  state.lastNavUrl = url;
  if (prev && prev !== url) {
    recordAction({ type: 'goto', url });
  }
}

// ---------------------------------------------------------------------------
// 帧推流
// ---------------------------------------------------------------------------

function startFrameLoop() {
  if (state.frameTimer) return;
  state.frameTimer = setInterval(async () => {
    if (!state.running || state.finished || state.capturing || !state.page) return;
    state.capturing = true;
    try {
      const shot = await state.page.screenshot({ type: 'jpeg', quality: 60 });
      pushEvent('frame', {
        mime: 'image/jpeg',
        data: shot.toString('base64'),
        w: state.viewport.width,
        h: state.viewport.height,
      });
    } catch (e) {
      // 页面可能已被关闭，忽略
    } finally {
      state.capturing = false;
    }
  }, 250);
}

function stopFrameLoop() {
  if (state.frameTimer) {
    clearInterval(state.frameTimer);
    state.frameTimer = null;
  }
}

// ---------------------------------------------------------------------------
// 脚本生成
// ---------------------------------------------------------------------------

function locatorExpr(selector) {
  if (!selector) return null;
  const { locator_type, locator_value } = selector;
  switch (locator_type) {
    case 'xpath':
      return `page.locator('xpath=${String(locator_value).replace(/'/g, "\\'")}')`;
    case 'id':
      return `page.locator('#${String(locator_value).replace(/"/g, '')}')`;
    case 'name':
      return `page.locator("[name='${String(locator_value).replace(/'/g, '')}']")`;
    case 'placeholder':
      return `page.get_by_placeholder('${String(locator_value).replace(/'/g, "\\'")}')`;
    case 'text':
      return `page.get_by_text('${String(locator_value).replace(/'/g, "\\'")}')`;
    case 'role':
      return `page.get_by_role('${String(locator_value).replace(/'/g, "\\'")}')`;
    default:
      return `page.locator('${String(locator_value).replace(/'/g, "\\'")}')`;
  }
}

function buildScript(actions, startUrl) {
  const lines = [];
  lines.push("const { chromium } = require('playwright');");
  lines.push('');
  lines.push('(async () => {');
  lines.push(`  const browser = await chromium.launch({ headless: true });`);
  lines.push(`  const page = await browser.newPage();`);
  if (startUrl) {
    lines.push(`  await page.goto('${startUrl.replace(/'/g, "\\'")}');`);
  }
  for (const a of actions) {
    if (a.type === 'goto') {
      lines.push(`  await page.goto('${String(a.url || '').replace(/'/g, "\\'")}');`);
      continue;
    }
    const loc = locatorExpr(a.selector);
    if (!loc) continue;
    const val = String(a.value || a.key || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    switch (a.type) {
      case 'click':
        lines.push(`  await ${loc}.click();`);
        break;
      case 'fill':
        lines.push(`  await ${loc}.fill('${val}');`);
        break;
      case 'check':
        lines.push(`  await ${loc}.check();`);
        break;
      case 'uncheck':
        lines.push(`  await ${loc}.uncheck();`);
        break;
      case 'press':
        lines.push(`  await ${loc}.press('${a.key || 'Enter'}');`);
        break;
      case 'assert':
        if (a.mode === 'url') {
          lines.push(`  await expect(page).to_have_url('${val}');`);
        } else if (a.mode === 'contain_text') {
          lines.push(`  await expect(${loc}).to_contain_text('${val}');`);
        } else {
          lines.push(`  await expect(${loc}).to_be_${a.mode === 'enabled' ? 'enabled' : 'visible'}();`);
        }
        break;
      default:
        break;
    }
  }
  lines.push(`  await browser.close();`);
  lines.push(`})();`);
  return lines.join('\n') + '\n';
}

// ---------------------------------------------------------------------------
// 方法实现
// ---------------------------------------------------------------------------

async function cmdPing() {
  return { ok: true, state: { alive: true, recorded: state.recorded.length } };
}

async function cmdStart(params) {
  if (state.browser) {
    return { ok: false, error: '录制会话已启动，不能重复 start' };
  }
  const skillDir = cli.skillDir;
  if (!skillDir || !fs.existsSync(path.join(skillDir, 'package.json'))) {
    return { ok: false, error: 'skill-dir 无效或缺少 package.json: ' + skillDir };
  }
  const requireFromSkill = Module.createRequire(path.join(skillDir, 'package.json'));
  if (!checkPlaywrightInstalled(requireFromSkill)) {
    if (!installPlaywright(skillDir)) {
      return { ok: false, error: '无法加载 playwright（skill 目录安装失败）' };
    }
  }
  const { chromium } = requireFromSkill('playwright');

  const viewport = params.viewport && params.viewport.width
    ? { width: Math.max(320, Math.min(1920, params.viewport.width || 1400)),
        height: Math.max(240, Math.min(1200, params.viewport.height || 900)) }
    : { width: 1400, height: 900 };
  state.viewport = viewport;

  const launchOptions = {
    headless: process.env.HEADLESS !== 'false',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  };
  try {
    state.browser = await chromium.launch(launchOptions);
    state.context = await state.browser.newContext({ viewport });
    await state.context.exposeFunction('__whartReport', handleReport);
    await state.context.addInitScript(INIT_SCRIPT);
    state.page = await state.context.newPage();
    state.page.on('framenavigated', (frame) => {
      if (frame === state.page.mainFrame()) {
        recordNavigation(frame.url());
      }
    });
  } catch (e) {
    return { ok: false, error: '浏览器启动失败: ' + (e && e.message ? e.message : String(e)) };
  }

  const url = params.url || '';
  state.running = true;
  if (url) {
    try {
      await state.page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    } catch (e) {
      serverLog('初始导航失败:', e && e.message ? e.message : String(e));
    }
    state.startedUrl = url;
    state.lastNavUrl = url;
  }
  state.finished = false;
  startFrameLoop();
  return { ok: true, state: { viewport, url: state.startedUrl } };
}

async function cmdInput(params) {
  if (!state.page || !state.running) {
    return { ok: false, error: '录制会话未启动' };
  }
  const type = params.type;
  try {
    if (type === 'mouse') {
      const x = Number(params.x) || 0;
      const y = Number(params.y) || 0;
      const button = params.button || 'left';
      if (params.event === 'move') {
        await state.page.mouse.move(x, y);
      } else if (params.event === 'down') {
        await state.page.mouse.down({ button, clickCount: Number(params.clickCount) || 1 });
      } else if (params.event === 'up') {
        await state.page.mouse.up({ button, clickCount: Number(params.clickCount) || 1 });
      }
    } else if (type === 'wheel') {
      await state.page.mouse.wheel(Number(params.deltaX) || 0, Number(params.deltaY) || 0);
    } else if (type === 'key') {
      const key = String(params.key || '');
      if (params.event === 'down') {
        if (key.length === 1 && key >= ' ' && key !== '\u0000') {
          await state.page.keyboard.type(key);
        } else if (key) {
          await state.page.keyboard.down(key);
        }
      } else if (params.event === 'up') {
        if (key && key.length > 1) {
          await state.page.keyboard.up(key);
        }
      }
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: '输入回放失败: ' + (e && e.message ? e.message : String(e)) };
  }
}

async function cmdAssert(params) {
  if (!state.page || !state.running) {
    return { ok: false, error: '录制会话未启动' };
  }
  const mode = String(params.mode || 'visible');
  if (mode === 'url') {
    recordAction({ type: 'assert', mode: 'url', value: state.page.url() });
    return { ok: true, state: { action: 'assert_url' } };
  }
  if (!['visible', 'contain_text', 'enabled'].includes(mode)) {
    return { ok: false, error: '不支持的断言模式: ' + mode };
  }
  try {
    const hovered = await state.page.evaluate(() => {
      const w = window.__whart;
      if (!w || !w.describe || !w.hovered) return null;
      return w.describe(w.hovered);
    });
    if (!hovered) {
      return { ok: false, error: '请先在浏览器画面中把鼠标悬停到要断言的元素上' };
    }
    let value = '';
    if (mode === 'contain_text') {
      value = await state.page.evaluate(() => {
        const el = window.__whart ? window.__whart.hovered : null;
        return el && el.textContent ? String(el.textContent).replace(/\s+/g, ' ').trim().slice(0, 60) : '';
      });
    }
    recordAction({ type: 'assert', mode, selector: hovered, value });
    return { ok: true, state: { action: 'assert_' + mode } };
  } catch (e) {
    return { ok: false, error: '断言记录失败: ' + (e && e.message ? e.message : String(e)) };
  }
}

async function cmdFinish() {
  stopFrameLoop();
  state.finished = true;
  state.running = false;
  return {
    ok: true,
    state: {
      actions: state.recorded,
      script: buildScript(state.recorded, state.startedUrl),
      started_url: state.startedUrl,
    },
  };
}

async function cmdClose() {
  stopFrameLoop();
  state.running = false;
  try {
    if (state.browser) {
      await state.browser.close();
      state.browser = null;
      state.context = null;
      state.page = null;
    }
  } catch (e) {
    serverLog('close browser error:', e && e.message ? e.message : String(e));
  }
  return { ok: true };
}

// ---------------------------------------------------------------------------
// 主循环
// ---------------------------------------------------------------------------

const cli = parseCli(process.argv.slice(2));
let chain = Promise.resolve();
const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

rl.on('line', (line) => {
  let msg;
  try {
    msg = JSON.parse(line);
  } catch (_) {
    return;
  }
  if (!msg || typeof msg.id !== 'string') return;

  const id = msg.id;
  const method = msg.method || '';
  chain = chain.then(async () => {
    try {
      switch (method) {
        case 'ping':
          return send(await cmdPing());
        case 'start':
          return send(await cmdStart(msg.params || {}));
        case 'input':
          return send(await cmdInput(msg.params || {}));
        case 'assert':
          return send(await cmdAssert(msg.params || {}));
        case 'finish':
          return send(await cmdFinish());
        case 'close': {
          const r = await cmdClose();
          send(r);
          setTimeout(() => process.exit(0), 50);
          return;
        }
        default:
          return send({ id, ok: false, error: '未知方法: ' + method });
      }
    } catch (e) {
      return send({ id, ok: false, error: e && e.message ? e.message : String(e) });
    }
  });
});

process.on('SIGTERM', () => {
  stopFrameLoop();
  try {
    if (state.browser) state.browser.close().finally(() => process.exit(0));
  } catch (_) {
    process.exit(0);
  }
});

rl.on('close', () => {
  stopFrameLoop();
  process.exit(0);
});