---
name: playwright-skill
description: 浏览器自动化执行工具。用于执行 Web 页面测试、表单填写、登录验证、截图等浏览器操作。
---

# Playwright 浏览器自动化

执行浏览器自动化任务，支持页面测试、表单操作、登录验证等。

## ⚠️ 强制规则：先获取页面结构，再操作元素

**禁止猜测选择器！禁止通过截图识别元素！**

打开任何页面后，必须**立即**调用 `helpers.describePageForAI(page)` 获取页面元素列表，然后根据返回的选择器进行操作。

```javascript
// 打开页面后第一件事：获取页面结构
await page.goto('http://example.com');
const desc = await helpers.describePageForAI(page);
console.log(desc);  // 输出所有可交互元素及其选择器
```

输出示例：
```
## Page: WHartTest
URL: http://192.168.150.114:8913/login

### Input Fields (2)
- text: selector="#username" placeholder="请输入用户名"
- password: selector="#password" placeholder="请输入密码"

### Buttons (1)
- "登录": selector="button[type="submit"]"
```

然后根据输出的选择器进行操作：
```javascript
await page.fill('#username', 'admin');
await page.fill('#password', '123456');
await page.click('button[type="submit"]');
```

## 使用方法

通过 `execute_skill_script` 工具调用，传入 inline 代码：

```
node run.js "your playwright code here"
```

**重要**：代码必须写在一行，语句用分号分隔。run.js 会自动包装 async IIFE 和 require 语句。**禁止添加 --session、--inline、--eval 等参数，run.js 不支持这些参数。**

## 截图路径约定

**必须使用环境变量 `process.env.SCREENSHOT_DIR`** 作为截图保存目录。系统会自动设置该变量指向 playwright-skill 目录下的 `media/screenshots/` 子目录。

截图命名建议：`case_{case_id}_step{step_number}.png`

**示例**：
```javascript
const screenshotDir = process.env.SCREENSHOT_DIR || './media/screenshots';
await page.screenshot({ path: `${screenshotDir}/case_11_step1.png` });
```

## 基础示例

### 打开页面并截图

```bash
node run.js "const dir = process.env.SCREENSHOT_DIR; const browser = await chromium.launch({ headless: false }); const page = await browser.newPage(); await page.goto('http://example.com'); await page.screenshot({ path: dir + '/example.png' }); console.log('截图已保存:', dir + '/example.png'); await browser.close();"
```

### 登录测试（带截图）

```bash
node run.js "const dir = process.env.SCREENSHOT_DIR; const browser = await chromium.launch({ headless: false, slowMo: 100 }); const page = await browser.newPage(); await page.goto('http://192.168.150.114:8913/'); await page.screenshot({ path: dir + '/step1_open.png' }); await page.fill('input[type=\"text\"]', 'admin'); await page.fill('input[type=\"password\"]', 'admin123456'); await page.screenshot({ path: dir + '/step2_filled.png' }); await page.click('button[type=\"submit\"]'); await page.waitForTimeout(2000); await page.screenshot({ path: dir + '/step3_result.png' }); console.log('截图已保存到', dir); await browser.close();"
```

### 表单填写

```bash
node run.js "const browser = await chromium.launch({ headless: false }); const page = await browser.newPage(); await page.goto('http://example.com/form'); await page.fill('input[name=\"username\"]', 'testuser'); await page.fill('input[name=\"email\"]', 'test@example.com'); await page.click('button[type=\"submit\"]'); console.log('表单提交完成'); await browser.close();"
```

## 其他 helpers 函数

### helpers.getPageStructure(page) - 获取结构化 JSON

返回 JSON 对象，适合程序化处理。

```javascript
const structure = await helpers.getPageStructure(page);
console.log(JSON.stringify(structure, null, 2));
```

### helpers.getPageText(page) - 获取纯文本内容

返回页面所有可见文本。

```javascript
const text = await helpers.getPageText(page);
console.log(text);
```

## 常用 API

### 浏览器启动

```javascript
// 可见模式（推荐调试）
const browser = await chromium.launch({ headless: false, slowMo: 100 });

// 无头模式（后台执行）
const browser = await chromium.launch({ headless: true });
```

### 页面导航

```javascript
await page.goto('http://example.com');
await page.goto('http://example.com', { waitUntil: 'networkidle' });
```

### 元素定位与操作

```javascript
// 输入文本
await page.fill('input[name="username"]', 'admin');
await page.fill('input[type="password"]', '123456');

// 点击
await page.click('button[type="submit"]');
await page.click('text=登录');
await page.click('.login-btn');

// 等待元素
await page.waitForSelector('.success-message');
await page.waitForURL('**/dashboard');
```

### 常用选择器

| 选择器类型 | 示例 |
|-----------|------|
| CSS | `input[name="username"]`, `.login-btn`, `#submit` |
| 文本 | `text=登录`, `button:has-text("提交")` |
| 类型 | `input[type="text"]`, `input[type="password"]` |
| 占位符 | `input[placeholder*="账号"]`, `input[placeholder*="密码"]` |

### 截图（使用环境变量）

```javascript
const dir = process.env.SCREENSHOT_DIR;
await page.screenshot({ path: `${dir}/screenshot.png` });
await page.screenshot({ path: `${dir}/full.png`, fullPage: true });
```

### 等待

```javascript
await page.waitForTimeout(2000);  // 等待2秒
await page.waitForLoadState('networkidle');  // 等待网络空闲
```

## 完整测试流程示例

执行一个完整的登录测试：

```bash
node run.js "const dir = process.env.SCREENSHOT_DIR; const browser = await chromium.launch({ headless: false, slowMo: 100 }); const page = await browser.newPage(); console.log('步骤1: 打开登录页'); await page.goto('http://192.168.150.114:8913/'); await page.screenshot({ path: dir + '/step1_open.png' }); console.log('步骤2: 输入账号'); await page.fill('input[type=\"text\"]', 'admin'); console.log('步骤3: 输入密码'); await page.fill('input[type=\"password\"]', 'admin123456'); await page.screenshot({ path: dir + '/step2_input.png' }); console.log('步骤4: 点击登录'); await page.click('button[type=\"submit\"]'); await page.waitForTimeout(2000); await page.screenshot({ path: dir + '/step3_result.png' }); console.log('登录结果 - 当前URL:', page.url()); await browser.close(); console.log('测试完成，截图保存在:', dir);"
```

## 注意事项

1. **截图路径**：必须使用 `process.env.SCREENSHOT_DIR` 环境变量
2. **代码格式**：inline 代码用分号分隔语句，写在一行内
3. **引号转义**：字符串内的双引号需要转义 `\"`
4. **browser.close()**：非持久化模式下执行完毕后务必关闭浏览器
5. **console.log()**：用于输出执行进度和结果
6. **headless: false**：调试时使用可见模式，方便观察

## 持久化会话模式

对于需要**跨多个步骤保持浏览器打开**的场景（如自动化测试用例），使用 `session_id` 参数：

### ⚠️ 核心规则（必须严格遵守）

1. **session_id 必须完全一致**：整个测试流程中所有步骤**必须使用完全相同的 session_id 字符串**，否则会创建新浏览器导致状态丢失！
   - ✅ 正确：所有步骤都用 `session_id="case_11"`
   - ❌ 错误：第一步用 `case_11`，第二步用 `case-11`，第三步用 `test-case-11`（这会创建3个不同的浏览器！）
2. **直接使用 `page` 变量**：无需 `chromium.launch()`，系统自动管理
3. **不要调用 `browser.close()`**：浏览器由系统管理，空闲 15 分钟自动关闭

### 持久化模式示例

**步骤 1：打开页面**
```python
execute_skill_script(
    skill_name="playwright-skill",
    command='node run.js "await page.goto(\'http://example.com\'); console.log(page.url());"',
    session_id="test-case-001"
)
```

**步骤 2：填写表单（复用同一浏览器）**
```python
execute_skill_script(
    skill_name="playwright-skill",
    command='node run.js "await page.fill(\'input[name=username]\', \'admin\'); await page.fill(\'input[name=password]\', \'123456\');"',
    session_id="test-case-001"
)
```

**步骤 3：点击登录（继续复用）**
```python
execute_skill_script(
    skill_name="playwright-skill",
    command='node run.js "await page.click(\'button[type=submit]\'); await page.waitForTimeout(2000); console.log(\'登录后URL:\', page.url());"',
    session_id="test-case-001"
)
```

### 持久化 vs 非持久化对比

| 特性 | 非持久化（无 session_id） | 持久化（有 session_id） |
|------|--------------------------|------------------------|
| 浏览器生命周期 | 代码手动管理 | 系统自动管理 |
| 启动方式 | `chromium.launch()` | 直接使用 `page` |
| 关闭方式 | `browser.close()` | 自动关闭（15分钟空闲） |
| 跨步骤状态 | 不保持 | 保持（登录态、cookie等） |
| 适用场景 | 单步操作 | 多步骤测试用例 |
