<template>
  <a-modal
    v-model:visible="modalVisible"
    title="测试套件管理"
    :width="1200"
    :footer="false"
    :mask-closable="false"
    @cancel="handleClose"
  >
    <div class="suite-list-container">
      <div class="list-header">
        <a-input-search
          v-model="searchKeyword"
          placeholder="搜索套件名称"
          allow-clear
          style="width: 300px;"
          @search="handleSearch"
        />
        <a-space>
          <a-button type="primary" @click="handleCreate">
            <template #icon>
              <icon-plus />
            </template>
            创建测试套件
          </a-button>
          <a-button @click="handleViewExecutions">
            <template #icon>
              <icon-history />
            </template>
            执行历史
          </a-button>
        </a-space>
      </div>

      <a-table
        :columns="columns"
        :data="suiteData"
        :pagination="paginationConfig"
        :loading="loading"
        :scroll="{ y: 500 }"
        :bordered="{ cell: true }"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
      >
        <template #name="{ record }">
          <a-tooltip :content="record.name">
            <span class="suite-name-link" @click="handleViewDetail(record)">
              {{ record.name }}
            </span>
          </a-tooltip>
        </template>
        <template #description="{ record }">
          <a-tooltip v-if="record.description" :content="record.description">
            <div class="description-cell">{{ record.description }}</div>
          </a-tooltip>
          <span v-else>-</span>
        </template>
        <template #testcase_count="{ record }">
          <a-tag color="blue">{{ record.testcase_count }} 个用例</a-tag>
        </template>
        <template #created_at="{ record }">
          {{ formatDate(record.created_at) }}
        </template>
        <template #operations="{ record }">
          <a-space :size="8">
            <a-button type="primary" size="small" @click="handleExecute(record)">
              <template #icon>
                <icon-play-arrow />
              </template>
              执行
            </a-button>
            <a-button type="outline" size="small" @click="handleEdit(record)">
              编辑
            </a-button>
            <a-button
              type="primary"
              status="danger"
              size="small"
              @click="handleDelete(record)"
            >
              删除
            </a-button>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 测试套件表单模态框 -->
    <TestSuiteFormModal
      v-model:visible="showSuiteForm"
      :current-project-id="currentProjectId"
      :suite-id="editingSuiteId"
      :initial-test-case-ids="initialTestCaseIds"
      @success="handleFormSuccess"
    />

    <!-- 执行确认模态框 -->
    <TestExecutionConfirmModal
      v-model:visible="showExecutionConfirm"
      :current-project-id="currentProjectId"
      :suite="selectedSuite"
      @success="handleExecutionSuccess"
    />

    <!-- 执行历史模态框 -->
    <TestExecutionListModal
      v-if="showExecutionList"
      v-model:visible="showExecutionList"
      :current-project-id="currentProjectId"
    />
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { IconPlus, IconPlayArrow, IconHistory } from '@arco-design/web-vue/es/icon';
import {
  getTestSuiteList,
  deleteTestSuite,
  type TestSuite,
} from '@/services/testSuiteService';
import { formatDate } from '@/utils/formatters';
import TestSuiteFormModal from './TestSuiteFormModal.vue';
import TestExecutionConfirmModal from './TestExecutionConfirmModal.vue';
import TestExecutionListModal from './TestExecutionListModal.vue';

interface Props {
  visible: boolean;
  currentProjectId: number | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
});

const loading = ref(false);
const searchKeyword = ref('');
const suiteData = ref<TestSuite[]>([]);
const showSuiteForm = ref(false);
const showExecutionConfirm = ref(false);
const showExecutionList = ref(false);
const editingSuiteId = ref<number | null>(null);
const initialTestCaseIds = ref<number[]>([]);
const selectedSuite = ref<TestSuite | null>(null);

const paginationConfig = reactive({
  total: 0,
  current: 1,
  pageSize: 10,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50],
});

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '套件名称', dataIndex: 'name', slotName: 'name', width: 200, ellipsis: true, tooltip: false },
  { title: '描述', dataIndex: 'description', slotName: 'description', width: 250, ellipsis: true, tooltip: false },
  { title: '用例数量', dataIndex: 'testcase_count', slotName: 'testcase_count', width: 100 },
  {
    title: '创建者',
    dataIndex: 'creator_detail',
    render: ({ record }: { record: TestSuite }) => record.creator_detail?.username || '-',
    width: 100,
  },
  { title: '创建时间', dataIndex: 'created_at', slotName: 'created_at', width: 150 },
  { title: '操作', slotName: 'operations', width: 200, fixed: 'right' as const },
];

// 获取测试套件列表
const fetchSuites = async () => {
  if (!props.currentProjectId) {
    suiteData.value = [];
    paginationConfig.total = 0;
    return;
  }

  loading.value = true;
  try {
    const response = await getTestSuiteList(props.currentProjectId, {
      search: searchKeyword.value,
    });

    if (response.success && response.data) {
      suiteData.value = response.data;
      paginationConfig.total = response.total || response.data.length;
    } else {
      Message.error(response.error || '获取测试套件列表失败');
      suiteData.value = [];
      paginationConfig.total = 0;
    }
  } catch (error) {
    console.error('获取测试套件列表出错:', error);
    Message.error('获取测试套件列表时发生错误');
    suiteData.value = [];
    paginationConfig.total = 0;
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  paginationConfig.current = 1;
  fetchSuites();
};

const onPageChange = (page: number) => {
  paginationConfig.current = page;
  fetchSuites();
};

const onPageSizeChange = (pageSize: number) => {
  paginationConfig.pageSize = pageSize;
  paginationConfig.current = 1;
  fetchSuites();
};

// 创建测试套件
const handleCreate = () => {
  editingSuiteId.value = null;
  initialTestCaseIds.value = [];
  showSuiteForm.value = true;
};

// 编辑测试套件
const handleEdit = (suite: TestSuite) => {
  editingSuiteId.value = suite.id;
  // TODO: 加载套件详情获取test case IDs
  initialTestCaseIds.value = [];
  showSuiteForm.value = true;
};

// 查看详情
const handleViewDetail = (suite: TestSuite) => {
  // TODO: 实现详情查看
  Message.info('详情查看功能开发中');
};

// 执行测试套件
const handleExecute = (suite: TestSuite) => {
  if (suite.testcase_count === 0) {
    Message.warning('该测试套件没有用例，无法执行');
    return;
  }
  selectedSuite.value = suite;
  showExecutionConfirm.value = true;
};

// 删除测试套件
const handleDelete = (suite: TestSuite) => {
  if (!props.currentProjectId) return;

  Modal.warning({
    title: '确认删除',
    content: `确定要删除测试套件 "${suite.name}" 吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await deleteTestSuite(props.currentProjectId!, suite.id);
        if (response.success) {
          Message.success('测试套件删除成功');
          fetchSuites();
        } else {
          Message.error(response.error || '删除测试套件失败');
        }
      } catch (error) {
        Message.error('删除测试套件时发生错误');
      }
    },
  });
};

// 表单提交成功
const handleFormSuccess = () => {
  fetchSuites();
};

// 执行成功
const handleExecutionSuccess = (executionId: number) => {
  Message.success('测试执行已启动');
  // 可以在这里直接打开报告,或者提示用户去历史记录查看
  showExecutionList.value = true;
};

const handleViewExecutions = () => {
  showExecutionList.value = true;
};

const handleClose = () => {
  emit('update:visible', false);
};

watch(
  () => props.visible,
  (newVal) => {
    if (newVal && props.currentProjectId) {
      fetchSuites();
    }
  }
);

onMounted(() => {
  if (props.visible && props.currentProjectId) {
    fetchSuites();
  }
});
</script>

<style scoped>
.suite-list-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.suite-name-link {
  display: inline-block;
  max-width: 180px;
  color: #1890ff;
  cursor: pointer;
  text-decoration: none;
  transition: color 0.2s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.suite-name-link:hover {
  color: #40a9ff;
  text-decoration: underline;
}

.description-cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 230px;
}
</style>