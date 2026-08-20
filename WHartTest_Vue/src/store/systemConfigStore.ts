import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { systemConfigService, type SystemConfig } from '@/services/systemConfigService';
import { brandLogoUrl, getPublicAssetUrl } from '@/utils/assetUrl';

const defaultBrandBadgeUrl = getPublicAssetUrl('CE.svg');

export const useSystemConfigStore = defineStore('systemConfig', () => {
  const config = ref<SystemConfig>({
    title: 'WHartTest',
    name: 'WHartTest',
    login_title: 'WHartTest',
    login_subtitle: '小麦智测自动化平台',
    login_tags: 'AI 智能生成, RAG 知识库, MCP 工具调用, Skills 技能库, Playwright 自动化, LangGraph',
    logo_url: '',
    brand_badge_enabled: true,
    brand_badge_url: defaultBrandBadgeUrl,
    operation_log_retention_days: 7,
  });

  const isLoaded = ref(false);

  const getLogo = computed(() => {
    return config.value.logo_url || brandLogoUrl;
  });

  const getBrandBadgeEnabled = computed(() => config.value.brand_badge_enabled !== false);
  const getBrandBadgeUrl = computed(() => config.value.brand_badge_url || defaultBrandBadgeUrl);

  const getTitle = computed(() => config.value.title);
  const getName = computed(() => config.value.name);
  const getLoginTitle = computed(() => config.value.login_title);
  const getLoginSubtitle = computed(() => config.value.login_subtitle);
  const getLoginTags = computed(() => {
    const tagsStr = config.value.login_tags || '';
    // 支持中文逗号和英文逗号分隔
    return tagsStr.split(/,|，/).map(t => t.trim()).filter(Boolean);
  });

  // 仅在应用初始化时拉取一次配置，没有后台轮询或监听，不浪费资源
  const fetchConfig = async () => {
    try {
      const response = await systemConfigService.getPublicConfig();
      if (response.success && response.data) {
        config.value = {
          ...config.value,
          ...response.data,
        };
        isLoaded.value = true;
        // 保存并立即修改浏览器标签页标题
        if (config.value.title) {
          document.title = config.value.title;
        }
      }
    } catch (e) {
      console.error('Failed to load system public config:', e);
    }
  };

  // 用户点击保存时，更新后端数据，并同步更新 Store 内的局部响应式状态实现即时生效
  const updateConfig = async (payload: Partial<SystemConfig>) => {
    const response = await systemConfigService.updateConfig(payload);
    if (response.success && response.data) {
      config.value = {
        ...config.value,
        ...response.data,
      };
      if (config.value.title) {
        document.title = config.value.title;
      }
    }
    return response;
  };

  return {
    config,
    isLoaded,
    getLogo,
    getBrandBadgeEnabled,
    getBrandBadgeUrl,
    getTitle,
    getName,
    getLoginTitle,
    getLoginSubtitle,
    getLoginTags,
    fetchConfig,
    updateConfig,
  };
});
