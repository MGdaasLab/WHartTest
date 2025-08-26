/**
 * 提示词验证工具函数
 */
import { PromptType, isProgramCallPromptType } from '../types/prompt';

/**
 * 验证提示词表单数据
 * @param formData 提示词表单数据
 * @returns 错误信息对象，如果没有错误则返回null
 */
export function validatePromptForm(formData: {
  prompt_type: PromptType;
  is_default?: boolean;
}): Record<string, string> | null {
  const errors: Record<string, string> = {};

  // 程序调用类型不能设为默认
  if (isProgramCallPromptType(formData.prompt_type) && formData.is_default) {
    errors.is_default = '程序调用类型的提示词不能设为默认，会影响对话功能';
  }

  return Object.keys(errors).length > 0 ? errors : null;
}

/**
 * 处理需求管理功能的提示词缺失错误
 * @param error 错误对象
 * @param showPromptConfigDialog 显示提示词配置对话框的回调函数
 */
export function handleRequirementPromptError(
  error: any,
  showPromptConfigDialog: () => void
): void {
  if (
    error?.message?.includes('未配置') && 
    error?.message?.includes('提示词')
  ) {
    // 引导用户到提示词管理页面
    showPromptConfigDialog();
  }
}