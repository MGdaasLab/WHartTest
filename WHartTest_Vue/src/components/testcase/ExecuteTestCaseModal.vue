<template>
  <a-modal
    v-model:visible="internalVisible"
    title="执行测试用例"
    :width="480"
    @ok="handleConfirm"
    @cancel="handleCancel"
    ok-text="开始执行"
    cancel-text="取消"
  >
    <div class="execute-modal-content">
      <a-descriptions :column="1" bordered size="small" class="testcase-info">
        <a-descriptions-item label="用例名称">
          {{ testCase?.name || '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="用例等级">
          <a-tag :color="getLevelColor(testCase?.level)">
            {{ testCase?.level || '-' }}
          </a-tag>
        </a-descriptions-item>
      </a-descriptions>

      <a-divider orientation="left">执行选项</a-divider>

      <a-form :model="formData" layout="vertical">
        <a-form-item>
          <a-checkbox v-model="formData.generatePlaywrightScript">
            <span class="checkbox-label">
              <span class="checkbox-text">
                <span class="checkbox-title">生成 UI 自动化用例</span>
                <span class="checkbox-desc">注意！！！断言失败或对话异常时，会生成失败。</span>
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
import type { TestCase } from '@/services/testcaseService';

interface Props {
  visible: boolean;
  testCase: TestCase | null;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'confirm', options: { generatePlaywrightScript: boolean }): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const internalVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const formData = ref({
  generatePlaywrightScript: false,
});

// 重置表单
watch(
  () => props.visible,
  (val) => {
    if (val) {
      formData.value = {
        generatePlaywrightScript: false,
      };
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
    generatePlaywrightScript: formData.value.generatePlaywrightScript,
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
    margin-bottom: 16px;
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
