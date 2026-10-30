import assert from 'node:assert/strict';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

const sourcePath = new URL('../src/utils/responseError.ts', import.meta.url);

assert.equal(
  existsSync(sourcePath),
  true,
  'responseError.ts should expose shared field-level error helpers'
);

const source = readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;

const compiledPath = join(tmpdir(), `responseError-${Date.now()}.mjs`);
writeFileSync(compiledPath, compiled);

const {
  extractFieldErrorMessages,
  joinFieldErrorMessages,
} = await import(pathToFileURL(compiledPath).href);

// ── 回归用例：用户上报的真实缺陷 ──
// 新建用户时后端返回统一响应（UnifiedResponseRenderer）：
//   { status: 'error', code: 400, message: '请求参数有误或处理失败',
//     data: null, errors: { password: ['密码只包含数字。'] } }
// 前端拦截器此前只透出顶层 message，用户只看到泛化文案；修复后必须能取出具体原因。
const createUserErrorPayload = {
  status: 'error',
  code: 400,
  message: '请求参数有误或处理失败',
  data: null,
  errors: { password: ['密码只包含数字。'] },
};
assert.deepEqual(
  extractFieldErrorMessages(createUserErrorPayload.errors),
  ['密码只包含数字。'],
  'must surface the field-level validation message hidden in errors'
);
assert.equal(
  joinFieldErrorMessages(createUserErrorPayload.errors),
  '密码只包含数字。',
  'single field error should render as that message itself'
);

// 多字段、多条错误：按字段出现顺序拼接，分隔符可指定（英文界面用 '; '）。
const multiFieldErrors = {
  email: ['该邮箱已被注册。'],
  password: ['密码长度至少 8 位。', '密码只包含数字。'],
};
assert.deepEqual(extractFieldErrorMessages(multiFieldErrors), [
  '该邮箱已被注册。',
  '密码长度至少 8 位。',
  '密码只包含数字。',
]);
assert.equal(
  joinFieldErrorMessages(multiFieldErrors),
  '该邮箱已被注册。；密码长度至少 8 位。；密码只包含数字。'
);
assert.equal(
  joinFieldErrorMessages(multiFieldErrors, '; '),
  '该邮箱已被注册。; 密码长度至少 8 位。; 密码只包含数字。'
);

// 元数据键（错误码 / 透传文案）不是字段级详情，不得混入提示。
assert.deepEqual(
  extractFieldErrorMessages({
    token_error: '授权已过期',
    error_code: 'LICENSE_EXPIRED',
    detail: '账号或密码错误',
    message: '请求参数有误或处理失败',
    status: 'error',
    code: 401,
    data: null,
  }),
  [],
  'meta-only errors must fall back to the existing message chain'
);

// 渲染器的列表形态错误（isinstance(data, (dict, list))）与非字符串条目。
assert.deepEqual(extractFieldErrorMessages(['第一个错误', '第二个错误']), [
  '第一个错误',
  '第二个错误',
]);
assert.deepEqual(extractFieldErrorMessages([404, null, '', '有效错误']), ['404', '有效错误']);

// 嵌套序列化器错误递归取具体文案，而不是 '[object Object]'。
assert.deepEqual(
  extractFieldErrorMessages({ profile: { phone: ['电话号码格式不正确。'] } }),
  ['电话号码格式不正确。']
);

// DRF 非字段级错误必须透出（旧 extractValidationMessage 的优先键）。
assert.deepEqual(
  extractFieldErrorMessages({ non_field_errors: ['两个日期必须二选一。'] }),
  ['两个日期必须二选一。']
);

// 兼容旧拦截器分支的 errors.error 形态（外部后端）。
assert.deepEqual(extractFieldErrorMessages({ error: '通道不存在' }), ['通道不存在']);

// 同句文案在多个字段出现时保序去重（password 与 confirm_password 同报一句）。
assert.deepEqual(
  extractFieldErrorMessages({
    password: ['密码只包含数字。'],
    confirm_password: ['密码只包含数字。'],
  }),
  ['密码只包含数字。']
);

// 循环引用防护：共享工具可能接到非 JSON 来源（如 axios error 对象天然成环），
// 必须终止递归而不是栈溢出。
const cyclic = { password: ['循环错误。'] };
cyclic.self = cyclic;
assert.doesNotThrow(() => extractFieldErrorMessages(cyclic));
assert.deepEqual(extractFieldErrorMessages(cyclic), ['循环错误。']);

// 空值 / 原始值输入一律不抛错，返回空数组或等价文案（拦截器渲染路径直接依赖）。
for (const value of [null, undefined, '', '   ', {}, [], 0, false]) {
  assert.doesNotThrow(() => extractFieldErrorMessages(value));
  assert.equal(
    joinFieldErrorMessages(value),
    undefined,
    `joinFieldErrorMessages(${JSON.stringify(value)}) must be undefined so the fallback chain runs`
  );
}
assert.deepEqual(extractFieldErrorMessages('裸字符串错误'), ['裸字符串错误']);

// ── 回归防线：request.ts 必须在顶层 message 之前解析字段级错误 ──
const requestSource = readFileSync(
  new URL('../src/utils/request.ts', import.meta.url),
  'utf8'
);
assert.match(requestSource, /import \{ joinFieldErrorMessages \} from '@\/utils\/responseError';/);
assert.match(
  requestSource,
  /joinFieldErrorMessages\(response\.data\.errors, fieldErrorSeparator\)/,
  'interceptor must extract field-level messages from the unified errors payload'
);
const fieldExtractionIndex = requestSource.indexOf('joinFieldErrorMessages(response.data.errors');
const topLevelMessageIndex = requestSource.indexOf("} else if (response.data.message) {");
assert.ok(
  fieldExtractionIndex > -1 && topLevelMessageIndex > -1 && fieldExtractionIndex < topLevelMessageIndex,
  'field-level errors must take precedence over the generic top-level message'
);
// 401 登录分支（登录页凭据错误提示）不得受本次改动影响。
// CE 适配：CE 线无 LICENSE_* 业务码透传（extractBusinessErrorCode 为 PE 专属），
// 此处只断言 CE 既有 401 分支的取值链保持原状。
assert.match(requestSource, /responseData\.message/);
assert.match(requestSource, /responseData\.detail/);
assert.match(requestSource, /errors\?\.detail/);

// ── 回归防线：通知模块必须复用共享实现，禁止再复制一份字段提取逻辑 ──
// CE 适配：CE 开源线无通知管理功能（notification-management 目录不存在），按需跳过。
const notificationErrorPath = new URL(
  '../src/features/notification-management/utils/error.ts',
  import.meta.url
);
if (existsSync(notificationErrorPath)) {
  const notificationErrorSource = readFileSync(notificationErrorPath, 'utf8');
  assert.match(
    notificationErrorSource,
    /import \{ extractFieldErrorMessages \} from '@\/utils\/responseError';/,
    'notification module must delegate to the shared extractor'
  );
}

console.log('responseError tests passed');
