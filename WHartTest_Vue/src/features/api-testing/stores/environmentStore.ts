import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { ApiEnvironment } from '../types/environment';
import { environmentService } from '../services/environmentService';
import { toArray } from '../services/responseHelpers';

const ENVIRONMENT_STORAGE_KEY = 'api_testing_selected_environments';

export const useEnvironmentStore = defineStore('apiEnvironment', () => {
  const environments = ref<ApiEnvironment[]>([]);
  const currentEnvironmentId = ref<number | null>(null);
  const activeProjectId = ref<number | null>(null);
  const loading = ref(false);

  const loadSavedEnvironmentMap = (): Record<string, number> => {
    try {
      const raw = localStorage.getItem(ENVIRONMENT_STORAGE_KEY);
      if (!raw) {
        return {};
      }

      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (error) {
      console.warn('读取保存的环境配置失败:', error);
      return {};
    }
  };

  const saveEnvironmentMap = (environmentMap: Record<string, number>) => {
    try {
      localStorage.setItem(ENVIRONMENT_STORAGE_KEY, JSON.stringify(environmentMap));
    } catch (error) {
      console.warn('保存环境配置失败:', error);
    }
  };

  const getSavedEnvironmentId = (projectId: number): number | null => {
    const environmentMap = loadSavedEnvironmentMap();
    const savedEnvironmentId = Number(environmentMap[String(projectId)]);
    return Number.isInteger(savedEnvironmentId) && savedEnvironmentId > 0
      ? savedEnvironmentId
      : null;
  };

  const saveEnvironmentId = (projectId: number, environmentId: number | null) => {
    const environmentMap = loadSavedEnvironmentMap();
    const storageKey = String(projectId);

    if (environmentId === null) {
      delete environmentMap[storageKey];
    } else {
      environmentMap[storageKey] = environmentId;
    }

    saveEnvironmentMap(environmentMap);
  };

  const currentEnvironment = computed(() =>
    environments.value.find((e) => e.id === currentEnvironmentId.value) ?? null,
  );

  const environmentOptions = computed(() =>
    environments.value
      .filter((e) => e.is_active)
      .map((e) => ({ label: e.name, value: e.id })),
  );

  async function fetchEnvironments(projectId: number) {
    const projectChanged = activeProjectId.value !== projectId;
    activeProjectId.value = projectId;
    loading.value = true;
    try {
      const res = await environmentService.list(projectId);
      if (res.success && res.data) {
        environments.value = toArray<ApiEnvironment>((res.data as any)?.results ?? res.data);
        const validEnvironmentIds = new Set(environments.value.map((environment) => environment.id));
        const canKeepCurrentSelection = !projectChanged
          && currentEnvironmentId.value !== null
          && validEnvironmentIds.has(currentEnvironmentId.value);

        if (canKeepCurrentSelection && currentEnvironmentId.value !== null) {
          saveEnvironmentId(projectId, currentEnvironmentId.value);
        } else {
          const savedEnvironmentId = getSavedEnvironmentId(projectId);
          currentEnvironmentId.value = savedEnvironmentId !== null && validEnvironmentIds.has(savedEnvironmentId)
            ? savedEnvironmentId
            : null;
        }
      } else {
        environments.value = [];
        currentEnvironmentId.value = null;
      }
    } catch (error) {
      environments.value = [];
      currentEnvironmentId.value = null;
      throw error;
    } finally {
      loading.value = false;
    }
  }

  function setCurrentEnvironment(id: number | null) {
    currentEnvironmentId.value = id;
    if (activeProjectId.value !== null) {
      saveEnvironmentId(activeProjectId.value, id);
    }
  }

  function $reset() {
    environments.value = [];
    currentEnvironmentId.value = null;
    activeProjectId.value = null;
    loading.value = false;
  }

  return {
    environments,
    currentEnvironmentId,
    currentEnvironment,
    environmentOptions,
    loading,
    fetchEnvironments,
    setCurrentEnvironment,
    $reset,
  };
});
