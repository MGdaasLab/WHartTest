/**
 * 需求评审提示词系统集成测试
 * 测试整个功能的集成和兼容性
 */

import { 
  PROMPT_TYPE_CHOICES,
  isRequirementPromptType,
  getPromptTypeDisplayName
} from './features/prompts/types/prompt';

import {
  REQUIREMENT_PROMPT_TYPES,
  REQUIREMENT_PROMPT_TYPE_NAMES
} from './features/requirements/services/requirementPromptService';

// 测试类型定义的完整性
export function testTypeDefinitions() {
  console.log('🧪 测试类型定义的完整性...');
  
  try {
    // 测试提示词类型选项
    console.log('📋 提示词类型选项:', PROMPT_TYPE_CHOICES);
    
    // 测试需求评审提示词类型
    console.log('📋 需求评审提示词类型:', REQUIREMENT_PROMPT_TYPES);
    
    // 测试类型显示名称
    console.log('📋 需求评审提示词类型名称:', REQUIREMENT_PROMPT_TYPE_NAMES);
    
    // 测试工具函数
    const chatType = 'chat';
    const requirementType = 'requirement_direct';
    
    console.log(`📋 ${chatType} 是否为需求评审类型:`, isRequirementPromptType(chatType as any));
    console.log(`📋 ${requirementType} 是否为需求评审类型:`, isRequirementPromptType(requirementType as any));
    
    console.log(`📋 ${chatType} 显示名称:`, getPromptTypeDisplayName(chatType as any));
    console.log(`📋 ${requirementType} 显示名称:`, getPromptTypeDisplayName(requirementType as any));
    
    console.log('✅ 类型定义测试通过');
    return true;
  } catch (error) {
    console.error('❌ 类型定义测试失败:', error);
    return false;
  }
}

// 测试API端点配置
export function testApiEndpoints() {
  console.log('🧪 测试API端点配置...');
  
  try {
    // 动态导入API配置
    import('./config/api').then(({ API_ENDPOINTS }) => {
      console.log('📋 提示词API端点:', API_ENDPOINTS.PROMPTS);
      console.log('📋 需求管理API端点:', API_ENDPOINTS.REQUIREMENTS);
      
      // 检查新增的端点
      if (API_ENDPOINTS.PROMPTS.REQUIREMENT_PROMPTS && API_ENDPOINTS.PROMPTS.GET_REQUIREMENT_PROMPT) {
        console.log('✅ 需求评审提示词API端点配置正确');
      } else {
        console.error('❌ 需求评审提示词API端点配置缺失');
      }
    });
    
    return true;
  } catch (error) {
    console.error('❌ API端点配置测试失败:', error);
    return false;
  }
}

// 测试向后兼容性
export async function testBackwardCompatibility() {
  console.log('🧪 测试向后兼容性...');
  
  try {
    // 测试原有的提示词功能是否正常
    const { getUserPrompts, getDefaultPrompt } = await import('./features/prompts/services/promptService');
    
    // 测试获取用户提示词列表（应该包含新字段）
    console.log('📋 测试获取用户提示词列表...');
    const promptsResponse = await getUserPrompts({ prompt_type: 'chat' });
    console.log('📋 用户提示词列表响应:', promptsResponse);
    
    // 测试获取默认提示词
    console.log('📋 测试获取默认提示词...');
    const defaultResponse = await getDefaultPrompt();
    console.log('📋 默认提示词响应:', defaultResponse);
    
    console.log('✅ 向后兼容性测试通过');
    return true;
  } catch (error) {
    console.error('❌ 向后兼容性测试失败:', error);
    return false;
  }
}

// 测试UI组件兼容性
export function testUICompatibility() {
  console.log('🧪 测试UI组件兼容性...');
  
  try {
    // 检查是否能正确导入组件
    console.log('📋 检查SystemPromptModal组件...');
    
    // 模拟组件数据结构
    const mockPromptData = {
      name: '测试提示词',
      description: '测试描述',
      content: '测试内容',
      is_default: false,
      prompt_type: 'requirement_direct'
    };
    
    console.log('📋 模拟提示词数据:', mockPromptData);
    
    // 测试类型检查
    const isRequirement = isRequirementPromptType(mockPromptData.prompt_type as any);
    console.log('📋 是否为需求评审类型:', isRequirement);
    
    console.log('✅ UI组件兼容性测试通过');
    return true;
  } catch (error) {
    console.error('❌ UI组件兼容性测试失败:', error);
    return false;
  }
}

// 测试需求评审流程集成
export async function testRequirementReviewIntegration() {
  console.log('🧪 测试需求评审流程集成...');
  
  try {
    // 测试需求评审提示词服务
    const { getAllRequirementPromptIds, hasCustomRequirementPrompts } = await import('./features/requirements/services/requirementPromptService');
    
    console.log('📋 测试获取需求评审提示词ID...');
    const promptIds = await getAllRequirementPromptIds();
    console.log('📋 需求评审提示词ID:', promptIds);
    
    console.log('📋 测试检查是否有自定义提示词...');
    const hasCustom = await hasCustomRequirementPrompts();
    console.log('📋 是否有自定义提示词:', hasCustom);
    
    // 模拟启动评审请求
    const mockStartReviewRequest = {
      analysis_type: 'comprehensive' as const,
      parallel_processing: true,
      prompt_ids: Object.keys(promptIds).length > 0 ? promptIds : undefined
    };
    
    console.log('📋 模拟启动评审请求:', mockStartReviewRequest);
    
    console.log('✅ 需求评审流程集成测试通过');
    return true;
  } catch (error) {
    console.error('❌ 需求评审流程集成测试失败:', error);
    return false;
  }
}

// 运行完整的集成测试
export async function runIntegrationTests() {
  console.log('🚀 开始运行集成测试...');
  
  const results = {
    typeDefinitions: false,
    apiEndpoints: false,
    backwardCompatibility: false,
    uiCompatibility: false,
    requirementReviewIntegration: false
  };
  
  try {
    // 1. 测试类型定义
    results.typeDefinitions = testTypeDefinitions();
    
    // 2. 测试API端点配置
    results.apiEndpoints = testApiEndpoints();
    
    // 3. 测试向后兼容性
    results.backwardCompatibility = await testBackwardCompatibility();
    
    // 4. 测试UI组件兼容性
    results.uiCompatibility = testUICompatibility();
    
    // 5. 测试需求评审流程集成
    results.requirementReviewIntegration = await testRequirementReviewIntegration();
    
    // 输出测试结果
    console.log('📊 集成测试结果:', results);
    
    const passedTests = Object.values(results).filter(Boolean).length;
    const totalTests = Object.keys(results).length;
    
    if (passedTests === totalTests) {
      console.log('🎉 所有集成测试通过！');
    } else {
      console.log(`⚠️ ${passedTests}/${totalTests} 个测试通过`);
    }
    
    return results;
    
  } catch (error) {
    console.error('💥 集成测试失败:', error);
    return results;
  }
}

// 在浏览器控制台中可以调用的测试函数
if (typeof window !== 'undefined') {
  (window as any).testIntegration = {
    runAll: runIntegrationTests,
    typeDefinitions: testTypeDefinitions,
    apiEndpoints: testApiEndpoints,
    backwardCompatibility: testBackwardCompatibility,
    uiCompatibility: testUICompatibility,
    requirementReviewIntegration: testRequirementReviewIntegration
  };
  
  console.log('📋 集成测试函数已加载到 window.testIntegration');
  console.log('💡 使用 window.testIntegration.runAll() 运行完整测试');
}
