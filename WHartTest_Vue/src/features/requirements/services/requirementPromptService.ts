/**
 * 需求评审提示词服务
 * 用于在需求评审流程中获取和使用提示词
 */

import { 
  getRequirementPrompts, 
  getRequirementPrompt,
  getPromptByType
} from '@/features/prompts/services/promptService';
import type { 
  PromptType, 
  UserPrompt 
} from '@/features/prompts/types/prompt';
import type { ApiResponse } from '@/features/langgraph/types/api';

/**
 * 需求评审提示词类型映射
 */
export const REQUIREMENT_PROMPT_TYPES = {
  STRUCTURE: 'document_structure' as PromptType,
  DIRECT: 'direct_analysis' as PromptType,
  GLOBAL: 'global_analysis' as PromptType,
  MODULE: 'module_analysis' as PromptType
};

/**
 * 需求评审提示词类型显示名称
 */
export const REQUIREMENT_PROMPT_TYPE_NAMES = {
  [REQUIREMENT_PROMPT_TYPES.STRUCTURE]: '文档结构分析',
  [REQUIREMENT_PROMPT_TYPES.DIRECT]: '直接分析',
  [REQUIREMENT_PROMPT_TYPES.GLOBAL]: '全局分析',
  [REQUIREMENT_PROMPT_TYPES.MODULE]: '模块分析'
};

/**
 * 需求评审提示词ID集合
 */
export interface RequirementPromptIds {
  document_structure?: number;
  direct_analysis?: number;
  global_analysis?: number;
  module_analysis?: number;
}

/**
 * 获取所有需求评审提示词状态
 * @returns 包含所有需求评审提示词状态的响应
 */
export async function getAllRequirementPrompts(): Promise<ApiResponse<any>> {
  return await getRequirementPrompts();
}

/**
 * 获取指定类型的需求评审提示词
 * @param promptType 提示词类型
 * @returns 提示词对象或null
 */
export async function getRequirementPromptByType(promptType: PromptType): Promise<ApiResponse<UserPrompt | null>> {
  // 使用新的API端点
  return await getPromptByType(promptType);
}

/**
 * 获取所有需求评审提示词ID
 * 用于在启动评审时传递给后端
 */
export async function getAllRequirementPromptIds(): Promise<RequirementPromptIds> {
  const result: RequirementPromptIds = {};
  
  try {
    const response = await getRequirementPrompts();
    
    if (response.status === 'success' && response.data) {
      const { prompts } = response.data;
      
      // 遍历所有提示词类型，获取ID
      Object.entries(prompts).forEach(([type, info]) => {
        if (info.exists && info.id) {
          result[type as keyof RequirementPromptIds] = info.id;
        }
      });
    }
  } catch (error) {
    console.error('获取需求评审提示词ID失败:', error);
  }
  
  return result;
}

/**
 * 检查是否有自定义的需求评审提示词
 * @returns 是否有自定义提示词
 */
export async function hasCustomRequirementPrompts(): Promise<boolean> {
  try {
    const promptIds = await getAllRequirementPromptIds();
    return Object.keys(promptIds).length > 0;
  } catch (error) {
    console.error('检查自定义提示词失败:', error);
    return false;
  }
}
