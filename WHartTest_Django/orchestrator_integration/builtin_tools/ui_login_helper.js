#!/usr/bin/env node
/**
 * WHartTest UI 生成会话登录辅助脚本（平台预置，凭据仅在进程内消费）。
 *
 * 用法：
 *   node run.js --url <登录页URL> [--state-out auth-state.json]
 *               [--user-sel "#username"] [--pass-sel "#password"] [--submit-sel "#btnLogin"]
 *               [--user-placeholder 账号] [--pass-placeholder 密码] [--timeout 20000]
 *
 * 行为：
 * - 从环境变量 WHARTTEST_UI_USERNAME / WHARTTEST_UI_PASSWORD 读取凭据（绝不打印）；
 * - 用本机 playwright-core 启动 chromium 打开登录页；
 * - 依次尝试：显式选择器 → 常见选择器 → placeholder 匹配 → 文本为"账号/用户名/邮箱"的输入框；
 * - 填入凭据后点击显式提交选择器或常见登录按钮，等待跳转；
 * - 导出 storageState 到 --state-out（相对当前目录），退出码 0 成功 / 3 凭据未注入 / 4 登录未生效 / 2 其它。
 */
const path = require('path');
const fs = require('fs');

function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  if (i >= 0 && i + 1 < process.argv.length) return process.argv[i + 1];
  const eq = process.argv.find((a) => a.startsWith('--' + name + '='));
  if (eq) return eq.slice(name.length + 3);
  return def;
}

(async () => {
  const username = process.env.WHARTTEST_UI_USERNAME || '';
  const password = process.env.WHARTTEST_UI_PASSWORD || '';
  if (!username || !password) {
    console.error('CREDENTIALS_UNSET: WHARTTEST_UI_USERNAME / WHARTTEST_UI_PASSWORD 未注入');
    process.exit(3);
  }
  const url = arg('url');
  if (!url) { console.error('缺少 --url'); process.exit(2); }
  const timeout = parseInt(arg('timeout', '20000'), 10);
  const stateOut = path.resolve(arg('state-out', 'auth-state.json'));

  let pw;
  const candidates = [
    'playwright-core',
    'playwright',
    '/usr/local/lib/node_modules/@playwright/cli/node_modules/playwright-core',
    '/usr/local/lib/node_modules/playwright',
  ];
  for (const c of candidates) {
    try { pw = require(c); break; } catch (e) { /* try next */ }
  }
  if (!pw) { console.error('未找到 playwright-core/playwright 模块'); process.exit(2); }

  const browser = await pw.chromium.launch({ headless: true });
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout });

    const userSelectors = [arg('user-sel'), '#username', 'input[name="username"]', 'input[name="account"]',
      'input[name="email"]', 'input[type="text"]', 'input[type="email"]', 'input[type="tel"]'].filter(Boolean);
    const passSelectors = [arg('pass-sel'), '#password', 'input[name="password"]', 'input[type="password"]'].filter(Boolean);
    const submitSelectors = [arg('submit-sel'), 'button[type="submit"]', '#btnLogin', 'button:has-text("登 录")',
      'button:has-text("登录")', 'input[type="submit"]'].filter(Boolean);

    async function fillFirst(selectors, value, placeholderHint) {
      for (const sel of selectors) {
        try {
          const el = page.locator(sel).first();
          await el.waitFor({ state: 'visible', timeout: 3000 });
          await el.fill(value, { timeout: 3000 });
          return sel;
        } catch (e) { /* next */ }
      }
      if (placeholderHint) {
        try {
          const el = page.getByPlaceholder(placeholderHint).first();
          await el.waitFor({ state: 'visible', timeout: 2000 });
          await el.fill(value, { timeout: 2000 });
          return 'placeholder:' + placeholderHint;
        } catch (e) { /* fallthrough */ }
      }
      return null;
    }

    const filledUser = await fillFirst(userSelectors, username, arg('user-placeholder', '账号'));
    const filledPass = await fillFirst(passSelectors, password, arg('pass-placeholder', '密码'));
    if (!filledUser || !filledPass) {
      console.error(`LOGIN_FORM_NOT_FOUND: user=${filledUser || 'miss'} pass=${filledPass || 'miss'}`);
      process.exit(4);
    }

    let clicked = false;
    for (const sel of submitSelectors) {
      try {
        const el = page.locator(sel).first();
        await el.waitFor({ state: 'visible', timeout: 2000 });
        await el.click({ timeout: 2000 });
        clicked = true;
        break;
      } catch (e) { /* next */ }
    }
    if (!clicked) { await page.keyboard.press('Enter'); }

    try { await page.waitForLoadState('networkidle', { timeout: 10000 }); } catch (e) { /* 登录页可能长轮询 */ }
    await page.waitForTimeout(2000);

    const state = await context.storageState({ path: stateOut });
    const cookieCount = (state.cookies || []).length;
    const finalUrl = page.url();
    console.log(JSON.stringify({
      ok: true,
      state_file: stateOut,
      cookies: cookieCount,
      origins: (state.origins || []).length,
      final_url: finalUrl,
      filled: { user: filledUser, pass: filledPass },
    }));
    process.exit(0);
  } finally {
    await browser.close().catch(() => {});
  }
})().catch((e) => { console.error('LOGIN_HELPER_ERROR:', e && e.message); process.exit(2); });
