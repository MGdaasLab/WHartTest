<template>
  <div class="testcase-content">
    <div class="page-header">
      <div class="search-box">
        <a-input-search
          placeholder="搜索用例名称/前置条件"
          allow-clear
          style="width: 300px"
          @search="onSearch"
          v-model="localSearchKeyword"
        />
        <a-select
          v-model="selectedLevel"
          placeholder="筛选优先级"
          allow-clear
          style="width: 150px; margin-left: 12px;"
          @change="onLevelChange"
        >
          <a-option value="P0">P0 - 最高</a-option>
          <a-option value="P1">P1 - 高</a-option>
          <a-option value="P2">P2 - 中</a-option>
          <a-option value="P3">P3 - 低</a-option>
        </a-select>
        <a-dropdown @select="handleExportAction" trigger="click" position="bottom">
          <a-button type="outline" style="margin-left: 12px;">
            <template #icon>
              <icon-download />
            </template>
            导出
          </a-button>
          <template #content>
            <a-doption value="exportAll">导出所有用例</a-doption>
            <a-doption value="exportSelected" :disabled="selectedTestCaseIds.length === 0">
              导出选中用例 ({{ selectedTestCaseIds.length }})
            </a-doption>
          </template>
        </a-dropdown>
        <a-button
          v-if="selectedTestCaseIds.length > 0"
          type="primary"
          status="danger"
          style="margin-left: 12px;"
          @click="handleBatchDelete"
        >
          批量删除 ({{ selectedTestCaseIds.length }})
        </a-button>
      </div>
      <div class="action-buttons">
        <a-button type="primary" @click="handleGenerateTestCases" style="margin-right: 10px;">生成用例</a-button>
        <a-button type="primary" @click="handleAddTestCase">添加用例</a-button>
      </div>
    </div>

    <div v-if="!currentProjectId" class="no-project-selected">
      <a-empty description="请在顶部选择一个项目">
        <template #image>
          <icon-folder style="font-size: 48px; color: #c2c7d0;" />
        </template>
      </a-empty>
    </div>

    <a-table
      v-else
      :columns="columns"
      :data="testCaseData"
      :pagination="paginationConfig"
      :loading="loading"
      :scroll="{ x: 1200, y: 800 }"
      :bordered="{ cell: true }"
      class="test-case-table"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"


    >
      <template #selection="{ record }">
        <div data-checkbox>
          <a-checkbox
            :model-value="selectedTestCaseIds.includes(record.id)"
            @change="(checked: boolean) => handleCheckboxChange(record.id, checked)"
            @click.stop
          />
        </div>
      </template>
      <template #selectAll>
        <div data-checkbox>
          <a-checkbox
            :model-value="isCurrentPageAllSelected"
            :indeterminate="isCurrentPageIndeterminate"
            @change="handleSelectCurrentPage"
            @click.stop
          />
        </div>
      </template>
      <template #name="{ record }">
        <a-tooltip :content="record.name">
          <span class="testcase-name-link" @click.stop="handleViewTestCase(record)">
            {{ record.name }}
          </span>
        </a-tooltip>
      </template>
      <template #level="{ record }">
        <a-tag :color="getLevelColor(record.level)">{{ record.level }}</a-tag>
      </template>
      <template #notes="{ record }">
        <a-tooltip v-if="record.notes" :content="record.notes">
          <div class="notes-cell">{{ record.notes }}</div>
        </a-tooltip>
        <span v-else>-</span>
      </template>
      <template #operations="{ record }">
        <a-space :size="10">
          <a-button type="primary" size="mini" @click.stop="handleViewTestCase(record)">查看</a-button>
          <a-button type="primary" size="mini" @click.stop="handleEditTestCase(record)">编辑</a-button>
          <a-button type="outline" size="mini" @click.stop="handleExecuteTestCase(record)">执行</a-button>
          <a-button type="primary" status="danger" size="mini" @click.stop="handleDeleteTestCase(record)">删除</a-button>
        </a-space>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch, toRefs } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import { IconFolder, IconDownload } from '@arco-design/web-vue/es/icon';
import {
  getTestCaseList,
  deleteTestCase as deleteTestCaseService,
  batchDeleteTestCases,
  exportAllTestCasesToExcel,
  exportSelectedTestCasesToExcel,
  type TestCase,
  type BatchDeleteResponse,
} from '@/services/testcaseService';
import { formatDate, getLevelColor } from '@/utils/formatters'; // 假设工具函数已移至此处

const props = defineProps<{
  currentProjectId: number | null;
  selectedModuleId?: number | null; // 可选的模块ID，用于筛选
}>();

const emit = defineEmits<{
  (e: 'addTestCase'): void;
  (e: 'generate-test-cases'): void;
  (e: 'editTestCase', testCase: TestCase): void;
  (e: 'viewTestCase', testCase: TestCase): void;
  (e: 'testCaseDeleted'): void;
  (e: 'executeTestCase', testCase: TestCase): void;
}>();

const { currentProjectId, selectedModuleId } = toRefs(props);

const loading = ref(false);
const localSearchKeyword = ref('');
const selectedLevel = ref<string>('');
const testCaseData = ref<TestCase[]>([]);
const selectedTestCaseIds = ref<number[]>([]);

const paginationConfig = reactive({
  total: 0,
  current: 1,
  pageSize: 10,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50, 100],
});

// 复选框选择相关的计算属性和方法
// 当前页是否全选
const isCurrentPageAllSelected = computed(() => {
  if (testCaseData.value.length === 0) return false;
  return testCaseData.value.every(item => selectedTestCaseIds.value.includes(item.id));
});

// 当前页是否半选状态
const isCurrentPageIndeterminate = computed(() => {
  const currentPageSelectedCount = testCaseData.value.filter(item =>
    selectedTestCaseIds.value.includes(item.id)
  ).length;
  return currentPageSelectedCount > 0 && currentPageSelectedCount < testCaseData.value.length;
});

// 处理单个复选框变化
const handleCheckboxChange = (id: number, checked: boolean) => {
  if (checked) {
    if (!selectedTestCaseIds.value.includes(id)) {
      selectedTestCaseIds.value.push(id);
    }
  } else {
    const index = selectedTestCaseIds.value.indexOf(id);
    if (index > -1) {
      selectedTestCaseIds.value.splice(index, 1);
    }
  }
};

// 处理当前页全选/取消全选
const handleSelectCurrentPage = (checked: boolean) => {
  if (checked) {
    // 选中当前页所有项目
    const currentPageIds = testCaseData.value.map(item => item.id);
    currentPageIds.forEach(id => {
      if (!selectedTestCaseIds.value.includes(id)) {
        selectedTestCaseIds.value.push(id);
      }
    });
  } else {
    // 取消选中当前页所有项目
    const currentPageIds = testCaseData.value.map(item => item.id);
    selectedTestCaseIds.value = selectedTestCaseIds.value.filter(id =>
      !currentPageIds.includes(id)
    );
  }
};

const columns = [
  {
    title: '选择',
    slotName: 'selection',
    width: 40,
    dataIndex: 'selection',
    titleSlotName: 'selectAll',
    align: 'center'
  },
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '用例名称', dataIndex: 'name', slotName: 'name', width: 240, ellipsis: true, tooltip: false },
  { title: '前置条件', dataIndex: 'precondition', width: 150, ellipsis: true, tooltip: true },
  { title: '优先级', dataIndex: 'level', slotName: 'level', width: 75 },
  { title: '备注', dataIndex: 'notes', slotName: 'notes', width: 150, ellipsis: true, tooltip: false }, // tooltip is handled by custom slot
  {
    title: '创建者',
    dataIndex: 'creator_detail',
    render: ({ record }: { record: TestCase }) => record.creator_detail?.username || '-',
    width: 80,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    render: ({ record }: { record: TestCase }) => formatDate(record.created_at),
    width: 150,
  },
  { title: '操作', slotName: 'operations', width: 180, fixed: 'right' },
];

const fetchTestCases = async () => {
  if (!currentProjectId.value) {
    testCaseData.value = [];
    paginationConfig.total = 0;
    selectedTestCaseIds.value = []; // 清空选中状态
    return;
  }
  loading.value = true;
  try {
    const response = await getTestCaseList(currentProjectId.value, {
      page: paginationConfig.current,
      pageSize: paginationConfig.pageSize,
      search: localSearchKeyword.value,
      module_id: selectedModuleId?.value || undefined, // 添加模块ID筛选
      level: selectedLevel.value || undefined, // 添加优先级筛选
    });
    if (response.success && response.data) {
      testCaseData.value = response.data;
      paginationConfig.total = response.total || response.data.length;
      // 清空之前页面的选中状态
      selectedTestCaseIds.value = [];
    } else {
      Message.error(response.error || '获取测试用例列表失败');
      testCaseData.value = [];
      paginationConfig.total = 0;
      selectedTestCaseIds.value = [];
    }
  } catch (error) {
    console.error('获取测试用例列表出错:', error);
    Message.error('获取测试用例列表时发生错误');
    testCaseData.value = [];
    paginationConfig.total = 0;
    selectedTestCaseIds.value = [];
  } finally {
    loading.value = false;
  }
};

const onSearch = (value: string) => {
  localSearchKeyword.value = value;
  paginationConfig.current = 1;
  fetchTestCases();
};

const onLevelChange = (value: string) => {
  selectedLevel.value = value;
  paginationConfig.current = 1;
  fetchTestCases();
};

const onPageChange = (page: number) => {
  paginationConfig.current = page;
  fetchTestCases();
};

const onPageSizeChange = (pageSize: number) => {
  paginationConfig.pageSize = pageSize;
  paginationConfig.current = 1;
  fetchTestCases();
};

const handleAddTestCase = () => {
  if (!currentProjectId.value) {
    Message.warning('请先选择一个项目');
    return;
  }
  emit('addTestCase');
};

const handleGenerateTestCases = () => {
  if (!currentProjectId.value) {
    Message.warning('请先选择一个项目');
    return;
  }
  emit('generate-test-cases');
};

const handleViewTestCase = (testCase: TestCase) => {
  emit('viewTestCase', testCase);
};

const handleEditTestCase = (testCase: TestCase) => {
  emit('editTestCase', testCase);
};

const handleDeleteTestCase = (testCase: TestCase) => {
  if (!currentProjectId.value) return;
  Modal.warning({
    title: '确认删除',
    content: `确定要删除测试用例 "${testCase.name}" 吗？此操作不可恢复。`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await deleteTestCaseService(currentProjectId.value!, testCase.id);
        if (response.success) {
          Message.success('测试用例删除成功');
          fetchTestCases(); // 重新加载列表
          emit('testCaseDeleted');
        } else {
          Message.error(response.error || '删除测试用例失败');
        }
      } catch (error) {
        Message.error('删除测试用例时发生错误');
      }
    },
  });
};

const handleExecuteTestCase = (testCase: TestCase) => {
  emit('executeTestCase', testCase);
};

// 批量删除处理函数
const handleBatchDelete = () => {
  if (!currentProjectId.value || selectedTestCaseIds.value.length === 0) return;

  // 获取选中的测试用例信息用于显示
  const selectedTestCases = testCaseData.value.filter(testCase =>
    selectedTestCaseIds.value.includes(testCase.id)
  );

  const testCaseNames = selectedTestCases.map(tc => tc.name).join('、');
  const displayNames = testCaseNames.length > 100 ?
    testCaseNames.substring(0, 100) + '...' : testCaseNames;

  Modal.warning({
    title: '确认批量删除',
    content: `确定要删除以下 ${selectedTestCaseIds.value.length} 个测试用例吗？此操作不可恢复。\n\n${displayNames}`,
    okText: '确认删除',
    cancelText: '取消',
    width: 500,
    onOk: async () => {
      try {
        const response = await batchDeleteTestCases(currentProjectId.value!, selectedTestCaseIds.value);
        if (response.success && response.data) {
          // 显示详细的删除结果
          const { deleted_count, deleted_testcases, deletion_details } = response.data;

          let detailMessage = `成功删除 ${deleted_count} 个测试用例`;
          if (deletion_details) {
            const details = Object.entries(deletion_details)
              .map(([key, count]) => `${key}: ${count}`)
              .join(', ');
            detailMessage += `\n删除详情: ${details}`;
          }

          Message.success(detailMessage);

          // 清空选中状态并重新加载列表
          selectedTestCaseIds.value = [];
          fetchTestCases();
          emit('testCaseDeleted');
        } else {
          Message.error(response.error || '批量删除测试用例失败');
        }
      } catch (error) {
        console.error('批量删除测试用例出错:', error);
        Message.error('批量删除测试用例时发生错误');
      }
    },
  });
};



// 导出处理函数
const handleExportAction = async (value: string) => {
  if (!currentProjectId.value) {
    Message.warning('请先选择一个项目');
    return;
  }

  try {
    if (value === 'exportAll') {
      // 导出所有用例
      const response = await exportAllTestCasesToExcel(currentProjectId.value);
      if (response.success) {
        Message.success(response.message || '导出成功');
      } else {
        Message.error(response.error || '导出失败');
      }
    } else if (value === 'exportSelected') {
      // 导出选中用例
      if (selectedTestCaseIds.value.length === 0) {
        Message.warning('请先选择要导出的用例');
        return;
      }
      const response = await exportSelectedTestCasesToExcel(currentProjectId.value, selectedTestCaseIds.value);
      if (response.success) {
        Message.success(response.message || '导出成功');
      } else {
        Message.error(response.error || '导出失败');
      }
    }
  } catch (error) {
    console.error('导出用例出错:', error);
    Message.error('导出用例时发生错误');
  }
};

onMounted(() => {
  fetchTestCases();
});

watch(currentProjectId, () => {
  paginationConfig.current = 1;
  localSearchKeyword.value = '';
  selectedLevel.value = ''; // 项目切换时清空优先级筛选
  fetchTestCases();
});

watch(selectedModuleId, () => {
  paginationConfig.current = 1; // 模块切换时重置到第一页
  selectedLevel.value = ''; // 模块变化时清空优先级筛选
  fetchTestCases();
});

// 暴露给父组件的方法
defineExpose({
  refreshTestCases: fetchTestCases,
});

</script>

<style scoped>
.testcase-content {
  flex: 1;
  background-color: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative; /* 添加相对定位，为分页器的绝对定位提供参考 */
  padding-bottom: 90px; /* 增加底部内边距，为分页器预留空间 */
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.no-project-selected {
  display: flex;
  justify-content: center;
  align-items: center;
  height: calc(100% - 60px); /* 减去头部高度 */
  flex-grow: 1;
}

.test-case-table {
  flex-grow: 1;
  overflow: hidden;
  height: 0;
  display: flex;
  flex-direction: column;
  min-height: 0; /* Allow shrinking for nested flex container */
  max-height: calc(100% - 90px); /* 增加留给分页器的空间 */
}
.notes-cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.test-case-table .arco-table-td) {
  white-space: nowrap;
}

:deep(.test-case-table .arco-table-container) {
  height: 100% !important;
  display: flex;
  flex-direction: column;
}

:deep(.test-case-table .arco-table-header) {
  flex-shrink: 0;
}

:deep(.test-case-table .arco-table-body) {
  flex: 1;
  overflow-y: auto !important;
  min-height: 0;
}

:deep(.test-case-table .arco-pagination) {
  flex-shrink: 0;
  margin-top: 8px;
  display: flex; /* 将分页栏设置为flex容器 */
  flex-wrap: wrap; /* 允许内部元素换行 */
  justify-content: flex-end; /* 元素换行后整体靠右对齐，可根据需要调整为 center 或 flex-start */
  align-items: center; /* 垂直居中对齐换行的元素 */
  gap: 8px; /* 为换行的元素之间添加一些间隙 */
  position: sticky;
  bottom: 0;
  background-color: #fff;
  z-index: 1;
}

/* 确保操作列按钮不会溢出 */
:deep(.test-case-table .arco-table-cell-fixed-right) {
  padding: 8px 4px;
}

:deep(.test-case-table .arco-space-compact) {
  display: flex;
  flex-wrap: nowrap;
}

:deep(.test-case-table .arco-btn-size-mini) {
  padding: 0 8px;
  font-size: 12px;
  min-width: 40px;
}

/* 勾选框居中显示 */
:deep(.test-case-table [data-checkbox]) {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
}

/* 用例名称链接样式 */
.testcase-name-link {
  display: inline-block;
  max-width: 220px;
  color: #1890ff;
  cursor: pointer;
  text-decoration: none;
  transition: color 0.2s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.testcase-name-link:hover {
  color: #40a9ff;
  text-decoration: underline;
}

/* 移除重复的样式定义 */
</style>
