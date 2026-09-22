/**
 * lib/clientCert.js 的单元测试 —— 零依赖，直接 `node test_client_cert.js` 运行。
 *
 * 之所以能零依赖：lib/clientCert.js 刻意不 require('playwright')，只做环境变量解析。
 * 因此本文件不需要 npm install，也不启动任何浏览器。
 *
 * 覆盖范围与 WHartTest_Actuator/test_client_cert.py 对齐：纯函数边界、camelCase 键名、
 * 环境变量三态、以及「不满足条件时不产生配置」的告警路径。
 * 不做真实证书握手（见文件末尾「已知缺口」）。
 */

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const clientCert = require('./lib/clientCert');

const CERT_ENV_KEYS = [
  'PW_CLIENT_CERT_PFX',
  'PW_CLIENT_CERT_PASSPHRASE',
  'PW_CLIENT_CERT_CERT',
  'PW_CLIENT_CERT_KEY',
  'PW_CLIENT_CERT_ORIGINS',
  'PW_IGNORE_HTTPS_ERRORS',
];

let passed = 0;
const failures = [];
const pending = [];

/** 在受控的环境变量与 console.warn 捕获下运行用例 */
function withEnv(env, fn) {
  const saved = {};
  for (const key of CERT_ENV_KEYS) {
    saved[key] = process.env[key];
    delete process.env[key];
  }
  Object.assign(process.env, env);

  const warnings = [];
  const originalWarn = console.warn;
  console.warn = (...args) => warnings.push(args.join(' '));

  try {
    return fn(warnings);
  } finally {
    console.warn = originalWarn;
    for (const key of CERT_ENV_KEYS) {
      if (saved[key] === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = saved[key];
      }
    }
  }
}

function recordSuccess(name) {
  passed += 1;
  console.log(`  ok   ${name}`);
}

function recordFailure(name, error) {
  failures.push({ name, error });
  console.log(`  FAIL ${name}`);
  console.log(`       ${error.message.split('\n').join('\n       ')}`);
}

/** 支持同步与异步用例 */
function test(name, fn) {
  let result;
  try {
    result = fn();
  } catch (error) {
    recordFailure(name, error);
    return;
  }

  if (result && typeof result.then === 'function') {
    pending.push(
      result.then(
        () => recordSuccess(name),
        (error) => recordFailure(name, error)
      )
    );
    return;
  }

  recordSuccess(name);
}

// 临时目录（用于「文件存在」的分支）
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'client-cert-test-'));
const pfxFile = path.join(tmpDir, 'client.pfx');
const pfxFile2 = path.join(tmpDir, 'other.p12');
const certFile = path.join(tmpDir, 'client.crt');
const keyFile = path.join(tmpDir, 'client.key');
for (const file of [pfxFile, pfxFile2, certFile, keyFile]) {
  fs.writeFileSync(file, 'dummy');
}
const missingFile = path.join(tmpDir, 'does-not-exist.pfx');

console.log('\nnormalizeOrigin');
test('去除 path/query/fragment', () => {
  assert.strictEqual(
    clientCert.normalizeOrigin('https://example.com/path?q=1#frag'),
    'https://example.com'
  );
});
test('保留非默认端口', () => {
  assert.strictEqual(
    clientCert.normalizeOrigin('https://example.com:8443/x'),
    'https://example.com:8443'
  );
});
test('去掉显式默认端口 443', () => {
  assert.strictEqual(
    clientCert.normalizeOrigin('https://example.com:443/x'),
    'https://example.com'
  );
});
test('拒绝非 https 与无 scheme', () => {
  assert.strictEqual(clientCert.normalizeOrigin('http://example.com'), null);
  assert.strictEqual(clientCert.normalizeOrigin('example.com'), null);
});
test('拒绝空值', () => {
  assert.strictEqual(clientCert.normalizeOrigin(''), null);
  assert.strictEqual(clientCert.normalizeOrigin('   '), null);
  assert.strictEqual(clientCert.normalizeOrigin(null), null);
  assert.strictEqual(clientCert.normalizeOrigin(undefined), null);
});
test('丢弃 userinfo', () => {
  assert.strictEqual(
    clientCert.normalizeOrigin('https://user:pw@example.com/x'),
    'https://example.com'
  );
});
test('保留 IPv6 方括号', () => {
  assert.strictEqual(clientCert.normalizeOrigin('https://[::1]:8443/x'), 'https://[::1]:8443');
});

console.log('\nparseOrigins');
test('拆分、去空格、去重且保序', () => {
  assert.deepStrictEqual(
    clientCert.parseOrigins('https://b.com, https://a.com ,https://b.com'),
    ['https://b.com', 'https://a.com']
  );
});
test('合并多个来源', () => {
  assert.deepStrictEqual(
    clientCert.parseOrigins('https://a.com', 'https://b.com'),
    ['https://a.com', 'https://b.com']
  );
});
test('丢弃非法项', () => {
  assert.deepStrictEqual(
    clientCert.parseOrigins('http://plain.com, ,https://ok.com, notaurl'),
    ['https://ok.com']
  );
});
test('空输入返回空数组', () => {
  assert.deepStrictEqual(clientCert.parseOrigins(''), []);
  assert.deepStrictEqual(clientCert.parseOrigins(undefined), []);
  assert.deepStrictEqual(clientCert.parseOrigins(), []);
});

console.log('\ngetClientCertificatesFromEnv');
test('pfx 模式：每个 origin 一条，键名为 camelCase 的 pfxPath', () => {
  withEnv(
    {
      PW_CLIENT_CERT_PFX: pfxFile,
      PW_CLIENT_CERT_PASSPHRASE: 'pw',
      PW_CLIENT_CERT_ORIGINS: 'https://a.example.com,https://b.example.com:8443',
    },
    () => {
      const entries = clientCert.getClientCertificatesFromEnv();
      assert.strictEqual(entries.length, 2);
      assert.strictEqual(entries[0].origin, 'https://a.example.com');
      assert.strictEqual(entries[1].origin, 'https://b.example.com:8443');
      assert.strictEqual(entries[0].pfxPath, pfxFile);
      assert.strictEqual(entries[0].passphrase, 'pw');
      assert.deepStrictEqual(Object.keys(entries[0]).sort(), ['origin', 'passphrase', 'pfxPath']);
    }
  );
});
test('snake_case 键名必须不存在（写错会被 Playwright 静默忽略）', () => {
  withEnv({ PW_CLIENT_CERT_PFX: pfxFile, PW_CLIENT_CERT_ORIGINS: 'https://a.com' }, () => {
    const entry = clientCert.getClientCertificatesFromEnv()[0];
    for (const wrong of ['pfx_path', 'cert_path', 'key_path', 'origin_url']) {
      assert.ok(!(wrong in entry), `不应出现 ${wrong}`);
    }
    assert.ok('pfxPath' in entry);
  });
});
test('PEM 模式：键名为 certPath / keyPath', () => {
  withEnv(
    {
      PW_CLIENT_CERT_CERT: certFile,
      PW_CLIENT_CERT_KEY: keyFile,
      PW_CLIENT_CERT_ORIGINS: 'https://a.com',
    },
    () => {
      const entry = clientCert.getClientCertificatesFromEnv()[0];
      assert.strictEqual(entry.certPath, certFile);
      assert.strictEqual(entry.keyPath, keyFile);
      assert.ok(!('cert' in entry));
      assert.ok(!('key' in entry));
      assert.ok(!('pfxPath' in entry));
    }
  );
});
test('未设置任何 env 时返回 null', () => {
  withEnv({}, () => {
    assert.strictEqual(clientCert.getClientCertificatesFromEnv(), null);
  });
});
test('只给 PEM 一半（缺 key）时返回 null 并告警', () => {
  withEnv({ PW_CLIENT_CERT_CERT: certFile, PW_CLIENT_CERT_ORIGINS: 'https://a.com' }, (warnings) => {
    assert.strictEqual(clientCert.getClientCertificatesFromEnv(), null);
    assert.ok(warnings.some((w) => w.includes('PW_CLIENT_CERT_KEY')));
  });
});
test('缺少 origins 时返回 null 并告警', () => {
  withEnv({ PW_CLIENT_CERT_PFX: pfxFile }, (warnings) => {
    assert.strictEqual(clientCert.getClientCertificatesFromEnv(), null);
    assert.ok(warnings.some((w) => w.includes('PW_CLIENT_CERT_ORIGINS')));
  });
});
test('全部 origin 非法时返回 null', () => {
  withEnv({ PW_CLIENT_CERT_PFX: pfxFile, PW_CLIENT_CERT_ORIGINS: 'http://a.com,notaurl' }, () => {
    assert.strictEqual(clientCert.getClientCertificatesFromEnv(), null);
  });
});
test('混入非法 origin 时只保留合法项', () => {
  withEnv(
    { PW_CLIENT_CERT_PFX: pfxFile, PW_CLIENT_CERT_ORIGINS: 'http://bad.com,https://good.com' },
    () => {
      const entries = clientCert.getClientCertificatesFromEnv();
      assert.strictEqual(entries.length, 1);
      assert.strictEqual(entries[0].origin, 'https://good.com');
    }
  );
});
test('空口令不带 passphrase 键', () => {
  withEnv(
    {
      PW_CLIENT_CERT_PFX: pfxFile,
      PW_CLIENT_CERT_PASSPHRASE: '   ',
      PW_CLIENT_CERT_ORIGINS: 'https://a.com',
    },
    () => {
      const entry = clientCert.getClientCertificatesFromEnv()[0];
      assert.ok(!('passphrase' in entry));
    }
  );
});
test('pfx 与 PEM 同时配置时优先 pfx 并告警', () => {
  withEnv(
    {
      PW_CLIENT_CERT_PFX: pfxFile,
      PW_CLIENT_CERT_CERT: certFile,
      PW_CLIENT_CERT_KEY: keyFile,
      PW_CLIENT_CERT_ORIGINS: 'https://a.com',
    },
    (warnings) => {
      const entry = clientCert.getClientCertificatesFromEnv()[0];
      assert.strictEqual(entry.pfxPath, pfxFile);
      assert.ok(!('certPath' in entry));
      assert.ok(warnings.some((w) => w.includes('优先使用 pfx')));
    }
  );
});
test('证书文件不存在时告警但不下发空配置', () => {
  withEnv(
    { PW_CLIENT_CERT_PFX: missingFile, PW_CLIENT_CERT_ORIGINS: 'https://a.com' },
    (warnings) => {
      const entries = clientCert.getClientCertificatesFromEnv();
      assert.strictEqual(entries.length, 1);
      assert.ok(warnings.some((w) => w.includes('文件不存在')));
    }
  );
});

console.log('\ngetIgnoreHttpsErrorsFromEnv');
test('true 值解析为 true', () => {
  for (const raw of ['true', 'TRUE', '1', 'yes', 'on']) {
    withEnv({ PW_IGNORE_HTTPS_ERRORS: raw }, () => {
      assert.strictEqual(clientCert.getIgnoreHttpsErrorsFromEnv(), true, `raw=${raw}`);
    });
  }
});
test('false 值解析为 false', () => {
  for (const raw of ['false', 'FALSE', '0', 'no', 'off']) {
    withEnv({ PW_IGNORE_HTTPS_ERRORS: raw }, () => {
      assert.strictEqual(clientCert.getIgnoreHttpsErrorsFromEnv(), false, `raw=${raw}`);
    });
  }
});
test('未设置 / auto 解析为 null', () => {
  withEnv({}, () => {
    assert.strictEqual(clientCert.getIgnoreHttpsErrorsFromEnv(), null);
  });
  for (const raw of ['auto', 'AUTO', '']) {
    withEnv({ PW_IGNORE_HTTPS_ERRORS: raw }, () => {
      assert.strictEqual(clientCert.getIgnoreHttpsErrorsFromEnv(), null, `raw=${raw}`);
    });
  }
});
test('无法识别的值按 auto 处理并告警', () => {
  withEnv({ PW_IGNORE_HTTPS_ERRORS: 'maybe' }, (warnings) => {
    assert.strictEqual(clientCert.getIgnoreHttpsErrorsFromEnv(), null);
    assert.ok(warnings.some((w) => w.includes('PW_IGNORE_HTTPS_ERRORS')));
  });
});

console.log('\nresolveContextCertOptions');
test('已配置证书且未显式设置时自动放宽 TLS 校验', () => {
  withEnv({ PW_CLIENT_CERT_PFX: pfxFile, PW_CLIENT_CERT_ORIGINS: 'https://a.com' }, (warnings) => {
    const result = clientCert.resolveContextCertOptions();
    assert.strictEqual(result.clientCertificates.length, 1);
    assert.strictEqual(result.ignoreHTTPSErrors, true);
    assert.ok(warnings.some((w) => w.includes('自动放宽 HTTPS 证书校验')));
  });
});
test('显式 false 时不被自动放宽覆盖', () => {
  withEnv(
    {
      PW_CLIENT_CERT_PFX: pfxFile,
      PW_CLIENT_CERT_ORIGINS: 'https://a.com',
      PW_IGNORE_HTTPS_ERRORS: 'false',
    },
    () => {
      const result = clientCert.resolveContextCertOptions();
      assert.strictEqual(result.ignoreHTTPSErrors, false);
    }
  );
});
test('未配置证书且未显式设置时保持 null（不改变原有行为）', () => {
  withEnv({}, () => {
    const result = clientCert.resolveContextCertOptions();
    assert.strictEqual(result.clientCertificates, null);
    assert.strictEqual(result.ignoreHTTPSErrors, null);
  });
});

console.log('\nhelpers.createContext 集成（stub playwright，不启动浏览器）');
test('createContext 把证书与 ignoreHTTPSErrors 传给 newContext', () => {
  // helpers.js 顶层 require('playwright')，而本目录没有 node_modules。
  // 这里用 Module._load 钩子注入一个最小 stub，从而在不安装依赖、不启动浏览器的前提下
  // 验证「解析出的选项确实被传进了 browser.newContext()」。
  const Module = require('module');
  const originalLoad = Module._load;
  Module._load = function (request, ...rest) {
    if (request === 'playwright') {
      return { chromium: {}, firefox: {}, webkit: {} };
    }
    return originalLoad.call(this, request, ...rest);
  };

  let helpers;
  try {
    const helpersPath = require.resolve('./lib/helpers');
    delete require.cache[helpersPath];
    helpers = require('./lib/helpers');
  } finally {
    Module._load = originalLoad;
  }

  // re-export 必须生效
  assert.strictEqual(typeof helpers.resolveContextCertOptions, 'function');
  assert.strictEqual(typeof helpers.getClientCertificatesFromEnv, 'function');
  assert.strictEqual(typeof helpers.getIgnoreHttpsErrorsFromEnv, 'function');

  const captured = {};
  const fakeBrowser = {
    newContext: async (options) => {
      captured.options = options;
      return { __fake: true };
    },
  };

  return withEnv(
    {
      PW_CLIENT_CERT_PFX: pfxFile,
      PW_CLIENT_CERT_PASSPHRASE: 'pw',
      PW_CLIENT_CERT_ORIGINS: 'https://a.example.com',
      PW_HEADER_NAME: 'X-Automated-By',
      PW_HEADER_VALUE: 'playwright-skill',
    },
    async () => {
      await helpers.createContext(fakeBrowser, { locale: 'zh-CN' });

      const options = captured.options;
      assert.ok(options, 'newContext 应被调用');
      assert.deepStrictEqual(options.clientCertificates, [
        { origin: 'https://a.example.com', pfxPath: pfxFile, passphrase: 'pw' },
      ]);
      // 已配置证书且未显式设置 PW_IGNORE_HTTPS_ERRORS -> 自动放宽（Node 侧键名是 HTTPS 全大写）
      assert.strictEqual(options.ignoreHTTPSErrors, true);
      // 原有能力未被破坏
      assert.strictEqual(options.locale, 'zh-CN');
      assert.strictEqual(options.extraHTTPHeaders['X-Automated-By'], 'playwright-skill');
    }
  );
});

test('未配置证书时不产生 clientCertificates / ignoreHTTPSErrors 键', () => {
  const Module = require('module');
  const originalLoad = Module._load;
  Module._load = function (request, ...rest) {
    if (request === 'playwright') {
      return { chromium: {}, firefox: {}, webkit: {} };
    }
    return originalLoad.call(this, request, ...rest);
  };

  let helpers;
  try {
    const helpersPath = require.resolve('./lib/helpers');
    delete require.cache[helpersPath];
    helpers = require('./lib/helpers');
  } finally {
    Module._load = originalLoad;
  }

  const captured = {};
  const fakeBrowser = {
    newContext: async (options) => {
      captured.options = options;
      return { __fake: true };
    },
  };

  return withEnv({}, async () => {
    await helpers.createContext(fakeBrowser, {});
    assert.ok(!('clientCertificates' in captured.options));
    assert.ok(!('ignoreHTTPSErrors' in captured.options));
  });
});

test('显式传入的 clientCertificates 优先于环境变量', () => {
  const Module = require('module');
  const originalLoad = Module._load;
  Module._load = function (request, ...rest) {
    if (request === 'playwright') {
      return { chromium: {}, firefox: {}, webkit: {} };
    }
    return originalLoad.call(this, request, ...rest);
  };

  let helpers;
  try {
    const helpersPath = require.resolve('./lib/helpers');
    delete require.cache[helpersPath];
    helpers = require('./lib/helpers');
  } finally {
    Module._load = originalLoad;
  }

  const captured = {};
  const fakeBrowser = {
    newContext: async (options) => {
      captured.options = options;
      return { __fake: true };
    },
  };

  const override = [{ origin: 'https://explicit.example.com', certPath: 'c', keyPath: 'k' }];

  return withEnv(
    { PW_CLIENT_CERT_PFX: pfxFile, PW_CLIENT_CERT_ORIGINS: 'https://env.example.com' },
    async () => {
      await helpers.createContext(fakeBrowser, { clientCertificates: override });
      assert.deepStrictEqual(captured.options.clientCertificates, override);
    }
  );
});

// 所有异步用例结束后再汇总
Promise.all(pending).then(() => {
  // 清理
  fs.rmSync(tmpDir, { recursive: true, force: true });

  console.log(`\n${passed} passed, ${failures.length} failed`);
  if (failures.length > 0) {
    console.log('\n失败用例：');
    for (const { name } of failures) {
      console.log(`  - ${name}`);
    }
  }
  console.log(
    '\n已知缺口：本文件不启动真实浏览器，因此无法验证「证书真的被服务端接受」，'
    + '也无法诊断 origin 不匹配导致的静默失败（属 TLS 握手层行为）。'
    + '\n建议合并后在真实环境手工验证一次（本地 nginx ssl_verify_client on：有证书 200 / 无证书 400）。'
  );
  process.exit(failures.length > 0 ? 1 : 0);
});
