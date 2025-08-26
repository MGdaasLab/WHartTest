/**
 * 测试项目添加成员接口参数修改
 * 验证请求参数从 "user" 改为 "user_id" 后的功能
 */

import { addProjectMember } from '@/services/projectService';

// 模拟测试数据
const testAddMember = async () => {
  console.log('🧪 开始测试项目添加成员接口参数修改...');
  
  try {
    // 测试项目ID和用户ID（这些是模拟数据，实际测试时需要使用真实数据）
    const projectId = 55;
    const userId = 15;
    const role = 'member';
    
    console.log('📝 测试参数:');
    console.log(`  项目ID: ${projectId}`);
    console.log(`  用户ID: ${userId}`);
    console.log(`  角色: ${role}`);
    console.log('  请求参数格式: { user_id: userId, role: role }');
    
    // 调用API
    const result = await addProjectMember(projectId, userId, role);
    
    if (result.success) {
      console.log('✅ 添加成员成功!');
      console.log('📊 响应数据:', result.data);
    } else {
      console.log('❌ 添加成员失败:', result.error);
      console.log('📋 状态码:', result.statusCode);
    }
    
  } catch (error) {
    console.error('🚨 测试过程中发生错误:', error);
  }
  
  console.log('🏁 测试完成');
};

// 导出测试函数
export { testAddMember };

// 控制台测试提示
console.log('💡 要运行测试，请在组件中调用 testAddMember() 函数或在浏览器控制台中运行');
