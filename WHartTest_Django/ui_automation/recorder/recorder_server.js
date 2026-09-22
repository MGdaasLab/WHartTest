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
 * 动画冻结（RECORDER_FREEZE_ANIMATION，默认开启）：暂停页面上的无限循环动画，
 * 消除动画页持续高频推帧导致的录制画布操作迟缓；有限入场动画不受影响。
 *
 * 录制动作来源：页面注入脚本上报（click/fill/press/check/uncheck）+ 主 frame 导航（goto）+
 * 前端断言命令（assert）。动作点击目标自动生成 UiElement 兼容的选择器
 * （id/name/placeholder/test_id→css/text/role/xpath），主定位 + 两个备用定位
 * （locator_type_2/3，同 xpath 候选链降级），入库后执行器可依次回退。
 * iframe 内元素自动识别：附 is_iframe/iframe_locator（' >> ' 链式定位，支持嵌套），
 * 入库自动打开 iframe 开关；复选框/单选框点击收敛为一次"点击可见 label"。
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
  window.__whart = { hovered: null, describe: null, lastZoneClick: null };

  function cleanText(s, max) {
    return (s || '').replace(/\\s+/g, ' ').trim().slice(0, max || 40);
  }

  function escAttr(v) {
    return String(v).replace(/["']/g, '');
  }

  // 动态 id 识别：框架运行时生成、刷新即变的 id 不能用作定位锚点。
  // 覆盖 Element Plus 各类实例/容器 id（el-id-920-7、el-popper-container-226、
  // el-select-xxx、el-popper-xxx 等）、构建工具前缀、纯数字与长随机串，
  // 以及自动生成的 id（auto-id-<时间戳> 等）与时间戳/序列号尾缀。
  function isDynamicId(id) {
    if (!id) return true;
    if (/^el-[a-z0-9-]+-\d+$/.test(id)) return true;          // Element Plus / 类 EP 运行时 id
    if (/^(vite|webpack|ember|app)-/.test(id)) return true;    // 构建工具前缀
    if (/^\d+$/.test(id)) return true;                          // 纯数字 id（易冲突且常为生成）
    if (id.length >= 24 && id.indexOf('-') >= 0) return true;   // 长随机串
    if (/^auto-[a-z0-9]+-\d+$/.test(id)) return true;           // 自动生成（auto-id-1788148064478）
    if (/-\d{9,}$/.test(id)) return true;                       // 时间戳/序列号尾缀（13 位毫秒等）
    if (/^(random|gen|generated|tmp|temp|uid|uuid)-/.test(id)) return true; // 随机/临时 id 前缀
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

  // 分层锚点：data-testid → 稳定 id → name（表单）→ placeholder（input/textarea/select）→
  // img 的 alt（语义文本）。每个候选都带元素标签且校验唯一，不唯一自动降级。
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
    // img 用 alt（业务语义，可点击图片/logo/图标钮），同样带标签+唯一性校验
    var alt = el.getAttribute('alt');
    if (alt && tag === 'img') {
      var xp5 = anchorXPath(tag, 'alt', alt);
      if (isUniqueXPath(xp5)) return xp5;
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
        if (!tk || isStateClass(tk) || isDynamicClassToken(tk)) continue;
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

  // 节点自身唯一文本语义步：文本在文档中唯一且非子元素聚合时，
  // 用 tag[normalize-space()="文本"] 直接表示该节点。菜单项（容器 li 承载
  // 可见文本）是典型场景——同级增删 li、子菜单展开收起都不影响文本锚点，
  // 比兄弟锚点/下标计数更稳；聚合文本（el-submenu 等）按 textAnchor 同规则排除。
  function uniqueNodeText(node) {
    var tag = node.tagName ? node.tagName.toLowerCase() : '';
    if (!tag) return null;
    var text = cleanText(node.textContent, 30);
    if (!text || text.length < 1 || text.length > 30) return null;
    if (node.children && node.children.length) {
      for (var i = 0; i < node.children.length; i++) {
        var cText = cleanText(node.children[i].textContent, 40);
        if (cText && cText !== text) return null;
      }
    }
    try {
      var matched = Array.prototype.filter.call(document.querySelectorAll(tag), function (n) {
        return cleanText(n.textContent, 40) === text;
      });
      if (matched.length === 1) {
        var pred = '[normalize-space()="' + text.replace(/["']/g, '') + '"]';
        // 用绝对形式校验唯一性，返回相对步（与前段路径拼接）
        return isUniqueXPath('//' + tag + pred) ? tag + pred : null;
      }
    } catch (_) {}
    return null;
  }

  // 兄弟锚点相对定位：同级节点（先前向后向，各 ≤5 跳）中找带唯一锚点
  // （属性/文本/短文本/唯一 class）的兄弟，用 following-sibling::tag[k] /
  // preceding-sibling::tag[k] 语义步代替纯 tag[n] 序号——页面插入节点时
  // 锚点兄弟的相对位置不变，比纯序号抗页面微调；序号仅作最后兜底。
  function siblingAnchor(n) {
    if (!n || n.nodeType !== 1) return null;
    return pickAnchor(n) || textAnchor(n) || looseTextAnchor(n) || selfClassAnchor(n);
  }

  // from 与 to 之间（不含两端）与 tag 同标签的元素个数
  function countSameTagBetween(from, to, tag) {
    var n = 0;
    var cur = from.nextElementSibling;
    while (cur && cur !== to) {
      if (cur.tagName && cur.tagName.toLowerCase() === tag) n++;
      cur = cur.nextElementSibling;
    }
    return n;
  }

  function siblingStep(node) {
    var tag = node.tagName ? node.tagName.toLowerCase() : '';
    if (!tag || !node.parentElement) return null;
    for (var pass = 0; pass < 2; pass++) {
      var backward = pass === 0;  // 前向（previousElementSibling 方向）优先
      var sib = backward ? node.previousElementSibling : node.nextElementSibling;
      var hops = 0;
      while (sib && hops < 5) {
        var anchor = siblingAnchor(sib);
        if (anchor) {
          var k = countSameTagBetween(sib, node, tag) + 1;
          var dir = backward ? 'following-sibling' : 'preceding-sibling';
          // 锚点是文档级绝对 xpath，去掉 // 前缀转为相对步与前段路径拼接
          return anchor.replace(/^\/\//, '') + '/' + dir + '::' + tag + '[' + k + ']';
        }
        sib = backward ? sib.previousElementSibling : sib.nextElementSibling;
        hops++;
      }
    }
    return null;
  }

// 从 ancestor 到 el 的相对路径（不含 ancestor 自身）；
// 每层用 tag[n] 序号步（不引入轴步——轴依赖兄弟顺序，折叠菜单最易错位）。
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
      var step = '/' + node.tagName.toLowerCase() + '[' + idx + ']';
      parts.unshift(step);
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

  // 构建产物/哈希类名识别：Vue scoped（v-xxxxxx）、CSS Modules（css-xxxxx / _name_hash）、
  // 纯字母数字长哈希。此类名当前构建恰好唯一（可通过唯一性校验），但每次构建变化，
  // 代码更新即失效；el-select__input、el-button--primary 等稳定类不受影响。
  function isDynamicClassToken(token) {
    if (/^v-[0-9a-f]{4,}$/i.test(token)) return true;              // Vue scoped（v-029384a）
    if (/^css-[a-zA-Z0-9]{5,}$/.test(token)) return true;          // CSS Modules（css-1a2b3c）
    // CSS Modules 局部类（_nav_abc123_7）：_名称_哈希，哈希段 ≥4 位且含数字（哈希可含 _/-）
    if (/^_[a-zA-Z0-9]+_(?=[a-zA-Z0-9_]*\d)[a-zA-Z0-9_]{4,}$/.test(token)) return true;
    // 其余纯字母数字混杂长串视为哈希（8 位起，同时含字母与数字）
    if (/^[a-zA-Z0-9]{8,}$/.test(token) && /[A-Za-z]/.test(token) && /[0-9]/.test(token)) return true;
    return false;
  }

  // 某 class token 是否在文档中唯一且非状态/非构建哈希类（可安全用作锚点）
  function isUniqueClassToken(token) {
    if (isStateClass(token)) return false;
    if (isDynamicClassToken(token)) return false;
    try {
      return document.querySelectorAll('[class~="' + token.replace(/["\\]/g, '') + '"]').length === 1;
    } catch (_) {
      return false;
    }
  }

  // 角色+文本 xpath 锚点：仅当该（标签+精确文本）在文档中唯一时使用。
  // 覆盖按钮/链接/标签、下拉项及文本载体（li/option/td/span 等），
  // 下拉选择项用文本定位最稳定；文本不唯一时自动降级，避免歧义。
  // 聚合文本排除：子元素携带与自身不同的文本（如 el-submenu 的 li 聚合了
  // 标题+全部子菜单项文本，展开/收起即变）不作为锚点；同文本子元素
  // （如 按钮>span）不构成聚合，仍可用。
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
    if (el.children && el.children.length) {
      for (var i = 0; i < el.children.length; i++) {
        var cText = cleanText(el.children[i].textContent, 40);
        if (cText && cText !== text) return null;
      }
    }
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
  // 与 textAnchor 同规则排除聚合文本（子元素携带不同文本）——
  // 否则 el-submenu 的 li（标题+子项拼接）展开/收起时文本变化，
  // 录制态与执行态的锚点会失配。
  function looseTextAnchor(el) {
    var text = cleanText(el.textContent, 16);
    if (!text || text.length < 1 || text.length > 15) return null;
    if (el.children && el.children.length) {
      for (var i = 0; i < el.children.length; i++) {
        var cText = cleanText(el.children[i].textContent, 20);
        if (cText && cText !== text) return null;
      }
    }
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

  // ---------------------------------------------------------------------------
  // 四梯队元素表达式提取（候选全部校验唯一后按梯队排序）：
  //   T1 唯一标识：data-testid / 语义化稳定 id（动态 id 由 isDynamicId 过滤）
  //   T2 业务属性：可见文本（按钮/链接等）、input 的 name/placeholder、img 的 alt
  //   T3 CSS 类名组合：语义化 class（状态类/框架动态类被黑名单过滤）、父容器>子级组合
  //   T4 XPath 轴/结构：兄弟轴、相对路径、contains 模糊匹配
  //   兜底：绝对路径 xpath（/html/body/...）
  // 每个候选为 {type, value}：type 是平台 locator_type 词汇（css/text/role/xpath/...），
  // 执行端（执行器 _get_locator / 录制器 buildLocator）均原生支持。
  // ---------------------------------------------------------------------------

  // 唯一性校验（xpath 与 css 通用）
  function isUniqueCss(sel) {
    try {
      return document.querySelectorAll(sel).length === 1;
    } catch (_) {
      return false;
    }
  }

  // T1：data-testid → css [data-testid="x"]（Playwright 原生语义）
  function testIdCandidate(el) {
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    var testId = el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-test-id');
    if (!testId) return null;
    var sel = tag + '[data-testid="' + testId + '"]';
    return isUniqueCss(sel) ? { type: 'css', value: sel } : null;
  }

  // T1：语义化稳定 id → css #id（id 含特殊字符时转义，非法则放弃）
  function idCandidate(el) {
    var id = el.getAttribute('id');
    if (!id || isDynamicId(id)) return null;
    if (!/^[A-Za-z][\w-]*$/.test(id)) return null;  // 非 CSS 安全 id 不硬转义，直接走后续梯队
    var sel = '#' + id;
    return isUniqueCss(sel) ? { type: 'css', value: sel } : null;
  }

  // T2：input/textarea/select 的 placeholder → getByPlaceholder
  // 注意：getByPlaceholder 匹配所有带 placeholder 属性的元素（含组件库挂在
  // 包装 div 上的），唯一性检查必须按属性全量统计，否则回放即 strict 冲突。
  function placeholderCandidate(el) {
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    var ph = el.getAttribute('placeholder');
    if (!ph || (tag !== 'input' && tag !== 'textarea' && tag !== 'select')) return null;
    try {
      var n = document.querySelectorAll('[placeholder="' + ph.replace(/"/g, '\\"') + '"]').length;
      return n === 1 ? { type: 'placeholder', value: ph } : null;
    } catch (_) {
      return null;
    }
  }

  // T2：表单元素 name → css [name="x"]
  function nameCandidate(el) {
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    var name = el.getAttribute('name');
    if (!name) return null;
    var sel = tag + '[name="' + name + '"]';
    return isUniqueCss(sel) ? { type: 'css', value: sel } : null;
  }

  // T2：img 的 alt → css img[alt="x"]
  function altCandidate(el) {
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    var alt = el.getAttribute('alt');
    if (!alt || tag !== 'img') return null;
    var sel = 'img[alt="' + alt + '"]';
    return isUniqueCss(sel) ? { type: 'css', value: sel } : null;
  }

  // T3：语义化 class（单个稳定 token）→ css .token 或 tag.token
  function semanticClassCandidate(el) {
    var cls = el.getAttribute && el.getAttribute('class');
    if (typeof cls !== 'string' || !cls.trim()) return null;
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    var tokens = cls.trim().split(/\s+/);
    // 优先语义化 token（含 - 或 __ 的 BEM 风格类，如 login-btn/el-input__inner），
    // 再试其余非动态/非状态 token
    tokens.sort(function (a, b) {
      var sa = /-|__/.test(a) ? 0 : 1, sb = /-|__/.test(b) ? 0 : 1;
      return sa - sb;
    });
    for (var i = 0; i < tokens.length; i++) {
      var tk = tokens[i];
      if (!tk || !isUniqueClassToken(tk)) continue;
      var sel = '.' + tk.replace(/([:.#\\\s])/g, '\\$1');
      if (!isUniqueCss(sel)) continue;
      // 单类在文档唯一时输出 .token；否则 tag.token 收窄
      return { type: 'css', value: sel };
    }
    return null;
  }

  // T3：父级语义容器 > 子级组合定位（缩小查找范围的组合 css）
  function containerComboCandidate(el) {
    var tag = el.tagName ? el.tagName.toLowerCase() : '';
    var node = el;
    for (var hop = 0; hop < 4 && node; hop++) {
      node = node.parentElement;
      if (!node || node === document.body) break;
      var cls = (node.getAttribute && node.getAttribute('class')) || '';
      var tokens = cls.trim().split(/\s+/);
      for (var i = 0; i < tokens.length; i++) {
        var tk = tokens[i];
        if (!tk || isStateClass(tk) || isDynamicClassToken(tk)) continue;
        var containerSel = '.' + tk;
        if (!isUniqueCss(containerSel)) continue;
        // 容器内定位子元素：tag 优先，容器内唯一即用；否则用自身语义 class
        var childTag = tag;
        var inner = containerSel + ' > ' + childTag;
        if (isUniqueCss(inner)) return { type: 'css', value: inner };
        var ownCls = (el.getAttribute && el.getAttribute('class')) || '';
        var ownTokens = ownCls.trim().split(/\s+/);
        for (var j = 0; j < ownTokens.length; j++) {
          if (!ownTokens[j] || isStateClass(ownTokens[j]) || isDynamicClassToken(ownTokens[j])) continue;
          var combo = containerSel + ' > ' + childTag + '.' + ownTokens[j].replace(/([:.#\\\s])/g, '\\$1');
          if (isUniqueCss(combo)) return { type: 'css', value: combo };
        }
      }
    }
    return null;
  }

  // 生成元素表达式候选（四梯队降级，全部校验唯一后按梯队排序收集）：
  // T1 唯一标识：data-testid → css / 语义化稳定 id → css #id（动态 id 黑名单过滤）
  // T2 业务属性：可见文本（按钮/链接等 → text/xpath 文本锚点）、input name/placeholder、
  //    img alt（均原生 locator 类型，语义明确）
  // T3 CSS 类名组合：自身语义 class（状态类/构建哈希类黑名单过滤）、父语义容器>子级组合
  // T4 XPath 轴/结构：兄弟轴语义步、祖先锚点+相对路径、contains 模糊匹配
  // 兜底：绝对路径 xpath（/html/body/...，页面微调即崩，仅最后手段）
  // 输出首位为主定位，第 2/3 位作为备用定位（执行器按 主→备1→备2 依次尝试）。
  function buildCandidates(el) {
    var out = [];
    function add(cand) {
      if (cand && cand.value) {
        for (var i = 0; i < out.length; i++) {
          if (out[i].type === cand.type && out[i].value === cand.value) return;
        }
        out.push(cand);
      }
    }

    // ---- T1 唯一标识 ----
    add(testIdCandidate(el));
    add(idCandidate(el));

    // ---- T2 业务属性 ----
    // 文本内容（按钮/链接/标签/菜单项等，含子元素文本与短文本变体）
    var textSelf = textAnchor(el);
    if (textSelf) add({ type: 'xpath', value: textSelf });
    var childText = childTextAnchor(el);
    if (childText) add({ type: 'xpath', value: childText });
    // 表单属性：placeholder / name / img alt
    add(placeholderCandidate(el));
    add(nameCandidate(el));
    add(altCandidate(el));

    // ---- T3 CSS 类名组合 ----
    var semanticCls = semanticClassCandidate(el);
    if (semanticCls) add(semanticCls);
    var combo = containerComboCandidate(el);
    if (combo) add(combo);

    // ---- T4 XPath 轴/结构（相对路径回溯 + 兄弟轴） ----
    var self = pickAnchor(el);
    var selfClass = selfClassAnchor(el);
    var selectBox = selectBoxAnchor(el);
    if (selectBox) add({ type: 'xpath', value: selectBox });

    // 结构路径：完整回溯到 body（不限层数）——截断的路径在真实 DOM 中不存在，
    // 宁长勿断；途中每个唯一锚点祖先都短路收集为相对路径候选（近的先收）。
    // 每层节点：① 节点自身唯一文本步（菜单项，抗同级增删）；② 祖先属性/文本锚点短路；
    // ③ 兄弟锚点语义步（轴）；④ 下标兜底。
    var parts = [];
    var node = el;
    while (node && node.nodeType === 1 && node !== document.documentElement) {
      // 当前节点自身唯一文本 → 优先（不依赖兄弟顺序）
      var step = uniqueNodeText(node);
      if (!step) {
        var idx = 1;
        var sib = node.previousElementSibling;
        while (sib) {
          if (sib.tagName === node.tagName) idx++;
          sib = sib.previousElementSibling;
        }
        step = node.tagName.toLowerCase() + '[' + idx + ']';
      }
      parts.unshift(step);
      var parent = node.parentElement;
      if (!parent || parent.nodeType !== 1 || parent === document.documentElement || parent === document.body) {
        break;
      }
      var anchor = pickAnchor(parent);
      if (anchor) add({ type: 'xpath', value: anchor + '/' + parts.join('/') });
      // 祖先文本锚点短路：折叠菜单项（li 等）文本唯一——绝对文本锚点不依赖展开状态
      var parentTextAnchor = textAnchor(parent);
      if (parentTextAnchor) add({ type: 'xpath', value: parentTextAnchor + '/' + parts.join('/') });
      var cls = parent.getAttribute && parent.getAttribute('class');
      if (typeof cls === 'string' && cls.trim()) {
        var tokens = cls.trim().split(/\s+/);
        for (var i = 0; i < tokens.length; i++) {
          var tk = tokens[i];
          if (tk && isUniqueClassToken(tk)) {
            var cand = '//*[contains(@class,"' + tk.replace(/["\\]/g, '') + '")]/' + parts.join('/');
            if (isUniqueXPath(cand)) {
              add({ type: 'xpath', value: cand });
              break;
            }
          }
        }
      }
      node = parent;
    }
    // 兜底前最后一次机会：短文本唯一锚点（动态容器内的文本项）
    var loose = looseTextAnchor(el);
    if (loose) add({ type: 'xpath', value: loose });
    // 兜底：完整绝对路径（含 body 层级），唯一性由 index 链保证
    if (parts.length) add({ type: 'xpath', value: '/html/body/' + parts.join('/') });
    return out;
  }

  function buildXPath(el) {
    var cands = buildCandidates(el);
    // 兼容旧调用（hover 高亮等只需要字符串）：取首位候选的表达式
    return cands.length ? cands[0].value : null;
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
    if (tag === 'LABEL' && el.querySelector) {
      // 复选/单选组件的 label 容器（EP: label.el-checkbox / label.el-radio）
      if (el.querySelector('input[type="checkbox"]')) return '复选框';
      if (el.querySelector('input[type="radio"]')) return '单选框';
    }
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
    // 四梯队候选链（typed：css/text/role/xpath 原生类型）：
    // 首位为主定位，第 2/3 位写入备用定位（locator_type_2/3），
    // 执行时主定位失效自动回退。locator_type 随候选真实类型输出，
    // 执行端（执行器/录制器回放）原生支持这些类型。
    var cands = buildCandidates(el);
    var first = cands.length ? cands[0] : { type: 'xpath', value: '' };
    var out = {
      locator_type: first.type,
      locator_value: first.value,
      name: name.slice(0, 24),
      ctrl_type: ctrlType,
    };
    if (cands.length > 1) {
      out.locator_type_2 = cands[1].type;
      out.locator_value_2 = cands[1].value;
    }
    if (cands.length > 2) {
      out.locator_type_3 = cands[2].type;
      out.locator_value_3 = cands[2].value;
    }
    return out;
  }

  window.__whart.describe = describe;
  window.__whart.buildXPath = buildXPath;

  // 复选框/单选框的"可见点击目标"：浏览器会为 label 关联的隐藏原生 input
  // 补发一次 click，随后 change 事件再报一次 check/uncheck——EP 等组件库的
  // 原始 input（el-checkbox__original / el-radio__original）被 CSS 隐藏
  // （宽高 0/opacity 0），原样录制会得到 点击视觉层/点击隐藏input/勾选input
  // 三个动作，其中隐藏 input 回放时"不可见"必失败。统一收敛为一次
  // "点击可见 label（无 label 时用 input 自身）"，回放即完成勾选。
  function checkboxZoneTarget(el) {
    if (!el || el.nodeType !== 1 || !el.closest) return null;
    var t = (el.getAttribute && el.getAttribute('type')) || '';
    if (el.tagName === 'INPUT' && (t === 'checkbox' || t === 'radio')) {
      var lab = el.closest('label');
      return lab || el;
    }
    var lab = el.closest('label');
    if (lab && lab.querySelector &&
        lab.querySelector('input[type="checkbox"], input[type="radio"]')) {
      return lab;
    }
    return null;
  }

  document.addEventListener('pointermove', function (e) {
    if (e.target && e.target.nodeType === 1) {
      window.__whart.hovered = e.target;
    }
  }, true);

  document.addEventListener('click', function (e) {
    var el = e.target;
    if (!el || el.nodeType !== 1) return;
    // 复选框/单选框：收敛为点击可见 label 的单动作
    var zone = checkboxZoneTarget(el);
    if (zone) {
      var dz = window.__whart.describe(zone);
      if (!dz) return;
      var zsel = JSON.stringify(dz);
      var znow = Date.now();
      // 同 zone 的合成 click（label→隐藏 input）与键盘空格触发只录一次
      if (window.__whart.lastZoneClick && window.__whart.lastZoneClick.sel === zsel &&
          znow - window.__whart.lastZoneClick.ts < 250) return;
      window.__whart.lastZoneClick = { sel: zsel, ts: znow };
      if (window.__whartReport) {
        window.__whartReport({ t: 'click', el: dz });
      }
      return;
    }
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
        // 点击已收敛录制（勾选动作由可见 label 的 click 承担）时不再重复报
        var zone = checkboxZoneTarget(el);
        if (zone) {
          var zsel = JSON.stringify(window.__whart.describe(zone));
          var znow = Date.now();
          if (window.__whart.lastZoneClick && window.__whart.lastZoneClick.sel === zsel &&
              znow - window.__whart.lastZoneClick.ts < 1000) {
            return;
          }
        }
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
// 动画冻结（RECORDER_FREEZE_ANIMATION，默认开启）
//
// 动画页使录制画布操作全面迟缓，两类来源分别处理：
// 1. CSS/WAAPI 无限循环动画（轮播等）：Web Animations API 逐个暂停。
// 2. requestAnimationFrame 自持续动画循环（canvas 渐变/粒子背景、GSAP ticker
//    等）：不走 CSS 动画体系，getAnimations() 拿不到；实测登录页渐变 canvas
//    循环使 mouse.move 延迟从 17ms 恶化到 130ms+。以"同一回调引用持续被调度
//    超过 1.5s"判定为动画循环，命中后降频为每秒 1 帧——主线程立即释放，
//    screencast 趋于停推，低频重绘保持画面内容。5s 空闲解除仅覆盖误判的
//    外部事件回调（如滚动节流）；真动画循环被代重注册维持活跃，保持降频。
//
// 有限入场动画（淡入/JS 补间等）在判据窗口内已播完、回调停止被调度，不受
// 影响，不会停在中间帧；元素定位不受冻结影响。
// 脚本随 addInitScript 注入每个文档（含 iframe），无外部依赖。
// ---------------------------------------------------------------------------

const FREEZE_ANIMATION_SCRIPT = () => {
  if (window.__whartFreeze) return;
  window.__whartFreeze = true;

  // ---- 1. CSS/WAAPI 无限循环动画暂停 ----
  function pauseInfiniteAnimations() {
    if (!document.getAnimations) return;
    var anims;
    try {
      anims = document.getAnimations();
    } catch (_) {
      return;
    }
    anims.forEach(function (anim) {
      try {
        // effect.getComputedTiming().iterations：CSS/WAAPI 动画为数字；
        // 无 effect 或读数失败时保守跳过（如 CSS transition，本身有限时长）
        var effect = anim.effect;
        var timing = effect && effect.getComputedTiming && effect.getComputedTiming();
        if (timing && timing.iterations === Infinity && anim.playState === 'running') {
          anim.pause();
        }
      } catch (_) {}
    });
  }

  // ---- 2. rAF 自持续循环降频 ----
  // 判据：同一回调引用持续被调度超过 FREEZE_CONFIRM_MS（1.5s）仍活跃——
  // 覆盖 CSS/WAAPI 拿不到的 JS 驱动动画（canvas 渐变/粒子背景、GSAP ticker 等）。
  // 不用"1 秒内命中 N 次"的速率判据：有限入场动画（0.3~1s 的 JS 弹簧/补间）
  // 同样高速调度但应完整播完，速率判据会把它们拦腰暂停、元素停在中间态。
  // 持续时长判据下有限动画早已播完（回调不再被调度），只有真正的循环会命中。
  // 长时间（FREEZE_IDLE_MS）不再被调度则自动解除并清理，滚动监听等复用
  // 同一引用的节流回调即便偶发误判也会在下轮空闲后恢复正常。
  var origRaf = window.requestAnimationFrame ? window.requestAnimationFrame.bind(window) : null;
  if (origRaf) {
    var FREEZE_CONFIRM_MS = 1500;   // 持续调度多久判定为动画循环
    var FREEZE_THROTTLE_MS = 1000;  // 命中后回调执行间隔（1fps）
    var FREEZE_IDLE_MS = 5000;      // 持续多久不被调度后解除降频并清理
    var cbStats = new Map();
    window.requestAnimationFrame = function (cb) {
      return origRaf(function (t) {
        var now = Date.now();
        var st = cbStats.get(cb);
        if (!st) {
          st = { firstAt: now, lastAt: now, throttled: false, lastRun: 0 };
          cbStats.set(cb, st);
        }
        // 调度断裂（距上次超过确认窗口）视为新一轮：外部事件驱动的 rAF
        // （滚动监听等）间歇触发不会因累计跨窗口被误判为持续动画循环
        if (!st.throttled && now - st.lastAt >= FREEZE_CONFIRM_MS) {
          st.firstAt = now;
        }
        st.lastAt = now;
        if (st.throttled) {
          // 降频窗口外放行一帧；窗口内跳过。自循环动画靠"回调内再次注册 rAF"
          // 存活，跳过帧不执行回调会导致循环饿死，因此由 wrapper 代为重注册，
          // 保证到点后仍有帧可放行。
          if (now - st.lastRun >= FREEZE_THROTTLE_MS) {
            st.lastRun = now;
            cb(t);
          } else {
            origRaf(function (t2) { window.requestAnimationFrame(cb); });
          }
          return;
        }
        if (now - st.firstAt >= FREEZE_CONFIRM_MS) {
          st.throttled = true;
          st.lastRun = now;
        }
        cb(t);
      });
    };
    setInterval(function () {
      var now = Date.now();
      cbStats.forEach(function (st, cb) {
        if (now - st.lastAt >= FREEZE_IDLE_MS) cbStats.delete(cb);
      });
    }, FREEZE_IDLE_MS);
  }

  pauseInfiniteAnimations();
  setInterval(pauseInfiniteAnimations, 1000);
};

/** 每文档冻结注入：addInitScript 在文档脚本执行前注入，随导航/iframe 自动生效。 */
async function attachFreezeAnimation(context, page) {
  if (!state.freezeAnimation) return;
  try {
    await context.addInitScript(FREEZE_ANIMATION_SCRIPT);
  } catch (_) {}
  try {
    await page.addInitScript(FREEZE_ANIMATION_SCRIPT);
  } catch (_) {}
}

// ---------------------------------------------------------------------------
// 录制状态
// ---------------------------------------------------------------------------

const state = {
  browser: null,
  context: null,
  page: null,
  cdpSession: null,
  frameMode: 'screencast',   // screencast（推流）| screenshot（截图回退）
  viewport: { width: 1400, height: 900 },
  // 目标帧率默认 25fps：录制画布只需"看清楚"，动画页 60fps 会产生巨量
  // JPEG 编码+WS 传输压力，反压输入转发造成操作迟缓。可用 RECORDER_FRAME_RATE 调整。
  frameRate: Math.max(1, Math.min(60, parseInt(process.env.RECORDER_FRAME_RATE || '25', 10) || 25)),
  // 推流缩放比例（0.1~1，默认 1=原生分辨率）。<1 时 CDP 按比例缩小推流帧，
  // 省带宽；浏览器页面本身仍按 viewport 原生分辨率渲染，录制动作定位不受影响。
  frameScale: (() => {
    const s = parseFloat(process.env.RECORDER_FRAME_SCALE || '1');
    return Number.isFinite(s) ? Math.min(1, Math.max(0.1, s)) : 1;
  })(),
  // 动画冻结开关：默认开启，暂停无限循环动画（帧流过载的主要来源）。
  // 设 RECORDER_FREEZE_ANIMATION=false 可关闭（如需观察动画本身的表现）。
  freezeAnimation: (process.env.RECORDER_FREEZE_ANIMATION || 'true').toLowerCase() !== 'false',
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
  tracePath: null,         // 执行 trace.zip 落盘路径（start_trace 设置，stop_trace 消费）
  pageErrors: [],          // 页面 JS 错误（pageerror 事件，执行日志展示用）
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

// iframe 元素定位链：从目标 frame 逐层向上到主 frame，每层用父文档的
// buildXPath 生成 iframe 元素的相对 xpath，以 ' >> ' 连接（执行器
// page.frame_locator 链式语法，支持嵌套 iframe）。返回 null 表示不在 iframe 内。
async function buildIframeChain(frame) {
  const parts = [];
  let f = frame;
  while (f && f !== state.page.mainFrame()) {
    const handle = await f.frameElement().catch(() => null);
    if (!handle) return null;
    const xp = await handle
      .evaluate((el) => {
        const w = window.__whart;
        if (!w || !w.buildXPath) return '';
        return w.buildXPath(el);
      })
      .catch(() => '');
    if (!xp) return null;
    // 绝对路径兜底（/html/body/...）转为 // 前缀：frame_locator 只认 // 或 xpath=，
    // 单斜杠开头会被当 CSS 解析而失败（执行器逐段 frame_locator(part) 下钻）
    parts.unshift(xp[0] === '/' && xp[1] !== '/' ? '/' + xp : xp);
    f = await handle.ownerFrame();  // ownerFrame 为异步 API，漏 await 会拿到 Promise
  }
  return parts.length ? parts.join(' >> ') : null;
}

async function handleReport(payload, frame) {
  if (!state.running || state.preRunning || !payload || !payload.t) return;
  // iframe 内元素：自动识别并附带 iframe 定位链，入库时填充 is_iframe/iframe_locator。
  // 元素表达式保持最内层 frame 文档相对（执行器先 frame_locator 进 frame 再定位）。
  if (payload.el && frame && !frame.isDetached() && frame !== state.page.mainFrame()) {
    try {
      const chain = await buildIframeChain(frame);
      if (chain) {
        payload.el.is_iframe = true;
        payload.el.iframe_locator = chain;
      }
    } catch (e) {
      serverLog('iframe 定位链生成失败:', e && e.message ? e.message : String(e));
    }
  }
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
      quality: parseInt(process.env.RECORDER_JPEG_QUALITY || '50', 10) || 50,
      maxWidth: Math.round(state.viewport.width * state.frameScale),
      maxHeight: Math.round(state.viewport.height * state.frameScale),
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
      const shot = await state.page.screenshot({
        type: 'jpeg',
        quality: parseInt(process.env.RECORDER_JPEG_QUALITY || '50', 10) || 50,
      });
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
  // iframe 元素：生成 frameLocator 链式调用（page.frameLocator('...')...）
  let container = 'page';
  if (selector.is_iframe && selector.iframe_locator) {
    container = String(selector.iframe_locator)
      .split(' >> ')
      .map((s) => s.trim())
      .filter(Boolean)
      .map((p) => `.frameLocator('${p.replace(/'/g, "\\'")}')`)
      .join('');
    container = 'page' + container;
  }
  switch (locator_type) {
    case 'xpath':
      return `${container}.locator('xpath=${String(locator_value).replace(/'/g, "\\'")}')`;
    case 'id':
      return `${container}.locator('#${String(locator_value).replace(/"/g, '')}')`;
    case 'name':
      return `${container}.locator("[name='${String(locator_value).replace(/'/g, "\\'")}']")`;
    case 'placeholder':
      return `${container}.getByPlaceholder('${String(locator_value).replace(/'/g, "\\'")}')`;
    case 'text':
      return `${container}.getByText('${String(locator_value).replace(/'/g, "\\'")}')`;
    case 'role':
      return `${container}.getByRole('${String(locator_value).replace(/'/g, "\\'")}')`;
    default:
      return `${container}.locator('${String(locator_value).replace(/'/g, "\\'")}')`;
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
    if (a.type === 'upload') {
      // 文件存在于平台文件管理，脚本中仅标注占位，执行时以平台 file_id 解析
      lines.push(`  // TODO upload: file_id=${String(a.file_id || '')} ${a.file_name || ''}`.trim());
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

/** 构建浏览器上下文参数：视口 + 可选登录态快照（storageState） */
function buildContextOptions(viewport, storageState) {
  const opts = { viewport };
  if (storageState) {
    opts.storageState = storageState;
  }
  return opts;
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
    state.context = await state.browser.newContext(buildContextOptions(viewport, params.storage_state));
    await state.context.exposeBinding('__whartReport', (source, payload) => handleReport(payload, source.frame));
    try {
      await state.context.addInitScript(INIT_SCRIPT);
    } catch (_) {
      // 个别环境下 context 级注入失败，改用页面级 + 兜底补注
    }
    state.page = await state.context.newPage();
    try {
      await state.page.addInitScript(INIT_SCRIPT);
    } catch (_) {}
    await attachFreezeAnimation(state.context, state.page);
    attachPageDiagnostics(state.page);
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

// 输入事件串行执行队列：输入立即 ack，后台按序回放。
// 动画复杂的页面单次 mouse.move 可能阻塞数百毫秒，若同步 await 会拖慢
// 事件接收节奏（前端→Node 串行排队），表现为鼠标/点击/输入全面迟缓。
// 排队深度设上限：积压超过阈值时丢弃最老的移动事件（保点击/键入优先）。
const inputQueue = [];
const INPUT_QUEUE_MAX = 24;
let inputDraining = false;

function enqueueInput(params) {
  // 移动事件可合并：队列里已有未执行的 move 就地覆盖坐标（永不增加延迟）
  if (params.type === 'mouse' && params.event === 'move') {
    const pendingMove = inputQueue.findLast
      ? inputQueue.findLast((p) => p.type === 'mouse' && p.event === 'move')
      : null;
    if (pendingMove) {
      pendingMove.x = Number(params.x) || 0;
      pendingMove.y = Number(params.y) || 0;
      return { ok: true };
    }
    // 满载时优先丢弃队首的老 move，给新事件腾位
    if (inputQueue.length >= INPUT_QUEUE_MAX) {
      const oldMoveIdx = inputQueue.findIndex((p) => p.type === 'mouse' && p.event === 'move');
      if (oldMoveIdx >= 0) inputQueue.splice(oldMoveIdx, 1);
      else inputQueue.shift();
    }
    inputQueue.push(params);
    drainInputQueue();
    return { ok: true };
  }
  if (inputQueue.length >= INPUT_QUEUE_MAX) inputQueue.shift();
  inputQueue.push(params);
  drainInputQueue();
  return { ok: true };
}

async function drainInputQueue() {
  if (inputDraining || !state.page) return;
  inputDraining = true;
  try {
    while (inputQueue.length > 0) {
      const params = inputQueue.shift();
      try {
        await applyInput(params);
      } catch (e) {
        serverLog('输入回放失败:', e && e.message ? e.message : String(e));
      }
    }
  } finally {
    inputDraining = false;
  }
}

async function applyInput(params) {
  const type = params.type;
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
      return;
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
}

async function cmdInput(params) {
  if (!state.page || !state.running) {
    return { ok: false, error: '录制会话未启动' };
  }
  // 立即 ack、后台按序回放：前端输入不被页面阻塞反压
  return enqueueInput(params);
}

// ---------------------------------------------------------------------------
// 前置步骤执行（录制前自动执行可复用页面步骤，如登录）
// ---------------------------------------------------------------------------

/** 页面诊断挂钩：采集页面 JS 错误（执行日志展示，与执行器 _page_errors 对齐） */
function attachPageDiagnostics(page) {
  try {
    page.on('pageerror', (err) => {
      const msg = String((err && err.message) || err || 'undefined');
      state.pageErrors.push(msg.slice(0, 200));
      if (state.pageErrors.length > 20) state.pageErrors.shift();
    });
  } catch (_) {}
}

function _guessMimeType(name) {
  const ext = String(name).split('.').pop().toLowerCase();
  const map = {
    txt: 'text/plain', csv: 'text/csv', json: 'application/json', xml: 'application/xml',
    pdf: 'application/pdf', doc: 'application/msword',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    xls: 'application/vnd.ms-excel',
    xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ppt: 'application/vnd.ms-powerpoint',
    pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    zip: 'application/zip', rar: 'application/vnd.rar', '7z': 'application/x-7z-compressed',
    png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif',
    bmp: 'image/bmp', svg: 'image/svg+xml', webp: 'image/webp',
    mp4: 'video/mp4', mov: 'video/quicktime', mp3: 'audio/mpeg', wav: 'audio/wav',
  };
  return map[ext] || 'application/octet-stream';
}

/** 按平台执行器同款映射构建 Playwright locator（支持 iframe 链式定位） */
function _locatorFromParts(container, type, value) {
  let loc = null;
  switch (type) {
    case 'xpath':
      loc = container.locator('xpath=' + value);
      break;
    case 'id':
      loc = container.locator('#' + value);
      break;
    case 'name':
      loc = container.locator("[name='" + value + "']");
      break;
    case 'text':
      loc = container.getByText(value);
      break;
    case 'role':
      loc = container.getByRole(value);
      break;
    case 'placeholder':
      loc = container.getByPlaceholder(value);
      break;
    case 'label':
      loc = container.getByLabel(value);
      break;
    case 'testid':
    case 'test_id':
      loc = container.getByTestId(value);
      break;
    default:
      loc = container.locator(value);
  }
  return loc;
}

function _applyLocatorIndex(loc, index) {
  const n = Number(index);
  // 与执行器一致：locator_index 语义为第 N 个（1 基），仅 >1 时收窄
  if (Number.isInteger(n) && n > 1) {
    return loc.nth(n - 1);
  }
  return loc;
}

function buildLocator(page, selector) {
  if (!selector) return null;
  // iframe 元素：按 ' >> ' 链逐层 frameLocator 下钻（与执行器一致）
  let container = page;
  if (selector.is_iframe && selector.iframe_locator) {
    const parts = String(selector.iframe_locator)
      .split(' >> ')
      .map((s) => s.trim())
      .filter(Boolean);
    for (const part of parts) {
      container = container.frameLocator(part);
    }
  }
  const type = selector.locator_type || 'xpath';
  const value = String(selector.locator_value || '');
  const loc = _locatorFromParts(container, type, value);
  return _applyLocatorIndex(loc, selector.locator_index);
}

/**
 * 构建主 + 备用定位器降级链（与执行器 _resolve_element 一致）：
 * 依次 wait_for，主定位严格冲突/失效时自动切换备用，全部不可见时
 * 返回最后一个定位器（保持与执行器相同的报错语义）。
 * 返回 { locator, usedIndex }；无任何候选返回 null。
 */
async function resolveLocatorWithFallback(page, selector, log) {
  if (!selector) return null;
  let container = page;
  if (selector.is_iframe && selector.iframe_locator) {
    const parts = String(selector.iframe_locator)
      .split(' >> ')
      .map((s) => s.trim())
      .filter(Boolean);
    for (const part of parts) {
      container = container.frameLocator(part);
    }
  }
  const candidates = [];
  const push = (t, v, idx) => {
    if (v && String(v).trim()) candidates.push([t, String(v), idx]);
  };
  push(selector.locator_type || 'xpath', selector.locator_value, selector.locator_index);
  push(selector.locator_type_2, selector.locator_value_2, selector.locator_index_2);
  push(selector.locator_type_3, selector.locator_value_3, selector.locator_index_3);
  if (!candidates.length) return null;

  let locator = null;
  let usedIndex = 0;
  for (let i = 0; i < candidates.length; i++) {
    const [t, v, idx] = candidates[i];
    let cand = _applyLocatorIndex(_locatorFromParts(container, t, v), idx);
    try {
      // 首选等待元素可见，备用定位器用更短超时快速切换（同执行器 5s/2s）
      await cand.waitFor({ state: 'visible', timeout: i === 0 ? 5000 : 2000 });
      locator = cand;
      usedIndex = i;
      if (log) log(`定位器 ${i + 1} [${t}=${v}] 命中`);
      break;
    } catch (e) {
      if (log) log(`定位器 ${i + 1} [${t}=${v}] 未命中: ${String((e && e.message) || e).slice(0, 120)}`);
      if (i === candidates.length - 1) {
        locator = cand;
        usedIndex = i;
      }
    }
  }
  return { locator, usedIndex };
}

/**
 * 带容错的导航：站点自身跳转（服务端 302 / 前端 location 跳转）仍在途中时，
 * 插入的 goto 会以 net::ERR_ABORTED 被中止。等待导航稳定后重试一次。
 */
async function gotoWithRetry(page, url, attempts = 2) {
  let lastErr = null;
  for (let i = 0; i < attempts; i++) {
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      return;
    } catch (e) {
      lastErr = e;
      const msg = String((e && e.message) || e);
      const aborted = msg.includes('ERR_ABORTED');
      const navigated = msg.includes('page.goto: Interrupted') || msg.includes('Navigation interrupted');
      // 导航已被其他跳转取代：页面实际上在跳转，等待其稳定后重试
      if (!aborted && !navigated) throw e;
      try { await page.waitForLoadState('domcontentloaded', { timeout: 8000 }); } catch (_) {}
    }
  }
  // 末次重试若目标已在当前页（前一次中止其实已把页面带到目标），视为成功
  if (page.url() === url) return;
  throw lastErr;
}

/** 执行一步平台步骤（ope_key 词汇表与执行器对齐），返回错误信息或 null */
async function runOneStep(page, step) {
  const opeKey = String(step.ope_key || '');
  const opeValue = step.ope_value && typeof step.ope_value === 'object' ? step.ope_value : {};
  const inputValue = String(
    opeValue.text || opeValue.value || opeValue.timeout || opeValue.url || opeValue.key || opeValue.expected || ''
  );

  if (opeKey === 'goto') {
    // 与上一跳同址时跳过：站点自身跳转（如登录页重定向）在途中时重复导航
    // 会以 net::ERR_ABORTED 中止当前跳转
    const target = inputValue;
    const cur = page.url();
    if (target && cur === target) return null;
    await gotoWithRetry(page, target);
    return null;
  }
  if (opeKey === 'wait') {
    const ms = parseInt(inputValue, 10);
    await page.waitForTimeout(Number.isFinite(ms) ? ms : 1000);
    return null;
  }

  // 定位器降级链（与执行器一致）：主定位严格冲突/失效自动切备用
  const sel = step.element || step.selector;
  const resolved = await resolveLocatorWithFallback(page, sel, (m) => {
    console.log('[run_steps] ' + m);
  });
  const locator = resolved ? resolved.locator : null;

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
    case 'upload': {
      // 平台已把附件解析为本地路径（opeValue.file_path / inputValue）
      const filePath = inputValue;
      if (!filePath) return '上传文件路径为空';
      // 以原件名上传：本地路径为平台存储的 hash/临时名，读取内容并携带
      // name/mimeType 载荷，目标系统收到原名（与执行器 _upload_file 同策）
      let payload = filePath;
      const originalName = (opeValue.file_name || '').trim();
      if (originalName) {
        try {
          const buffer = fs.readFileSync(filePath);
          const mime = opeValue.mime_type || _guessMimeType(originalName);
          payload = [{ name: originalName, mimeType: mime, buffer }];
        } catch (e) {
          return '读取上传文件失败: ' + ((e && e.message) || String(e));
        }
      }
      try {
        await locator.setInputFiles(payload);
      } catch (e) {
        // 定位到的是可见触发区（如 el-upload__text，非 file input）：
        // 与执行器同策略——点击触发原生文件选择器并拦截注入
        const [chooser] = await Promise.all([
          page.waitForEvent('filechooser', { timeout: 10000 }),
          locator.click(),
        ]);
        await chooser.setFiles(payload);
      }
      return null;
    }
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

// 上传控件定位：前端点击到位后，找 input[type=file]（自身或最近祖先），
// 返回可点击/可 setInputFiles 的选择器（执行器支持 file input 与 file chooser 两种回放）。
async function cmdLocateUpload(params) {
  if (!state.page || !state.running) {
    return { ok: false, error: '录制会话未启动' };
  }
  if (params.x === undefined || params.y === undefined) {
    return { ok: false, error: '缺少定位坐标' };
  }
  try {
    const info = await state.page.evaluate(([x, y]) => {
      const w = window.__whart;
      if (!w || !w.describe) return null;
      const el = document.elementFromPoint(x, y);
      if (!el || !(el instanceof Element)) return null;
      let fileInput = null;
      let node = el;
      while (node && node.nodeType === 1 && node !== document.documentElement && node !== document.body) {
        if (node.tagName === 'INPUT' && ((node.getAttribute('type') || '')).toLowerCase() === 'file') {
          fileInput = node;
          break;
        }
        node = node.parentElement;
      }
      const target = fileInput || el;
      const sel = w.describe(target);
      if (!sel) return null;
      return { selector: sel, is_file_input: !!fileInput };
    }, [Number(params.x), Number(params.y)]);
    if (!info || !info.selector) {
      return { ok: false, error: '请点击上传控件（文件输入框或上传按钮）' };
    }
    return { ok: true, state: { selector: info.selector, is_file_input: info.is_file_input } };
  } catch (e) {
    return { ok: false, error: '上传控件定位失败: ' + (e && e.message ? e.message : String(e)) };
  }
}

// 插入上传动作（文件已由前端上传到平台文件管理，此处只记录 file_id）
async function cmdAddUpload(params) {
  const sel = params.selector;
  if (!sel || !sel.locator_type || !sel.locator_value) {
    return { ok: false, error: '缺少上传控件定位信息' };
  }
  const fileId = Number(params.file_id);
  if (!Number.isFinite(fileId) || fileId <= 0) {
    return { ok: false, error: '缺少有效的文件 file_id' };
  }
  recordAction({
    type: 'upload',
    selector: sel,
    file_id: fileId,
    file_name: String(params.file_name || ''),
  });
  return { ok: true, state: { action: 'upload' } };
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
    return { ok: true, state: { executed: 0, failed: false, step_results: [] } };
  }
  // 前置执行期间不记录任何动作/导航
  state.preRunning = true;
  let executed = 0;
  let failedStep = -1;
  let errorMsg = '';
  // 逐步骤结果（含失败截图 base64）：供平台执行记录展示，与执行器路径对齐
  const stepResults = [];
  try {
    for (let i = 0; i < steps.length; i++) {
      const stepInfo = steps[i] || {};
      const resultEntry = {
        index: i + 1,
        ope_key: String(stepInfo.ope_key || ''),
        // 与执行器 description 同源：元素名称优先，回退步骤描述/操作名
        description: String(
          stepInfo.element_name
          || (stepInfo.ope_value && stepInfo.ope_value.description)
          || stepInfo.description
          || stepInfo.ope_key
          || ''
        ).slice(0, 100),
        status: 'success',
        message: '',
        screenshot: null,
        duration: 0,
      };
      const stepStart = Date.now();
      try {
        const err = await runOneStep(state.page, steps[i]);
        resultEntry.duration = (Date.now() - stepStart) / 1000;
        if (err) {
          failedStep = i;
          errorMsg = err;
          resultEntry.status = 'failed';
          resultEntry.message = String(err).slice(0, 300);
          stepResults.push(resultEntry);
          break;
        }
        executed += 1;
        // 成功消息与执行器同款："元素操作 click 执行成功"
        resultEntry.message = `元素操作 ${resultEntry.ope_key} 执行成功`;
        stepResults.push(resultEntry);
        await state.page.waitForTimeout(200);
      } catch (e) {
        failedStep = i;
        errorMsg = '第 ' + (i + 1) + ' 步执行失败: ' + (e && e.message ? e.message : String(e));
        resultEntry.status = 'failed';
        resultEntry.message = errorMsg.slice(0, 300);
        resultEntry.duration = (Date.now() - stepStart) / 1000;
        stepResults.push(resultEntry);
        break;
      } finally {
        // 失败步骤补一张现场截图（成功步骤不截，控制负载）
        if (resultEntry.status === 'failed') {
          try {
            const shot = await state.page.screenshot({ type: 'jpeg', quality: 60 });
            resultEntry.screenshot = 'data:image/jpeg;base64,' + shot.toString('base64');
          } catch (_) {}
        }
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
    // 注意：必须返回 ok:true + state.failed 标记。Python 侧 session.request()
    // 对 ok:false 会抛 RecorderSessionError 并丢弃整个响应——step_results
    // （含失败截图）会随之丢失，执行记录就没有步骤执行结果可展示。
    return {
      ok: true,
      state: {
        executed,
        failed: true,
        failed_step: failedStep + 1,
        error: errorMsg,
        step_results: stepResults,
      },
    };
  }
  return { ok: true, state: { executed, failed: false, step_results: stepResults } };
}

/**
 * 重建干净页面：前置执行结束后调用。
 * 关闭旧页面并在同一上下文新建页面（登录态/cookie 保留），
 * 导航到当前地址并重新建立帧推流——彻底消除滚动/弹层/半渲染等残留.
 */
/**
 * 切换登录态：关闭当前 context，按新 storageState 重建 context+page（多步骤
 * 绑定不同登录态的用例按组切换注入）。重建后重新绑定帧流（screencast CDP
 * 会话随旧 page 失效；截图循环引用 state.page 自动生效）。
 */
async function cmdSwitchContext(params) {
  const storageState = params.storage_state || undefined;
  if (!state.browser) return { ok: false, error: '浏览器未启动' };
  try {
    if (state.context) {
      try { await state.context.close(); } catch (_) {}
    }
    state.context = await state.browser.newContext(buildContextOptions(state.viewport, storageState));
    await state.context.exposeBinding('__whartReport', (source, payload) => handleReport(payload, source.frame));
    try { await state.context.addInitScript(INIT_SCRIPT); } catch (_) {}
    state.page = await state.context.newPage();
    try { await state.page.addInitScript(INIT_SCRIPT); } catch (_) {}
    await attachFreezeAnimation(state.context, state.page);
    attachPageDiagnostics(state.page);
    state.page.on('framenavigated', (frame) => {
      if (frame === state.page.mainFrame()) {
        recordNavigation(frame.url());
        ensureInjection();
      }
    });
    state.running = true;
    state.finished = false;
    stopFrameStream();
    state.lastFrameTs = 0;
    // 新 context 若处于录制执行模式，重新开启 tracing（context 重建会丢弃旧 trace）
    if (state.tracePath) {
      startTracing(state.context);
    }
    const streamed = await startFrameStream(state.page);
    if (streamed) {
      startFrameLoop(400, 300);
    } else {
      startFrameLoop(250, 0);
    }
    return { ok: true, state: { viewport: state.viewport } };
  } catch (e) {
    return { ok: false, error: '切换登录态失败: ' + (e && e.message ? e.message : String(e)) };
  }
}

// ---------------------------------------------------------------------------
// 执行 Trace（录制器浏览器执行用例时采集 Playwright trace.zip，
// 与执行器路径对齐：执行完成后平台拉取 zip 上传，展示 Trace 下载）
// ---------------------------------------------------------------------------

function ensureTraceDir() {
  const dir = process.env.RECORDER_TRACE_DIR || path.join(process.cwd(), 'data', 'traces');
  try { fs.mkdirSync(dir, { recursive: true }); } catch (_) {}
  return dir;
}

/** 开启 context tracing（screenshots+snapshots+sources 与执行器默认一致） */
async function startTracing(context) {
  if (!context) return;
  try {
    await context.tracing.start({
      screenshots: true,
      snapshots: true,
      sources: true,
    });
  } catch (e) {
    serverLog('tracing 启动失败:', e && e.message ? e.message : String(e));
  }
}

async function cmdStartTrace(params) {
  if (!state.context) return { ok: false, error: '浏览器未启动' };
  const dir = ensureTraceDir();
  const name = String(params && params.name || 'recorder_exec');
  state.tracePath = path.join(dir, `${name}_${Date.now()}.zip`);
  await startTracing(state.context);
  return { ok: true, state: { trace_path: state.tracePath } };
}

/** 停止 tracing 并落盘 zip，返回文件路径（由平台读取上传/转发） */
async function cmdStopTrace() {
  if (!state.context) return { ok: false, error: '浏览器未启动' };
  const tracePath = state.tracePath;
  state.tracePath = null;
  const pageErrors = state.pageErrors.slice();
  if (!tracePath) return { ok: true, state: { page_errors: pageErrors } };
  try {
    await state.context.tracing.stop({ path: tracePath });
    return { ok: true, state: { trace_path: tracePath, page_errors: pageErrors } };
  } catch (e) {
    return { ok: false, error: 'tracing 停止失败: ' + (e && e.message ? e.message : String(e)), state: { page_errors: pageErrors } };
  }
}

/**
 * 无痕切换账号：关闭整个 context（含页面），新开干净上下文。
 * 与点"退出登录"不同：服务端会话（TGT 等）不会被销毁，
 * 此前已保存的登录态保持有效。重建后重绑帧流。
 */
async function cmdResetContext(params) {
  if (!state.browser) return { ok: false, error: '录制会话未启动' };
  const url = (params && params.url) || state.startedUrl || 'about:blank';
  try {
    stopFrameLoop();
    stopFrameStream();
    if (state.context) {
      try { await state.context.close(); } catch (_) {}
    }
    state.context = await state.browser.newContext(buildContextOptions(state.viewport, undefined));
    await state.context.exposeBinding('__whartReport', (source, payload) => handleReport(payload, source.frame));
    try { await state.context.addInitScript(INIT_SCRIPT); } catch (_) {}
    state.page = await state.context.newPage();
    try { await state.page.addInitScript(INIT_SCRIPT); } catch (_) {}
    await attachFreezeAnimation(state.context, state.page);
    attachPageDiagnostics(state.page);
    state.page.on('framenavigated', (frame) => {
      if (frame === state.page.mainFrame()) {
        recordNavigation(frame.url());
        ensureInjection();
      }
    });
    state.running = true;
    state.finished = false;
    state.lastFrameTs = 0;
    if (url && url !== 'about:blank') {
      try {
        await state.page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      } catch (e) {
        serverLog('切换账号后导航失败:', e && e.message ? e.message : String(e));
      }
      state.startedUrl = url;
      state.lastNavUrl = url;
    }
    await ensureInjection();
    const streamed = await startFrameStream(state.page);
    if (streamed) {
      startFrameLoop(400, 300);
    } else {
      startFrameLoop(250, 0);
    }
    return { ok: true, state: { viewport: state.viewport, url: state.lastNavUrl || '' } };
  } catch (e) {
    return { ok: false, error: '切换账号失败: ' + (e && e.message ? e.message : String(e)) };
  }
}

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
    // 同一 context 已在启动/切换时注入过冻结脚本，此处仅补 page 级，
    // 避免 context 级 init script 随多次重建页面无上限追加副本
    if (state.freezeAnimation) {
      try { await state.page.addInitScript(FREEZE_ANIMATION_SCRIPT); } catch (_) {}
    }
    attachPageDiagnostics(state.page);
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
    // 只升级录制时无可用锚点的绝对路径兜底（/html/body/...）：
    // 已带属性/文本/class/锚点祖先的表达式保持原样。收尾重解析用的是结束时刻的
    // 实时 DOM，positional 计数（following-sibling::li[6] 等）在菜单展开/收起、
    // 弹层销毁等状态变化后会解析到其它元素，无条件重写会错位覆盖正确表达式。
    if (!/^\/html\/body\//.test(sel.locator_value)) continue;
    try {
      const improved = await state.page.evaluate((xpath) => {
        const w = window.__whart;
        if (!w || !w.describe) return null;
        let el = null;
        try {
          const res = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
          el = res.singleNodeValue;
        } catch (_) {
          return null;
        }
        if (!el || !(el instanceof Element)) return null;
        // 把录制时的绝对路径升级为属性锚点 / 带锚祖先的相对路径
        const d = w.describe(el);
        if (d && d.locator_value) return d;
        return null;
      }, sel.locator_value);
      if (improved) {
        // 语义名不一致说明绝对路径已错位解析到其它元素，保留原值不覆盖
        if (sel.name && improved.name && sel.name !== improved.name) continue;
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
        case 'locate_upload':
          return respond(await cmdLocateUpload(msg.params || {}));
        case 'add_upload':
          return respond(await cmdAddUpload(msg.params || {}));
        case 'reset_page':
          return respond(await cmdResetPage(msg.params || {}));
        case 'switch_context':
          return respond(await cmdSwitchContext(msg.params || {}));
        case 'start_trace':
          return respond(await cmdStartTrace(msg.params || {}));
        case 'stop_trace':
          return respond(await cmdStopTrace());
        case 'reset_context':
          return respond(await cmdResetContext(msg.params || {}));
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