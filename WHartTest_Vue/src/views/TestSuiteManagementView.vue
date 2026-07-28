<template>
  <div class="test-suite-management-view">
    <div v-if="!currentProjectId" class="no-project-selected">
      <a-empty :description="pageText.noProjectSelected">
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
            :placeholder="pageText.searchPlaceholder"
            allow-clear
            style="width: 300px;"
            @search="handleSearch"
            @clear="handleSearch"
          />
          <a-button type="primary" @click="handleCreate" style="margin-left: 12px">
            <template #icon>
              <icon-plus />
            </template>
            {{ pageText.createSuite }}
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
          <a-tag color="blue">{{ formatCaseCount(record.testcase_count) }}</a-tag>
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
              {{ pageText.execute }}
            </a-button>
            <a-button type="outline" size="small" @click="handleEdit(record)">
              {{ pageText.edit }}
            </a-button>
            <a-button
              type="primary"
              status="danger"
              size="small"
              @click="handleDelete(record)"
            >
              {{ pageText.delete }}
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
import { useAppI18n } from '@/composables/useAppI18n';
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
const { isEnglish } = useAppI18n();
const currentProjectId = computed(() => projectStore.currentProjectId);

const pageText = computed(() => (
  isEnglish.value
    ? {
        noProjectSelected: 'Select a project from the top bar',
        searchPlaceholder: 'Search suite name',
        createSuite: 'Create suite',
        execute: 'Run',
        edit: 'Edit',
        delete: 'Delete',
        caseUnit: 'cases',
        suiteName: 'Suite name',
        description: 'Description',
        testContent: 'Test content',
        creator: 'Created by',
        createdAt: 'Created at',
        actions: 'Actions',
        fetchListFailed: 'Failed to fetch test suites',
        fetchListError: 'An error occurred while fetching test suites',
        suiteWithoutCases: 'This test suite has no cases and cannot be run',
        confirmDeleteTitle: 'Confirm deletion',
        confirmDeleteContent: (name: string) => `Delete test suite "${name}"? This action cannot be undone.`,
        deleteSuiteSuccess: 'Test suite deleted successfully',
        deleteSuiteFailed: 'Failed to delete test suite',
        deleteSuiteError: 'An error occurred while deleting the test suite',
        executionStarted: 'Test execution started',
      }
    : {
        noProjectSelected: '请在顶部选择一个项目',
        searchPlaceholder: '搜索套件名称',
        createSuite: '创建测试套件',
        execute: '执行',
        edit: '编辑',
        delete: '删除',
        caseUnit: '用例',
        suiteName: '套件名称',
        description: '描述',
        testContent: '测试内容',
        creator: '创建者',
        createdAt: '创建时间',
        actions: '操作',
        fetchListFailed: '获取测试套件列表失败',
        fetchListError: '获取测试套件列表时发生错误',
        suiteWithoutCases: '该测试套件没有用例，无法执行',
        confirmDeleteTitle: '确认删除',
        confirmDeleteContent: (name: string) => `确定要删除测试套件 "${name}" 吗？此操作不可恢复。`,
        deleteSuiteSuccess: '测试套件删除成功',
        deleteSuiteFailed: '删除测试套件失败',
        deleteSuiteError: '删除测试套件时发生错误',
        executionStarted: '测试执行已启动',
      }
));

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

const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', width: 60, align: 'center' as const },
  { title: pageText.value.suiteName, dataIndex: 'name', slotName: 'name', width: 220, ellipsis: true, tooltip: false, align: 'center' as const },
  { title: pageText.value.description, dataIndex: 'description', slotName: 'description', width: 180, ellipsis: true, tooltip: false, align: 'center' as const },
  { title: pageText.value.testContent, dataIndex: 'testcase_count', slotName: 'testcase_count', width: 160, align: 'center' as const },
  {
    title: pageText.value.creator,
    dataIndex: 'creator_detail',
    render: ({ record }: { record: TestSuite }) => record.creator_detail?.username || '-',
    width: 100,
    align: 'center' as const,
  },
  { title: pageText.value.createdAt, dataIndex: 'created_at', slotName: 'created_at', width: 180, align: 'center' as const },
  { title: pageText.value.actions, slotName: 'operations', width: 280, fixed: 'right' as const, align: 'center' as const },
]);

const formatCaseCount = (count: number) => (
  isEnglish.value ? `${count} ${count === 1 ? 'case' : pageText.value.caseUnit}` : `${count} ${pageText.value.caseUnit}`
);

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
      Message.error(response.error || pageText.value.fetchListFailed);
      suiteData.value = [];
      paginationConfig.total = 0;
    }
  } catch (error) {
    console.error('获取测试套件列表出错:', error);
    Message.error(pageText.value.fetchListError);
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
  if ((suite.testcase_count || 0) === 0) {
    Message.warning(pageText.value.suiteWithoutCases);
    return;
  }
  selectedSuite.value = suite;
  showExecutionConfirm.value = true;
};

// 删除测试套件
const handleDelete = (suite: TestSuite) => {
  if (!currentProjectId.value) return;

  Modal.warning({
    title: pageText.value.confirmDeleteTitle,
    content: pageText.value.confirmDeleteContent(suite.name),
    onOk: async () => {
      try {
        const response = await deleteTestSuite(currentProjectId.value!, suite.id);
        if (response.success) {
          Message.success(pageText.value.deleteSuiteSuccess);
          fetchSuites();
        } else {
          Message.error(response.error || pageText.value.deleteSuiteFailed);
        }
      } catch (error) {
        Message.error(pageText.value.deleteSuiteError);
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
  Message.success(pageText.value.executionStarted);
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
  background: var(--color-bg-2, white);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.filter-section {
  margin-bottom: 16px;
  padding: 16px 24px;
  background: var(--color-bg-2, white);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.content-section {
  background: var(--color-bg-2, white);
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
