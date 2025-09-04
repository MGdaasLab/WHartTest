<template>
  <div class="login-container">
    <!-- 背景装饰 -->
    <div class="background-decoration">
      <div class="decoration-circle circle-1"></div>
      <div class="decoration-circle circle-2"></div>
      <div class="decoration-circle circle-3"></div>
    </div>

    <!-- 登录卡片 -->
    <div class="login-card">
      <!-- 品牌标识区域 -->
      <div class="brand-section">
        <div class="brand-logo">
          <img src="/WHartTest.png" alt="WHartTest Logo" class="logo-icon" />
        </div>
        <h1 class="brand-title">WHartTest</h1>
        <p class="brand-subtitle">小麦智测自动化平台</p>
      </div>

      <!-- 登录表单 -->
      <form @submit.prevent="handleLogin" class="login-form">
        <!-- 用户名输入框 -->
        <div class="input-group">
          <div class="input-wrapper">
            <div class="input-icon">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
              </svg>
            </div>
            <input
              type="text"
              id="username"
              v-model="username"
              required
              class="form-input"
              placeholder="请输入用户名"
            />
          </div>
        </div>

        <!-- 密码输入框 -->
        <div class="input-group">
          <div class="input-wrapper">
            <div class="input-icon">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
              </svg>
            </div>
            <input
              :type="showPassword ? 'text' : 'password'"
              id="password"
              v-model="password"
              required
              class="form-input"
              placeholder="请输入密码"
            />
            <div class="password-toggle" @click="togglePasswordVisibility">
              <svg v-if="!showPassword" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
              </svg>
            </div>
          </div>
        </div>

        <!-- 记住我选项 -->
        <div class="form-options">
          <div class="checkbox-group">
            <input
              id="remember-me"
              type="checkbox"
              v-model="rememberMe"
              class="form-checkbox"
            />
            <label for="remember-me" class="checkbox-label">记住我</label>
          </div>
        </div>

        <!-- 登录按钮 -->
        <button
          type="submit"
          class="login-button"
          :class="{'loading': isLoading}"
          :disabled="isLoading"
        >
          <span v-if="!isLoading">登录</span>
          <span v-else class="loading-content">
            <svg class="loading-spinner" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            登录中...
          </span>
        </button>

        <!-- 错误消息 -->
        <div v-if="errorMessage" class="error-message">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="error-icon">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          {{ errorMessage }}
        </div>

        <!-- 注册链接 -->
        <div class="register-link">
          <p>
            还没有账号?
            <router-link to="/register" class="link">立即注册</router-link>
          </p>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/store/authStore';
import { Message } from '@arco-design/web-vue';

// 基本表单数据
const username = ref('');
const password = ref('');
const rememberMe = ref(false);
const showPassword = ref(false);

const router = useRouter();
const authStore = useAuthStore();

// 从 store 获取加载状态和错误信息
const isLoading = computed(() => authStore.getIsLoading);
const errorMessage = computed(() => authStore.getLoginError);

// 切换密码可见性
const togglePasswordVisibility = () => {
  showPassword.value = !showPassword.value;
};

// 处理登录逻辑
const handleLogin = async () => {
  if (!username.value || !password.value) {
    Message.warning('请输入用户名和密码');
    return;
  }

  const success = await authStore.login(username.value, password.value);

  if (success) {
    Message.success('登录成功！');
    if (rememberMe.value) {
      localStorage.setItem('rememberedUsername', username.value);
    } else {
      localStorage.removeItem('rememberedUsername');
    }
    
    // 使用 nextTick 确保状态更新后再跳转
    await router.push('/projects');
  }
};

onMounted(() => {
  // 检查用户是否已登录
  authStore.checkAuthStatus();
  if (authStore.isLoggedIn) {
    router.push('/projects');
  }

  // 检查是否有记住的用户名
  const rememberedUsername = localStorage.getItem('rememberedUsername');
  if (rememberedUsername) {
    username.value = rememberedUsername;
    rememberMe.value = true;
  }
});
</script>

<style scoped>
/* 主容器 */
.login-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: linear-gradient(135deg, #f8f9fc 0%, #e9ecf3 100%);
  position: relative;
  overflow: hidden;
  box-sizing: border-box;
}

/* 背景装饰 */
.background-decoration {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 1;
}

.decoration-circle {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(0, 160, 233, 0.1) 0%, rgba(0, 160, 233, 0.05) 100%);
  animation: float 6s ease-in-out infinite;
}

.circle-1 {
  width: 200px;
  height: 200px;
  top: 10%;
  left: 10%;
  animation-delay: 0s;
}

.circle-2 {
  width: 150px;
  height: 150px;
  top: 70%;
  right: 15%;
  animation-delay: 2s;
}

.circle-3 {
  width: 100px;
  height: 100px;
  top: 50%;
  left: 80%;
  animation-delay: 4s;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0px) scale(1);
    opacity: 0.7;
  }
  50% {
    transform: translateY(-20px) scale(1.05);
    opacity: 1;
  }
}

/* 登录卡片 */
.login-card {
  background: #ffffff;
  border-radius: 20px;
  box-shadow:
    0 25px 50px rgba(0, 0, 0, 0.08),
    0 15px 25px rgba(0, 0, 0, 0.04),
    0 0 0 1px rgba(255, 255, 255, 0.1);
  padding: 40px 45px;
  width: 100%;
  max-width: 460px;
  position: relative;
  z-index: 2;
  backdrop-filter: blur(20px);
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.login-card:hover {
  transform: translateY(-5px);
  box-shadow: 
    0 30px 60px rgba(0, 0, 0, 0.15),
    0 15px 30px rgba(0, 0, 0, 0.1),
    0 0 0 1px rgba(255, 255, 255, 0.1);
}

/* 品牌标识区域 */
.brand-section {
  text-align: center;
  margin-bottom: 32px;
}

.brand-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 70px;
  height: 70px;
  margin-bottom: 20px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.brand-logo:hover {
  transform: translateY(-3px) scale(1.05);
}

.logo-icon {
  width: 48px;
  height: 48px;
  color: #ffffff;
}

.brand-title {
  font-size: 28px;
  font-weight: 700;
  color: #333333;
  margin: 0 0 6px 0;
  letter-spacing: -0.5px;
}

.brand-subtitle {
  font-size: 15px;
  color: #6b7280;
  margin: 0;
  font-weight: 500;
}

/* 登录表单 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 输入组 */
.input-group {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 18px;
  z-index: 1;
  color: #9ca3af;
  transition: color 0.3s ease;
}

.input-icon svg {
  width: 20px;
  height: 20px;
}

.form-input {
  width: 100%;
  padding: 16px 20px 16px 54px;
  border: 1.5px solid #e5e7eb;
  border-radius: 14px;
  font-size: 16px;
  color: #374151;
  background: #fafafa;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-sizing: border-box;
  min-height: 52px;
}

.form-input:focus {
  outline: none;
  border-color: #00a0e9;
  background: #ffffff;
  box-shadow: 0 0 0 4px rgba(0, 160, 233, 0.08);
  transform: translateY(-1px);
}

.form-input:focus + .input-icon,
.input-wrapper:focus-within .input-icon {
  color: #00a0e9;
}

.password-toggle {
  position: absolute;
  right: 18px;
  cursor: pointer;
  color: #9ca3af;
  transition: color 0.3s ease;
  z-index: 1;
}

.password-toggle:hover {
  color: #00a0e9;
}

.password-toggle svg {
  width: 20px;
  height: 20px;
}

/* 表单选项 */
.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 16px 0 24px 0;
}

.checkbox-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-checkbox {
  width: 20px;
  height: 20px;
  border: 2px solid #d1d5db;
  border-radius: 4px;
  background: #ffffff;
  cursor: pointer;
  transition: all 0.2s ease;
}

.form-checkbox:checked {
  background: #00a0e9;
  border-color: #00a0e9;
}

.checkbox-label {
  font-size: 15px;
  color: #6b7280;
  cursor: pointer;
  user-select: none;
}

.forgot-password .link {
  font-size: 15px;
  color: #00a0e9;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s ease;
}

.forgot-password .link:hover {
  color: #0090d1;
  text-decoration: underline;
}

/* 登录按钮 */
.login-button {
  width: 100%;
  padding: 12px 24px;
  background: #00a0e9;
  border: none;
  border-radius: 14px;
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 6px 16px rgba(0, 160, 233, 0.25);
  position: relative;
  overflow: hidden;
  min-height: 48px;
  letter-spacing: 0.2px;
}

.login-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(26, 170, 235, 0.35);
  background: #1aaaeb;
}

.login-button:active:not(:disabled) {
  transform: translateY(0);
  background: #0090d1;
}

.login-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
  transform: none;
}

.loading-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 错误消息 */
.error-message {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #dc2626;
  font-size: 15px;
  margin-top: 8px;
}

.error-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}

/* 注册链接 */
.register-link {
  text-align: center;
  margin-top: 20px;
}

.register-link p {
  font-size: 15px;
  color: #6b7280;
  margin: 0;
}

.register-link .link {
  color: #00a0e9;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s ease;
}

.register-link .link:hover {
  color: #0090d1;
  text-decoration: underline;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .login-container {
    padding: 16px;
    height: 100vh;
    overflow-y: auto;
  }

  .login-card {
    margin: 0;
    padding: 24px 20px;
    max-width: none;
    min-height: auto;
  }

  .brand-section {
    margin-bottom: 20px;
  }

  .brand-logo {
    width: 50px;
    height: 50px;
    border-radius: 12px;
    margin-bottom: 12px;
  }

  .logo-icon {
    width: 26px;
    height: 26px;
  }

  .brand-title {
    font-size: 22px;
  }

  .brand-subtitle {
    font-size: 13px;
  }

  .login-form {
    gap: 18px;
  }

  .form-input {
    padding: 12px 14px 12px 42px;
    font-size: 16px;
    min-height: 44px;
  }

  .input-icon {
    left: 14px;
  }

  .password-toggle {
    right: 14px;
  }

  .login-button {
    padding: 12px 18px;
    min-height: 44px;
  }

  .register-link {
    margin-top: 16px;
  }
}

@media (max-width: 480px) {
  .login-container {
    padding: 12px;
    height: 100vh;
    overflow-y: auto;
  }

  .login-card {
    margin: 0;
    padding: 20px 16px;
  }

  .brand-section {
    margin-bottom: 16px;
  }

  .brand-title {
    font-size: 20px;
  }

  .form-options {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    margin: 8px 0 14px 0;
  }

  .register-link {
    margin-top: 12px;
  }
}

/* 高度不足时的处理 */
@media (max-height: 600px) {
  .login-container {
    height: 100vh;
    overflow-y: auto;
    align-items: flex-start;
    padding-top: 20px;
  }

  .login-card {
    margin: 0 auto;
  }

  .brand-section {
    margin-bottom: 16px;
  }

  .login-form {
    gap: 16px;
  }
}

/* 动画效果 */
.login-card {
  animation: slideUp 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(40px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* 输入框聚焦动画 */
.form-input:focus {
  animation: inputFocus 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes inputFocus {
  0% {
    box-shadow: 0 0 0 0 rgba(0, 160, 233, 0.3);
    transform: translateY(0);
  }
  50% {
    box-shadow: 0 0 0 2px rgba(0, 160, 233, 0.15);
  }
  100% {
    box-shadow: 0 0 0 4px rgba(0, 160, 233, 0.08);
    transform: translateY(-1px);
  }
}

/* 按钮点击效果 */
.login-button:active:not(:disabled) {
  transform: translateY(1px) scale(0.98);
  transition: all 0.1s ease;
}

/* 品牌logo旋转效果 */
@keyframes logoRotate {
  0% { transform: rotate(0deg) scale(1); }
  50% { transform: rotate(180deg) scale(1.1); }
  100% { transform: rotate(360deg) scale(1); }
}

.brand-logo:active {
  animation: logoRotate 0.6s ease-in-out;
}

/* 微妙的脉冲效果 */
.login-button:not(:disabled) {
  position: relative;
  overflow: hidden;
}

.login-button:not(:disabled)::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s ease;
}

.login-button:hover:not(:disabled)::before {
  left: 100%;
}
</style>