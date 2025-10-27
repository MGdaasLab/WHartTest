<template>
  <div class="test-suite-management-view">
    <div v-if="!currentProjectId" class="no-project-selected">
      <a-empty description="请在顶部选择一个项目">
        <template #image>
          <icon-folder style="font-size: 48px; color: #c2c7d0;" />
        </template>
      </a-empty>
    </div>

    <div v-else>
      <!-- 搜索和筛选区域 -->
      <div class="filter-section">
        <div class="filter-row">
          <a-input-search
            v-model="searchKeyword"
            placeholder="搜索套件名称"
            allow-clear
            style="width: 300px;"
            @search="handleSearch"
            @clear="handleSearch"
          />
          <a-button type="primary" @click="handleCreate" style="margin-left: 12px">
            <template #icon>
              <icon-plus />
            </template>
            创建测试套件
          </a-button>
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="content-section">
        <a-table
          :columns="columns"
          :data="suiteData"
          :pagination="paginationConfig"
          :loading="loading"
          :bordered="{ cell: true }"
          @page-change="onPageChange"
          @page-size-change="onPageSizeChange"
          row-key="id"
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

    <!-- 测试套件详情模态框 -->
    <TestSuiteDetailModal
      v-model:visible="showDetailModal"
      :current-project-id="currentProjectId"
      :suite-id="viewingSuiteId"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { IconPlus, IconPlayArrow, IconFolder } from '@arco-design/web-vue/es/icon';
import { useProjectStore } from '@/store/projectStore';
import {
  getTestSuiteList,
  deleteTestSuite,
  type TestSuite,
} from '@/services/testSuiteService';
import { formatDate } from '@/utils/formatters';
import TestSuiteFormModal from '@/components/testcase/TestSuiteFormModal.vue';
import TestExecutionConfirmModal from '@/components/testcase/TestExecutionConfirmModal.vue';
import TestSuiteDetailModal from '@/components/testcase/TestSuiteDetailModal.vue';

const projectStore = useProjectStore();
const currentProjectId = computed(() => projectStore.currentProjectId);

const loading = ref(false);
const searchKeyword = ref('');
const suiteData = ref<TestSuite[]>([]);
const showSuiteForm = ref(false);
const showExecutionConfirm = ref(false);
const showDetailModal = ref(false);
const editingSuiteId = ref<number | null>(null);
const initialTestCaseIds = ref<number[]>([]);
const selectedSuite = ref<TestSuite | null>(null);
const viewingSuiteId = ref<number | null>(null);

const paginationConfig = reactive({
  total: 0,
  current: 1,
  pageSize: 10,
  showTotal: true,
  showPageSize: true,
});

const columns = [
  { title: 'ID', dataIndex: 'id', width: 60, align: 'center' as const },
  { title: '套件名称', dataIndex: 'name', slotName: 'name', width: 250, ellipsis: true, tooltip: false, align: 'center' as const },
  { title: '描述', dataIndex: 'description', slotName: 'description', width: 200, ellipsis: true, tooltip: false, align: 'center' as const },
  { title: '用例数量', dataIndex: 'testcase_count', slotName: 'testcase_count', width: 100, align: 'center' as const },
  {
    title: '创建者',
    dataIndex: 'creator_detail',
    render: ({ record }: { record: TestSuite }) => record.creator_detail?.username || '-',
    width: 120,
    align: 'center' as const,
  },
  { title: '创建时间', dataIndex: 'created_at', slotName: 'created_at', width: 160, align: 'center' as const },
  { title: '操作', slotName: 'operations', width: 250, fixed: 'right' as const, align: 'center' as const },
];

// 获取测试套件列表
const fetchSuites = async () => {
  if (!currentProjectId.value) {
    suiteData.value = [];
    paginationConfig.total = 0;
    return;
  }

  loading.value = true;
  try {
    const response = await getTestSuiteList(currentProjectId.value, {
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
  initialTestCaseIds.value = [];
  showSuiteForm.value = true;
};

// 查看详情
const handleViewDetail = (suite: TestSuite) => {
  viewingSuiteId.value = suite.id;
  showDetailModal.value = true;
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
  if (!currentProjectId.value) return;

  Modal.warning({
    title: '确认删除',
    content: `确定要删除测试套件 "${suite.name}" 吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await deleteTestSuite(currentProjectId.value!, suite.id);
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
};

watch(currentProjectId, () => {
  paginationConfig.current = 1;
  searchKeyword.value = '';
  fetchSuites();
});

onMounted(() => {
  if (currentProjectId.value) {
    fetchSuites();
  }
});
</script>

<style scoped>
.test-suite-management-view {
  padding: 24px;
  background: transparent;
  min-height: 100%;
}

.no-project-selected {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.filter-section {
  margin-bottom: 16px;
  padding: 16px 24px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.content-section {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.suite-name-link {
  display: inline-block;
  max-width: 230px;
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
  max-width: 180px;
}
</style>