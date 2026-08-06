// Playwright 辅助函数模块
// Playwright 自动化可复用工具函数

const { chromium, firefox, webkit } = require('playwright');

/**
 * 从环境变量解析额外 HTTP 请求头。
 * 支持两种格式：
 * - PW_HEADER_NAME + PW_HEADER_VALUE：单个请求头（简单常用）
 * - PW_EXTRA_HEADERS：多个请求头的 JSON 对象（高级用法）
 * 若两种同时存在，优先使用单请求头格式。
 * @returns {Object|null} 请求头对象；若未配置则返回 null
 */
function getExtraHeadersFromEnv() {
  const headerName = process.env.PW_HEADER_NAME;
  const headerValue = process.env.PW_HEADER_VALUE;

  if (headerName && headerValue) {
    return { [headerName]: headerValue };
  }

  const headersJson = process.env.PW_EXTRA_HEADERS;
  if (headersJson) {
    try {
      const parsed = JSON.parse(headersJson);
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        return parsed;
      }
      console.warn('PW_EXTRA_HEADERS must be a JSON object, ignoring...');
    } catch (e) {
      console.warn('Failed to parse PW_EXTRA_HEADERS as JSON:', e.message);
    }
  }

  return null;
}

/**
 * 以标准配置启动浏览器
 * @param {string} browserType - 浏览器类型：'chromium'、'firefox' 或 'webkit'
 * @param {Object} options - 额外启动配置
 */
async function launchBrowser(browserType = 'chromium', options = {}) {
  const defaultOptions = {
    headless: process.env.HEADLESS !== 'false',
    slowMo: process.env.SLOW_MO ? parseInt(process.env.SLOW_MO) : 0,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  };
  
  const browsers = { chromium, firefox, webkit };
  const browser = browsers[browserType];
  
  if (!browser) {
    throw new Error(`Invalid browser type: ${browserType}`);
  }
  
  return await browser.launch({ ...defaultOptions, ...options });
}

/**
 * 创建新页面并应用视口与 UA 配置
 * @param {Object} context - 浏览器上下文
 * @param {Object} options - 页面配置
 */
async function createPage(context, options = {}) {
  const page = await context.newPage();
  
  if (options.viewport) {
    await page.setViewportSize(options.viewport);
  }
  
  if (options.userAgent) {
    await page.setExtraHTTPHeaders({
      'User-Agent': options.userAgent
    });
  }
  
  // 设置默认超时时间
  page.setDefaultTimeout(options.timeout || 30000);
  
  return page;
}

/**
 * 智能等待页面就绪
 * @param {Object} page - Playwright 页面对象
 * @param {Object} options - 等待配置
 */
async function waitForPageReady(page, options = {}) {
  const waitOptions = {
    waitUntil: options.waitUntil || 'networkidle',
    timeout: options.timeout || 30000
  };
  
  try {
    await page.waitForLoadState(waitOptions.waitUntil, { 
      timeout: waitOptions.timeout 
    });
  } catch (e) {
    console.warn('Page load timeout, continuing...');
  }
  
  // 若提供了选择器，则额外等待动态内容出现
  if (options.waitForSelector) {
    await page.waitForSelector(options.waitForSelector, { 
      timeout: options.timeout 
    });
  }
}

/**
 * 带重试机制的安全点击
 * @param {Object} page - Playwright 页面对象
 * @param {string} selector - 元素选择器
 * @param {Object} options - 点击配置
 */
async function safeClick(page, selector, options = {}) {
  const maxRetries = options.retries || 3;
  const retryDelay = options.retryDelay || 1000;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      await page.waitForSelector(selector, { 
        state: 'visible',
        timeout: options.timeout || 5000 
      });
      await page.click(selector, {
        force: options.force || false,
        timeout: options.timeout || 5000
      });
      return true;
    } catch (e) {
      if (i === maxRetries - 1) {
        console.error(`Failed to click ${selector} after ${maxRetries} attempts`);
        throw e;
      }
      console.log(`Retry ${i + 1}/${maxRetries} for clicking ${selector}`);
      await page.waitForTimeout(retryDelay);
    }
  }
}

/**
 * 安全文本输入（输入前可先清空）
 * @param {Object} page - Playwright 页面对象
 * @param {string} selector - 输入框选择器
 * @param {string} text - 要输入的文本
 * @param {Object} options - 输入配置
 */
async function safeType(page, selector, text, options = {}) {
  await page.waitForSelector(selector, { 
    state: 'visible',
    timeout: options.timeout || 10000 
  });
  
  if (options.clear !== false) {
    await page.fill(selector, '');
  }
  
  if (options.slow) {
    await page.type(selector, text, { delay: options.delay || 100 });
  } else {
    await page.fill(selector, text);
  }
}

/**
 * 批量提取多个元素文本
 * @param {Object} page - Playwright 页面对象
 * @param {string} selector - 元素选择器
 */
async function extractTexts(page, selector) {
  await page.waitForSelector(selector, { timeout: 10000 });
  return await page.$$eval(selector, elements => 
    elements.map(el => el.textContent?.trim()).filter(Boolean)
  );
}

/**
 * 截图并附加时间戳
 * @param {Object} page - Playwright 页面对象
 * @param {string} name - 截图名称
 * @param {Object} options - 截图配置
 */
async function takeScreenshot(page, name, options = {}) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `${name}-${timestamp}.png`;
  
  await page.screenshot({
    path: filename,
    fullPage: options.fullPage !== false,
    ...options
  });
  
  console.log(`Screenshot saved: ${filename}`);
  return filename;
}

/**
 * 处理登录认证流程
 * @param {Object} page - Playwright 页面对象
 * @param {Object} credentials - 用户名与密码
 * @param {Object} selectors - 登录表单选择器
 */
async function authenticate(page, credentials, selectors = {}) {
  const defaultSelectors = {
    username: 'input[name="username"], input[name="email"], #username, #email',
    password: 'input[name="password"], #password',
    submit: 'button[type="submit"], input[type="submit"], button:has-text("Login"), button:has-text("Sign in")'
  };
  
  const finalSelectors = { ...defaultSelectors, ...selectors };
  
  await safeType(page, finalSelectors.username, credentials.username);
  await safeType(page, finalSelectors.password, credentials.password);
  await safeClick(page, finalSelectors.submit);
  
  // 等待页面跳转或登录成功标识
  await Promise.race([
    page.waitForNavigation({ waitUntil: 'networkidle' }),
    page.waitForSelector(selectors.successIndicator || '.dashboard, .user-menu, .logout', { timeout: 10000 })
  ]).catch(() => {
    console.log('Login might have completed without navigation');
  });
}

/**
 * 滚动页面
 * @param {Object} page - Playwright 页面对象
 * @param {string} direction - 滚动方向：'down'、'up'、'top'、'bottom'
 * @param {number} distance - 滚动像素（仅对 up/down 生效）
 */
async function scrollPage(page, direction = 'down', distance = 500) {
  switch (direction) {
    case 'down':
      await page.evaluate(d => window.scrollBy(0, d), distance);
      break;
    case 'up':
      await page.evaluate(d => window.scrollBy(0, -d), distance);
      break;
    case 'top':
      await page.evaluate(() => window.scrollTo(0, 0));
      break;
    case 'bottom':
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      break;
  }
  await page.waitForTimeout(500); // 等待滚动动画完成
}

/**
 * 提取表格数据
 * @param {Object} page - Playwright 页面对象
 * @param {string} tableSelector - 表格选择器
 */
async function extractTableData(page, tableSelector) {
  await page.waitForSelector(tableSelector);
  
  return await page.evaluate((selector) => {
    const table = document.querySelector(selector);
    if (!table) return null;
    
    const headers = Array.from(table.querySelectorAll('thead th')).map(th => 
      th.textContent?.trim()
    );
    
    const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr => {
      const cells = Array.from(tr.querySelectorAll('td'));
      if (headers.length > 0) {
        return cells.reduce((obj, cell, index) => {
          obj[headers[index] || `column_${index}`] = cell.textContent?.trim();
          return obj;
        }, {});
      } else {
        return cells.map(cell => cell.textContent?.trim());
      }
    });
    
    return { headers, rows };
  }, tableSelector);
}

/**
 * 等待并关闭 Cookie 提示条
 * @param {Object} page - Playwright 页面对象
 * @param {number} timeout - 最大等待时间
 */
async function handleCookieBanner(page, timeout = 3000) {
  const commonSelectors = [
    'button:has-text("Accept")',
    'button:has-text("Accept all")',
    'button:has-text("OK")',
    'button:has-text("Got it")',
    'button:has-text("I agree")',
    '.cookie-accept',
    '#cookie-accept',
    '[data-testid="cookie-accept"]'
  ];
  
  for (const selector of commonSelectors) {
    try {
      const element = await page.waitForSelector(selector, { 
        timeout: timeout / commonSelectors.length,
        state: 'visible'
      });
      if (element) {
        await element.click();
        console.log('Cookie banner dismissed');
        return true;
      }
    } catch (e) {
      // 当前选择器失败，继续尝试下一个
    }
  }
  
  return false;
}

/**
 * 使用指数退避重试函数
 * @param {Function} fn - 待重试函数
 * @param {number} maxRetries - 最大重试次数
 * @param {number} initialDelay - 初始延迟（毫秒）
 */
async function retryWithBackoff(fn, maxRetries = 3, initialDelay = 1000) {
  let lastError;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      const delay = initialDelay * Math.pow(2, i);
      console.log(`Attempt ${i + 1} failed, retrying in ${delay}ms...`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  throw lastError;
}

/**
 * 使用通用配置创建浏览器上下文
 * @param {Object} browser - 浏览器实例
 * @param {Object} options - 上下文配置
 */
async function createContext(browser, options = {}) {
  const envHeaders = getExtraHeadersFromEnv();

  // 将环境变量请求头与传入配置合并
  const mergedHeaders = {
    ...envHeaders,
    ...options.extraHTTPHeaders
  };

  const defaultOptions = {
    viewport: { width: 1280, height: 720 },
    userAgent: options.mobile
      ? 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1'
      : undefined,
    permissions: options.permissions || [],
    geolocation: options.geolocation,
    locale: options.locale || 'en-US',
    timezoneId: options.timezoneId || 'America/New_York',
    // 仅在存在请求头时附加 extraHTTPHeaders
    ...(Object.keys(mergedHeaders).length > 0 && { extraHTTPHeaders: mergedHeaders })
  };

  return await browser.newContext({ ...defaultOptions, ...options });
}

/**
 * 在常见端口检测正在运行的开发服务器
 * @param {Array<number>} customPorts - 额外要检测的端口
 * @returns {Promise<Array>} 检测到的服务 URL 列表
 */
async function detectDevServers(customPorts = []) {
  const http = require('http');

  // 常见开发服务器端口
  const commonPorts = [3000, 3001, 3002, 5173, 8080, 8000, 4200, 5000, 9000, 1234];
  const allPorts = [...new Set([...commonPorts, ...customPorts])];

  const detectedServers = [];

  console.log('🔍 Checking for running dev servers...');

  for (const port of allPorts) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.request({
          hostname: 'localhost',
          port: port,
          path: '/',
          method: 'HEAD',
          timeout: 500
        }, (res) => {
          if (res.statusCode < 500) {
            detectedServers.push(`http://localhost:${port}`);
            console.log(`  ✅ Found server on port ${port}`);
          }
          resolve();
        });

        req.on('error', () => resolve());
        req.on('timeout', () => {
          req.destroy();
          resolve();
        });

        req.end();
      });
    } catch (e) {
      // 端口不可用，继续检测
    }
  }

  if (detectedServers.length === 0) {
    console.log('  ❌ No dev servers detected');
  }

  return detectedServers;
}

/**
 * 获取可读页面文本（便于 AI 理解）
 * @param {Object} page - Playwright 页面对象
 * @returns {string} 页面文本内容
 */
async function getPageText(page) {
  return await page.innerText('body');
}

/**
 * 获取页面结构，帮助 AI 理解可交互元素
 * 返回表单、按钮、链接、输入框等简化结构
 * @param {Object} page - Playwright 页面对象
 * @returns {Object} 页面结构信息（表单/按钮/链接/输入框）
 */
async function getPageStructure(page) {
  return await page.evaluate(() => {
    const getSelector = (el) => {
      if (el.id) return `#${el.id}`;
      if (el.name) return `[name="${el.name}"]`;
      if (el.type) return `${el.tagName.toLowerCase()}[type="${el.type}"]`;
      if (el.className) return `${el.tagName.toLowerCase()}.${el.className.split(' ')[0]}`;
      return el.tagName.toLowerCase();
    };

    const inputs = Array.from(document.querySelectorAll('input, textarea, select')).map(el => ({
      type: el.type || el.tagName.toLowerCase(),
      name: el.name || null,
      id: el.id || null,
      placeholder: el.placeholder || null,
      selector: getSelector(el),
      value: el.type === 'password' ? '***' : (el.value || null)
    }));

    const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], [role="button"]')).map(el => ({
      text: el.innerText?.trim() || el.value || null,
      type: el.type || null,
      selector: getSelector(el)
    }));

    const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 20).map(el => ({
      text: el.innerText?.trim() || null,
      href: el.href,
      selector: getSelector(el)
    }));

    const headings = Array.from(document.querySelectorAll('h1, h2, h3')).map(el => ({
      level: el.tagName,
      text: el.innerText?.trim()
    }));

    return {
      title: document.title,
      url: window.location.href,
      headings,
      inputs,
      buttons,
      links: links.filter(l => l.text)
    };
  });
}

/**
 * 以可读格式生成页面描述（供 AI 使用）
 * @param {Object} page - Playwright 页面对象
 * @returns {string} 人类与 AI 都易读的页面描述
 */
async function describePageForAI(page) {
  const structure = await getPageStructure(page);
  let desc = `## Page: ${structure.title}\nURL: ${structure.url}\n\n`;

  if (structure.headings.length > 0) {
    desc += `### Headings\n`;
    structure.headings.forEach(h => { desc += `- ${h.level}: ${h.text}\n`; });
    desc += '\n';
  }

  if (structure.inputs.length > 0) {
    desc += `### Input Fields (${structure.inputs.length})\n`;
    structure.inputs.forEach(i => {
      desc += `- ${i.type}: selector="${i.selector}"`;
      if (i.placeholder) desc += ` placeholder="${i.placeholder}"`;
      if (i.name) desc += ` name="${i.name}"`;
      desc += '\n';
    });
    desc += '\n';
  }

  if (structure.buttons.length > 0) {
    desc += `### Buttons (${structure.buttons.length})\n`;
    structure.buttons.forEach(b => {
      desc += `- "${b.text || 'no text'}": selector="${b.selector}"\n`;
    });
    desc += '\n';
  }

  if (structure.links.length > 0) {
    desc += `### Links (showing ${structure.links.length})\n`;
    structure.links.forEach(l => {
      desc += `- "${l.text}": ${l.href}\n`;
    });
  }

  return desc;
}

module.exports = {
  launchBrowser,
  createPage,
  waitForPageReady,
  safeClick,
  safeType,
  extractTexts,
  takeScreenshot,
  authenticate,
  scrollPage,
  extractTableData,
  handleCookieBanner,
  retryWithBackoff,
  createContext,
  detectDevServers,
  getExtraHeadersFromEnv,
  getPageText,
  getPageStructure,
  describePageForAI
};
