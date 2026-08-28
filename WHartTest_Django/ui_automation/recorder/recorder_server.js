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
 *   - save_login_state  保存当前浏览器上下文登录态（storageState：cookies + localStorage）
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
      const raw = argv[i + 1] || '';
      out.skillDir = raw ? path.resolve(raw) : '';
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

const INIT_SCRIPT = () => {
  if (window.__whart) return;
  window.__whart = { hovered: null, describe: null };

  function cleanText(s, max) {
    return (s || '').replace(/\\s+/g, ' ').trim().slice(0, max || 40);
  }

  function escAttr(v) {
    return String(v).replace(/["']/g, '');
  }

  // 动态 id 识别：框架运行时生成、刷新即变的 id 不能用作定位锚点。
  // 覆盖 Element Plus 各类实例/容器 id（el-id-920-7、el-popper-container-226、
  // el-select-xxx、el-popper-xxx 等）、构建工具前缀、纯数字与长随机串。
  function isDynamicId(id) {
    if (!id) return true;
    if (/^el-[a-z0-9-]+-\d+$/.test(id)) return true;          // Element Plus / 类 EP 运行时 id
    if (/^(vite|webpack|ember|app)-/.test(id)) return true;    // 构建工具前缀
    if (/^\d+$/.test(id)) return true;                          // 纯数字 id（易冲突且常为生成）
    if (id.length >= 24 && id.indexOf('-') >= 0) return true;   // 长随机串
    return false;
  }

  // 带标签的属性锚点：//input[@placeholder="x"] 而非 //*[...]，
  // 避免不同标签共享同名属性时匹配到多个元素。
  function anchorXPath(tag, attr, value) {
    var t = tag ? tag.toLowerCase() : '*';
    return '//' + t + '[@' + attr + '="' + escAttr(value) + '"]';
  }

  // xpath 唯一性校验：页面中恰好匹配 1 个才允许作为锚点。
  function isUniqueXPath(xp) {
    try {
      var res = document.evaluate(xp, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
      return res.snapshotLength === 1;
    } catch (_) {
      return false;
    }
  }

  // 分层锚点：data-testid → 稳定 id → name（表单）→ placeholder（input/textarea/select）。
  // 每个候选都带元素标签且校验唯一，不唯一自动降级。
  function pickAnchor(el) {
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    if (!el.getAttribute) return null;
    var testId = el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-test-id');
    if (testId) {
      var xp1 = anchorXPath(tag, 'data-testid', testId);
      if (isUniqueXPath(xp1)) return xp1;
    }
    var id = el.getAttribute('id');
    if (id && !isDynamicId(id)) {
      var xp2 = anchorXPath(tag, 'id', id);
      if (isUniqueXPath(xp2)) return xp2;
    }
    var name = el.getAttribute('name');
    if (name && (tag === 'input' || tag === 'textarea' || tag === 'select' || tag === 'button' || tag === 'form')) {
      var xp3 = anchorXPath(tag, 'name', name);
      if (isUniqueXPath(xp3)) return xp3;
    }
    var ph = el.getAttribute('placeholder');
    if (ph && (tag === 'input' || tag === 'textarea' || tag === 'select')) {
      var xp4 = anchorXPath(tag, 'placeholder', ph);
      if (isUniqueXPath(xp4)) return xp4;
    }
    return null;
  }

  // 选择框场景：占位文本 span 只是视觉层，EP 的只读 input 会拦截所有指针事件
  // （点 span 必超时）。定位必须落在 input 自身 / 选择框 wrapper 的稳定 class 上。
  function selectBoxAnchor(el) {
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    if (tag !== 'input') return null;
    var t = ((el.getAttribute && el.getAttribute('type')) || '').toLowerCase();
    if (t === 'password' || t === 'checkbox' || t === 'radio' || t === 'file') return null;

    // ① input 自身的唯一 class（如 el-select__input）
    var own = selfClassAnchor(el);
    if (own && isUniqueXPath(own)) return own;

    // ② 祖先选择框容器（el-select / select-box 等）的唯一 class 锚点 + 相对路径
    var node = el;
    for (var hop = 0; hop < 4 && node; hop++) {
      node = node.parentElement;
      if (!node || node === document.body) break;
      var cls = (node.getAttribute && node.getAttribute('class')) || '';
      var tokens = cls.trim().split(/\s+/);
      for (var i = 0; i < tokens.length; i++) {
        var tk = tokens[i];
        if (!tk || isStateClass(tk)) continue;
        var cand = '//*[contains(@class,"' + tk.replace(/["\\]/g, '') + '")]';
        if (isUniqueXPath(cand)) {
          // 相对路径回到 input 自身（若无中间层级则直接用容器）
          var rel = relativePath(el, node);
          return rel ? cand + rel : cand;
        }
      }
    }
    return null;
  }

  // 从 ancestor 到 el 的相对路径（不含 ancestor 自身）
  function relativePath(el, ancestor) {
    var parts = [];
    var node = el;
    var guard = 0;
    while (node && node !== ancestor && guard < 16) {
      var idx = 1;
      var sib = node.previousElementSibling;
      while (sib) {
        if (sib.tagName === node.tagName) idx++;
        sib = sib.previousElementSibling;
      }
      parts.unshift('/' + node.tagName.toLowerCase() + '[' + idx + ']');
      node = node.parentElement;
      guard++;
    }
    return parts.join('');
  }

  // 交互状态 class（聚焦/悬停/选中/禁用等）变化无常，禁止作定位锚点
  function isStateClass(token) {
    if (/^(is-|is_)/.test(token)) return true;  // Element Plus 等框架状态类：is-focused/is-active...
    return /(hover|focus|active|open|disabled|checked|selected|expanded|loading|collapsed)/.test(token);
  }

  // 某 class token 是否在文档中唯一且非状态类（可安全用作锚点）
  function isUniqueClassToken(token) {
    if (isStateClass(token)) return false;
    try {
      return document.querySelectorAll('[class~="' + token.replace(/["\\]/g, '') + '"]').length === 1;
    } catch (_) {
      return false;
    }
  }

  // 角色+文本 xpath 锚点：仅当该（标签+精确文本）在文档中唯一时使用。
  // 覆盖按钮/链接/标签、下拉项及文本载体（li/option/td/span 等），
  // 下拉选择项用文本定位最稳定；文本不唯一时自动降级，避免歧义。
  // 注意：div 容器的 textContent 会聚合子元素文本（多层父级同文本），
  // 因此容器类标签要求"无元素子节点"（叶子文本载体）才算数。
  function textAnchor(el) {
    var tag = el.tagName || '';
    var role = el.getAttribute && el.getAttribute('role');
    var textLike = (tag === 'BUTTON' || tag === 'A' || tag === 'LABEL' || tag === 'SUMMARY' ||
      tag === 'LI' || tag === 'OPTION' || tag === 'TD' ||
      role === 'button' || role === 'link' || role === 'tab' || role === 'option' ||
      role === 'menuitem' || role === 'listitem');
    if (!textLike) return null;
    var text = cleanText(el.textContent, 40);
    if (!text || text.length < 1 || text.length > 30) return null;
    var selector = tag.toLowerCase();
    try {
      var matched = Array.prototype.filter.call(document.querySelectorAll(selector), function (n) {
        return cleanText(n.textContent, 50) === text;
      });
      if (matched.length === 1) {
        var xp = '//' + selector + '[normalize-space()="' + text.replace(/["']/g, '') + '"]';
        return isUniqueXPath(xp) ? xp : null;
      }
    } catch (_) {}
    return null;
  }

  // 短文本唯一锚点：任意标签、文本 ≤15 字符且在文档中唯一时使用。
  // 用于结构路径兜底前的一次机会（如动态渲染容器内的文本项）。
  function looseTextAnchor(el) {
    var text = cleanText(el.textContent, 16);
    if (!text || text.length < 1 || text.length > 15) return null;
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    try {
      var selector = tag ? tag : '*';
      var matched = Array.prototype.filter.call(document.querySelectorAll(selector), function (n) {
        return cleanText(n.textContent, 20) === text;
      });
      if (matched.length === 1) {
        var xp = '//' + selector + '[normalize-space()="' + text.replace(/["']/g, '') + '"]';
        return isUniqueXPath(xp) ? xp : null;
      }
    } catch (_) {}
    return null;
  }

  // 元素自身唯一 class 锚点（非状态类、页面唯一）
  function selfClassAnchor(el) {
    var cls = el.getAttribute && el.getAttribute('class');
    if (typeof cls !== 'string' || !cls.trim()) return null;
    var tokens = cls.trim().split(/\s+/);
    for (var i = 0; i < tokens.length; i++) {
      var tk = tokens[i];
      if (tk && isUniqueClassToken(tk)) {
        var cand = '//*[contains(@class,"' + tk.replace(/["\\]/g, '') + '")]';
        if (isUniqueXPath(cand)) return cand;
      }
    }
    return null;
  }

  // 子元素文本锚点：点击的是容器 div，但其首个文本型子元素（span/按钮等）
  // 文本唯一时直接指向子元素（运行时点击等价）。
  function childTextAnchor(el) {
    if (!el || !el.children || !el.children.length) return null;
    for (var i = 0; i < el.children.length; i++) {
      var t = textAnchor(el.children[i]);
      if (t) return t;
    }
    return null;
  }

  // 生成相对定位 xpath：
  // ① 自身分层锚点（data-testid/稳定id/name/placeholder，带标签+唯一性校验）；
  // ② 角色+文本锚点（唯一时，带标签）；
  // ③ 自身唯一 class 锚点（此前只检查父级，漏掉了元素自身）；
  // ④ 子元素文本锚点（点击 div、文本在子 span 时直接指向子元素，运行时可点击等价）；
  // ⑤ 向上找最近的唯一锚点祖先（属性锚点 / 唯一 class），从锚点向下写相对路径；
  // ⑥ 兜底短绝对路径（index 保证唯一）。
  function buildXPath(el) {
    var self = pickAnchor(el);
    if (self) return self;
    var selfClass = selfClassAnchor(el);
    if (selfClass) return selfClass;
    var textSelf = textAnchor(el);
    if (textSelf) return textSelf;
    var childText = childTextAnchor(el);
    if (childText) return childText;
    // 下拉选择框：只读 input 无锚点时，用容器内"请选择xx"占位文本锚点
    var selectBox = selectBoxAnchor(el);
    if (selectBox) return selectBox;

    // 结构路径：完整回溯到 body（不限层数）——截断的路径在真实 DOM 中不存在，
    // 宁长勿断；途中遇到唯一锚点祖先则提前短路为相对路径。
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
      var parent = node.parentElement;
      if (!parent || parent.nodeType !== 1 || parent === document.documentElement || parent === document.body) {
        break;
      }
      var anchor = pickAnchor(parent);
      if (anchor) return anchor + '/' + parts.join('/');
      var cls = parent.getAttribute && parent.getAttribute('class');
      if (typeof cls === 'string' && cls.trim()) {
        var tokens = cls.trim().split(/\s+/);
        for (var i = 0; i < tokens.length; i++) {
          var tk = tokens[i];
          if (tk && isUniqueClassToken(tk)) {
            var cand = '//*[contains(@class,"' + tk.replace(/["\\]/g, '') + '")]/' + parts.join('/');
            if (isUniqueXPath(cand)) return cand;
          }
        }
      }
      node = parent;
    }
    // 兜底前最后一次机会：短文本唯一锚点（动态容器内的文本项）
    var looseText = looseTextAnchor(el);
    if (looseText) return looseText;
    // 兜底：完整绝对路径（含 body 层级），唯一性由 index 链保证
    return '/html/body/' + parts.join('/');
  }

  // 控件类型识别：tag + type + class/role 特征 → 平台控件词表
  function detectControlType(el) {
    var tag = el.tagName || '';
    var type = (el.getAttribute && el.getAttribute('type')) || '';
    var cls = (el.getAttribute && el.getAttribute('class')) || '';
    var role = (el.getAttribute && el.getAttribute('role')) || '';
    if (tag === 'TEXTAREA') return '文本域';
    if (tag === 'SELECT') return '下拉框';
    if (tag === 'INPUT') {
      var t = type.toLowerCase();
      if (t === 'password') return '密码框';
      if (t === 'checkbox') return '复选框';
      if (t === 'radio') return '单选框';
      if (t === 'button' || t === 'submit' || t === 'reset') return '按钮';
      if (t === 'file') return '上传';
      return '输入框';
    }
    if (tag === 'BUTTON' || role === 'button' ||
        (type && /button|submit|reset/i.test(type))) return '按钮';
    if (tag === 'A' || role === 'link') return '链接';
    if (/el-pagination|ant-pagination|pagination/i.test(cls)) return '分页';
    if (/el-dialog|modal|ant-modal/i.test(cls) || role === 'dialog') return '弹窗';
    if (/el-tabs__item|ant-tabs-tab|tab\b/i.test(cls) || role === 'tab') return '标签页';
    if (/el-table|ant-table|datagrid/i.test(cls) || tag === 'TABLE') return '表格';
    if (/el-select|ant-select|select\b|combobox/i.test(cls) || role === 'combobox') return '下拉框';
    return '元素';
  }

  // 元素命名：业务语义 + 控件类型（如"用户名输入框"）。
  // 语义优先级：aria-label → placeholder → 关联 label → name → 可见文本（均不含用户输入值）。
  function elementLabel(el) {
    var tag = el.tagName || '';
    var type = ((el.getAttribute && el.getAttribute('type')) || '').toLowerCase();
    var aria = (el.getAttribute && el.getAttribute('aria-label')) || '';
    var ph = (el.getAttribute && el.getAttribute('placeholder')) || '';
    var name = (el.getAttribute && el.getAttribute('name')) || '';
    var semantic = '';
    if (aria) {
      semantic = aria;
    } else if (ph) {
      semantic = ph;
    } else if (el.labels && el.labels.length && el.labels[0].textContent) {
      semantic = cleanText(el.labels[0].textContent, 20);
    } else if (name && /^[a-z0-9_\-\u4e00-\u9fa5]+$/i.test(name)) {
      // name 属性仅在具备可读性（含中文/单词式命名）时使用，避免 base64 串
      semantic = name;
    } else if (tag === 'BUTTON' || tag === 'A' || tag === 'LABEL' || tag === 'SUMMARY' ||
               tag === 'LI' || tag === 'OPTION' || tag === 'TD' || tag === 'SPAN') {
      semantic = cleanText(el.textContent, 20);
    }
    semantic = (semantic || '').replace(/^(请)?(输入|选择|填写)/, '').trim();
    return semantic;
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
    }
    var text = cleanText(el.textContent, 40);
    var ctrlType = detectControlType(el);
    var semantic = elementLabel(el);
    // 无语义时用类型本身（"输入框"→"输入框"不重复拼），或退回原 label 逻辑
    var name;
    if (semantic) {
      // 语义已完整包含控件类型词（如"密码"含"密码框"的"密码"）时直接用语义，
      // 避免出现"密码密码框"这类重复
      name = semantic.indexOf(ctrlType.replace(/框|域|页/g, '')) >= 0 ? semantic : semantic + ctrlType;
    } else if (ctrlType !== '元素') {
      name = ctrlType;
    } else {
      name = text || attrs.id || attrs.name || attrs.placeholder || '元素';
    }
    // 一律输出 xpath 相对定位：
    // 动态 id（el-id-920-7 等）会被过滤，稳定的 id/name/placeholder/data-testid
    // 作为 xpath 锚点保留，其余走唯一 class 锚点 / 结构化相对路径。
    return { locator_type: 'xpath', locator_value: buildXPath(el), name: name.slice(0, 24), ctrl_type: ctrlType };
  }

  window.__whart.describe = describe;
  window.__whart.buildXPath = buildXPath;

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
};

// ---------------------------------------------------------------------------
// 录制状态
// ---------------------------------------------------------------------------

const state = {
  browser: null,
  context: null,
  page: null,
  cdpSession: null,
  frameMode: 'screencast',   // screencast（60fps 推流）| screenshot（截图回退）
  viewport: { width: 1400, height: 900 },
  frameRate: Math.max(1, Math.min(60, parseInt(process.env.RECORDER_FRAME_RATE || '60', 10) || 60)),
  running: false,
  preRunning: false,      // 前置步骤执行中（不记录动作/导航）
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
  lastFrameTs: 0,          // 最近一次推帧时间（screencast 高帧率 / 截图基线兜底）
  finished: false,
};

// 连续输入合并窗口：同一元素在该窗口内多次 input 事件合并为一次 fill
const FILL_MERGE_WINDOW = 1500;

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
  if (!state.running || state.preRunning || !payload || !payload.t) return;
  const now = Date.now();
  try {
    if (payload.t === 'click') {
      const selKey = JSON.stringify(payload.el);
      if (selKey === state.lastClick.sel && now - state.lastClick.ts < 400) return;
      state.lastClick = { sel: selKey, ts: now };
      recordAction({ type: 'click', selector: payload.el });
    } else if (payload.t === 'fill') {
      // 连续输入合并：同一元素窗口内的多次 input 事件合并为一次 fill。
      // 按元素回溯最近一条同元素 fill 原地更新（期间混入 click/断言等记录也不断链）。
      const selKey = JSON.stringify(payload.el);
      if (selKey === state.lastFill.sel && now - state.lastFill.ts < FILL_MERGE_WINDOW) {
        for (let i = state.recorded.length - 1; i >= 0; i--) {
          const prev = state.recorded[i];
          if (prev.type === 'fill' && JSON.stringify(prev.selector) === selKey) {
            prev.value = payload.value;
            state.lastFill = { sel: selKey, value: payload.value, ts: now };
            pushEvent('actions', prev);
            return;
          }
          if (i < state.recorded.length - 8) break;
        }
      }
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
  // 不单独记录 goto：页面跳转是前面操作（点击/提交等）的自然结果，
  // 额外记录反而会在执行时产生与真实流程冲突的硬导航。
  state.lastNavUrl = url || state.lastNavUrl;
}

// ---------------------------------------------------------------------------
// 帧推流
// ---------------------------------------------------------------------------

/**
 * CDP Page.startScreencast：浏览器原生编码 jpeg 帧并推送（最高 60fps），
 * 每帧需回 Ack 否则浏览器会暂停推流。启动失败时回退到截图轮询模式。
 */
async function startFrameStream(page) {
  try {
    const cdpSession = await page.context().newCDPSession(page);
    cdpSession.on('Page.screencastFrame', (params) => {
      if (!state.running || state.finished || !params.data) return;
      pushEvent('frame', {
        mime: 'image/jpeg',
        data: params.data.replace(/^data:image\/jpeg;base64,/, ''),
        w: state.viewport.width,
        h: state.viewport.height,
      });
      state.lastFrameTs = Date.now();
      cdpSession.send('Page.screencastFrameAck', { sessionId: params.sessionId }).catch(() => {});
    });
    await cdpSession.send('Page.startScreencast', {
      format: 'jpeg',
      quality: 65,
      maxWidth: state.viewport.width,
      maxHeight: state.viewport.height,
      everyNthFrame: 1,
      maxFrameRate: state.frameRate,
    });
    state.cdpSession = cdpSession;
    state.frameMode = 'screencast';
    serverLog('screencast 模式启动，目标帧率:', state.frameRate);
    return true;
  } catch (e) {
    serverLog('screencast 启动失败，回退截图模式:', e && e.message ? e.message : String(e));
    return false;
  }
}

function stopFrameStream() {
  if (state.cdpSession) {
    state.cdpSession.send('Page.stopScreencast').catch(() => {});
    state.cdpSession = null;
  }
}

/**
 * 截图基线兜底。
 * - screencast 模式：Chromium 只在内容变化时合成新帧（静态页面几乎不推帧），
 *   因此保留一个低频基线（intervalMs=400，距上次推帧 >300ms 才截），
 *   保证画布在页面静止时也能刷新、反映悬停等状态。
 * - 截图回退模式：无 screencast 时的主推流（250ms 间隔）。
 */
function startFrameLoop(intervalMs = 250, minGapMs = 0) {
  if (state.frameTimer) return;
  state.frameTimer = setInterval(async () => {
    if (!state.running || state.finished || state.capturing || !state.page) return;
    const gap = Date.now() - state.lastFrameTs;
    if (minGapMs > 0 && gap < minGapMs) return;
    state.capturing = true;
    try {
      const shot = await state.page.screenshot({ type: 'jpeg', quality: 60 });
      pushEvent('frame', {
        mime: 'image/jpeg',
        data: shot.toString('base64'),
        w: state.viewport.width,
        h: state.viewport.height,
      });
      state.lastFrameTs = Date.now();
    } catch (e) {
      // 页面可能已被关闭，忽略
    } finally {
      state.capturing = false;
    }
  }, intervalMs);
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
      return `page.getByPlaceholder('${String(locator_value).replace(/'/g, "\\'")}')`;
    case 'text':
      return `page.getByText('${String(locator_value).replace(/'/g, "\\'")}')`;
    case 'role':
      return `page.getByRole('${String(locator_value).replace(/'/g, "\\'")}')`;
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
    if (a.type === 'wait') {
      lines.push(`  await page.waitForTimeout(${Math.round((Number(a.seconds) || 1) * 1000)});`);
      continue;
    }
    // 页面校验断言（URL/标题）不需要元素定位
    if (a.type === 'assert' && (a.mode === 'url' || a.mode === 'title')) {
      const val = String(a.value || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
      lines.push(a.mode === 'url'
        ? `  await expect(page).toHaveURL('${val}');`
        : `  await expect(page).toHaveTitle('${val}');`);
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
          lines.push(`  await expect(page).toHaveURL('${val}');`);
        } else if (a.mode === 'title') {
          lines.push(`  await expect(page).toHaveTitle('${val}');`);
        } else if (a.mode === 'contain_text') {
          lines.push(`  await expect(${loc}).toContainText('${val}');`);
        } else if (a.mode === 'text') {
          lines.push(`  await expect(${loc}).toHaveText('${val}');`);
        } else if (a.mode === 'value') {
          lines.push(`  await expect(${loc}).toHaveValue('${val}');`);
        } else if (a.mode === 'count') {
          lines.push(`  await expect(${loc}).toHaveCount(parseInt('${val}', 10) || 0);`);
        } else if (['visible', 'hidden', 'enabled', 'disabled', 'checked'].includes(a.mode)) {
          lines.push(`  await expect(${loc}).toBe${a.mode.charAt(0).toUpperCase() + a.mode.slice(1)}();`);
        } else if (loc) {
          lines.push(`  await expect(${loc}).toBeVisible();`);
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

let ensureInjectionBusy = false;

/** 校验录制注入脚本是否在页面中生效；未生效则手动补注（导航到新文档后会丢失注入）。 */
async function ensureInjection() {
  if (ensureInjectionBusy || !state.page || !state.context) return;
  ensureInjectionBusy = true;
  try {
    const ok = await state.page.evaluate(() => typeof window.__whart === 'object' && typeof window.__whart.describe === 'function');
    if (!ok) {
      await state.page.evaluate(INIT_SCRIPT);
    }
  } catch (e) {
    serverLog('ensureInjection 异常:', e && e.message ? e.message : String(e));
  } finally {
    ensureInjectionBusy = false;
  }
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
    try {
      await state.context.addInitScript(INIT_SCRIPT);
    } catch (_) {
      // 个别环境下 context 级注入失败，改用页面级 + 兜底补注
    }
    state.page = await state.context.newPage();
    try {
      await state.page.addInitScript(INIT_SCRIPT);
    } catch (_) {}
    state.page.on('framenavigated', (frame) => {
      if (frame === state.page.mainFrame()) {
        recordNavigation(frame.url());
        ensureInjection();
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
  await ensureInjection();
  state.finished = false;
  state.lastFrameTs = 0;
  const streamed = await startFrameStream(state.page);
  if (streamed) {
    // screencast 高帧率 + 截图基线兜底（静态页面也能持续刷新）
    startFrameLoop(400, 300);
  } else {
    startFrameLoop(250, 0);
  }
  return { ok: true, state: { viewport, url: state.startedUrl, frame_mode: state.frameMode, frame_rate: state.frameRate } };
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
      // 输入法组合键（Process/Dead/Unidentified）不产生可输入字符，直接忽略
      if (key === 'Process' || key === 'Unidentified' || key === 'Dead') {
        return { ok: true };
      }
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
    } else if (type === 'text') {
      // 输入法组合完成后的最终文本（compositionend.data），直接插入聚焦元素
      const text = String(params.text || '');
      if (text) {
        await state.page.keyboard.insertText(text);
      }
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: '输入回放失败: ' + (e && e.message ? e.message : String(e)) };
  }
}

// ---------------------------------------------------------------------------
// 前置步骤执行（录制前自动执行可复用页面步骤，如登录）
// ---------------------------------------------------------------------------

/** 按平台执行器同款映射构建 Playwright locator */
function buildLocator(page, selector) {
  if (!selector) return null;
  const type = selector.locator_type || 'xpath';
  const value = String(selector.locator_value || '');
  let loc = null;
  switch (type) {
    case 'xpath':
      loc = page.locator('xpath=' + value);
      break;
    case 'id':
      loc = page.locator('#' + value);
      break;
    case 'name':
      loc = page.locator("[name='" + value + "']");
      break;
    case 'text':
      loc = page.getByText(value);
      break;
    case 'role':
      loc = page.getByRole(value);
      break;
    case 'placeholder':
      loc = page.getByPlaceholder(value);
      break;
    case 'label':
      loc = page.getByLabel(value);
      break;
    default:
      loc = page.locator(value);
  }
  const index = Number(selector.locator_index);
  if (Number.isInteger(index) && index > 1) {
    loc = loc.nth(index - 1);
  }
  return loc;
}

/** 执行一步平台步骤（ope_key 词汇表与执行器对齐），返回错误信息或 null */
async function runOneStep(page, step) {
  const opeKey = String(step.ope_key || '');
  const opeValue = step.ope_value && typeof step.ope_value === 'object' ? step.ope_value : {};
  const inputValue = String(
    opeValue.text || opeValue.value || opeValue.timeout || opeValue.url || opeValue.key || opeValue.expected || ''
  );
  const locator = buildLocator(page, step.element || step.selector);

  if (opeKey === 'goto') {
    await page.goto(inputValue, { waitUntil: 'domcontentloaded', timeout: 30000 });
    return null;
  }
  if (opeKey === 'wait') {
    const ms = parseInt(inputValue, 10);
    await page.waitForTimeout(Number.isFinite(ms) ? ms : 1000);
    return null;
  }
  if (opeKey.startsWith('assert_')) {
    const assertType = opeKey.replace('assert_', '');
    const options = { timeout: 10000 };
    if (assertType === 'visible') await locator.waitFor({ state: 'visible', ...options });
    else if (assertType === 'hidden') await locator.waitFor({ state: 'hidden', ...options });
    else if (assertType === 'enabled') await locator.waitFor({ state: 'attached', ...options });
    else if (assertType === 'text' || assertType === 'contain_text') {
      await locator.waitFor({ state: 'visible', ...options });
      if (inputValue) {
        await locator.filter({ hasText: inputValue }).waitFor({ state: 'visible', ...options });
      }
    }
    else await locator.waitFor({ state: 'visible', ...options });
    return null;
  }
  if (!locator) {
    return '步骤缺少元素定位（' + opeKey + '）';
  }
  switch (opeKey) {
    case 'click':
      await locator.click({ timeout: 15000 });
      return null;
    case 'fill':
      await locator.fill(inputValue);
      return null;
    case 'clear':
      await locator.fill('');
      return null;
    case 'check':
      await locator.check();
      return null;
    case 'uncheck':
      await locator.uncheck();
      return null;
    case 'select':
    case 'select_option':
      await locator.select_option(inputValue);
      return null;
    case 'hover':
      await locator.hover();
      return null;
    case 'press':
      await locator.press(inputValue || 'Enter');
      return null;
    case 'upload':
      return 'upload 步骤请手动录制';
    default:
      return '不支持的操作类型: ' + opeKey;
  }
}

async function cmdAddWait(params) {
  // 在录制位置插入等待动作（0.5s ~ 60s），用于步骤间隔控制
  const seconds = Math.max(0.5, Math.min(60, Number(params && params.seconds) || 3));
  recordAction({ type: 'wait', seconds });
  return { ok: true, state: { action: 'wait' } };
}

async function cmdRemoveAction(params) {
  const seq = Number(params && params.seq);
  if (!Number.isFinite(seq)) {
    return { ok: false, error: '缺少有效的操作序号 seq' };
  }
  const before = state.recorded.length;
  state.recorded = state.recorded.filter((a) => a.seq !== seq);
  const removed = before - state.recorded.length;
  return { ok: true, state: { removed } };
}

async function cmdRunSteps(params) {
  if (!state.page || !state.running) {
    return { ok: false, error: '录制会话未启动' };
  }
  const steps = Array.isArray(params.steps) ? params.steps : [];
  if (!steps.length) {
    return { ok: true, state: { executed: 0, failed: false } };
  }
  // 前置执行期间不记录任何动作/导航
  state.preRunning = true;
  let executed = 0;
  let failedStep = -1;
  let errorMsg = '';
  try {
    for (let i = 0; i < steps.length; i++) {
      try {
        const err = await runOneStep(state.page, steps[i]);
        if (err) {
          failedStep = i;
          errorMsg = err;
          break;
        }
        executed += 1;
        await state.page.waitForTimeout(200);
      } catch (e) {
        failedStep = i;
        errorMsg = '第 ' + (i + 1) + ' 步执行失败: ' + (e && e.message ? e.message : String(e));
        break;
      }
    }
  } finally {
    state.preRunning = false;
    // 前置执行往往会把元素滚动到可视区，并留下焦点与下拉/弹层（popper 为 fixed 定位，
    // 归位后仍悬浮遮挡画面）。结束后统一归位：
    // ① Escape 收起下拉/菜单等弹层；② 滚回顶部；③ 清除焦点；④ 立即推一帧干净画面。
    try {
      await state.page.keyboard.press('Escape');
    } catch (_) {}
    try {
      await state.page.evaluate(() => {
        window.scrollTo(0, 0);
        var ae = document.activeElement;
        if (ae && typeof ae.blur === 'function') ae.blur();
      });
    } catch (_) {}
    try {
      const shot = await state.page.screenshot({ type: 'jpeg', quality: 60 });
      pushEvent('frame', {
        mime: 'image/jpeg',
        data: shot.toString('base64'),
        w: state.viewport.width,
        h: state.viewport.height,
      });
      state.lastFrameTs = Date.now();
    } catch (_) {}
  }
  if (failedStep >= 0) {
    return { ok: false, error: errorMsg, state: { executed, failed_step: failedStep + 1 } };
  }
  return { ok: true, state: { executed, failed: false } };
}

/**
 * 重建干净页面：前置执行结束后调用。
 * 关闭旧页面并在同一上下文新建页面（登录态/cookie 保留），
 * 导航到当前地址并重新建立帧推流——彻底消除滚动/弹层/半渲染等残留.
 */
async function cmdResetPage(params) {
  if (!state.browser || !state.context) {
    return { ok: false, error: '录制会话未启动' };
  }
  const url = (params && params.url) || state.lastNavUrl || state.startedUrl || 'about:blank';
  stopFrameStream();
  try {
    if (state.page) {
      await state.page.close();
    }
    state.page = await state.context.newPage();
    state.page.on('framenavigated', (frame) => {
      if (frame === state.page.mainFrame()) {
        recordNavigation(frame.url());
        ensureInjection();
      }
    });
    await ensureInjection();
  } catch (e) {
    return { ok: false, error: '重建页面失败: ' + (e && e.message ? e.message : String(e)) };
  }
  try {
    await state.page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  } catch (e) {
    serverLog('重建后导航失败:', e && e.message ? e.message : String(e));
  }
  try {
    await state.page.keyboard.press('Escape');
  } catch (_) {}
  try {
    await state.page.evaluate(() => window.scrollTo(0, 0));
  } catch (_) {}
  const streamed = await startFrameStream(state.page);
  if (streamed) {
    startFrameLoop(400, 300);
  } else {
    startFrameLoop(250, 0);
  }
  try {
    const shot = await state.page.screenshot({ type: 'jpeg', quality: 60 });
    pushEvent('frame', {
      mime: 'image/jpeg',
      data: shot.toString('base64'),
      w: state.viewport.width,
      h: state.viewport.height,
    });
    state.lastFrameTs = Date.now();
  } catch (_) {}
  return { ok: true, state: { url: url, page_url: state.page.url() } };
}

// 断言模式分类（与平台执行器 assert_* 词汇表对齐）
const ASSERT_ELEMENT_STATE = ['visible', 'hidden', 'enabled', 'disabled', 'checked'];
const ASSERT_CONTENT = ['text', 'contain_text', 'value', 'count'];
const ASSERT_PAGE = ['url', 'title'];

async function cmdAssert(params) {
  if (!state.page || !state.running) {
    return { ok: false, error: '录制会话未启动' };
  }
  const mode = String(params.mode || 'visible');
  const inputValue = String(params.value || '');

  // 页面校验：断言当前页面 URL / 标题，无需选择元素
  if (mode === 'url') {
    recordAction({ type: 'assert', mode: 'url', value: inputValue || state.page.url() });
    return { ok: true, state: { action: 'assert_url' } };
  }
  if (mode === 'title') {
    if (!inputValue) {
      return { ok: false, error: '请先输入要断言的页面标题' };
    }
    recordAction({ type: 'assert', mode: 'title', value: inputValue });
    return { ok: true, state: { action: 'assert_title' } };
  }

  if (!ASSERT_ELEMENT_STATE.includes(mode) && !ASSERT_CONTENT.includes(mode)) {
    return { ok: false, error: '不支持的断言模式: ' + mode };
  }

  // 内容校验：期望值必填
  if (ASSERT_CONTENT.includes(mode) && !inputValue) {
    return { ok: false, error: '请先输入要校验的内容' };
  }

  try {
    // 优先按坐标定位（断言模式下点击页面元素）；无坐标时回退到悬停元素
    const hasPoint = params.x !== undefined && params.x !== null && params.y !== undefined && params.y !== null;
    let info = null;
    if (hasPoint) {
      info = await state.page.evaluate(([x, y]) => {
        const el = document.elementFromPoint(x, y);
        const w = window.__whart;
        if (!el || !w || !w.describe) return null;
        const sel = w.describe(el);
        if (!sel) return null;
        return {
          selector: sel,
          text: el.textContent ? String(el.textContent).replace(/\s+/g, ' ').trim().slice(0, 60) : '',
        };
      }, [Number(params.x), Number(params.y)]);
      if (!info) {
        return { ok: false, error: '请点击页面上的可断言元素（点击空白处无法断言）' };
      }
    } else {
      info = await state.page.evaluate(() => {
        const w = window.__whart;
        if (!w || !w.describe || !w.hovered) return null;
        const sel = w.describe(w.hovered);
        if (!sel) return null;
        return {
          selector: sel,
          text: w.hovered.textContent ? String(w.hovered.textContent).replace(/\s+/g, ' ').trim().slice(0, 60) : '',
        };
      });
      if (!info) {
        return { ok: false, error: '请先在浏览器画面中把鼠标悬停到要断言的元素上' };
      }
    }
    const value = ASSERT_CONTENT.includes(mode) ? inputValue : '';
    recordAction({ type: 'assert', mode, selector: info.selector, value });
    return { ok: true, state: { action: 'assert_' + mode } };
  } catch (e) {
    return { ok: false, error: '断言记录失败: ' + (e && e.message ? e.message : String(e)) };
  }
}

async function cmdFinish() {
  stopFrameStream();
  stopFrameLoop();
  // 收尾优化：对已录的 xpath 选择器用页面实时 DOM 重新定位，
  // 把绝对路径（/html/body[...]）升级为属性锚点 / 带锚祖先的相对路径。
  await optimizeXpathSelectors();
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

async function cmdSaveLoginState(params) {
  // 保存当前浏览器上下文登录态（storageState：cookies + localStorage）。
  // 一套快照同时覆盖 Cookie/Session 会话系统与 JWT(localStorage) 现代系统，
  // 由平台绑定到当前录制会话所属的环境配置，执行时自动注入复用。
  if (!state.context) {
    return { ok: false, error: '录制会话未启动或已结束' };
  }
  try {
    const snap = await state.context.storageState();
    return { ok: true, state: { storage_state: snap } };
  } catch (e) {
    return { ok: false, error: '保存登录态失败: ' + (e && e.message ? e.message : String(e)) };
  }
}

async function optimizeXpathSelectors() {
  if (!state.page || !state.recorded.length) return;
  for (const action of state.recorded) {
    const sel = action.selector;
    if (!sel || sel.locator_type !== 'xpath' || !sel.locator_value) continue;
    try {
      const improved = await state.page.evaluate((xpath) => {
        const w = window.__whart;
        if (!w || !w.describe || !w.buildXPath) return null;
        let el = null;
        try {
          const res = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
          el = res.singleNodeValue;
        } catch (_) {
          return null;
        }
        if (!el || !(el instanceof Element)) return null;
        // 优先升级为属性/文本/role 定位；否则用带锚相对 xpath
        const d = w.describe(el);
        if (d && d.locator_type !== 'xpath') return d;
        return { locator_type: 'xpath', locator_value: w.buildXPath(el), name: d && d.name ? d.name : sel.name };
      }, sel.locator_value);
      if (improved) {
        action.selector = improved;
      }
    } catch (_) {
      // 页面已跳转等场景下保持原选择器
    }
  }
}

async function cmdClose() {
  stopFrameStream();
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
  // 所有响应必须回显请求 id，Python 侧按 id 配对请求/响应
  const respond = async (result) => send({ id, ...result });
  chain = chain.then(async () => {
    try {
      switch (method) {
        case 'ping':
          return respond(await cmdPing());
        case 'start':
          return respond(await cmdStart(msg.params || {}));
        case 'input':
          return respond(await cmdInput(msg.params || {}));
        case 'run_steps':
          return respond(await cmdRunSteps(msg.params || {}));
        case 'remove_action':
          return respond(await cmdRemoveAction(msg.params || {}));
        case 'add_wait':
          return respond(await cmdAddWait(msg.params || {}));
        case 'reset_page':
          return respond(await cmdResetPage(msg.params || {}));
        case 'assert':
          return respond(await cmdAssert(msg.params || {}));
        case 'save_login_state':
          return respond(await cmdSaveLoginState(msg.params || {}));
        case 'eval': {
          // 调试命令：在页面上下文执行 JS 并返回结果
          const code = String((msg.params && msg.params.code) || '');
          if (!state.page) {
            return respond({ ok: false, error: '录制会话未启动' });
          }
          const val = await state.page.evaluate((c) => {
            try {
              return { ok: true, result: (0, eval)(c) };
            } catch (e) {
              return { ok: false, error: String(e && e.message ? e.message : e) };
            }
          }, code);
          return respond({ ok: true, state: { eval: val } });
        }
        case 'finish':
          return respond(await cmdFinish());
        case 'close': {
          const r = await cmdClose();
          respond(r);
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