/**
 * 测试编辑提示词修复
 * 验证编辑提示词时数据能正确填充到表单中
 */

import { getUserPrompt } from './features/prompts/services/promptService';

// 测试获取提示词详情
export async function testGetPromptDetail(promptId: number) {
  console.log(`🧪 测试获取提示词详情 (ID: ${promptId})...`);
  try {
    const response = await getUserPrompt(promptId);
    console.log('✅ 获取提示词详情成功:', response);
    
    if (response.status === 'success' && response.data) {
      const prompt = response.data;
      console.log('📋 提示词详细信息:');
      console.log('  - ID:', prompt.id);
      console.log('  - 名称:', prompt.name);
      console.log('  - 类型:', prompt.prompt_type);
      console.log('  - 类型显示:', prompt.prompt_type_display);
      console.log('  - 是否需求评审类型:', prompt.is_requirement_type);
      console.log('  - 内容长度:', prompt.content?.length || 0);
      console.log('  - 内容预览:', prompt.content?.substring(0, 100) + '...');
      
      // 模拟表单数据填充
      const formData = {
        name: prompt.name,
        description: prompt.description || '',
        content: prompt.content || '',
        is_default: prompt.is_default,
        prompt_type: prompt.prompt_type || 'chat',
      };
      
      console.log('📋 模拟表单数据填充:', formData);
      
      // 验证关键字段
      if (!formData.content) {
        console.error('❌ 内容字段为空！');
        return false;
      }
      
      if (!formData.prompt_type) {
        console.error('❌ 提示词类型字段为空！');
        return false;
      }
      
      console.log('✅ 表单数据填充验证通过');
      return true;
    } else {
      console.error('❌ 获取提示词详情失败:', response.message);
      return false;
    }
  } catch (error) {
    console.error('❌ 获取提示词详情异常:', error);
    return false;
  }
}

// 测试编辑表单数据结构
export function testEditFormDataStructure() {
  console.log('🧪 测试编辑表单数据结构...');
  
  // 模拟从API获取的提示词数据
  const mockPromptData = {
    id: 27,
    name: "需求一致性检查",
    content: "你正在进行需求文档的跨模块一致性检查...",
    description: "用于检查跨模块一致性问题的提示词",
    prompt_type: "requirement_consistency",
    prompt_type_display: "需求一致性检查",
    is_default: true,
    is_active: true,
    is_requirement_type: true
  };
  
  console.log('📋 模拟提示词数据:', mockPromptData);
  
  // 模拟表单数据填充逻辑
  const formData = {
    name: mockPromptData.name,
    description: mockPromptData.description || '',
    content: mockPromptData.content || '',
    is_default: mockPromptData.is_default,
    prompt_type: mockPromptData.prompt_type || 'chat',
  };
  
  console.log('📋 表单数据填充结果:', formData);
  
  // 验证数据完整性
  const checks = [
    { field: 'name', value: formData.name, expected: mockPromptData.name },
    { field: 'content', value: formData.content, expected: mockPromptData.content },
    { field: 'prompt_type', value: formData.prompt_type, expected: mockPromptData.prompt_type },
    { field: 'is_default', value: formData.is_default, expected: mockPromptData.is_default }
  ];
  
  let allPassed = true;
  checks.forEach(check => {
    if (check.value === check.expected) {
      console.log(`✅ ${check.field} 字段验证通过`);
    } else {
      console.error(`❌ ${check.field} 字段验证失败: 期望 ${check.expected}, 实际 ${check.value}`);
      allPassed = false;
    }
  });
  
  return allPassed;
}

// 运行所有测试
export async function runEditPromptFixTests() {
  console.log('🚀 开始运行编辑提示词修复测试...');
  
  const results = {
    dataStructure: false,
    apiCall: false
  };
  
  try {
    // 1. 测试数据结构
    results.dataStructure = testEditFormDataStructure();
    
    // 2. 测试API调用（使用示例ID 27）
    results.apiCall = await testGetPromptDetail(27);
    
    console.log('📊 测试结果:', results);
    
    const passedTests = Object.values(results).filter(Boolean).length;
    const totalTests = Object.keys(results).length;
    
    if (passedTests === totalTests) {
      console.log('🎉 所有编辑提示词修复测试通过！');
    } else {
      console.log(`⚠️ ${passedTests}/${totalTests} 个测试通过`);
    }
    
    return results;
    
  } catch (error) {
    console.error('💥 编辑提示词修复测试失败:', error);
    return results;
  }
}

// 在浏览器控制台中可以调用的测试函数
if (typeof window !== 'undefined') {
  (window as any).testEditPromptFix = {
    runAll: runEditPromptFixTests,
    testDataStructure: testEditFormDataStructure,
    testApiCall: testGetPromptDetail
  };
  
  console.log('📋 编辑提示词修复测试函数已加载到 window.testEditPromptFix');
  console.log('💡 使用 window.testEditPromptFix.runAll() 运行完整测试');
  console.log('💡 使用 window.testEditPromptFix.testApiCall(27) 测试特定提示词');
}
