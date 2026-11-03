// 统一响应字段级错误文案提取（全站共享）。
// 背景：后端 UnifiedResponseRenderer 对序列化器字段校验失败固定返回泛化 message
// （如「请求参数有误或处理失败」），真实原因在 errors 里（{ field: ["msg", ...] }）。
// 此前 request.ts 错误拦截器优先取顶层 message，导致所有页面只能看到泛化文案，
// 用户无从知道该改什么；通知模块与激活页各自做过一份本地提取实现。
// 这里抽取为共享工具，供 axios 拦截器与页面统一使用。

// errors 中的元数据键：承载错误码 / 透传文案等结构信息，不是字段级校验详情；
// 这些键对应的展示由各调用方既有兜底链处理（如 detail 会同步写入顶层 message）。
const META_KEYS = ['status', 'code', 'message', 'detail', 'data', 'error_code', 'token_error'];

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function collectMessages(value: unknown, out: string[], seen: WeakSet<object>): void {
  if (value === null || value === undefined) {
    return;
  }

  if (typeof value === 'string') {
    if (value.trim()) {
      // 同一句文案可能出现在多个字段（如 password 与 confirm_password），保序去重。
      if (!out.includes(value)) {
        out.push(value);
      }
    }
    return;
  }

  if (Array.isArray(value)) {
    value.forEach(item => collectMessages(item, out, seen));
    return;
  }

  if (isPlainObject(value)) {
    // 循环引用防护：共享工具不能假设输入永远来自 JSON 解析
    // （axios 的 error/error.request 对象天然成环），成环时跳过已访问对象。
    if (seen.has(value)) {
      return;
    }
    seen.add(value);
    // 嵌套序列化器的错误（{ profile: { phone: ["..."] } }）递归提取具体文案。
    Object.entries(value).forEach(([key, nested]) => {
      if (META_KEYS.includes(key)) {
        return;
      }
      collectMessages(nested, out, seen);
    });
    return;
  }

  // 数字 / 布尔等原始值：转为可读文案（如 DRF 的 choice 枚举错误）。
  const text = String(value).trim();
  if (text) {
    out.push(text);
  }
}

/**
 * 从统一响应的 errors 中提取字段级错误文案，保持字段出现顺序。
 * 非对象 / 空值输入一律返回空数组，不抛错（拦截器渲染路径直接依赖）。
 * 顶层的数字 / 布尔属于畸形载荷（如 errors: 0），直接交回调用方兜底链，
 * 避免把 "0" 之类的无意义文案当成错误提示渲染。
 */
export function extractFieldErrorMessages(errors: unknown): string[] {
  const messages: string[] = [];
  if (typeof errors === 'number' || typeof errors === 'boolean') {
    return messages;
  }
  collectMessages(errors, messages, new WeakSet());
  return messages;
}

/**
 * 将字段级错误拼接为单条提示文案；没有可用文案时返回 undefined，
 * 便于调用方沿用既有 message 兜底链。
 */
export function joinFieldErrorMessages(errors: unknown, separator = '；'): string | undefined {
  const messages = extractFieldErrorMessages(errors);
  return messages.length > 0 ? messages.join(separator) : undefined;
}
