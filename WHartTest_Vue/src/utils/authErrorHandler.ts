/**
 * 认证错误处理工具函数
 */

import { useAuthStore } from '@/store/authStore';

/**
 * 检查是否是令牌无效的错误
 * @param responseData 响应数据
 * @returns 是否是令牌无效错误
 */
export function isTokenInvalidError(responseData: any): boolean {
  if (!responseData) {
    return false;
  }

  // 检查标准API响应格式
  if (responseData.status === 'error' && responseData.code === 401) {
    // 检查message字段
    if (responseData.message && 
        (responseData.message.includes('令牌') && responseData.message.includes('无效') ||
         responseData.message.includes('此令牌对任何类型的令牌无效'))) {
      return true;
    }
    
    // 检查errors字段中的详细信息
    if (responseData.errors && 
        responseData.errors.detail && 
        (responseData.errors.detail.includes('令牌') && responseData.errors.detail.includes('无效') ||
         responseData.errors.detail.includes('此令牌对任何类型的令牌无效'))) {
      return true;
    }
  }
  
  // 检查其他可能的401错误格式
  if (responseData.detail && 
      (responseData.detail.includes('令牌') && responseData.detail.includes('无效') ||
       responseData.detail.includes('此令牌对任何类型的令牌无效'))) {
    return true;
  }

  return false;
}

/**
 * 处理认证错误，执行登出操作
 * @param errorMessage 可选的错误消息
 */
export function handleAuthError(errorMessage?: string): void {
  console.log('检测到认证错误，执行自动登出:', errorMessage || '令牌无效');
  
  const authStore = useAuthStore();
  authStore.logout();
  
  // 重定向到登录页面
  if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
}

/**
 * 检查401错误并处理
 * @param error 错误对象
 * @returns 是否已处理该错误
 */
export function handle401Error(error: any): boolean {
  if (error.response && error.response.status === 401) {
    if (isTokenInvalidError(error.response.data)) {
      handleAuthError('令牌无效');
      return true;
    }
  }
  return false;
}
