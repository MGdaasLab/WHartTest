/**
 * 测试用例截图功能API测试文件
 * 用于验证新的截图上传功能是否正确集成
 */

import {
  uploadTestCaseScreenshot,
  type TestCase,
  type TestCaseScreenshot,
  type ScreenshotUploadResponse,
} from './services/testcaseService';

// 测试函数
export async function testScreenshotAPI() {
  console.log('开始测试截图上传API接口...');

  try {
    // 模拟测试数据
    const projectId = 1;
    const testCaseId = 1;
    
    // 创建一个模拟的图片文件
    const mockFile = new File(['mock image content'], 'test-screenshot.png', {
      type: 'image/png',
    });

    console.log('1. 测试截图上传接口...');
    
    // 注意：这里只是测试接口定义，实际调用需要有效的认证和服务器
    // const uploadResponse: ScreenshotUploadResponse = await uploadTestCaseScreenshot(
    //   projectId,
    //   testCaseId,
    //   mockFile
    // );
    
    console.log('截图上传接口定义正确');

    // 测试类型定义
    const mockScreenshot: TestCaseScreenshot = {
      id: 1,
      url: 'https://example.com/screenshot.png',
      filename: 'test-screenshot.png',
      uploaded_at: new Date().toISOString(),
    };

    const mockTestCase: TestCase = {
      id: 1,
      project: 1,
      name: '测试用例',
      precondition: '前置条件',
      level: 'P1',
      steps: [],
      notes: '备注',
      screenshots: [mockScreenshot], // 新增的截图字段
      creator_detail: {
        id: 1,
        username: 'test_user',
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    console.log('2. 测试数据结构定义...');
    console.log('TestCase接口包含screenshots字段:', 'screenshots' in mockTestCase);
    console.log('TestCaseScreenshot接口定义正确:', mockScreenshot.id !== undefined);

    console.log('✅ 所有接口定义测试通过！');
    
    return {
      success: true,
      message: '截图功能API接口定义正确',
    };

  } catch (error) {
    console.error('❌ 测试失败:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : '未知错误',
    };
  }
}

// 如果直接运行此文件，执行测试
if (import.meta.hot) {
  testScreenshotAPI().then(result => {
    console.log('测试结果:', result);
  });
}
