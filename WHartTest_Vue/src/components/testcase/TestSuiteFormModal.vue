<template>
  <a-modal
    v-model:visible="modalVisible"
    :title="isEditing ? '编辑测试套件' : '创建测试套件'"
    :width="800"
    :mask-closable="false"
    @before-ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form :model="formData" :rules="rules" ref="formRef" layout="vertical">
      <a-form-item label="套件名称" field="name" required>
        <a-input
          v-model="formData.name"
          placeholder="请输入测试套件名称"
          :max-length="100"
          show-word-limit
        />
      </a-form-item>

      <a-form-item label="套件描述" field="description">
        <a-textarea
          v-model="formData.description"
          placeholder="请输入套件描述(可选)"
          :max-length="500"
          :auto-size="{ minRows: 3, maxRows: 6 }"
          show-word-limit
        />
      </a-form-item>

      <a-form-item label="并发执行数" field="max_concurrent_tasks" required>
        <a-input-number
          v-model="formData.max_concurrent_tasks"
          :min="1"
          :max="10"
          :default-value="1"
          :style="{ width: '200px' }"
        />
        <div class="field-hint">
          <icon-info-circle style="margin-right: 4px;" />
          设置同时执行的测试用例数量。1表示串行执行，2-10表示并发执行。建议根据系统资源设置为2-5。
        </div>
      </a-form-item>

      <a-form-item label="选择测试用例" field="testcase_ids" required>
        <div class="testcase-selection">
          <a-space direction="vertical" style="width: 100%;">
            <a-alert v-if="selectedTestCaseIds.length > 0" type="info">
              已选择 <strong>{{ selectedTestCaseIds.length }}</strong> 个测试用例
            </a-alert>
            <a-alert v-else type="warning">
              请至少选择一个测试用例
            </a-alert>

            <a-button
              type="outline"
              @click="showTestCaseSelector = true"
              style="width: 100%;"
            >
              <template #icon>
                <icon-plus />
              </template>
              {{ selectedTestCaseIds.length > 0 ? '重新选择测试用例' : '选择测试用例' }}
            </a-button>

            <!-- 已选择的用例列表 -->
            <div v-if="selectedTestCases.length > 0" class="selected-testcases">
              <div class="testcase-list-header">
                <span>已选择的测试用例:</span>
                <a-button
                  type="text"
                  size="small"
                  status="danger"
                  @click="handleClearSelection"
                >
                  清空
                </a-button>
              </div>
              <a-list :max-height="300" :scrollbar="true">
                <a-list-item
                  v-for="testcase in selectedTestCases"
                  :key="testcase.id"
                  class="testcase-item"
                >
                  <a-list-item-meta
                    :title="testcase.name"
                    :description="`优先级: ${testcase.level} | 创建者: ${testcase.creator_detail?.username}`"
                  />
                  <template #actions>
                    <a-button
                      type="text"
                      size="small"
                      status="danger"
                      @click="handleRemoveTestCase(testcase.id)"
                    >
                      <icon-close />
                    </a-button>
                  </template>
                </a-list-item>
              </a-list>
            </div>
          </a-space>
        </div>
      </a-form-item>
    </a-form>

    <!-- 测试用例选择器模态框 -->
    <a-modal
      v-model:visible="showTestCaseSelector"
      title="选择测试用例"
      :width="1000"
      :footer="false"
      :mask-closable="false"
    >
      <TestCaseSelectorTable
        :current-project-id="currentProjectId"
        :initial-selected-ids="selectedTestCaseIds"
        @confirm="handleTestCaseSelect"
        @cancel="showTestCaseSelector = false"
      />
    </a-modal>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconPlus, IconClose, IconInfoCircle } from '@arco-design/web-vue/es/icon';
import {
  createTestSuite,
  updateTestSuite,
  getTestSuiteDetail,
  type CreateTestSuiteRequest,
} from '@/services/testSuiteService';
import { getTestCaseDetail, type TestCase } from '@/services/testcaseService';
import TestCaseSelectorTable from './TestCaseSelectorTable.vue';

interface Props {
  visible: boolean;
  currentProjectId: number | null;
  suiteId?: number | null;
  initialTestCaseIds?: number[];
}

const props = withDefaults(defineProps<Props>(), {
  suiteId: null,
  initialTestCaseIds: () => [],
});

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'success'): void;
}>();

const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
});

const isEditing = computed(() => !!props.suiteId);

const formRef = ref();
const showTestCaseSelector = ref(false);
const selectedTestCaseIds = ref<number[]>([]);
const selectedTestCases = ref<TestCase[]>([]);
const loading = ref(false);

const formData = ref<CreateTestSuiteRequest>({
  name: '',
  description: '',
  testcase_ids: [],
  max_concurrent_tasks: 1,
});

const rules = {
  name: [
    { required: true, message: '请输入套件名称' },
    { minLength: 2, message: '套件名称至少2个字符' },
  ],
  max_concurrent_tasks: [
    { required: true, message: '请设置并发执行数' },
    {
      type: 'number',
      min: 1,
      max: 10,
      message: '并发数必须在1-10之间',
    },
  ],
  testcase_ids: [
    {
      required: true,
      validator: (value: any, callback: any) => {
        if (selectedTestCaseIds.value.length === 0) {
          callback('请至少选择一个测试用例');
        } else {
          callback();
        }
      },
    },
  ],
};

// 加载已选择的测试用例详情
const loadSelectedTestCases = async () => {
  if (!props.currentProjectId || selectedTestCaseIds.value.length === 0) {
    selectedTestCases.value = [];
    return;
  }

  try {
    const promises = selectedTestCaseIds.value.map((id) =>
      getTestCaseDetail(props.currentProjectId!, id)
    );
    const responses = await Promise.all(promises);
    selectedTestCases.value = responses
      .filter((r) => r.success && r.data)
      .map((r) => r.data!);
  } catch (error) {
    console.error('加载测试用例详情失败:', error);
  }
};

// 处理测试用例选择
const handleTestCaseSelect = (testcaseIds: number[]) => {
  selectedTestCaseIds.value = testcaseIds;
  loadSelectedTestCases();
  showTestCaseSelector.value = false;
};

// 移除单个测试用例
const handleRemoveTestCase = (id: number) => {
  selectedTestCaseIds.value = selectedTestCaseIds.value.filter((tcId) => tcId !== id);
  selectedTestCases.value = selectedTestCases.value.filter((tc) => tc.id !== id);
};

// 清空选择
const handleClearSelection = () => {
  selectedTestCaseIds.value = [];
  selectedTestCases.value = [];
};

// 提交表单
const handleSubmit = async () => {
  if (!props.currentProjectId) {
    Message.error('缺少项目ID');
    return false;
  }

  try {
    await formRef.value?.validate();

    loading.value = true;
    formData.value.testcase_ids = selectedTestCaseIds.value;

    const response = isEditing.value
      ? await updateTestSuite(props.currentProjectId, props.suiteId!, formData.value)
      : await createTestSuite(props.currentProjectId, formData.value);

    if (response.success) {
      Message.success(response.message || (isEditing.value ? '更新成功' : '创建成功'));
      emit('success');
      handleCancel();
      return true;
    } else {
      Message.error(response.error || '操作失败');
      return false;
    }
  } catch (error) {
    console.error('提交表单失败:', error);
    return false;
  } finally {
    loading.value = false;
  }
};

// 取消
const handleCancel = () => {
  formRef.value?.resetFields();
  selectedTestCaseIds.value = [];
  selectedTestCases.value = [];
  emit('update:visible', false);
};

// 加载套件详情
const loadSuiteDetail = async () => {
  if (!props.currentProjectId || !props.suiteId) {
    return;
  }

  loading.value = true;
  try {
    const response = await getTestSuiteDetail(props.currentProjectId, props.suiteId);
    
    if (response.success && response.data) {
      const suite = response.data;
      
      // 填充表单数据
      formData.value.name = suite.name;
      formData.value.description = suite.description || '';
      formData.value.max_concurrent_tasks = suite.max_concurrent_tasks || 1;
      
      // 获取用例ID列表
      if (suite.testcases_detail && suite.testcases_detail.length > 0) {
        selectedTestCaseIds.value = suite.testcases_detail.map((tc) => tc.id);
        selectedTestCases.value = [...suite.testcases_detail];
      }
    } else {
      Message.error(response.error || '加载套件详情失败');
    }
  } catch (error) {
    console.error('加载套件详情失败:', error);
    Message.error('加载套件详情时发生错误');
  } finally {
    loading.value = false;
  }
};

// 监听visible变化，初始化数据
watch(
  () => props.visible,
  async (newVal) => {
    if (newVal) {
      // 如果是编辑模式，加载套件数据
      if (isEditing.value && props.suiteId) {
        await loadSuiteDetail();
      } else {
        // 创建模式，初始化选中的测试用例
        selectedTestCaseIds.value = [...props.initialTestCaseIds];
        loadSelectedTestCases();
      }
    }
  }
);
</script>

<style scoped>
.testcase-selection {
  width: 100%;
}

.selected-testcases {
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 12px;
}

.testcase-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 500;
}

.testcase-item {
  padding: 8px 0;
}

.testcase-item:not(:last-child) {
  border-bottom: 1px solid var(--color-border-1);
}

.field-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-text-3);
  display: flex;
  align-items: flex-start;
  line-height: 1.5;
}
</style>