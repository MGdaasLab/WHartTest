import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export type ApiTab =
  | 'interfaces'
  | 'testcases'
  | 'testtasks'
  | 'environments'
  | 'functions'
  | 'database-configs'
  | 'sync-config'
  | 'test-reports'
  | 'dashboard';

export interface InterfaceTab {
  id: string;
  interfaceId?: number;
  method: string;
  url: string;
  name: string;
  module?: any;
  params?: any;
  headers?: any;
  body?: any;
  setupHooks?: any;
  teardownHooks?: any;
  extractRules?: any;
  extractMeta?: any;
  assertRules?: any;
  response?: any;
  activeTab?: string;
}

const STORAGE_KEY = 'api-testing-tabs';

let _tabCounter = 0;
function genTabId(): string {
  return `tab-${Date.now()}-${++_tabCounter}`;
}

export const useApiTabsStore = defineStore('apiTabs', () => {
  // --- Top-level navigation tab (interfaces / testcases / etc.) ---
  const activeTab = ref<ApiTab>('interfaces');

  const setActiveTab = (tab: ApiTab) => {
    activeTab.value = tab;
  };

  const isActive = computed(() => (tab: ApiTab) => activeTab.value === tab);

  // --- Interface editor tabs ---
  const tabs = ref<InterfaceTab[]>([]);
  const activeTabId = ref<string | null>(null);

  function createTab(): string {
    const tab: InterfaceTab = {
      id: genTabId(),
      method: 'GET',
      url: '',
      name: '新接口',
    };
    tabs.value.push(tab);
    activeTabId.value = tab.id;
    return tab.id;
  }

  function activateTab(tabId: string) {
    activeTabId.value = tabId;
  }

  function removeTab(tabId: string) {
    const idx = tabs.value.findIndex(t => t.id === tabId);
    if (idx === -1) return;
    tabs.value.splice(idx, 1);
    if (activeTabId.value === tabId) {
      activeTabId.value = tabs.value.length > 0
        ? tabs.value[Math.min(idx, tabs.value.length - 1)].id
        : null;
    }
  }

  function removeInterfaceTabs(interfaceId: number): string[] {
    const tabIds = tabs.value
      .filter(tab => tab.interfaceId === interfaceId)
      .map(tab => tab.id);

    tabIds.forEach(removeTab);
    return tabIds;
  }

  function openOrActivateInterface(api: { id?: number; name?: string; method?: string; url?: string; module?: any }): string {
    if (api.id) {
      const existing = tabs.value.find(t => t.interfaceId === api.id);
      if (existing) {
        activeTabId.value = existing.id;
        return existing.id;
      }
    }
    const tab: InterfaceTab = {
      id: genTabId(),
      interfaceId: api.id,
      method: (api.method as string) || 'GET',
      url: (api.url as string) || '',
      name: api.name || '新接口',
      module: api.module,
    };
    tabs.value.push(tab);
    activeTabId.value = tab.id;
    return tab.id;
  }

  function updateTabRequest(tabId: string, data: Partial<Omit<InterfaceTab, 'id'>>) {
    const tab = tabs.value.find(t => t.id === tabId);
    if (!tab) return;
    Object.assign(tab, data);
  }

  function updateTabResponse(tabId: string, response: any) {
    const tab = tabs.value.find(t => t.id === tabId);
    if (!tab) return;
    tab.response = response;
  }

  function updateTabUIState(tabId: string, state: { activeTab?: string }) {
    const tab = tabs.value.find(t => t.id === tabId);
    if (!tab) return;
    if (state.activeTab !== undefined) tab.activeTab = state.activeTab;
  }

  function findTabByInterface(interfaceId: number): InterfaceTab | undefined {
    return tabs.value.find(t => t.interfaceId === interfaceId);
  }

  function saveToLocalStorage() {
    try {
      const data = tabs.value.map(t => ({
        ...t,
        response: undefined, // don't persist response data
      }));
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ tabs: data, activeTabId: activeTabId.value }));
    } catch { /* ignore quota errors */ }
  }

  function loadFromLocalStorage() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.tabs)) {
        tabs.value = parsed.tabs;
        activeTabId.value = parsed.activeTabId ?? (tabs.value.length > 0 ? tabs.value[0].id : null);
      }
    } catch { /* ignore parse errors */ }
  }

  return {
    // Top-level nav
    activeTab,
    setActiveTab,
    isActive,
    // Interface editor tabs
    tabs,
    activeTabId,
    createTab,
    activateTab,
    removeTab,
    removeInterfaceTabs,
    openOrActivateInterface,
    updateTabRequest,
    updateTabResponse,
    updateTabUIState,
    findTabByInterface,
    saveToLocalStorage,
    loadFromLocalStorage,
  };
});
