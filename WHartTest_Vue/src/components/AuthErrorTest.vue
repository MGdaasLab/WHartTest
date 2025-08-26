<template>
  <div class="auth-error-test">
    <h3>401错误处理测试</h3>
    <p>点击下面的按钮测试不同类型的401错误处理：</p>
    
    <div class="test-buttons">
      <a-button @click="testTokenInvalidError" type="primary" style="margin-right: 10px;">
        测试令牌无效错误
      </a-button>
      
      <a-button @click="testGeneral401Error" style="margin-right: 10px;">
        测试一般401错误
      </a-button>
      
      <a-button @click="testValidRequest" type="outline">
        测试正常请求
      </a-button>
    </div>
    
    <div v-if="testResult" class="test-result" :class="testResult.success ? 'success' : 'error'">
      <h4>测试结果：</h4>
      <pre>{{ JSON.stringify(testResult, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { Button as AButton } from '@arco-design/web-vue';
import { request } from '@/utils/request';

const testResult = ref<any>(null);

// 模拟令牌无效错误
const testTokenInvalidError = async () => {
  testResult.value = null;
  
  try {
    // 创建一个模拟的401错误响应
    const mockError = {
      response: {
        status: 401,
        data: {
          status: 'error',
          code: 401,
          message: '此令牌对任何类型的令牌无效',
          data: null,
          errors: {
            detail: '此令牌对任何类型的令牌无效'
          }
        }
      }
    };
    
    // 手动触发错误处理
    throw mockError;
  } catch (error: any) {
    console.log('捕获到错误:', error);
    testResult.value = {
      success: false,
      type: '令牌无效错误',
      error: error.response?.data || error.message,
      handled: true
    };
  }
};

// 模拟一般401错误
const testGeneral401Error = async () => {
  testResult.value = null;
  
  try {
    const mockError = {
      response: {
        status: 401,
        data: {
          detail: 'Authentication credentials were not provided.'
        }
      }
    };
    
    throw mockError;
  } catch (error: any) {
    console.log('捕获到错误:', error);
    testResult.value = {
      success: false,
      type: '一般401错误',
      error: error.response?.data || error.message,
      handled: true
    };
  }
};

// 测试正常请求
const testValidRequest = async () => {
  testResult.value = null;
  
  try {
    // 这里可以调用一个实际的API端点
    testResult.value = {
      success: true,
      type: '正常请求',
      message: '请求成功（模拟）',
      handled: true
    };
  } catch (error: any) {
    console.log('捕获到错误:', error);
    testResult.value = {
      success: false,
      type: '正常请求失败',
      error: error.response?.data || error.message,
      handled: true
    };
  }
};
</script>

<style scoped>
.auth-error-test {
  padding: 20px;
  background: #f5f5f5;
  border-radius: 8px;
  margin: 20px 0;
}

.test-buttons {
  margin: 20px 0;
}

.test-result {
  margin-top: 20px;
  padding: 15px;
  border-radius: 4px;
  border: 1px solid #ddd;
}

.test-result.success {
  background-color: #f6ffed;
  border-color: #b7eb8f;
}

.test-result.error {
  background-color: #fff2f0;
  border-color: #ffccc7;
}

.test-result pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
