// tests/skillsPageScroll.test.mjs — 「Skill 页面列表超长无法滚动」的页面级回归。
//
// 背景：MainLayout 的 .content 是固定高度 + overflow: hidden（子页面自行控制滚动），
// 而 Skills 页面根节点此前没有任何高度与滚动处理，已安装条目一多，
// 列表会把 .content 无限撑高后被裁掉，底部条目不可达且无法滚动。
// 修复方式：页面根节点 height:100% + overflow-y:auto，页面自身滚动，
// 内部布局与卡片高度保持原样（文档式布局不变）。
//
// CE 适配（同步自 master-pe be9ec9c5）：CE 开源线无子代理库功能
// （features/subagents 与 /subagents 路由均不存在），已剔除子代理场景，
// 仅保留 Skills 管理页与 Skill 中心弹窗的滚动回归。
//
// 运行前提：先启动前端 dev server（默认 http://127.0.0.1:5199），可用 BASE_URL 覆盖：
//   cd WHartTest_Vue && npm run dev -- --port 5199
//   node tests/skillsPageScroll.test.mjs
//
// 通过 Playwright 拦截 /api/projects/、/api/projects/1/skills/、
// /api/projects/1/skills/store-config|store-manifest/
// 构造「已安装大量 Skill」的场景，不依赖真实后端数据。
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5199';

// 只拦截「以 /api/ 开头」的同源接口请求。
// 不能用 glob **/api/**：它会把源码模块 /src/features/ui-automation/api/index.ts
// 也当成接口拦掉，导致页面模块加载失败。
const API_ROUTE_RE = /^https?:\/\/[^/]+\/api\//;

// Playwright 的 glob 模式按「完整 URL（含查询串）」匹配：
// store-manifest/?url=... 这类带查询串的请求会因尾部 ?... 导致 glob 失配、
// 落进兜底 mock。统一用「忽略查询串」的正则来注册具体端点。
const endpoint = (path) => new RegExp(`^https?://[^/]+${path}(\\?.*)?$`);

const PROJECT_ID = 1;
const SKILL_COUNT = 60;

const installedSkills = Array.from({ length: SKILL_COUNT }, (_, i) => ({
  id: i + 1,
  name: `regression-skill-${i + 1}`,
  description: `回归用 Skill #${i + 1}：验证列表超长时页面可以滚动到底部。`,
  is_active: true,
  creator_name: 'tester',
  is_owner: true,
  can_edit: true,
  created_at: '2026-10-29T10:00:00+08:00',
}));

const manifestSkills = Array.from({ length: SKILL_COUNT }, (_, i) => ({
  id: `reg--skill-${i + 1}`,
  name: `regression-skill-${i + 1}`,
  description: `Skill Hub 条目 #${i + 1}`,
  version: '1.0.0',
  author: 'tester',
  zip_path: `skills/regression-skill-${i + 1}.zip`,
}));

// 新版统一报文（顶层带 status）：projects 等接口使用，
// axios 拦截器会拆包成 { success, data }。
function wrapped(data, httpStatus = 200) {
  return {
    status: httpStatus,
    contentType: 'application/json',
    body: JSON.stringify({ status: 'success', code: 'OK', message: '操作成功', data }),
  };
}

// skills 系列接口的真实线上报文是「双层嵌套」：
// views.py 返回 {code,message,data}（无顶层 status，不满足 UnifiedResponseRenderer
// 的合并分支条件），被全局渲染器整体塞进外层统一结构的 data 字段，即
// {status:'success', code:200, message:'操作成功', data:{code:200, message:'获取成功', data:[...]}}。
// 前端 axios 拦截器拆外层包后，response.data 恰为内层对象，
// skillService.getSkills 再取 response.data.data 得到列表。
function skillsWrapped(data, httpStatus = 200) {
  return {
    status: httpStatus,
    contentType: 'application/json',
    body: JSON.stringify({
      status: 'success',
      code: 200,
      message: '操作成功',
      data: { code: 200, message: '获取成功', data },
    }),
  };
}

async function waitForServer(url, timeoutMs = 90000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // dev server 尚未就绪，继续轮询真实状态
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`dev server 未就绪：${url}（请先执行 npm run dev -- --port 5199）`);
}

async function openApp(browser, path, viewport = { width: 1280, height: 800 }) {
  const page = await browser.newPage({ viewport });
  page.on('pageerror', (e) => console.log('  [pageerror]', e.message));

  // 直接以已登录管理员身份进入（is_staff 跳过权限接口）
  await page.addInitScript(() => {
    localStorage.setItem('auth-isAuthenticated', 'true');
    localStorage.setItem('auth-accessToken', 'fake-token-for-scroll-regression');
    localStorage.setItem('auth-refreshToken', 'fake-refresh-token');
    localStorage.setItem(
      'auth-user',
      JSON.stringify({ id: 1, username: 'scroll-tester', is_staff: true })
    );
    localStorage.setItem('selected_project_id', '1');
  });

  // 兜底：其余 /api 请求一律成功空数据，避免布局被无关请求挂起
  await page.route(API_ROUTE_RE, (route) => route.fulfill(wrapped(null)));
  // 具体路由后注册，优先级高于兜底
  await page.route(endpoint('/api/projects/'), (route) =>
    route.fulfill(
      wrapped([
        {
          id: PROJECT_ID,
          name: '滚动回归项目',
          description: '',
          created_at: '2026-10-29T10:00:00+08:00',
          updated_at: '2026-10-29T10:00:00+08:00',
        },
      ])
    )
  );
  await page.route(endpoint('/api/projects/1/skills/'), (route) =>
    route.fulfill(skillsWrapped(installedSkills))
  );
  await page.route(endpoint('/api/projects/1/skills/store-config/'), (route) =>
    route.fulfill(
      skillsWrapped({
        default_source: 'https://gitee.com/mgdaas-lab/wharttest/',
        default_source_name: 'SkillHub',
        allow_custom_source: true,
        max_zip_size: 52428800,
      })
    )
  );
  await page.route(endpoint('/api/projects/1/skills/store-manifest/'), (route) =>
    route.fulfill(skillsWrapped({ version: '1', skills: manifestSkills }))
  );

  await page.goto(BASE + path, { waitUntil: 'domcontentloaded', timeout: 120000 });
  return page;
}

async function collectMetrics(page, selectors) {
  return page.evaluate((s) => {
    const out = {};
    for (const [key, sel] of Object.entries(s.sel)) {
      const el = document.querySelector(sel);
      out[key] = el
        ? { client: el.clientHeight, scroll: el.scrollHeight, top: el.getBoundingClientRect().top }
        : null;
    }
    return out;
  }, { sel: selectors });
}

async function viewportHeight(page) {
  return page.evaluate(() => window.innerHeight);
}

/**
 * 滚动断言：
 * - scrollerSel 是承担滚动的容器（页面根节点或弹窗内部滚动区）；
 * - hoverSel 是滚轮事件落点（用户实际滚动时鼠标所在区域，通常是卡片列表）；
 * - noSpillSels 里的每一层都不允许自身溢出（修复前列表会把 MainLayout .content
 *   无限撑高后被 overflow:hidden 裁掉，底部条目不可达且无法滚动）。
 */
async function checkScrollableList(page, scrollerSel, hoverSel, lastItemSel, noSpillSels, label) {
  // 1. 滚动容器确实溢出（回归前提：条目多到必须滚动）
  const before = await page.evaluate(
    ([sel]) => {
      const el = document.querySelector(sel);
      return { client: el?.clientHeight ?? 0, scroll: el?.scrollHeight ?? 0 };
    },
    [scrollerSel]
  );
  assert.ok(
    before.scroll > before.client + 1,
    `${label}: 滚动容器应产生纵向溢出（scroll=${before.scroll} client=${before.client}）。` +
      `若数值都很小，则是测试数据不足以复现超长列表场景。`
  );

  // 2. 各层外框不允许自身溢出（回归信号：.content 被撑破 = 列表被裁掉且无法滚动）
  const boxes = await collectMetrics(page, Object.fromEntries(noSpillSels.map((s) => [s, s])));
  for (const [sel, m] of Object.entries(boxes)) {
    assert.ok(m, `${label}: 未找到 ${sel}`);
    assert.ok(
      m.scroll <= m.client + 1,
      `${label}: ${sel} 不应自身溢出（scroll=${m.scroll} client=${m.client}）——` +
        `溢出未收敛进滚动容器，底部内容会被裁掉且无法滚动`
    );
  }

  // 3. 模拟真实滚轮：在列表区上滚动，滚动容器产生实际位移。
  //    注意：单次超大 deltaY（如 100000）在 Chromium headless 下不会触发滚动，
  //    用多次常规步进（500px）模拟真实操作。
  const hoverBox = await page.locator(hoverSel).first().boundingBox();
  assert.ok(hoverBox, `${label}: 滚轮落点区域不可见`);
  await page.mouse.move(
    hoverBox.x + hoverBox.width / 2,
    hoverBox.y + Math.min(hoverBox.height / 2, 100)
  );
  for (let i = 0; i < 6; i++) {
    await page.mouse.wheel(0, 500);
  }
  const scrolled = await page.evaluate(
    ([sel]) => document.querySelector(sel).scrollTop,
    [scrollerSel]
  );
  assert.ok(scrolled > 0, `${label}: 滚轮事件应使滚动容器产生实际滚动（scrollTop=${scrolled}）`);

  // 4. 最后一个条目可滚动到可视区内
  const last = page.locator(lastItemSel).last();
  await last.scrollIntoViewIfNeeded();
  await last.waitFor({ state: 'visible', timeout: 5000 });
  const lastBox = await last.boundingBox();
  const viewportH = await viewportHeight(page);
  assert.ok(
    lastBox && lastBox.y + lastBox.height <= viewportH + 1,
    `${label}: 最后一个条目应可滚动到可视区内（bottom=${lastBox?.y + lastBox?.height} viewport=${viewportH}）`
  );
  return { overflow: before, scrolled };
}

async function main() {
  await waitForServer(BASE);
  const browser = await chromium.launch();
  let failed = 0;

  // 场景 1：Skills 管理页，已安装 60 个 Skill（页面级滚动）
  try {
    const page = await openApp(browser, '/skills');
    await page.waitForSelector('.skill-card', { timeout: 30000 });
    await page.waitForFunction(
      (n) => document.querySelectorAll('.skill-card').length === n,
      SKILL_COUNT,
      { timeout: 15000 }
    );
    const r = await checkScrollableList(
      page,
      '.skills-management-view',
      '.skill-list',
      '.skill-card',
      ['.skills-container', '.content'],
      'Skills 页'
    );
    console.log('  [ok] Skills 管理页可滚动到底部', JSON.stringify(r));
    await page.close();
  } catch (e) {
    failed++;
    console.error('  [fail] Skills 管理页:', e.message);
  }

  // 场景 2：Skill 中心弹窗，源内 60 个 Skill（弹窗内部滚动链路，防回归）
  try {
    const page = await openApp(browser, '/skills');
    await page.waitForSelector('.skill-card', { timeout: 30000 });
    await page.getByRole('button', { name: 'Skill 中心' }).click();
    await page.waitForSelector('.store-card', { timeout: 30000 });
    await page.waitForFunction(
      (n) => document.querySelectorAll('.store-card').length === n,
      SKILL_COUNT,
      { timeout: 15000 }
    );
    const r = await checkScrollableList(
      page,
      '.store-grid',
      '.store-grid',
      '.store-card',
      ['.skill-store'],
      'Skill 中心弹窗'
    );
    console.log('  [ok] Skill 中心弹窗网格可滚动到底部', JSON.stringify(r));
    await page.close();
  } catch (e) {
    failed++;
    console.error('  [fail] Skill 中心弹窗:', e.message);
  }

  // 场景 3：小视口下的 Skills 页（矮屏 / 窄屏单列，验证响应式布局下滚动仍收敛）
  const smallViewports = [
    { name: '矮屏 1280x480', viewport: { width: 1280, height: 480 } },
    { name: '窄屏 420x700', viewport: { width: 420, height: 700 } },
  ];
  const c = {
    path: '/skills',
    waitSel: '.skill-card',
    count: SKILL_COUNT,
    scroller: '.skills-management-view',
    hover: '.skill-list',
    lastItem: '.skill-card',
    noSpill: ['.skills-container', '.content'],
    pageName: 'Skills 页',
  };
  for (const v of smallViewports) {
    try {
      const page = await openApp(browser, c.path, v.viewport);
      await page.waitForSelector(c.waitSel, { timeout: 30000 });
      await page.waitForFunction(
        ([sel, n]) => document.querySelectorAll(sel).length === n,
        [c.waitSel, c.count],
        { timeout: 15000 }
      );
      const r = await checkScrollableList(
        page,
        c.scroller,
        c.hover,
        c.lastItem,
        c.noSpill,
        `${c.pageName}（${v.name}）`
      );
      console.log(`  [ok] ${c.pageName}（${v.name}）可滚动到底部`, JSON.stringify(r));
      await page.close();
    } catch (e) {
      failed++;
      console.error(`  [fail] ${c.pageName}（${v.name}）:`, e.message);
    }
  }

  await browser.close();
  if (failed > 0) {
    console.error(`skillsPageScroll: ${failed} 个场景失败`);
    process.exit(1);
  }
  console.log('skillsPageScroll: 全部场景通过');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
