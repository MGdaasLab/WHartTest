#!/usr/bin/env node
'use strict';

/**
 * Playwright 持久化会话服务
 *
 * 协议：stdin/stdout 行分隔 JSON
 * 请求：
 *   - 心跳：{ id, method: "ping", params: {} }
 *   - 执行：{ id, method: "exec", params: { args: string[], env?: object } }
 *   - 关闭：{ id, method: "close", params: {} }
 *
 * 响应：
 *   - 响应结构：{ id, ok: boolean, stdout?: string[], stderr?: string[], error?: string, state?: object }
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const Module = require('module');
const { execSync } = require('child_process');

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + '\n');
}

function serverLog(...args) {
  try {
    process.stderr.write(args.map(String).join(' ') + '\n');
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

  serverLog('[playwright_persistent_server] Playwright not found. Installing...');
  try {
    execSync('npm install', { stdio: 'inherit', cwd: skillDir });
    execSync('npx playwright install chromium', { stdio: 'inherit', cwd: skillDir });
    serverLog('[playwright_persistent_server] Playwright installed successfully');
    return true;
  } catch (e) {
    serverLog('[playwright_persistent_server] Failed to install Playwright:', e?.message || String(e));
    return false;
  }
}

function createCapturedConsole() {
  const stdout = [];
  const stderr = [];

  const fmt = (args) =>
    args
      .map((a) => {
        if (typeof a === 'string') return a;
        try {
          return JSON.stringify(a);
        } catch (_) {
          return String(a);
        }
      })
      .join(' ');

  return {
    stdout,
    stderr,
    console: {
      log: (...args) => stdout.push(fmt(args)),
      info: (...args) => stdout.push(fmt(args)),
      warn: (...args) => stderr.push(fmt(args)),
      error: (...args) => stderr.push(fmt(args)),
      debug: (...args) => stdout.push(fmt(args)),
    },
  };
}

async function safeClose(target, timeoutMs = 5000) {
  /**
   * Close a Playwright handle with a hard timeout.
   * Returns true if close finished within timeout, false on timeout/error/null.
   * Attach .catch immediately so a late close() rejection cannot become an
   * unhandledRejection after Promise.race already settled on timeout.
   */
  if (!target) return true;
  let timer;
  let timedOut = false;
  const closePromise = Promise.resolve()
    .then(() => target.close())
    .catch(() => undefined);
  try {
    await Promise.race([
      closePromise,
      new Promise((_, reject) => {
        timer = setTimeout(() => {
          timedOut = true;
          reject(new Error('close timeout'));
        }, timeoutMs);
      }),
    ]);
    return !timedOut;
  } catch (_) {
    return false;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function forceKillBrowserProcess(browser) {
  // Last resort when browser.close() hangs: kill the Chromium child process.
  try {
    const proc = typeof browser?.process === 'function' ? browser.process() : null;
    if (!proc || proc.killed) return false;
    serverLog('[forceKillBrowserProcess] killing pid=', proc.pid);
    try {
      proc.kill('SIGKILL');
    } catch (_) {
      try {
        proc.kill();
      } catch (__) {}
    }
    return true;
  } catch (e) {
    serverLog('[forceKillBrowserProcess]', e?.message || String(e));
    return false;
  }
}

async function main() {
  const cli = parseCli(process.argv.slice(2));
  if (!cli.skillDir) {
    serverLog('Usage: node playwright_persistent_server.js --skill-dir <path>');
    process.exit(2);
  }

  const skillDir = path.resolve(cli.skillDir);
  process.chdir(skillDir);

  const requireAnchor = fs.existsSync(path.join(skillDir, 'package.json'))
    ? path.join(skillDir, 'package.json')
    : path.join(skillDir, 'run.js');
  const requireFromSkill = Module.createRequire(requireAnchor);

  if (!checkPlaywrightInstalled(requireFromSkill)) {
    const installed = installPlaywright(skillDir);
    if (!installed) {
      serverLog('[playwright_persistent_server] Playwright unavailable.');
    }
  }

  let playwright = null;
  let chromium = null;
  let firefox = null;
  let webkit = null;
  let devices = null;
  let helpers = null;

  const state = {
    browser: null,
    context: null,
    page: null,
  };

  async function loadDeps() {
    if (playwright && helpers) return;
    playwright = requireFromSkill('playwright');
    chromium = playwright.chromium;
    firefox = playwright.firefox;
    webkit = playwright.webkit;
    devices = playwright.devices;
    try {
      helpers = requireFromSkill('./lib/helpers');
    } catch (_) {
      helpers = {
        launchBrowser: async (type) => {
          const browsers = { chromium, firefox, webkit };
          return browsers[type || 'chromium'].launch({ headless: false });
        },
        getExtraHeadersFromEnv: () => null,
      };
    }
  }

  function getContextOptionsWithHeaders(options = {}) {
    if (!helpers?.getExtraHeadersFromEnv) return options;
    const extra = helpers.getExtraHeadersFromEnv();
    if (!extra) return options;
    return {
      ...options,
      extraHTTPHeaders: {
        ...(extra || {}),
        ...(options?.extraHTTPHeaders || {}),
      },
    };
  }

  async function resetBrowserState() {
    // Drop refs first so concurrent ensureBrowserContextPage cannot reuse them.
    // Close browser first (covers pages/contexts). Sequential page->context->browser
    // left orphans when page.close() hung past timeout and browser never closed.
    const page = state.page;
    const context = state.context;
    const browser = state.browser;
    state.page = null;
    state.context = null;
    state.browser = null;

    serverLog('[resetBrowserState] closing browser (then context/page fallback)');
    if (browser) {
      const ok = await safeClose(browser, 8000);
      if (!ok) {
        serverLog('[resetBrowserState] browser.close timed out; force-killing process');
        forceKillBrowserProcess(browser);
      }
    } else {
      // No browser handle (e.g. only context from launchPersistentContext path).
      await Promise.all([safeClose(page, 3000), safeClose(context, 5000)]);
    }
    serverLog('[resetBrowserState] done');
  }

  async function pruneUntrackedResources() {
    // User code may open extra pages/contexts that are not assigned back to state.
    try {
      if (!state.browser || (typeof state.browser.isConnected === 'function' && !state.browser.isConnected())) {
        return;
      }
      const contexts =
        typeof state.browser.contexts === 'function' ? state.browser.contexts() : [];
      const contextTasks = (contexts || []).map(async (ctx) => {
        try {
          if (state.context && ctx === state.context) {
            const pages = typeof ctx.pages === 'function' ? ctx.pages() : [];
            const pageTasks = [];
            for (const p of pages || []) {
              if (state.page && p === state.page) {
                continue;
              }
              pageTasks.push(safeClose(p));
            }
            await Promise.all(pageTasks);
            return;
          }
          await safeClose(ctx);
        } catch (e) {
          serverLog('[pruneUntrackedResources]', e?.stack || e?.message || String(e));
        }
      });
      await Promise.all(contextTasks);
    } catch (e) {
      serverLog('[pruneUntrackedResources]', e?.stack || e?.message || String(e));
    }
  }

  async function ensureBrowserContextPage() {
    await loadDeps();

    const browserMissing = !state.browser;
    const browserDisconnected =
      !!state.browser &&
      typeof state.browser.isConnected === 'function' &&
      !state.browser.isConnected();

    if (browserMissing || browserDisconnected) {
      // Close old handles before launching again to avoid orphan Chromium processes.
      await resetBrowserState();
      const browserType = (process.env.PW_BROWSER_TYPE || 'chromium').toLowerCase();
      state.browser = await helpers.launchBrowser(browserType);
    }

    if (!state.context) {
      state.context = await state.browser.newContext(getContextOptionsWithHeaders({}));
    }

    if (!state.page || (typeof state.page.isClosed === 'function' && state.page.isClosed())) {
      state.page = await state.context.newPage();
    }
  }

  function resolveCodeFromArgs(args) {
    const a = Array.isArray(args) ? args : [];
    if (a.length > 0) {
      const first = a[0];
      if (typeof first === 'string' && fs.existsSync(first)) {
        const filePath = path.resolve(first);
        return fs.readFileSync(filePath, 'utf8');
      }
      return a.join(' ');
    }
    return '';
  }

  async function runUserCode(code) {
    const captured = createCapturedConsole();
    const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

    const safeProcess = Object.assign({}, process, {
      exit: (code) => {
        throw new Error(`process.exit(${code}) blocked in persistent session`);
      },
    });

    // 调试：记录实际执行的代码
    serverLog('[runUserCode] Code length:', code.length);
    serverLog('[runUserCode] Code preview:', code.slice(0, 200));

    const fn = new AsyncFunction(
      'console',
      'state',
      'helpers',
      'chromium',
      'firefox',
      'webkit',
      'devices',
      'require',
      'process',
      'getContextOptionsWithHeaders',
      `
let { browser, context, page } = state;
${code}
state.browser = browser;
state.context = context;
state.page = page;
`
    );

    try {
      await fn(
        captured.console,
        state,
        helpers,
        chromium,
        firefox,
        webkit,
        devices,
        requireFromSkill,
        safeProcess,
        getContextOptionsWithHeaders
      );
      return { ok: true, stdout: captured.stdout, stderr: captured.stderr };
    } catch (e) {
      const msg = e?.stack || e?.message || String(e);
      captured.stderr.push(msg);
      return { ok: false, stdout: captured.stdout, stderr: captured.stderr, error: msg };
    }
  }

  let chain = Promise.resolve();
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

  rl.on('line', (line) => {
    const raw = (line || '').trim();
    if (!raw) return;

    chain = chain.then(async () => {
      let req;
      try {
        req = JSON.parse(raw);
      } catch (_) {
        // 无效 JSON，忽略
        return;
      }

      // 验证请求格式：必须是对象且包含 id
      if (!req || typeof req !== 'object' || Array.isArray(req) || !req.id) {
        // 畸形请求，忽略（无法响应因为没有有效 id）
        serverLog('[playwright_persistent_server] Malformed request ignored:', raw.slice(0, 100));
        return;
      }

      const id = req.id;
      const method = req.method;
      const params = req.params || {};

      // 仅处理允许的 env 变量，过滤敏感变量
      const BLOCKED_ENV_KEYS = ['NODE_OPTIONS', 'PATH', 'HOME', 'USERPROFILE', 'TEMP', 'TMP'];
      if (params.env && typeof params.env === 'object') {
        for (const [k, v] of Object.entries(params.env)) {
          if (BLOCKED_ENV_KEYS.includes(k.toUpperCase())) {
            continue; // 跳过敏感变量
          }
          if (v === null || v === undefined) {
            delete process.env[k];
          } else {
            process.env[k] = String(v);
          }
        }
      }

      try {
        if (method === 'ping') {
          send({ id, ok: true, state: { alive: true } });
          return;
        }

        if (method === 'close') {
          await resetBrowserState();
          send({ id, ok: true });
          setTimeout(() => process.exit(0), 10);
          return;
        }

        if (method === 'exec') {
          await ensureBrowserContextPage();
          const code = resolveCodeFromArgs(params.args);
          if (!code) {
            send({
              id,
              ok: false,
              error: 'No code to execute (args empty)',
              stdout: [],
              stderr: [],
            });
            return;
          }

          const result = await runUserCode(code);
          await pruneUntrackedResources();
          const pageUrl = state.page && typeof state.page.url === 'function' ? state.page.url() : null;
          send({
            id,
            ok: !!result.ok,
            stdout: result.stdout || [],
            stderr: result.stderr || [],
            error: result.error,
            state: { pageUrl },
          });
          return;
        }

        send({ id, ok: false, error: `Unknown method: ${method}`, stdout: [], stderr: [] });
      } catch (e) {
        const msg = e?.stack || e?.message || String(e);
        send({ id, ok: false, error: msg, stdout: [], stderr: [msg] });
      }
    });
  });

  serverLog('[playwright_persistent_server] Ready. Waiting for commands...');
}

main().catch((e) => {
  serverLog('[playwright_persistent_server] fatal:', e?.stack || String(e));
  process.exit(1);
});
