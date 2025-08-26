/**
 * 通用 API 响应结构
 */
export interface ApiResponse<T = Record<string, any>> {
  status: 'success' | 'error';
  code: number; // HTTP 状态码
  message: string; // 描述结果的用户友好消息
  data: T; // 成功时的数据负载 (对象或数组)
  errors?: Record<string, string[]>; // 失败时的错误详情 (对象)
}