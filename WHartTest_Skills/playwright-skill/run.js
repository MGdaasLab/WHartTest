#!/usr/bin/env node
/**
 * Claude Code 通用 Playwright 执行器
 *
 * 支持以下方式执行 Playwright 自动化代码：
 * - 文件路径：node run.js script.js
 * - 内联代码：node run.js 'await page.goto("...")'
 * - 标准输入：cat script.js | node run.js
 *
 * 通过在 skill 目录执行，确保模块解析路径正确。
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// 切换到 skill 目录，确保模块解析正确
process.chdir(__dirname);

/**
 * 检查是否已安装 Playwright
 */
function checkPlaywrightInstalled() {
  try {
    require.resolve('playwright');
    return true;
  } catch (e) {
    return false;
  }
}

/**
 * 若缺失则安装 Playwright
 */
function installPlaywright() {
  console.log('📦 Playwright not found. Installing...');
  try {
    execSync('npm install', { stdio: 'inherit', cwd: __dirname });
    execSync('npx playwright install chromium', { stdio: 'inherit', cwd: __dirname });
    console.log('✅ Playwright installed successfully');
    return true;
  } catch (e) {
    console.error('❌ Failed to install Playwright:', e.message);
    console.error('Please run manually: cd', __dirname, '&& npm run setup');
    return false;
  }
}

/**
 * 从不同输入源获取待执行代码
 */
function getCodeToExecute() {
  const args = process.argv.slice(2);

  // 情况1：传入了文件路径
  if (args.length > 0 && fs.existsSync(args[0])) {
    const filePath = path.resolve(args[0]);
    console.log(`📄 Executing file: ${filePath}`);
    return fs.readFileSync(filePath, 'utf8');
  }

  // 情况2：通过参数传入内联代码
  if (args.length > 0) {
    console.log('⚡ Executing inline code');
    return args.join(' ');
  }

  // 情况3：从标准输入读取代码
  if (!process.stdin.isTTY) {
    console.log('📥 Reading from stdin');
    return fs.readFileSync(0, 'utf8');
  }

  // 没有输入内容
  console.error('❌ No code to execute');
  console.error('Usage:');
  console.error('  node run.js script.js          # Execute file');
  console.error('  node run.js "code here"        # Execute inline');
  console.error('  cat script.js | node run.js    # Execute from stdin');
  process.exit(1);
}

/**
 * 清理历史运行遗留的临时执行文件
 */
function cleanupOldTempFiles() {
  try {
    const files = fs.readdirSync(__dirname);
    const tempFiles = files.filter(f => f.startsWith('.temp-execution-') && f.endsWith('.js'));

    if (tempFiles.length > 0) {
      tempFiles.forEach(file => {
        const filePath = path.join(__dirname, file);
        try {
          fs.unlinkSync(filePath);
        } catch (e) {
          // 忽略清理异常：文件可能正在使用或已被删除
        }
      });
    }
  } catch (e) {
    // 忽略目录读取异常
  }
}

/**
 * 若代码尚未包裹为 async IIFE，则自动包裹
 */
function wrapCodeIfNeeded(code) {
  // 检查代码是否已包含 require() 与 async 结构
  const hasRequire = code.includes('require(');
  const hasAsyncIIFE = code.includes('(async () => {') || code.includes('(async()=>{');

  // 若已是完整脚本，直接返回
  if (hasRequire && hasAsyncIIFE) {
    return code;
  }

  // 若仅是 Playwright 指令，套用完整模板
  if (!hasRequire) {
    return `
const { chromium, firefox, webkit, devices } = require('playwright');
const helpers = require('./lib/helpers');

// 从环境变量读取额外请求头（如有配置）
const __extraHeaders = helpers.getExtraHeadersFromEnv();

/**
 * 将环境变量请求头合并到 context 配置。
 * 当直接使用原生 Playwright API 创建 context（而非 helpers.createContext）时使用。
 * @param {Object} options - Context 配置
 * @returns {Object} 合并了 extraHTTPHeaders 的配置对象
 */
function getContextOptionsWithHeaders(options = {}) {
  if (!__extraHeaders) return options;
  return {
    ...options,
    extraHTTPHeaders: {
      ...__extraHeaders,
      ...(options.extraHTTPHeaders || {})
    }
  };
}

(async () => {
  try {
    ${code}
  } catch (error) {
    console.error('❌ Automation error:', error.message);
    if (error.stack) {
      console.error(error.stack);
    }
    process.exit(1);
  }
})();
`;
  }

  // 若有 require 但没有 async 包裹
  if (!hasAsyncIIFE) {
    return `
(async () => {
  try {
    ${code}
  } catch (error) {
    console.error('❌ Automation error:', error.message);
    if (error.stack) {
      console.error(error.stack);
    }
    process.exit(1);
  }
})();
`;
  }

  return code;
}

/**
 * 主执行入口
 */
async function main() {
  console.log('🎭 Playwright Skill - Universal Executor\n');

  // 清理历史临时文件
  cleanupOldTempFiles();

  // 检查 Playwright 安装状态
  if (!checkPlaywrightInstalled()) {
    const installed = installPlaywright();
    if (!installed) {
      process.exit(1);
    }
  }

  // 获取并处理待执行代码
  const rawCode = getCodeToExecute();
  const code = wrapCodeIfNeeded(rawCode);

  // 创建临时文件用于执行
  const tempFile = path.join(__dirname, `.temp-execution-${Date.now()}.js`);

  try {
    // 写入临时代码文件
    fs.writeFileSync(tempFile, code, 'utf8');

    // 使用子进程执行代码，确保异步流程完整结束
    console.log('🚀 Starting automation...\n');
    const { spawn } = require('child_process');
    const child = spawn('node', [tempFile], {
      stdio: 'inherit',
      cwd: __dirname
    });

    // 等待子进程执行完成
    await new Promise((resolve, reject) => {
      child.on('close', (code) => {
        // 执行结束后清理临时文件
        try {
          fs.unlinkSync(tempFile);
        } catch (e) {
          // 忽略清理异常
        }
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(`Process exited with code ${code}`));
        }
      });
      child.on('error', reject);
    });

  } catch (error) {
    console.error('❌ Execution failed:', error.message);
    if (error.stack) {
      console.error('\n📋 Stack trace:');
      console.error(error.stack);
    }
    process.exit(1);
  }
}

// 运行主函数
main().catch(error => {
  console.error('❌ Fatal error:', error.message);
  process.exit(1);
});
