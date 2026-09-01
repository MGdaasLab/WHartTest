<template>
  <a-modal
    v-model:visible="internalVisible"
    :title="tl('执行测试用例')"
    :width="540"
    @ok="handleConfirm"
    @cancel="handleCancel"
    :ok-text="tl('开始执行')"
    :cancel-text="tl('取消')"
  >
    <div class="execute-modal-content">
      <a-descriptions :column="1" bordered size="small" class="testcase-info">
        <a-descriptions-item :label="tl('用例名称')">
          {{ testCase?.name || '-' }}
        </a-descriptions-item>
        <a-descriptions-item :label="tl('用例等级')">
          <a-tag :color="getLevelColor(testCase?.level)">
            {{ testCase?.level || '-' }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item :label="tl('UI 自动化绑定')">
          <div v-if="boundUiTestCase" class="bound-ui-info">
            <a-tag color="green" size="small">
              <template #icon><icon-check-circle /></template>
              {{ tl('已绑定') }}
            </a-tag>
            <span class="bound-name">{{ boundUiTestCase.name }}</span>
            <a-tag v-if="boundUiTestCase.step_count !== undefined" color="arcoblue" size="small">
              {{ boundUiTestCase.step_count }} {{ tl('步') }}
            </a-tag>
          </div>
          <div v-else class="unbound-ui-info">
            <a-tag color="gray" size="small">{{ tl('未绑定 UI 脚本') }}</a-tag>
            <a-button type="text" size="mini" @click="showBindSelect = !showBindSelect">
              {{ showBindSelect ? tl('取消选择') : tl('关联已有 UI 用例') }}
            </a-button>
          </div>
        </a-descriptions-item>
      </a-descriptions>

      <!-- 快速关联已有 UI 用例 -->
      <div v-if="showBindSelect || (!boundUiTestCase && uiTestCases.length > 0)" class="bind-select-box">
        <a-form-item :label="tl('选择要绑定的 UI 自动化用例')">
          <a-select
            v-model="selectedUiTestCaseId"
            :placeholder="tl('请选择项目下的 UI 自动化用例')"
            allow-clear
            :loading="loadingUiCases"
          >
            <a-option
              v-for="item in uiTestCases"
              :key="item.id"
              :value="item.id"
              :label="`${item.name} (${item.level || 'P2'})`"
            />
          </a-select>
        </a-form-item>
      </div>

      <a-divider orientation="left">{{ tl('执行模式配置') }}</a-divider>

      <a-form :model="formData" layout="vertical">
        <a-form-item :label="tl('执行模式')">
          <a-radio-group v-model="formData.executionMode" direction="vertical" class="mode-radio-group">
            <a-radio value="hybrid" :disabled="!hasAvailableUiCase">
              <div class="radio-label">
                <span class="radio-title">{{ tl('智能双模执行（推荐）') }}</span>
                <span class="radio-desc">{{ tl('先高速运行 UI 自动化脚本（零 Token、秒级执行）；若执行失败，AI 测试工程师自动介入诊断并自愈！') }}</span>
              </div>
            </a-radio>
            <a-radio value="script_only" :disabled="!hasAvailableUiCase">
              <div class="radio-label">
                <span class="radio-title">{{ tl('仅执行 UI 自动化脚本') }}</span>
                <span class="radio-desc">{{ tl('仅运行绑定的 Playwright/Actuator UI 脚本，失败不调用 AI 介入。') }}</span>
              </div>
            </a-radio>
            <a-radio value="ai_only">
              <div class="radio-label">
                <span class="radio-title">{{ tl('纯 AI 探索执行') }}</span>
                <span class="radio-desc">{{ tl('由大模型 Agent 全程操作浏览器探索执行测试步骤。') }}</span>
              </div>
            </a-radio>
          </a-radio-group>
        </a-form-item>

        <!-- 纯 AI 执行时的选项 -->
        <a-form-item v-if="formData.executionMode === 'ai_only'">
          <a-checkbox v-model="formData.generatePlaywrightScript">
            <span class="checkbox-label">
              <span class="checkbox-text">
                <span class="checkbox-title">{{ tl('执行完成后自动生成并绑定 UI 自动化用例') }}</span>
                <span class="checkbox-desc">{{ tl('执行成功后将操作步骤转化为 UI 自动化脚本资产，下次可直接高速运行。') }}</span>
              </span>
            </span>
          </a-checkbox>
        </a-form-item>
      </a-form>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { IconCheckCircle } from '@arco-design/web-vue/es/icon';
import type { TestCase } from '@/services/testcaseService';
import { useAppI18n } from '@/composables/useAppI18n';
import { testCaseApi } from '@/features/ui-automation/api';
import type { UiTestCase } from '@/features/ui-automation/types';
import { extractPaginationData } from '@/features/ui-automation/types';

interface Props {
  visible: boolean;
  testCase: TestCase | null;
}

export interface ExecuteConfirmOptions {
  executionMode: 'hybrid' | 'script_only' | 'ai_only';
  generatePlaywrightScript: boolean;
  uiTestCaseId?: number | null;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'confirm', options: ExecuteConfirmOptions): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();
const { tl } = useAppI18n();

const internalVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const formData = ref<{
  executionMode: 'hybrid' | 'script_only' | 'ai_only';
  generatePlaywrightScript: boolean;
}>({
  executionMode: 'hybrid',
  generatePlaywrightScript: false,
});

const showBindSelect = ref(false);
const selectedUiTestCaseId = ref<number | undefined>(undefined);
const uiTestCases = ref<UiTestCase[]>([]);
const loadingUiCases = ref(false);

const boundUiTestCase = computed(() => {
  if (props.testCase?.ui_test_case_detail) {
    return props.testCase.ui_test_case_detail;
  }
  if (selectedUiTestCaseId.value) {
    const found = uiTestCases.value.find(c => c.id === selectedUiTestCaseId.value);
    if (found) {
      return {
        id: found.id,
        name: found.name,
        level: found.level,
        status: found.status,
        step_count: undefined,
      };
    }
  }
  return null;
});

const hasAvailableUiCase = computed(() => {
  return Boolean(props.testCase?.ui_test_case || selectedUiTestCaseId.value);
});

// 加载当前项目下的 UI 测试用例
const loadProjectUiCases = async () => {
  if (!props.testCase?.project) return;
  loadingUiCases.value = true;
  try {
    const res = await testCaseApi.list({ project: props.testCase.project });
    const { items } = extractPaginationData(res);
    uiTestCases.value = items || [];
  } catch (e) {
    console.error('加载 UI 用例列表失败', e);
  } finally {
    loadingUiCases.value = false;
  }
};

// 重置表单
watch(
  () => props.visible,
  (val) => {
    if (val) {
      const hasBound = Boolean(props.testCase?.ui_test_case);
      formData.value = {
        executionMode: hasBound ? (props.testCase?.execution_mode || 'hybrid') : 'ai_only',
        generatePlaywrightScript: !hasBound,
      };
      selectedUiTestCaseId.value = props.testCase?.ui_test_case || undefined;
      showBindSelect.value = false;
      loadProjectUiCases();
    }
  }
);

watch(
  () => selectedUiTestCaseId.value,
  (val) => {
    if (val && formData.value.executionMode === 'ai_only') {
      formData.value.executionMode = 'hybrid';
    } else if (!val && !props.testCase?.ui_test_case && formData.value.executionMode !== 'ai_only') {
      formData.value.executionMode = 'ai_only';
    }
  }
);

const getLevelColor = (level?: string) => {
  const colors: Record<string, string> = {
    P0: 'red',
    P1: 'orange',
    P2: 'blue',
    P3: 'gray',
  };
  return colors[level || ''] || 'gray';
};

const handleConfirm = () => {
  emit('confirm', {
    executionMode: formData.value.executionMode,
    generatePlaywrightScript: formData.value.generatePlaywrightScript,
    uiTestCaseId: selectedUiTestCaseId.value || props.testCase?.ui_test_case || null,
  });
  internalVisible.value = false;
};

const handleCancel = () => {
  internalVisible.value = false;
};
</script>

<style scoped lang="less">
.execute-modal-content {
  .testcase-info {
    margin-bottom: 14px;
  }

  .bound-ui-info {
    display: flex;
    align-items: center;
    gap: 8px;

    .bound-name {
      font-weight: 500;
      color: var(--color-text-1);
    }
  }

  .unbound-ui-info {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .bind-select-box {
    margin-top: 10px;
    background: var(--color-fill-2);
    padding: 10px 14px 2px 14px;
    border-radius: 6px;
    margin-bottom: 12px;
  }

  .mode-radio-group {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 10px;

    :deep(.arco-radio) {
      align-items: center;
      padding: 10px 12px;
      border: 1px solid var(--color-border-2);
      border-radius: 6px;
      margin-right: 0;
      transition: all 0.2s;

      &.arco-radio-checked {
        border-color: rgb(var(--primary-6));
        background: rgba(var(--primary-1), 0.3);
      }
    }
  }

  .radio-label {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-left: 4px;

    .radio-title {
      font-weight: 600;
      font-size: 14px;
      color: var(--color-text-1);
    }

    .radio-desc {
      font-size: 12px;
      color: var(--color-text-3);
      line-height: 1.4;
    }
  }

  .checkbox-label {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    font-weight: 500;
  }

  .checkbox-text {
    display: flex;
    flex-direction: column;
  }

  .checkbox-title {
    font-weight: 500;
  }

  .checkbox-desc {
    font-size: 12px;
    color: var(--color-text-3);
    margin-top: 4px;
    font-weight: 400;
  }
}
</style>

