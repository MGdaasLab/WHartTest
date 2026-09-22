// HTTPS 客户端证书支持 —— 纯环境变量解析
//
// 本模块刻意 **不 require('playwright')**，因此可以被零依赖单元测试直接加载
// （见 ../test_client_cert.js）。helpers.js 会 re-export 这里的函数。
//
// Playwright 的约束（Node 侧同样适用）：
//   1. `clientCertificates` 每一项的键名是 camelCase：origin / pfxPath / passphrase / certPath / keyPath。
//      写成 snake_case 会被静默忽略 —— 证书不生效且不报错。
//   2. `origin` 必填且需**精确匹配** `https://host[:port]`，不支持通配。
//   3. 证书文件在 newContext() 时才读取，文件不存在会抛 ENOENT。
//   4. Node 侧忽略 HTTPS 错误的选项名是 `ignoreHTTPSErrors`（HTTPS 全大写），
//      与 Python 侧的 `ignore_https_errors` 不同，勿混淆。

const fs = require('fs');

const TRUE_VALUES = ['1', 'true', 'yes', 'on'];
const FALSE_VALUES = ['0', 'false', 'no', 'off'];

/**
 * 把任意 URL 归一化为 Playwright 需要的 origin（`https://host[:port]`）。
 * 仅接受 https；丢弃 path/query/fragment/userinfo。WHATWG URL 的 `origin`
 * 恰好就是这个形式，且默认端口（443）会被自动省略。
 * @param {string} value
 * @returns {string|null} origin；无法解析或非 https 时返回 null
 */
function normalizeOrigin(value) {
  if (!value || typeof value !== 'string') return null;

  const raw = value.trim();
  if (!raw) return null;

  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    return null;
  }

  if (parsed.protocol !== 'https:') return null;

  return parsed.origin;
}

/**
 * 把若干「逗号分隔的 origin 字符串」合并为去重、保序的 origin 数组。
 * 非 https 与无法解析的项被丢弃。
 * @param {...string} values
 * @returns {string[]}
 */
function parseOrigins(...values) {
  const result = [];
  const seen = new Set();

  for (const value of values) {
    if (!value || typeof value !== 'string') continue;
    for (const chunk of value.split(',')) {
      const origin = normalizeOrigin(chunk);
      if (origin && !seen.has(origin)) {
        seen.add(origin);
        result.push(origin);
      }
    }
  }

  return result;
}

function readEnv(name) {
  const value = process.env[name];
  return typeof value === 'string' ? value.trim() : '';
}

/**
 * 从环境变量构造 Playwright `clientCertificates` 参数。
 *
 * 支持的变量：
 * - `PW_CLIENT_CERT_ORIGINS`     证书生效的 origin（逗号分隔，必填）
 * - `PW_CLIENT_CERT_PFX`         PKCS#12 文件路径（.pfx/.p12）
 * - `PW_CLIENT_CERT_PASSPHRASE`  PKCS#12 口令（可选）
 * - `PW_CLIENT_CERT_CERT` + `PW_CLIENT_CERT_KEY`  PEM 方案（与 pfx 二选一，优先 pfx）
 *
 * @returns {Array<Object>|null} 每个 origin 一条；未配置或不完整时返回 null
 */
function getClientCertificatesFromEnv() {
  const pfxPath = readEnv('PW_CLIENT_CERT_PFX');
  const certPath = readEnv('PW_CLIENT_CERT_CERT');
  const keyPath = readEnv('PW_CLIENT_CERT_KEY');
  const passphrase = readEnv('PW_CLIENT_CERT_PASSPHRASE');
  const origins = parseOrigins(readEnv('PW_CLIENT_CERT_ORIGINS'));

  const hasPfx = Boolean(pfxPath);
  const hasPem = Boolean(certPath) && Boolean(keyPath);

  if (!hasPfx && !hasPem) {
    if (pfxPath || certPath || keyPath) {
      console.warn(
        '[clientCert] PEM 客户端证书需要同时提供 PW_CLIENT_CERT_CERT 与 PW_CLIENT_CERT_KEY，'
        + '本次不启用客户端证书'
      );
    }
    return null;
  }

  if (origins.length === 0) {
    console.warn(
      '[clientCert] 已配置客户端证书但未提供 PW_CLIENT_CERT_ORIGINS；'
      + 'Playwright 要求 origin 精确匹配且不支持通配，本次不启用客户端证书'
    );
    return null;
  }

  if (hasPfx && hasPem) {
    console.warn('[clientCert] 同时提供了 pfx 与 PEM 证书，优先使用 pfx');
  }

  // 文件存在性只告警不阻断：显式报错比「证书被静默忽略」更容易排查
  for (const filePath of [pfxPath, certPath, keyPath].filter(Boolean)) {
    if (!fileExists(filePath)) {
      console.warn(
        `[clientCert] 客户端证书文件不存在：${filePath}（Playwright 会在创建上下文时报错）`
      );
    }
  }

  const common = hasPfx
    ? { pfxPath }
    : { certPath, keyPath };

  // 空口令不能带该键：Playwright 会把空字符串当作无效口令
  if (hasPfx && passphrase) {
    common.passphrase = passphrase;
  }

  return origins.map((origin) => ({ origin, ...common }));
}

function fileExists(filePath) {
  try {
    return fs.existsSync(filePath);
  } catch {
    return false;
  }
}

/**
 * 解析 `PW_IGNORE_HTTPS_ERRORS`。
 * @returns {boolean|null} true/false 为显式配置；null 表示未配置（auto）
 */
function getIgnoreHttpsErrorsFromEnv() {
  const raw = process.env.PW_IGNORE_HTTPS_ERRORS;
  if (raw === undefined || raw === null) return null;

  const normalized = String(raw).trim().toLowerCase();
  if (!normalized || normalized === 'auto') return null;
  if (TRUE_VALUES.includes(normalized)) return true;
  if (FALSE_VALUES.includes(normalized)) return false;

  console.warn(`[clientCert] 无法解析 PW_IGNORE_HTTPS_ERRORS="${raw}"，按 auto 处理`);
  return null;
}

/**
 * 综合解析出最终要传给 newContext 的两个选项。
 *
 * auto 语义（与 WHartTest_Actuator 的 ignore_https_errors 保持一致）：
 * `PW_IGNORE_HTTPS_ERRORS` 未配置时，若已启用客户端证书则自动放宽 TLS 校验
 * —— 需要客户端证书的站点绝大多数同时使用自签名服务端证书。
 *
 * @returns {{clientCertificates: Array<Object>|null, ignoreHTTPSErrors: boolean|null}}
 */
function resolveContextCertOptions() {
  const clientCertificates = getClientCertificatesFromEnv();
  let ignoreHTTPSErrors = getIgnoreHttpsErrorsFromEnv();

  if (ignoreHTTPSErrors === null && clientCertificates) {
    ignoreHTTPSErrors = true;
    console.warn(
      '[clientCert] 已启用客户端证书，自动放宽 HTTPS 证书校验（ignoreHTTPSErrors=true）；'
      + '如需强制校验请设置 PW_IGNORE_HTTPS_ERRORS=false'
    );
  }

  return { clientCertificates, ignoreHTTPSErrors };
}

module.exports = {
  normalizeOrigin,
  parseOrigins,
  getClientCertificatesFromEnv,
  getIgnoreHttpsErrorsFromEnv,
  resolveContextCertOptions,
};
