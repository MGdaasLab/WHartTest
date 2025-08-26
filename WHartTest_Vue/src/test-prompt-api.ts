/**
 * 提示词API测试文件
 * 用于测试提示词管理相关的API功能
 */

import {
  getUserPrompts,
  getDefaultPrompt,
  createUserPrompt,
  updateUserPrompt,
  deleteUserPrompt,
  setDefaultPrompt,
  clearDefaultPrompt,
  duplicateUserPrompt
} from './features/prompts/services/promptService';

// 测试获取用户提示词列表
export async function testGetUserPrompts() {
  console.log('🧪 测试获取用户提示词列表...');
  try {
    const response = await getUserPrompts({
      page: 1,
      page_size: 10,
      is_active: true
    });
    console.log('✅ 获取用户提示词列表成功:', response);
    return response;
  } catch (error) {
    console.error('❌ 获取用户提示词列表失败:', error);
    throw error;
  }
}

// 测试获取默认提示词
export async function testGetDefaultPrompt() {
  console.log('🧪 测试获取默认提示词...');
  try {
    const response = await getDefaultPrompt();
    console.log('✅ 获取默认提示词成功:', response);
    return response;
  } catch (error) {
    console.error('❌ 获取默认提示词失败:', error);
    throw error;
  }
}

// 测试创建用户提示词
export async function testCreateUserPrompt() {
  console.log('🧪 测试创建用户提示词...');
  try {
    const promptData = {
      name: '测试提示词',
      description: '这是一个测试用的提示词',
      content: '你是一个测试助手，专门用于测试系统功能。请按照用户的要求进行测试相关的回答。',
      is_default: false,
      is_active: true
    };
    
    const response = await createUserPrompt(promptData);
    console.log('✅ 创建用户提示词成功:', response);
    return response;
  } catch (error) {
    console.error('❌ 创建用户提示词失败:', error);
    throw error;
  }
}

// 测试更新用户提示词
export async function testUpdateUserPrompt(promptId: number) {
  console.log('🧪 测试更新用户提示词...');
  try {
    const updateData = {
      name: '更新后的测试提示词',
      description: '这是一个更新后的测试用提示词',
      content: '你是一个更新后的测试助手，专门用于测试系统功能的更新版本。',
      is_default: false,
      is_active: true
    };
    
    const response = await updateUserPrompt(promptId, updateData);
    console.log('✅ 更新用户提示词成功:', response);
    return response;
  } catch (error) {
    console.error('❌ 更新用户提示词失败:', error);
    throw error;
  }
}

// 测试设置默认提示词
export async function testSetDefaultPrompt(promptId: number) {
  console.log('🧪 测试设置默认提示词...');
  try {
    const response = await setDefaultPrompt(promptId);
    console.log('✅ 设置默认提示词成功:', response);
    return response;
  } catch (error) {
    console.error('❌ 设置默认提示词失败:', error);
    throw error;
  }
}

// 测试复制提示词
export async function testDuplicateUserPrompt(promptId: number) {
  console.log('🧪 测试复制提示词...');
  try {
    const response = await duplicateUserPrompt(promptId);
    console.log('✅ 复制提示词成功:', response);
    return response;
  } catch (error) {
    console.error('❌ 复制提示词失败:', error);
    throw error;
  }
}

// 测试删除用户提示词
export async function testDeleteUserPrompt(promptId: number) {
  console.log('🧪 测试删除用户提示词...');
  try {
    const response = await deleteUserPrompt(promptId);
    console.log('✅ 删除用户提示词成功:', response);
    return response;
  } catch (error) {
    console.error('❌ 删除用户提示词失败:', error);
    throw error;
  }
}

// 运行完整的测试流程
export async function runPromptApiTests() {
  console.log('🚀 开始运行提示词API测试...');
  
  try {
    // 1. 获取现有提示词列表
    await testGetUserPrompts();
    
    // 2. 获取默认提示词
    await testGetDefaultPrompt();
    
    // 3. 创建新提示词
    const createResponse = await testCreateUserPrompt();
    const newPromptId = createResponse.data.id;
    
    // 4. 更新提示词
    await testUpdateUserPrompt(newPromptId);
    
    // 5. 复制提示词
    const duplicateResponse = await testDuplicateUserPrompt(newPromptId);
    const duplicatedPromptId = duplicateResponse.data.id;
    
    // 6. 设置为默认提示词
    await testSetDefaultPrompt(newPromptId);
    
    // 7. 清理测试数据
    await testDeleteUserPrompt(duplicatedPromptId);
    await testDeleteUserPrompt(newPromptId);
    
    console.log('🎉 所有提示词API测试完成！');
    
  } catch (error) {
    console.error('💥 提示词API测试失败:', error);
  }
}

// 在浏览器控制台中可以调用的测试函数
if (typeof window !== 'undefined') {
  (window as any).testPromptApi = {
    runAll: runPromptApiTests,
    getUserPrompts: testGetUserPrompts,
    getDefaultPrompt: testGetDefaultPrompt,
    createUserPrompt: testCreateUserPrompt,
    updateUserPrompt: testUpdateUserPrompt,
    setDefaultPrompt: testSetDefaultPrompt,
    duplicateUserPrompt: testDuplicateUserPrompt,
    deleteUserPrompt: testDeleteUserPrompt
  };
  
  console.log('📋 提示词API测试函数已加载到 window.testPromptApi');
  console.log('💡 使用 window.testPromptApi.runAll() 运行完整测试');
}
