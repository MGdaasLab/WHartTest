/**
 * 需求评审提示词功能测试文件
 * 用于测试需求评审提示词相关的API功能
 */

import {
  getUserPrompts,
  createUserPrompt,
  updateUserPrompt,
  deleteUserPrompt,
  getRequirementPrompts,
  getRequirementPrompt
} from './features/prompts/services/promptService';

import {
  getAllRequirementPromptIds,
  hasCustomRequirementPrompts,
  REQUIREMENT_PROMPT_TYPES
} from './features/requirements/services/requirementPromptService';

import type { PromptType } from './features/prompts/types/prompt';

// 测试获取需求评审提示词列表
export async function testGetRequirementPrompts() {
  console.log('🧪 测试获取需求评审提示词列表...');
  try {
    const response = await getRequirementPrompts();
    console.log('✅ 获取需求评审提示词列表成功:', response);
    return response;
  } catch (error) {
    console.error('❌ 获取需求评审提示词列表失败:', error);
    throw error;
  }
}

// 测试获取指定类型的需求评审提示词
export async function testGetRequirementPrompt(promptType: PromptType) {
  console.log(`🧪 测试获取${promptType}提示词...`);
  try {
    const response = await getRequirementPrompt({ prompt_type: promptType });
    console.log(`✅ 获取${promptType}提示词成功:`, response);
    return response;
  } catch (error) {
    console.error(`❌ 获取${promptType}提示词失败:`, error);
    throw error;
  }
}

// 测试创建需求评审提示词
export async function testCreateRequirementPrompt(promptType: PromptType) {
  console.log(`🧪 测试创建${promptType}提示词...`);
  try {
    const promptData = {
      name: `测试${promptType}提示词`,
      description: `这是一个测试用的${promptType}提示词`,
      content: `你是一个专业的需求分析师，请帮我分析以下需求文档。这是一个测试提示词。`,
      is_default: false,
      is_active: true,
      prompt_type: promptType
    };
    
    const response = await createUserPrompt(promptData);
    console.log(`✅ 创建${promptType}提示词成功:`, response);
    return response;
  } catch (error) {
    console.error(`❌ 创建${promptType}提示词失败:`, error);
    throw error;
  }
}

// 测试更新需求评审提示词
export async function testUpdateRequirementPrompt(promptId: number, promptType: PromptType) {
  console.log(`🧪 测试更新${promptType}提示词...`);
  try {
    const updateData = {
      name: `更新后的${promptType}提示词`,
      description: `这是一个更新后的${promptType}提示词`,
      content: `你是一个专业的需求分析师，这是更新后的提示词内容。请帮我分析以下需求文档。`,
      is_active: true,
      prompt_type: promptType
    };
    
    const response = await updateUserPrompt(promptId, updateData);
    console.log(`✅ 更新${promptType}提示词成功:`, response);
    return response;
  } catch (error) {
    console.error(`❌ 更新${promptType}提示词失败:`, error);
    throw error;
  }
}

// 测试删除需求评审提示词
export async function testDeleteRequirementPrompt(promptId: number) {
  console.log('🧪 测试删除需求评审提示词...');
  try {
    const response = await deleteUserPrompt(promptId);
    console.log('✅ 删除需求评审提示词成功:', response);
    return response;
  } catch (error) {
    console.error('❌ 删除需求评审提示词失败:', error);
    throw error;
  }
}

// 测试获取所有需求评审提示词ID
export async function testGetAllRequirementPromptIds() {
  console.log('🧪 测试获取所有需求评审提示词ID...');
  try {
    const promptIds = await getAllRequirementPromptIds();
    console.log('✅ 获取所有需求评审提示词ID成功:', promptIds);
    return promptIds;
  } catch (error) {
    console.error('❌ 获取所有需求评审提示词ID失败:', error);
    throw error;
  }
}

// 测试检查是否有自定义需求评审提示词
export async function testHasCustomRequirementPrompts() {
  console.log('🧪 测试检查是否有自定义需求评审提示词...');
  try {
    const hasCustomPrompts = await hasCustomRequirementPrompts();
    console.log('✅ 检查是否有自定义需求评审提示词成功:', hasCustomPrompts);
    return hasCustomPrompts;
  } catch (error) {
    console.error('❌ 检查是否有自定义需求评审提示词失败:', error);
    throw error;
  }
}

// 运行完整的测试流程
export async function runRequirementPromptTests() {
  console.log('🚀 开始运行需求评审提示词测试...');
  
  try {
    // 1. 获取需求评审提示词列表
    await testGetRequirementPrompts();
    
    // 2. 创建需求结构分析提示词
    const createResponse = await testCreateRequirementPrompt(REQUIREMENT_PROMPT_TYPES.STRUCTURE);
    const newPromptId = createResponse.data.id;
    
    // 3. 获取指定类型的提示词
    await testGetRequirementPrompt(REQUIREMENT_PROMPT_TYPES.STRUCTURE);
    
    // 4. 更新提示词
    await testUpdateRequirementPrompt(newPromptId, REQUIREMENT_PROMPT_TYPES.STRUCTURE);
    
    // 5. 获取所有需求评审提示词ID
    await testGetAllRequirementPromptIds();
    
    // 6. 检查是否有自定义需求评审提示词
    await testHasCustomRequirementPrompts();
    
    // 7. 清理测试数据
    await testDeleteRequirementPrompt(newPromptId);
    
    console.log('🎉 所有需求评审提示词测试完成！');
    
  } catch (error) {
    console.error('💥 需求评审提示词测试失败:', error);
  }
}

// 在浏览器控制台中可以调用的测试函数
if (typeof window !== 'undefined') {
  (window as any).testRequirementPrompts = {
    runAll: runRequirementPromptTests,
    getRequirementPrompts: testGetRequirementPrompts,
    getRequirementPrompt: testGetRequirementPrompt,
    createRequirementPrompt: testCreateRequirementPrompt,
    updateRequirementPrompt: testUpdateRequirementPrompt,
    deleteRequirementPrompt: testDeleteRequirementPrompt,
    getAllPromptIds: testGetAllRequirementPromptIds,
    hasCustomPrompts: testHasCustomRequirementPrompts
  };
  
  console.log('📋 需求评审提示词测试函数已加载到 window.testRequirementPrompts');
  console.log('💡 使用 window.testRequirementPrompts.runAll() 运行完整测试');
}
