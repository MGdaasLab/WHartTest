<template>
  <div class="testcase-selector">
    <div class="selector-header">
      <a-input-search
        v-model="searchKeyword"
        placeholder="搜索用例名称"
        allow-clear
        style="width: 300px;"
        @search="handleSearch"
      />
      <a-select
        v-model="selectedLevel"
        placeholder="筛选优先级"
        allow-clear
        style="width: 150px; margin-left: 12px;"
        @change="handleLevelChange"
      >
        <a-option value="P0">P0 - 最高</a-option>
        <a-option value="P1">P1 - 高</a-option>
        <a-option value="P2">P2 - 中</a-option>
        <a-option value="P3">P3 - 低</a-option>
      </a-select>
    </div>

    <a-table
      :columns="columns"
      :data="testCaseData"
      :pagination="paginationConfig"
      :loading="loading"
      :scroll="{ y: 400 }"
      :bordered="{ cell: true }"
      row-key="id"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
    >
      <template #selection="{ record }">
        <a-checkbox
          :model-value="localSelectedIds.includes(record.id)"
          @change="(checked: boolean) => handleCheckboxChange(record.id, checked)"
        />
      </template>
      <template #selectAll>
        <a-checkbox
          :model-value="isCurrentPageAllSelected"
          :indeterminate="isCurrentPageIndeterminate"
          @change="handleSelectCurrentPage"
        />
      </template>
      <template #level="{ record }">
        <a-tag :color="getLevelColor(record.level)">{{ record.level }}</a-tag>
      </template>
    </a-table>

    <div class="selector-footer">
      <div class="selected-info">
        已选择 <strong>{{ localSelectedIds.length }}</strong> 个测试用例
      </div>
      <a-space>
        <a-button @click="handleCancel">取消</a-button>
        <a-button
          type="primary"
          :disabled="localSelectedIds.length === 0"
          @click="handleConfirm"
        >
          确认选择
        </a-button>
      </a-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { getTestCaseList, type TestCase } from '@/services/testcaseService';
import { formatDate, getLevelColor } from '@/utils/formatters';

interface Props {
  currentProjectId: number | null;
  initialSelectedIds?: number[];
}

const props = withDefaults(defineProps<Props>(), {
  initialSelectedIds: () => [],
});

const emit = defineEmits<{
  (e: 'confirm', selectedIds: number[]): void;
  (e: 'cancel'): void;
}>();

const loading = ref(false);
const searchKeyword = ref('');
const selectedLevel = ref<string>('');
const testCaseData = ref<TestCase[]>([]);
const localSelectedIds = ref<number[]>([...props.initialSelectedIds]);

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
  {
    title: '选择',
    slotName: 'selection',
    width: 50,
    titleSlotName: 'selectAll',
    align: 'center' as const,
  },
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '用例名称', dataIndex: 'name', width: 200, ellipsis: true, tooltip: true },
  { title: '前置条件', dataIndex: 'precondition', width: 150, ellipsis: true, tooltip: true },
  { title: '优先级', dataIndex: 'level', slotName: 'level', width: 80 },
  {
    title: '创建者',
    dataIndex: 'creator_detail',
    render: ({ record }: { record: TestCase }) => record.creator_detail?.username || '-',
    width: 100,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    render: ({ record }: { record: TestCase }) => formatDate(record.created_at),
    width: 150,
  },
];

// 当前页是否全选
const isCurrentPageAllSelected = computed(() => {
  if (testCaseData.value.length === 0) return false;
  return testCaseData.value.every((item) => localSelectedIds.value.includes(item.id));
});

// 当前页是否半选状态
const isCurrentPageIndeterminate = computed(() => {
  const currentPageSelectedCount = testCaseData.value.filter((item) =>
    localSelectedIds.value.includes(item.id)
  ).length;
  return currentPageSelectedCount > 0 && currentPageSelectedCount < testCaseData.value.length;
});

// 处理单个复选框变化
const handleCheckboxChange = (id: number, checked: boolean) => {
  if (checked) {
    if (!localSelectedIds.value.includes(id)) {
      localSelectedIds.value.push(id);
    }
  } else {
    const index = localSelectedIds.value.indexOf(id);
    if (index > -1) {
      localSelectedIds.value.splice(index, 1);
    }
  }
};

// 处理当前页全选/取消全选
const handleSelectCurrentPage = (checked: boolean) => {
  if (checked) {
    const currentPageIds = testCaseData.value.map((item) => item.id);
    currentPageIds.forEach((id) => {
      if (!localSelectedIds.value.includes(id)) {
        localSelectedIds.value.push(id);
      }
    });
  } else {
    const currentPageIds = testCaseData.value.map((item) => item.id);
    localSelectedIds.value = localSelectedIds.value.filter((id) => !currentPageIds.includes(id));
  }
};

// 获取测试用例列表
const fetchTestCases = async () => {
  if (!props.currentProjectId) {
    testCaseData.value = [];
    paginationConfig.total = 0;
    return;
  }

  loading.value = true;
  try {
    const response = await getTestCaseList(props.currentProjectId, {
      page: paginationConfig.current,
      pageSize: paginationConfig.pageSize,
      search: searchKeyword.value,
      level: selectedLevel.value || undefined,
    });

    if (response.success && response.data) {
      testCaseData.value = response.data;
      paginationConfig.total = response.total || response.data.length;
    } else {
      Message.error(response.error || '获取测试用例列表失败');
      testCaseData.value = [];
      paginationConfig.total = 0;
    }
  } catch (error) {
    console.error('获取测试用例列表出错:', error);
    Message.error('获取测试用例列表时发生错误');
    testCaseData.value = [];
    paginationConfig.total = 0;
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  paginationConfig.current = 1;
  fetchTestCases();
};

const handleLevelChange = () => {
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

const handleConfirm = () => {
  emit('confirm', [...localSelectedIds.value]);
};

const handleCancel = () => {
  emit('cancel');
};

onMounted(() => {
  fetchTestCases();
});

watch(
  () => props.currentProjectId,
  () => {
    paginationConfig.current = 1;
    searchKeyword.value = '';
    selectedLevel.value = '';
    fetchTestCases();
  }
);
</script>

<style scoped>
.testcase-selector {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.selector-header {
  display: flex;
  align-items: center;
}

.selector-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}

.selected-info {
  font-size: 14px;
  color: var(--color-text-2);
}
</style>