<template>
  <a-modal
    v-model:visible="modalVisible"
    title="确认执行测试套件"
    :width="600"
    :mask-closable="false"
    @before-ok="handleConfirm"
    @cancel="handleCancel"
  >
    <div class="execution-confirm-content">
      <a-alert type="info" style="margin-bottom: 16px;">
        <template #icon>
          <icon-info-circle />
        </template>
        测试将在后台异步执行,您可以在执行历史中查看进度
      </a-alert>

      <a-descriptions :column="1" bordered>
        <a-descriptions-item label="测试套件">
          <strong>{{ suite?.name }}</strong>
        </a-descriptions-item>
        <a-descriptions-item label="套件描述">
          {{ suite?.description || '-' }}
        </a-descriptions-item>
        <a-descriptions-item label="用例数量">
          <a-tag color="blue">{{ suite?.testcase_count }} 个用例</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="预计耗时">
          <a-tag color="orange">约 {{ estimatedTime }} 分钟</a-tag>
        </a-descriptions-item>
      </a-descriptions>

      <a-alert type="warning" style="margin-top: 16px;">
        <template #icon>
          <icon-exclamation-circle />
        </template>
        <div>
          <p style="margin-bottom: 8px;">执行注意事项:</p>
          <ul style="margin: 0; padding-left: 20px;">
            <li>测试执行期间会占用系统资源</li>
            <li>执行过程中可以随时取消</li>
            <li>每个用例的执行结果和截图将被记录</li>
          </ul>
        </div>
      </a-alert>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconInfoCircle, IconExclamationCircle } from '@arco-design/web-vue/es/icon';
import { createTestExecution } from '@/services/testExecutionService';
import type { TestSuite } from '@/services/testSuiteService';

interface Props {
  visible: boolean;
  currentProjectId: number | null;
  suite: TestSuite | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'success', executionId: number): void;
}>();

const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
});

const loading = ref(false);

// 预估执行时间 (每个用例约30秒)
const estimatedTime = computed(() => {
  if (!props.suite) return 0;
  const minutes = Math.ceil((props.suite.testcase_count * 30) / 60);
  return minutes;
});

// 确认执行
const handleConfirm = async () => {
  if (!props.currentProjectId || !props.suite) {
    Message.error('缺少必要信息');
    return false;
  }

  loading.value = true;
  try {
    const response = await createTestExecution(props.currentProjectId, {
      suite_id: props.suite.id,
    });

    if (response.success && response.data) {
      Message.success(response.message || '测试执行已启动');
      emit('success', response.data.id);
      handleCancel();
      return true;
    } else {
      Message.error(response.error || '启动执行失败');
      return false;
    }
  } catch (error) {
    console.error('启动执行失败:', error);
    Message.error('启动执行时发生错误');
    return false;
  } finally {
    loading.value = false;
  }
};

// 取消
const handleCancel = () => {
  emit('update:visible', false);
};
</script>

<style scoped>
.execution-confirm-content {
  padding: 8px 0;
}
</style>