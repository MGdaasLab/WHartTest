// tests/userCreateFieldError.e2e.mjs — 「新建用户只显示泛化错误」的页面级回归。
//
// 缺陷现象：新建用户密码为纯数字时，后端返回
//   { status: 'error', code: 400, message: '请求参数有误或处理失败',
//     data: null, errors: { password: ['密码只包含数字。'] } }
// 前端 toast 只显示泛化 message，用户以为系统坏了；修复后必须展示字段级原因。
//
// 运行前提：先启动前端 dev server（默认 http://127.0.0.1:5199），可用 BASE_URL 覆盖：
//   cd WHartTest_Vue && npm run dev -- --port 5199
//   node tests/userCreateFieldError.e2e.mjs
//
// 通过 Playwright 拦截 /api/accounts/users/ 的 POST，回放用户上报的原始 400 报文；
// 页面、axios 拦截器、toast 渲染全部走真实构建产物。
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5199';

// 用户上报的真实响应体（UnifiedResponseRenderer 对字段校验失败的固定形态）。
const createUser400 = {
  status: 400,
  contentType: 'application/json',
  body: JSON.stringify({
    status: 'error',
    code: 400,
    message: '请求参数有误或处理失败',
    data: null,
    errors: { password: ['密码只包含数字。'] },
  }),
};

function wrapped(data, httpStatus = 200) {
  return {
    status: httpStatus,
    contentType: 'application/json',
    body: JSON.stringify({ status: 'success', code: 200, message: '操作成功', data }),
  };
}

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // 种入登录态（路由守卫 + axios 请求头读取 localStorage）。
  await page.addInitScript(() => {
    localStorage.setItem('auth-isAuthenticated', 'true');
    localStorage.setItem('auth-accessToken', 'e2e-fake-access-token');
    localStorage.setItem('auth-refreshToken', 'e2e-fake-refresh-token');
    localStorage.setItem(
      'auth-user',
      JSON.stringify({ id: 1, username: 'admin', is_staff: true, is_active: true })
    );
  });

  // 拦截页面加载期的全部接口，POST /accounts/users/ 回放用户上报的 400 报文。
  // 注意：glob '**/api/**' 也会命中 dev server 的源码模块（如 /src/features/ui-automation/api/index.ts，
  // 路径里同样含 /api/），必须用 pathname 前缀甄别，其余请求 fallback 透传，否则应用加载即崩。
  let createUserCalled = 0;
  await page.route('**/api/**', (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith('/api/')) {
      return route.fallback();
    }
    const method = route.request().method();
    if (method === 'POST' && url.pathname.endsWith('/accounts/users/')) {
      createUserCalled += 1;
      return route.fulfill(createUser400);
    }
    if (method === 'GET' && url.pathname.endsWith('/accounts/users/')) {
      return route.fulfill(wrapped([]));
    }
    if (url.pathname.endsWith('/license/status/')) {
      return route.fulfill(wrapped({ activated: true, status: 'OK', seats: 10, used_seats: 2 }));
    }
    return route.fulfill(wrapped(null));
  });

  await page.goto(`${BASE}/users`);
  await page.getByRole('button', { name: '添加用户' }).first().waitFor({ timeout: 15000 });

  // 打开新建用户弹窗并填写表单：密码 12345678 —— 通过前端校验（必填 + 长度 ≥ 8），
// 但会被后端的「密码只包含数字」规则拒绝，正中缺陷场景。
  await page.getByRole('button', { name: '添加用户' }).first().click();
  // 页面里有 4 个常驻 modal（权限/添加/编辑/额度），DOM 始终存在，按标题过滤到目标弹窗。
  const modal = page.locator('.arco-modal').filter({ hasText: '添加用户' });
  await modal.waitFor({ state: 'visible' });
  await modal.locator('.arco-form-item', { hasText: '用户名' }).locator('input').fill('e2euser');
  await modal.locator('.arco-form-item', { hasText: '邮箱' }).locator('input').fill('e2e@example.com');
  await modal.locator('.arco-form-item').filter({ hasText: '密码' }).filter({ hasNotText: '确认' }).locator('input').fill('12345678');
  await modal.locator('.arco-form-item', { hasText: '确认密码' }).locator('input').fill('12345678');
  await modal.getByRole('button', { name: '确定' }).click();

  // 断言 1：错误 toast 展示字段级原因，而不是泛化文案。
  const toast = page.locator('.arco-message');
  await toast.first().waitFor({ state: 'visible', timeout: 10000 });
  const toastText = (await toast.allTextContents()).join('\n');
  assert.match(toastText, /密码只包含数字/, `toast 应包含字段级错误，实际：${toastText}`);
  assert.doesNotMatch(
    toastText,
    /请求参数有误或处理失败/,
    `toast 不应只显示泛化文案，实际：${toastText}`
  );

  // 断言 2：弹窗保持打开（保存失败不得关闭），且确实发出了创建请求。
  assert.equal(createUserCalled, 1, '应恰好发起一次创建用户请求');
  assert.ok(await modal.isVisible(), '创建失败后弹窗应保持打开');

  console.log('userCreateFieldError e2e passed');
} finally {
  await browser.close();
}
