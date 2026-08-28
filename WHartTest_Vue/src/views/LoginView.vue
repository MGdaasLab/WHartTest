<template>
  <div class="login-page">
    <canvas ref="canvasRef" class="starry-canvas" />
    <div class="header-controls">
      <AppLocaleToggle />
      <button
        type="button"
        class="theme-toggle-btn"
        :aria-label="isBlack ? 'Switch to light theme' : 'Switch to dark theme'"
        :title="isBlack ? '切换至亮色模式' : '切换至暗色模式'"
        @click="toggleTheme"
      >
        <span class="theme-icon-wrap" :class="{ 'is-dark': isBlack }">
          <svg v-if="isBlack" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="theme-icon">
            <path d="M12 2.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM6.162 5.736a.75.75 0 011.06 0l1.591 1.591a.75.75 0 11-1.06 1.06L6.162 6.796a.75.75 0 010-1.06zm10.614 0a.75.75 0 010 1.06l-1.591 1.591a.75.75 0 11-1.06-1.06l1.591-1.591a.75.75 0 011.06 0zM12 7.5a4.5 4.5 0 100 9 4.5 4.5 0 000-9zM2.25 12a.75.75 0 01.75-.75h2.25a.75.75 0 010 1.5H3a.75.75 0 01-.75-.75zm13.5 0a.75.75 0 01.75-.75h2.25a.75.75 0 010 1.5h-2.25a.75.75 0 01-.75-.75zM6.162 17.204a.75.75 0 011.06-1.06l1.591 1.59a.75.75 0 11-1.06 1.061l-1.59-1.591a.75.75 0 010-1.06zm10.614 0a.75.75 0 010 1.06l-1.59 1.591a.75.75 0 11-1.061-1.06l1.59-1.59a.75.75 0 011.06 0zM12 17.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V18a.75.75 0 01.75-.75z" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="theme-icon">
            <path fill-rule="evenodd" d="M9.528 1.718a.75.75 0 01.162.819A8.97 8.97 0 009 6a9 9 0 009 9 8.97 8.97 0 003.463-.69.75.75 0 01.981.98 10.503 10.503 0 01-9.694 6.46c-5.799 0-10.5-4.701-10.5-10.5 0-4.368 2.667-8.112 6.46-9.694a.75.75 0 01.818.162z" clip-rule="evenodd" />
          </svg>
        </span>
      </button>
    </div>

    <div class="content-layer">
      <div class="brand-area">
        <img :src="brandLogoUrl" alt="Logo" class="brand-logo" />
        <div class="brand-title-row">
          <h1 class="brand-title">{{ brandTitle }}</h1>
          <img v-if="brandBadgeEnabled" :src="brandBadgeUrl" alt="CE" class="brand-ce-icon" />
        </div>
        <p class="brand-subtitle">{{ brandSubtitle }}</p>
        <div class="brand-tags">
          <span v-for="tag in featureTags" :key="tag" class="tag">{{ tag }}</span>
        </div>
      </div>

      <button
        ref="launcherButtonRef"
        type="button"
        class="login-launcher"
        :aria-label="t('login.openDialog')"
        @click="openLoginDialog"
      >
        <span class="launcher-aura" />
        <span class="launcher-icon" aria-hidden="true">
          <img
            v-if="!fingerprintImageLoadFailed && currentFingerprintAsset"
            :src="currentFingerprintAsset"
            alt=""
            class="launcher-fingerprint-img"
            @error="handleFingerprintAssetError"
          />
          <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.8" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V7.875a4.5 4.5 0 00-9 0V10.5m9 0h.75A2.25 2.25 0 0119.5 12.75v5.625a2.25 2.25 0 01-2.25 2.25h-10.5a2.25 2.25 0 01-2.25-2.25V12.75A2.25 2.25 0 016.75 10.5h.75" />
          </svg>
        </span>
        <span class="launcher-copy">
          <strong>{{ launcherTitle }}</strong>
          <span>{{ launcherSubtitle }}</span>
        </span>
      </button>
    </div>

    <Transition name="login-dialog">
      <div v-if="loginDialogVisible" class="login-overlay" @click.self="closeLoginDialog">
        <div
          ref="loginDialogRef"
          class="login-card"
          role="dialog"
          aria-modal="true"
          aria-labelledby="login-title"
          aria-describedby="login-description"
          @keydown="handleDialogKeydown"
        >
          <button type="button" class="dialog-close" :aria-label="t('login.closeDialog')" @click="closeLoginDialog">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>

          <div class="card-header">
            <h2 id="login-title">{{ dialogTitle }}</h2>
            <p id="login-description">{{ dialogDescription }}</p>
          </div>

          <form class="login-form" @submit.prevent="handleLogin">
            <div class="input-wrapper">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="input-icon">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
              </svg>
              <input
                ref="usernameInputRef"
                v-model="username"
                type="text"
                required
                autocomplete="username"
                :placeholder="usernamePlaceholder"
                class="form-input"
              />
            </div>

            <div class="input-wrapper">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="input-icon">
                <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
              </svg>
              <input
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                required
                autocomplete="current-password"
                :placeholder="passwordPlaceholder"
                class="form-input"
              />
              <button
                v-if="!showPassword"
                class="toggle-icon"
                type="button"
                :aria-label="t('login.showPassword')"
                :aria-pressed="showPassword"
                @click="showPassword = true"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </button>
              <button
                v-else
                class="toggle-icon"
                type="button"
                :aria-label="t('login.hidePassword')"
                :aria-pressed="showPassword"
                @click="showPassword = false"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                </svg>
              </button>
            </div>

            <label class="remember-me">
              <input v-model="rememberMe" type="checkbox" />
              <span>{{ rememberMeLabel }}</span>
            </label>

            <button type="submit" class="login-btn" :disabled="isLoading">
              <template v-if="!isLoading">{{ submitLabel }}</template>
              <template v-else>
                <svg class="spinner" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" opacity="0.25" />
                  <path fill="currentColor" opacity="0.75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                {{ submittingLabel }}
              </template>
            </button>

            <div v-if="errorMessage" class="error-msg">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="error-icon">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              {{ errorMessage }}
            </div>

            <p class="register-link">
              {{ registerPrompt }}
              <router-link to="/register">{{ registerLinkLabel }}</router-link>
            </p>
          </form>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { useRouter } from 'vue-router'
import { useStarryBackground } from '@/composables/useStarryBackground'
import { useAppI18n } from '@/composables/useAppI18n'
import { useAuthStore } from '@/store/authStore'
import { useSystemConfigStore } from '@/store/systemConfigStore'
import { useThemeStore } from '@/store/themeStore'
import AppLocaleToggle from '@/components/AppLocaleToggle.vue'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const usernameInputRef = ref<HTMLInputElement | null>(null)
const launcherButtonRef = ref<HTMLButtonElement | null>(null)
const loginDialogRef = ref<HTMLDivElement | null>(null)
const username = ref('')
const password = ref('')
const rememberMe = ref(false)
const showPassword = ref(false)
const loginDialogVisible = ref(false)
const previousFocusedElement = ref<HTMLElement | null>(null)
const previousBodyOverflow = ref('')
const fingerprintAssetCandidates = ['/login-fingerprint.svg', '/login-fingerprint.png'] as const
const currentFingerprintAssetIndex = ref(0)
const fingerprintImageLoadFailed = ref(false)

useStarryBackground(canvasRef)

const themeStore = useThemeStore()
const isBlack = computed(() => themeStore.isBlack)
const toggleTheme = () => themeStore.toggleTheme()

const router = useRouter()
const authStore = useAuthStore()
const { isEnglish, t } = useAppI18n()
const isLoading = computed(() => authStore.getIsLoading)
const errorMessage = computed(() => authStore.getLoginError)
const currentFingerprintAsset = computed(() => fingerprintAssetCandidates[currentFingerprintAssetIndex.value] ?? null)

const systemConfigStore = useSystemConfigStore()
const brandLogoUrl = computed(() => systemConfigStore.getLogo)
const brandBadgeEnabled = computed(() => systemConfigStore.getBrandBadgeEnabled)
const brandBadgeUrl = computed(() => systemConfigStore.getBrandBadgeUrl)
const brandTitle = computed(() => systemConfigStore.getLoginTitle)
const brandSubtitle = computed(() => {
  return systemConfigStore.config.login_subtitle || (isEnglish.value ? 'Wheat intelligence test automation platform' : '小麦智测自动化平台')
})
const featureTags = computed(() => {
  const configTags = systemConfigStore.getLoginTags
  if (configTags && configTags.length > 0) {
    return configTags
  }
  return isEnglish.value
    ? ['AI generation', 'RAG knowledge base', 'MCP tool calling', 'Skills library', 'Playwright automation', 'LangGraph']
    : ['AI 智能生成', 'RAG 知识库', 'MCP 工具调用', 'Skills 技能库', 'Playwright 自动化', 'LangGraph']
})
const launcherTitle = computed(() => (
  isEnglish.value ? 'Account Login' : '账号登录'
))
const launcherSubtitle = computed(() => (
  isEnglish.value ? 'Click to open the sign-in dialog' : '点击展开登录框'
))
const usernamePlaceholder = computed(() => t('register.usernamePlaceholder'))
const passwordPlaceholder = computed(() => t('register.passwordPlaceholder'))
const dialogTitle = computed(() => (
  isEnglish.value ? 'Welcome back' : '欢迎回来'
))
const dialogDescription = computed(() => (
  isEnglish.value ? 'Sign in to your account' : '请登录您的账户'
))
const rememberMeLabel = computed(() => (
  isEnglish.value ? 'Remember me' : '记住我'
))
const submitLabel = computed(() => (
  isEnglish.value ? 'Sign in' : '登录'
))
const submittingLabel = computed(() => (
  isEnglish.value ? 'Signing in...' : '登录中...'
))
const registerPrompt = computed(() => (
  isEnglish.value ? 'No account yet?' : '还没有账号?'
))
const registerLinkLabel = computed(() => (
  isEnglish.value ? 'Register now' : '立即注册'
))
const loginRequiredMessage = computed(() => (
  isEnglish.value ? 'Enter username and password' : '请输入用户名和密码'
))
const loginSuccessMessage = computed(() => (
  isEnglish.value ? 'Signed in successfully!' : '登录成功！'
))

const focusableSelector = [
  'button:not([disabled])',
  'input:not([disabled])',
  'a[href]',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const focusUsernameInput = async () => {
  await nextTick()
  usernameInputRef.value?.focus()
}

const handleFingerprintAssetError = () => {
  if (currentFingerprintAssetIndex.value < fingerprintAssetCandidates.length - 1) {
    currentFingerprintAssetIndex.value += 1
    return
  }

  fingerprintImageLoadFailed.value = true
}

const openLoginDialog = async () => {
  previousFocusedElement.value = document.activeElement instanceof HTMLElement ? document.activeElement : launcherButtonRef.value
  loginDialogVisible.value = true
  await focusUsernameInput()
}

const closeLoginDialog = () => {
  if (isLoading.value) {
    return
  }
  loginDialogVisible.value = false
  showPassword.value = false
  nextTick(() => {
    const target = previousFocusedElement.value ?? launcherButtonRef.value
    target?.focus()
  })
}

const handleWindowKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && loginDialogVisible.value) {
    closeLoginDialog()
  }
}

const handleDialogKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Tab') {
    return
  }

  const focusableElements = loginDialogRef.value?.querySelectorAll<HTMLElement>(focusableSelector)
  if (!focusableElements || focusableElements.length === 0) {
    event.preventDefault()
    return
  }

  const firstElement = focusableElements[0]
  const lastElement = focusableElements[focusableElements.length - 1]
  const activeElement = document.activeElement

  if (event.shiftKey && activeElement === firstElement) {
    event.preventDefault()
    lastElement.focus()
    return
  }

  if (!event.shiftKey && activeElement === lastElement) {
    event.preventDefault()
    firstElement.focus()
  }
}

const handleLogin = async () => {
  if (!username.value || !password.value) {
    Message.warning(loginRequiredMessage.value)
    return
  }

  const success = await authStore.login(username.value, password.value)
  if (success) {
    Message.success(loginSuccessMessage.value)
    if (rememberMe.value) {
      localStorage.setItem('rememberedUsername', username.value)
    } else {
      localStorage.removeItem('rememberedUsername')
    }
    loginDialogVisible.value = false
    await router.push({ name: 'Dashboard' })
  }
}

watch(loginDialogVisible, (visible) => {
  if (visible) {
    previousBodyOverflow.value = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return
  }

  document.body.style.overflow = previousBodyOverflow.value
})

onMounted(() => {
  authStore.checkAuthStatus()
  if (authStore.isLoggedIn) {
    router.push({ name: 'Dashboard' })
  }
  const saved = localStorage.getItem('rememberedUsername')
  if (saved) {
    username.value = saved
    rememberMe.value = true
  }
})

watch(loginDialogVisible, (visible) => {
  if (visible) {
    window.addEventListener('keydown', handleWindowKeydown)
    return
  }

  window.removeEventListener('keydown', handleWindowKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleWindowKeydown)
  document.body.style.overflow = previousBodyOverflow.value
})
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background: linear-gradient(135deg, #f0f9ff 0%, #f1f5f9 50%, #dbeafe 100%);
  transition: background-color 0.5s ease;
}

:root[data-theme='black'] .login-page {
  background: radial-gradient(ellipse at 20% 50%, #0a1628 0%, #020810 100%);
}

.header-controls {
  position: absolute;
  top: 24px;
  right: 24px;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 12px;
}

.theme-toggle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.04);
  color: var(--theme-text-secondary, #4e5969);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.theme-toggle-btn:hover {
  background: rgba(15, 23, 42, 0.08);
  color: var(--theme-text, #1c1f23);
  transform: scale(1.05);
}

:root[data-theme='black'] .theme-toggle-btn {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(224, 236, 255, 0.8);
}

:root[data-theme='black'] .theme-toggle-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.theme-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
}

.theme-icon {
  width: 18px;
  height: 18px;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.theme-toggle-btn:hover .theme-icon {
  transform: rotate(15deg);
}

.starry-canvas,
.login-overlay {
  position: absolute;
  inset: 0;
}

.starry-canvas {
  z-index: 0;
}

.content-layer {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 36px;
  min-height: 100vh;
  padding: 12px 20px 150px;
}

.brand-area {
  text-align: center;
  animation: fade-in-down 0.8s ease-out;
}

.brand-logo {
  display: block;
  width: 72px;
  height: 72px;
  margin: 0 auto 16px;
  filter: drop-shadow(0 4px 12px rgba(59, 130, 246, 0.2));
  transform: translateX(-4px);
  transition: filter 0.3s ease;
}

:root[data-theme='black'] .brand-logo {
  filter: drop-shadow(0 0 20px rgba(100, 180, 255, 0.4));
}

.brand-title-row {
  display: inline-flex;
  align-items: flex-start;
  justify-content: center;
  margin: 0 0 8px;
}

.brand-title {
  margin: 0;
  color: #0f172a;
  font-size: 42px;
  font-weight: 800;
  letter-spacing: -0.5px;
  text-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
  transition: color 0.3s ease;
}

:root[data-theme='black'] .brand-title {
  color: #fff;
  text-shadow: 0 0 30px rgba(100, 180, 255, 0.3);
}

.brand-ce-icon {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  margin-left: 10px;
  object-fit: contain;
  transform: translateY(-25%);
  filter: drop-shadow(0 4px 10px rgba(14, 165, 233, 0.22));
}

:root[data-theme='black'] .brand-ce-icon {
  filter: drop-shadow(0 0 16px rgba(100, 180, 255, 0.45));
}

.brand-subtitle {
  margin: 0 0 20px;
  color: #475569;
  font-size: 16px;
  font-weight: 400;
  letter-spacing: 2px;
  transition: color 0.3s ease;
}

:root[data-theme='black'] .brand-subtitle {
  color: rgba(180, 210, 255, 0.8);
}

.brand-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.tag {
  padding: 4px 14px;
  border: 1px solid rgba(14, 165, 233, 0.18);
  border-radius: 999px;
  background: rgba(14, 165, 233, 0.04);
  backdrop-filter: blur(4px);
  color: #0284c7;
  font-size: 12px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.tag:hover {
  border-color: rgba(56, 189, 248, 0.4);
  background: rgba(56, 189, 248, 0.08);
  color: #38bdf8;
  transform: translateY(-1px);
}

:root[data-theme='black'] .tag {
  border: 1px solid rgba(100, 180, 255, 0.15);
  background: rgba(100, 180, 255, 0.08);
  color: rgba(180, 210, 255, 0.85);
}

:root[data-theme='black'] .tag:hover {
  border-color: rgba(100, 180, 255, 0.35);
  background: rgba(100, 180, 255, 0.14);
  color: #fff;
}

.login-launcher {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px 14px 14px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.65);
  box-shadow: 0 16px 40px rgba(148, 163, 184, 0.15);
  backdrop-filter: blur(18px);
  cursor: pointer;
  transition: transform 0.28s ease, box-shadow 0.28s ease, border-color 0.28s ease, background-color 0.28s ease;
  animation: fade-in-up 0.8s ease-out 0.15s both;
}

.login-launcher:hover {
  transform: translateY(-3px) scale(1.02);
  border-color: rgba(14, 165, 233, 0.4);
  background: rgba(255, 255, 255, 0.85);
  box-shadow: 0 18px 50px rgba(14, 165, 233, 0.12);
}

:root[data-theme='black'] .login-launcher {
  border: 1px solid rgba(129, 184, 255, 0.26);
  background: rgba(9, 20, 38, 0.54);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
}

:root[data-theme='black'] .login-launcher:hover {
  border-color: rgba(129, 184, 255, 0.44);
  background: rgba(12, 28, 52, 0.66);
  box-shadow: 0 18px 50px rgba(20, 74, 169, 0.28);
}

.login-launcher:focus-visible,
.dialog-close:focus-visible,
.toggle-icon:focus-visible {
  outline: 2px solid rgba(96, 165, 250, 0.9);
  outline-offset: 3px;
}

.launcher-aura {
  position: absolute;
  inset: -10px;
  border-radius: inherit;
  background: radial-gradient(circle, rgba(6, 182, 212, 0.2) 0%, rgba(16, 185, 129, 0.12) 40%, rgba(14, 165, 233, 0.06) 70%, transparent 100%);
  opacity: 0.85;
  filter: blur(12px);
  transition: background 0.3s ease;
}

:root[data-theme='black'] .launcher-aura {
  background: radial-gradient(circle, rgba(100, 180, 255, 0.24), transparent 72%);
}

.launcher-logo,
.launcher-copy {
  position: relative;
  z-index: 1;
}

.launcher-icon {
  position: relative;
  z-index: 1;
  flex: 0 0 56px;
  width: 56px;
  height: 56px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.85), rgba(56, 189, 248, 0.85));
  box-shadow: 0 12px 28px rgba(14, 165, 233, 0.35);
  overflow: hidden;
}

.launcher-icon svg,
.launcher-fingerprint-img {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 36px;
  height: 36px;
  display: block;
  object-fit: contain;
  color: #eaf3ff;
  transform: translate(-50%, -50%);
}

.launcher-fingerprint-img {
  transform: translate(calc(-50% + 1px), -50%);
}

.launcher-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  color: #1e293b;
  text-align: left;
  transition: color 0.3s ease;
}

:root[data-theme='black'] .launcher-copy {
  color: #e8f0ff;
}

.launcher-copy strong {
  font-size: 18px;
  font-weight: 700;
}

.launcher-copy span {
  color: #64748b;
  font-size: 13px;
  transition: color 0.3s ease;
}

:root[data-theme='black'] .launcher-copy span {
  color: rgba(180, 210, 255, 0.72);
}

.login-overlay {
  position: fixed;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: transparent;
  backdrop-filter: none;
}

.login-card {
  position: relative;
  width: min(100%, 420px);
  padding: 36px 32px 32px;
  border: 1px solid rgba(14, 165, 233, 0.15);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 
    inset 0 0 0 1px rgba(255, 255, 255, 0.8),
    0 8px 32px -4px rgba(14, 165, 233, 0.06),
    0 20px 48px -8px rgba(30, 41, 59, 0.08);
  backdrop-filter: blur(24px);
  transform-origin: center;
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

:root[data-theme='black'] .login-card {
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: linear-gradient(180deg, rgba(8, 18, 34, 0.56), rgba(10, 22, 40, 0.62));
  box-shadow: 0 22px 60px rgba(0, 0, 0, 0.28);
}

.dialog-close {
  position: absolute;
  top: 16px;
  right: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.04);
  color: #475569;
  cursor: pointer;
  transition: background-color 0.24s ease, transform 0.24s ease, color 0.3s ease;
}

.dialog-close:hover {
  background: rgba(59, 130, 246, 0.1);
  transform: rotate(90deg);
}

:root[data-theme='black'] .dialog-close {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(224, 236, 255, 0.88);
}

:root[data-theme='black'] .dialog-close:hover {
  background: rgba(96, 165, 250, 0.16);
}

.dialog-close svg,
.toggle-icon svg,
.error-icon,
.input-icon {
  width: 18px;
  height: 18px;
}

.card-header {
  margin-bottom: 28px;
  text-align: center;
}

.card-header h2 {
  margin: 0 0 6px;
  color: #1e293b;
  font-size: 24px;
  font-weight: 700;
  transition: color 0.3s ease;
}

:root[data-theme='black'] .card-header h2 {
  color: #fff;
}

.card-header p,
.remember-me,
.register-link {
  color: #64748b;
  transition: color 0.3s ease;
}

:root[data-theme='black'] .card-header p,
:root[data-theme='black'] .remember-me,
:root[data-theme='black'] .register-link {
  color: rgba(180, 210, 255, 0.62);
}

.card-header p {
  margin: 0;
  font-size: 14px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 14px;
  color: #94a3b8;
  pointer-events: none;
  transition: color 0.3s ease;
}

:root[data-theme='black'] .input-icon {
  color: rgba(180, 210, 255, 0.4);
}

.form-input {
  box-sizing: border-box;
  width: 100%;
  padding: 12px 42px 12px 44px;
  border: 1px solid rgba(14, 165, 233, 0.16);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.65);
  color: #0f172a;
  font-size: 14px;
  outline: none;
  transition: all 0.3s ease;
}

.form-input::placeholder {
  color: #94a3b8;
}

.form-input:focus {
  border-color: rgba(14, 165, 233, 0.6);
  background: #ffffff;
  box-shadow: 
    0 0 0 3px rgba(14, 165, 233, 0.08),
    inset 0 1px 2px rgba(14, 165, 233, 0.05);
}

.input-wrapper:focus-within .input-icon {
  color: #0ea5e9;
}

:root[data-theme='black'] .form-input {
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  color: #e8f0ff;
}

:root[data-theme='black'] .form-input::placeholder {
  color: rgba(180, 210, 255, 0.35);
}

:root[data-theme='black'] .form-input:focus {
  border-color: rgba(100, 180, 255, 0.5);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: 0 0 0 3px rgba(100, 180, 255, 0.1);
}

:root[data-theme='black'] .input-wrapper:focus-within .input-icon {
  color: rgba(100, 180, 255, 0.8);
}

.form-input::-ms-clear,
.form-input::-ms-reveal {
  display: none;
}

.toggle-icon {
  position: absolute;
  right: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: none;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  transition: color 0.3s ease;
}

.toggle-icon:hover {
  color: #0ea5e9;
}

:root[data-theme='black'] .toggle-icon {
  color: rgba(180, 210, 255, 0.4);
}

:root[data-theme='black'] .toggle-icon:hover {
  color: rgba(100, 180, 255, 0.8);
}

.remember-me {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
  user-select: none;
}

.remember-me input {
  accent-color: #0ea5e9;
}

:root[data-theme='black'] .remember-me input {
  accent-color: #4a9eff;
}

.login-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #0ea5e9, #0284c7);
  box-shadow: 0 4px 18px rgba(14, 165, 233, 0.28);
  color: #fff;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  transition: transform 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-1.5px);
  background: linear-gradient(135deg, #38bdf8, #0ea5e9);
  box-shadow: 0 6px 22px rgba(14, 165, 233, 0.38);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner {
  width: 18px;
  height: 18px;
  animation: spin 1s linear infinite;
}

.error-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.06);
  color: #dc2626;
  font-size: 13px;
  transition: all 0.3s ease;
}

:root[data-theme='black'] .error-msg {
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
}

.error-icon {
  flex-shrink: 0;
}

.register-link {
  margin: 4px 0 0;
  font-size: 13px;
  text-align: center;
}

.register-link a {
  color: #0284c7;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.2s ease;
}

.register-link a:hover {
  color: #0ea5e9;
  text-decoration: none;
  text-shadow: 0 0 8px rgba(14, 165, 233, 0.3);
}

:root[data-theme='black'] .register-link a {
  color: #60a5fa;
}

:root[data-theme='black'] .register-link a:hover {
  color: #93c5fd;
  text-shadow: 0 0 8px rgba(147, 197, 253, 0.4);
}

.login-dialog-enter-active,
.login-dialog-leave-active {
  transition: opacity 0.24s ease;
}

.login-dialog-enter-active .login-card,
.login-dialog-leave-active .login-card {
  transition: transform 0.28s ease, opacity 0.28s ease;
}

.login-dialog-enter-from,
.login-dialog-leave-to {
  opacity: 0;
}

.login-dialog-enter-from .login-card,
.login-dialog-leave-to .login-card {
  opacity: 0;
  transform: scale(0.78) translateY(12px);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes fade-in-down {
  from {
    opacity: 0;
    transform: translateY(-24px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(24px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 640px) {
  .content-layer {
    gap: 28px;
    padding: 12px 16px 88px;
  }

  .brand-title {
    font-size: 32px;
  }

  .brand-ce-icon {
    width: 28px;
    height: 28px;
    margin-left: 8px;
  }

  .login-launcher {
    width: min(100%, 320px);
    gap: 12px;
    padding-right: 18px;
  }

  .launcher-icon {
    width: 50px;
    height: 50px;
  }

  .login-overlay {
    padding: 16px;
  }

  .login-card {
    padding: 32px 24px 24px;
  }

  .brand-tags {
    gap: 6px;
  }

  .tag {
    padding: 3px 10px;
    font-size: 11px;
  }
}
</style>
