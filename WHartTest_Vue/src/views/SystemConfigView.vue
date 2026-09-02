<template>
  <div class="system-config-page">
    <!-- 未授权展示 -->
    <div v-if="!hasViewPermission" class="access-denied">
      <div class="denied-card">
        <div class="denied-icon">
          <icon-exclamation-polygon-fill />
        </div>
        <h2>{{ tl('无访问权限') }}</h2>
        <p>{{ tl('系统全局配置仅允许具有相应权限的用户访问。') }}</p>
        <a-button type="primary" @click="$router.push('/')">{{ tl('返回首页') }}</a-button>
      </div>
    </div>

    <!-- 系统全局配置界面 -->
    <div v-else class="config-container">
      <div class="config-header">
        <h1 class="page-title">
          <icon-settings class="title-icon" />
          {{ tl('系统全局配置') }}
        </h1>
        <p class="page-subtitle">{{ tl('定制您的平台标识、Logo图标及登录页展示，更改后即时对全平台生效，无需重新部署。') }}</p>
      </div>

      <div class="config-grid">
        <!-- 配置表单卡片 -->
        <a-card class="glass-card form-card" :bordered="false">
          <template #title>
            <div class="card-header-title">
              <icon-edit />
              <span>{{ tl('配置表单') }}</span>
            </div>
          </template>

          <!-- 只读模式提示 -->
          <a-alert v-if="!hasChangePermission" type="warning" show-icon style="margin-bottom: 20px; border-radius: 8px;">
            {{ tl('您当前仅有只读权限，无法修改系统配置。如需修改，请联系系统管理员分配“修改系统全局配置”权限。') }}
          </a-alert>

          <a-form :model="formData" layout="vertical" class="premium-form">
            <a-row :gutter="24">
              <!-- 浏览器标题 -->
              <a-col :span="12">
                <a-form-item :label="tl('平台浏览器标题')" field="title" required>
                  <a-input v-model="formData.title" :disabled="!hasChangePermission" :placeholder="tl('如：WHartTest')" max-length="100" />
                  <template #extra>
                    <span class="field-hint">{{ tl('展示在浏览器标签页上的网站标题（Document Title）。') }}</span>
                  </template>
                </a-form-item>
              </a-col>

              <!-- 平台名称 -->
              <a-col :span="12">
                <a-form-item :label="tl('平台展示名称')" field="name" required>
                  <a-input v-model="formData.name" :disabled="!hasChangePermission" :placeholder="tl('如：WHartTest')" max-length="100" />
                  <template #extra>
                    <span class="field-hint">{{ tl('系统主界面左上角 Logo 旁展示的品牌文字名称。') }}</span>
                  </template>
                </a-form-item>
              </a-col>
            </a-row>

            <a-divider />

            <a-row :gutter="24">
              <!-- 登录页大标题 -->
              <a-col :span="12">
                <a-form-item :label="tl('登录页主标题')" field="login_title" required>
                  <a-input v-model="formData.login_title" :disabled="!hasChangePermission" :placeholder="tl('如：WHartTest')" max-length="100" />
                  <template #extra>
                    <span class="field-hint">{{ tl('登录页面品牌中心展示的主标题文本。') }}</span>
                  </template>
                </a-form-item>
              </a-col>

              <!-- 登录页副标题 -->
              <a-col :span="12">
                <a-form-item :label="tl('登录页副标题')" field="login_subtitle" required>
                  <a-input v-model="formData.login_subtitle" :disabled="!hasChangePermission" :placeholder="tl('如：小麦智测自动化平台')" max-length="200" />
                  <template #extra>
                    <span class="field-hint">{{ tl('登录页面主标题下方的宣传或简短说明副标题。') }}</span>
                  </template>
                </a-form-item>
              </a-col>
            </a-row>

            <!-- 登录页特色标签 -->
            <a-form-item :label="tl('登录页特色标签')" field="login_tags">
              <a-textarea 
                v-model="formData.login_tags" 
                :disabled="!hasChangePermission"
                :placeholder="tl('以逗号分隔，例如：AI智能生成, RAG知识库, MCP工具调用')"
                :auto-size="{ minRows: 2, maxRows: 4 }" 
              />
              <template #extra>
                <span class="field-hint">{{ tl('显示在登录页上的产品卖点标签，多个标签请使用中文或英文逗号分隔。') }}</span>
              </template>
            </a-form-item>

            <a-divider />

            <!-- 自定义 Logo -->
            <a-form-item :label="tl('系统Logo图片路径或Base64')" field="logo_url">
              <a-space direction="vertical" fill :size="12" style="width: 100%">
                <div class="image-config-row">
                  <div class="logo-preview-box">
                    <img :src="previewLogo" class="logo-preview-img" alt="Logo Preview" />
                  </div>
                  <a-space wrap>
                    <a-button :disabled="!hasChangePermission" @click="triggerLogoUpload">
                      {{ tl('上传图片') }}
                    </a-button>
                    <a-button :disabled="!hasChangePermission" @click="useDefaultLogo">
                      {{ tl('使用默认Logo') }}
                    </a-button>
                    <a-button :disabled="!hasChangePermission" @click="clearLogoUrl">
                      {{ tl('清空') }}
                    </a-button>
                  </a-space>
                  <input ref="logoFileInput" type="file" accept="image/*" class="hidden-file-input" @change="handleLogoFileChange" />
                </div>
                <a-textarea 
                  v-model="formData.logo_url" 
                  :disabled="!hasChangePermission"
                  :placeholder="tl('可粘贴图片URL/Base64，也可以点击上方上传图片自动转换')"
                  :auto-size="{ minRows: 3, maxRows: 6 }" 
                />
              </a-space>
              <template #extra>
                <span class="field-hint">{{ tl('支持上传图片自动转换为Base64，也支持粘贴图片URL或Base64；留空则自动回退至默认麦穗图标。') }}</span>
              </template>
            </a-form-item>

            <!-- 品牌角标设置 -->
            <a-form-item :label="tl('品牌角标设置')" field="brand_badge_enabled">
              <a-space direction="vertical" fill :size="12" style="width: 100%">
                <div class="badge-config-row">
                  <div class="badge-preview-box" :class="{ disabled: !formData.brand_badge_enabled }">
                    <img v-if="formData.brand_badge_enabled" :src="previewBrandBadge" class="badge-preview-img" alt="Badge Preview" />
                    <span v-else class="badge-preview-empty">{{ tl('已隐藏') }}</span>
                  </div>
                  <a-space wrap>
                    <a-button :disabled="!hasChangePermission || !formData.brand_badge_enabled" @click="triggerBadgeUpload">
                      {{ tl('上传图片') }}
                    </a-button>
                    <a-button :disabled="!hasChangePermission || !formData.brand_badge_enabled" @click="useDefaultBadge">
                      {{ tl('使用默认PE图标') }}
                    </a-button>
                    <a-button :disabled="!hasChangePermission || !formData.brand_badge_enabled" @click="clearBadgeUrl">
                      {{ tl('清空') }}
                    </a-button>
                    <a-switch v-model="formData.brand_badge_enabled" :disabled="!hasChangePermission">
                      <template #checked>{{ tl('显示') }}</template>
                      <template #unchecked>{{ tl('隐藏') }}</template>
                    </a-switch>
                  </a-space>
                  <input ref="badgeFileInput" type="file" accept="image/*" class="hidden-file-input" @change="handleBadgeFileChange" />
                </div>

                <a-textarea
                  v-model="formData.brand_badge_url"
                  :disabled="!hasChangePermission || !formData.brand_badge_enabled"
                  :placeholder="tl('可粘贴图片URL/Base64，也可以点击上方上传图片自动转换')"
                  :auto-size="{ minRows: 2, maxRows: 5 }"
                />
              </a-space>
              <template #extra>
                <span class="field-hint">{{ tl('控制登录页标题右侧和登录后导航栏品牌文字右侧的角标；推荐直接上传图片，系统会自动转换为Base64保存。') }}</span>
              </template>
            </a-form-item>

            <!-- 提交按钮 -->
            <div class="form-actions">
              <a-button type="secondary" :disabled="!hasChangePermission" @click="resetToCurrent">{{ tl('重置修改') }}</a-button>
              <a-button type="primary" :loading="saving" :disabled="!hasChangePermission" @click="handleSave" class="save-button">
                <template #icon><icon-check /></template>
                {{ tl('保存配置') }}
              </a-button>
            </div>
          </a-form>
        </a-card>

        <!-- 实时视觉预览卡片 -->
        <div class="preview-column">
          <a-card class="glass-card preview-card" :bordered="false">
            <template #title>
              <div class="card-header-title">
                <icon-eye />
                <span>{{ tl('实时品牌预览 (无需刷新)') }}</span>
              </div>
            </template>

            <div class="preview-sections">
              <!-- 侧边栏/顶栏预览 -->
              <div class="preview-section-box">
                <div class="preview-badge">{{ tl('系统顶栏/侧边栏效果') }}</div>
                <div class="mock-header">
                  <div class="mock-logo">
                    <img :src="previewLogo" class="mock-logo-img" alt="Logo Preview" />
                    <span class="mock-logo-text">{{ formData.name || 'WHartTest' }}</span>
                    <img v-if="formData.brand_badge_enabled" :src="previewBrandBadge" class="mock-logo-badge" alt="Badge Preview" />
                  </div>
                  <div class="mock-nav-items">
                    <span class="mock-nav-item active"></span>
                    <span class="mock-nav-item"></span>
                    <span class="mock-nav-item"></span>
                  </div>
                </div>
              </div>

              <!-- 登录页品牌区域预览 -->
              <div class="preview-section-box">
                <div class="preview-badge">{{ tl('登录页品牌效果') }}</div>
                <div class="mock-login-brand">
                  <img :src="previewLogo" class="mock-login-logo" alt="Login Logo Preview" />
                  <div class="mock-login-title-row">
                    <h2 class="mock-login-title">{{ formData.login_title || 'WHartTest' }}</h2>
                    <img v-if="formData.brand_badge_enabled" :src="previewBrandBadge" class="mock-login-badge" alt="Badge Preview" />
                  </div>
                  <p class="mock-login-subtitle">{{ formData.login_subtitle || tl(DEFAULT_LOGIN_SUBTITLE) }}</p>
                  <div class="mock-login-tags">
                    <span v-for="tag in parsedTags" :key="tag" class="mock-tag">{{ tag }}</span>
                  </div>
                </div>
              </div>

              <!-- 浏览器标题效果 -->
              <div class="preview-section-box">
                <div class="preview-badge">{{ tl('浏览器页签预览') }}</div>
                <div class="mock-browser-tab">
                  <div class="mock-tab-icon">
                    <img :src="previewLogo" class="mock-tab-img" alt="Tab Icon" />
                  </div>
                  <span class="mock-tab-title">{{ formData.title || 'WHartTest' }}</span>
                  <icon-close class="mock-tab-close" />
                </div>
              </div>
            </div>
          </a-card>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useAuthStore } from '@/store/authStore';
import { useSystemConfigStore } from '@/store/systemConfigStore';
import { useAppI18n } from '@/composables/useAppI18n';
import { Message } from '@arco-design/web-vue';
import { brandLogoUrl, getPublicAssetUrl } from '@/utils/assetUrl';
import {
  IconSettings,
  IconExclamationPolygonFill,
  IconEdit,
  IconEye,
  IconCheck,
  IconClose
} from '@arco-design/web-vue/es/icon';

const authStore = useAuthStore();
const systemConfigStore = useSystemConfigStore();
const { t, tl } = useAppI18n();
const DEFAULT_LOGIN_SUBTITLE = '小麦智测自动化平台';
const DEFAULT_LOGIN_TAGS = 'AI 智能生成, RAG 知识库, MCP 工具调用, Skills 技能库, Playwright 自动化, LangGraph, 接口自动化';
const DEFAULT_BRAND_BADGE_URL = getPublicAssetUrl('PE.svg');

const hasViewPermission = computed(() => authStore.hasPermission('accounts.view_systemconfig'));
const hasChangePermission = computed(() => authStore.hasPermission('accounts.change_systemconfig'));
const saving = ref(false);
const logoFileInput = ref<HTMLInputElement | null>(null);
const badgeFileInput = ref<HTMLInputElement | null>(null);

const formData = ref({
  title: '',
  name: '',
  login_title: '',
  login_subtitle: '',
  login_tags: '',
  logo_url: '',
  brand_badge_enabled: true,
  brand_badge_url: DEFAULT_BRAND_BADGE_URL,
});

// 加载现有配置
const loadConfig = () => {
  const cfg = systemConfigStore.config;
  formData.value = {
    title: cfg.title || 'WHartTest',
    name: cfg.name || 'WHartTest',
    login_title: cfg.login_title || 'WHartTest',
    login_subtitle: cfg.login_subtitle || tl(DEFAULT_LOGIN_SUBTITLE),
    login_tags: cfg.login_tags || tl(DEFAULT_LOGIN_TAGS),
    logo_url: cfg.logo_url || '',
    brand_badge_enabled: cfg.brand_badge_enabled !== false,
    brand_badge_url: cfg.brand_badge_url || DEFAULT_BRAND_BADGE_URL,
  };
};

onMounted(async () => {
  if (hasViewPermission.value) {
    if (!systemConfigStore.isLoaded) {
      await systemConfigStore.fetchConfig();
    }
    loadConfig();
  }
});

// 重置修改
const resetToCurrent = () => {
  loadConfig();
  Message.info(tl('已重置回当前系统生效的配置'));
};



const triggerLogoUpload = () => {
  logoFileInput.value?.click();
};

const useDefaultLogo = () => {
  formData.value.logo_url = '';
};

const clearLogoUrl = () => {
  formData.value.logo_url = '';
};

const handleLogoFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (!file.type.startsWith('image/')) {
    Message.warning(tl('请选择图片文件'));
    input.value = '';
    return;
  }
  const maxSize = 10 * 1024 * 1024;
  if (file.size > maxSize) {
    Message.warning(tl('图片不能超过10MB'));
    input.value = '';
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    formData.value.logo_url = String(reader.result || '');
    Message.success(tl('Logo图片已转换为Base64'));
    input.value = '';
  };
  reader.onerror = () => {
    Message.error(tl('图片读取失败'));
    input.value = '';
  };
  reader.readAsDataURL(file);
};

const triggerBadgeUpload = () => {
  badgeFileInput.value?.click();
};

const useDefaultBadge = () => {
  formData.value.brand_badge_url = DEFAULT_BRAND_BADGE_URL;
};

const clearBadgeUrl = () => {
  formData.value.brand_badge_url = '';
};

const handleBadgeFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (!file.type.startsWith('image/')) {
    Message.warning(tl('请选择图片文件'));
    input.value = '';
    return;
  }
  const maxSize = 10 * 1024 * 1024;
  if (file.size > maxSize) {
    Message.warning(tl('图片不能超过10MB'));
    input.value = '';
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    formData.value.brand_badge_url = String(reader.result || '');
    Message.success(tl('角标图片已转换为Base64'));
    input.value = '';
  };
  reader.onerror = () => {
    Message.error(tl('图片读取失败'));
    input.value = '';
  };
  reader.readAsDataURL(file);
};

// 保存配置
const handleSave = async () => {
  if (!formData.value.title.trim()) {
    Message.warning(tl('请填写浏览器标题'));
    return;
  }
  if (!formData.value.name.trim()) {
    Message.warning(tl('请填写平台展示名称'));
    return;
  }
  if (!formData.value.login_title.trim()) {
    Message.warning(tl('请填写登录页主标题'));
    return;
  }

  saving.value = true;
  try {
    const res = await systemConfigStore.updateConfig(formData.value);
    if (res.success) {
      Message.success(tl('系统全局配置修改成功，已即时对全平台应用！'));
    } else {
      Message.error(res.error || tl('修改失败，请重试'));
    }
  } catch (e: any) {
    Message.error(e.message || tl('保存过程中发生错误'));
  } finally {
    saving.value = false;
  }
};

// 实时预览图片
const previewLogo = computed(() => {
  return formData.value.logo_url ? formData.value.logo_url.trim() : brandLogoUrl;
});

const previewBrandBadge = computed(() => {
  return formData.value.brand_badge_url ? formData.value.brand_badge_url.trim() : DEFAULT_BRAND_BADGE_URL;
});

// 解析特色标签供预览展示
const parsedTags = computed(() => {
  const tagsStr = formData.value.login_tags || '';
  return tagsStr.split(/,|，/).map(t => t.trim()).filter(Boolean);
});
</script>

<style scoped>
.system-config-page {
  padding: 24px;
  height: 100%;
  box-sizing: border-box;
  overflow-y: auto;
  background: var(--color-bg-1);
}

.access-denied {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 200px);
}

.denied-card {
  max-width: 480px;
  text-align: center;
  padding: 40px;
  background: var(--color-bg-2);
  border-radius: 16px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
  border: 1px solid var(--color-border-2);
  backdrop-filter: blur(8px);
}

.denied-icon {
  font-size: 56px;
  color: var(--color-warning-light-4);
  margin-bottom: 20px;
}

.denied-card h2 {
  font-size: 24px;
  color: var(--color-text-1);
  margin-bottom: 12px;
}

.denied-card p {
  color: var(--color-text-3);
  margin-bottom: 24px;
  font-size: 14px;
  line-height: 1.6;
}

.config-container {
  max-width: 1300px;
  margin: 0 auto;
}

.config-header {
  margin-bottom: 30px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-1);
  margin: 0 0 8px 0;
  letter-spacing: -0.5px;
}

.title-icon {
  color: var(--color-primary-light-4);
}

.page-subtitle {
  color: var(--color-text-3);
  font-size: 15px;
  margin: 0;
}

.config-grid {
  display: grid;
  grid-template-columns: 1fr 420px;
  gap: 24px;
  align-items: start;
}

@media (max-width: 1024px) {
  .config-grid {
    grid-template-columns: 1fr;
  }
}

.glass-card {
  background: var(--color-bg-2);
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
  border: 1px solid var(--color-border-2);
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.glass-card:hover {
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
}

.card-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-1);
}

.premium-form {
  padding-top: 10px;
}

.field-hint {
  font-size: 12px;
  color: var(--color-text-3);
}



.image-config-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.logo-preview-box {
  width: 88px;
  min-height: 54px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  border: 1px dashed var(--color-border-3);
  border-radius: 10px;
  background: var(--color-bg-1);
}

.logo-preview-img {
  max-width: 64px;
  max-height: 38px;
  object-fit: contain;
}

.badge-config-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.badge-preview-box {
  width: 88px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  border: 1px dashed var(--color-border-3);
  border-radius: 10px;
  background: var(--color-bg-1);
}

.badge-preview-box.disabled {
  color: var(--color-text-4);
  background: var(--color-fill-1);
}

.badge-preview-img {
  max-width: 64px;
  max-height: 28px;
  object-fit: contain;
}

.badge-preview-empty {
  font-size: 12px;
  color: var(--color-text-4);
}

.hidden-file-input {
  display: none;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 30px;
}

.save-button {
  min-width: 120px;
  background: linear-gradient(135deg, rgb(var(--primary-6)) 0%, rgb(var(--primary-5)) 100%);
  border: none;
  transition: transform 0.2s;
}

.save-button:hover {
  transform: translateY(-1px);
}

.preview-column {
  position: sticky;
  top: 24px;
}

.preview-card {
  background: var(--color-bg-2);
}

.preview-sections {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 10px 0;
}

.preview-section-box {
  position: relative;
  background: var(--color-bg-1);
  border: 1px dashed var(--color-border-3);
  border-radius: 12px;
  padding: 24px 16px 16px;
}

.preview-badge {
  position: absolute;
  top: -10px;
  left: 12px;
  background: var(--color-primary-light-1);
  color: rgb(var(--primary-6));
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid var(--color-primary-light-2);
}

/* 顶栏预览模拟 */
.mock-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--color-menu-light-bg, #ffffff);
  border: 1px solid var(--color-border-2);
  border-radius: 8px;
  height: 48px;
  padding: 0 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.mock-logo {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mock-logo-img {
  width: 20px;
  height: 20px;
  object-fit: contain;
}

.mock-logo-text {
  font-weight: 700;
  font-size: 14px;
  color: var(--color-text-1);
}

.mock-logo-badge {
  width: 18px;
  height: 13px;
  object-fit: contain;
  transform: translateY(-25%);
}

.mock-nav-items {
  display: flex;
  gap: 8px;
}

.mock-nav-item {
  width: 24px;
  height: 6px;
  background: var(--color-fill-3);
  border-radius: 3px;
}

.mock-nav-item.active {
  background: rgb(var(--primary-6));
}

/* 登录品牌模拟 */
.mock-login-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  background: radial-gradient(circle at center, var(--color-bg-2) 0%, var(--color-bg-1) 100%);
  border: 1px solid var(--color-border-2);
  border-radius: 12px;
  padding: 24px 16px;
  box-shadow: inset 0 0 20px rgba(0,0,0,0.02);
}

.mock-login-logo {
  width: 44px;
  height: 44px;
  margin-bottom: 12px;
  object-fit: contain;
}

.mock-login-title-row {
  display: inline-flex;
  align-items: flex-start;
  justify-content: center;
  margin: 0 0 6px 0;
}

.mock-login-title {
  font-size: 20px;
  font-weight: 800;
  margin: 0;
  color: var(--color-text-1);
}

.mock-login-badge {
  flex: 0 0 auto;
  width: 24px;
  height: 18px;
  margin-left: 6px;
  object-fit: contain;
  transform: translateY(-25%);
}

.mock-login-subtitle {
  font-size: 12px;
  color: var(--color-text-3);
  margin: 0 0 14px 0;
}

.mock-login-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
}

.mock-tag {
  font-size: 10px;
  color: rgb(var(--primary-6));
  background: var(--color-primary-light-1);
  border: 1px solid var(--color-primary-light-2);
  padding: 1px 6px;
  border-radius: 4px;
}

/* 页签模拟 */
.mock-browser-tab {
  display: flex;
  align-items: center;
  background: var(--color-bg-3);
  border: 1px solid var(--color-border-2);
  border-radius: 6px 6px 0 0;
  padding: 6px 12px;
  width: 180px;
  margin: 0 auto;
  gap: 8px;
}

.mock-tab-icon {
  width: 14px;
  height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mock-tab-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.mock-tab-title {
  font-size: 12px;
  color: var(--color-text-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.mock-tab-close {
  font-size: 10px;
  color: var(--color-text-4);
  cursor: pointer;
}
</style>
