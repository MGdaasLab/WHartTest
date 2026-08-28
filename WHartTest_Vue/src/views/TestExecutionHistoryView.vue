<template>
  <div class="test-execution-history-view">
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
          <a-input
            v-model="searchKeyword"
            :placeholder="pageText.searchPlaceholder"
            allow-clear
            style="width: 300px;"
            @change="handleSearch"
          >
            <template #prefix>
              <icon-search />
            </template>
          </a-input>
          
          <a-select
            v-model="statusFilter"
            :placeholder="pageText.filterStatusPlaceholder"
            style="width: 150px;"
            allow-clear
            @change="handleSearch"
          >
            <a-option
              v-for="option in statusOptions"
              :key="option.value || 'all'"
              :value="option.value"
            >
              {{ option.label }}
            </a-option>
          </a-select>

          <a-button @click="handleRefresh" style="margin-left: 12px">
            <template #icon>
              <icon-refresh />
            </template>
            {{ pageText.refresh }}
          </a-button>
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="content-section">
        <a-table
          :data="executionData"
          :loading="loading"
          :pagination="paginationConfig"
          @page-change="handlePageChange"
          @page-size-change="handlePageSizeChange"
          :columns="columns"
          :bordered="{ cell: true }"
          row-key="id"
          stripe
        >
        <!-- 套件名称 -->
        <template #suite="{ record }">
          <a-tooltip :content="record.suite_detail?.description || pageText.noDescription">
            <span class="suite-name">{{ record.suite_detail?.name || '-' }}</span>
          </a-tooltip>
        </template>

        <!-- 状态 -->
        <template #status="{ record }">
          <a-tag :color="getStatusColor(record.status)">
            {{ getStatusText(record.status) }}
          </a-tag>
        </template>

        <!-- 统计 -->
        <template #statistics="{ record }">
          <div class="statistics">
            <a-tag color="blue">{{ pageText.total }}: {{ record.total_count }}</a-tag>
            <a-tag color="green">{{ pageText.passed }}: {{ record.passed_count }}</a-tag>
            <a-tag v-if="record.failed_count > 0" color="red">{{ pageText.failed }}: {{ record.failed_count }}</a-tag>
            <a-tag v-if="record.error_count > 0" color="orange">{{ pageText.error }}: {{ record.error_count }}</a-tag>
          </div>
        </template>

        <!-- 通过率 -->
        <template #pass-rate="{ record }">
          <div class="pass-rate">
            <a-progress
              :percent="record.pass_rate"
              :color="getPassRateColor(record.pass_rate)"
              :show-text="false"
              size="small"
            />
            <span class="rate-text">{{ record.pass_rate.toFixed(1) }}%</span>
          </div>
        </template>

        <!-- 执行时长 -->
        <template #duration="{ record }">
          <span v-if="record.duration">{{ formatDuration(record.duration) }}</span>
          <span v-else>-</span>
        </template>

        <!-- 操作 -->
        <template #actions="{ record }">
          <a-space>
            <a-button
              type="primary"
              size="small"
              @click="handleViewReport(record)"
            >
              <template #icon>
                <icon-file />
              </template>
              {{ pageText.viewReport }}
            </a-button>
            
            <a-button
              v-if="record.status === 'running'"
              type="outline"
              status="warning"
              size="small"
              @click="handleCancel(record)"
            >
              <template #icon>
                <icon-close />
              </template>
              {{ pageText.cancel }}
            </a-button>

            <a-button
              type="text"
              size="small"
              @click="handleDelete(record)"
              status="danger"
            >
              {{ pageText.delete }}
            </a-button>
          </a-space>
        </template>
        </a-table>
      </div>
    </div>

    <!-- 报告查看模态框 -->
    <TestExecutionReportModal
      v-model:visible="showReport"
      :current-project-id="currentProjectId"
      :execution-id="selectedExecutionId"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import {
  IconSearch,
  IconRefresh,
  IconFile,
  IconClose,
  IconFolder,
} from '@arco-design/web-vue/es/icon';
import { useProjectStore } from '@/store/projectStore';
import { useAppI18n } from '@/composables/useAppI18n';
import {
  getTestExecutionList,
  cancelTestExecution,
  deleteTestExecution,
  type TestExecution,
} from '@/services/testExecutionService';
import { formatDate } from '@/utils/formatters';
import TestExecutionReportModal from '@/components/testcase/TestExecutionReportModal.vue';

const projectStore = useProjectStore();
const { isEnglish } = useAppI18n();
const currentProjectId = computed(() => projectStore.currentProjectId);

const pageText = computed(() => (
  isEnglish.value
    ? {
        noProjectSelected: 'Select a project from the top bar',
        searchPlaceholder: 'Search suite name',
        filterStatusPlaceholder: 'Filter status',
        refresh: 'Refresh',
        noDescription: 'No description',
        total: 'Total',
        passed: 'Passed',
        failed: 'Failed',
        error: 'Error',
        viewReport: 'View report',
        cancel: 'Cancel',
        delete: 'Delete',
        suiteName: 'Suite name',
        status: 'Status',
        statistics: 'Statistics',
        passRate: 'Pass rate',
        duration: 'Duration',
        executor: 'Executed by',
        createdAt: 'Created at',
        actions: 'Actions',
        fetchExecutionsFailed: 'Failed to fetch execution history',
        fetchExecutionsError: 'An error occurred while fetching execution history',
        confirmCancelTitle: 'Confirm cancellation',
        confirmCancelContent: (name: string) => `Cancel execution for "${name}"?`,
        cancelSubmitted: 'Cancellation request sent',
        cancelExecutionFailed: 'Failed to cancel execution',
        cancelExecutionError: 'An error occurred while cancelling execution',
        deleteBlocked: (status: string) => `Cannot delete executions in "${status}" status. Cancel the execution first.`,
        confirmDeleteTitle: 'Confirm deletion',
        confirmDeleteContent: (name: string) => `Delete the execution record for "${name}"? This action cannot be undone.`,
        confirmDeleteOk: 'Delete',
        deleteExecutionSuccess: 'Execution record deleted',
        deleteExecutionFailed: 'Failed to delete execution record',
        deleteExecutionError: 'An error occurred while deleting the execution record',
        allStatuses: 'All statuses',
        statusPending: 'Pending',
        statusRunning: 'Running',
        statusCompleted: 'Completed',
        statusFailed: 'Failed',
        statusCancelled: 'Cancelled',
        secondsUnit: 's',
        minutesUnit: 'm',
      }
    : {
        noProjectSelected: '请在顶部选择一个项目',
        searchPlaceholder: '搜索套件名称',
        filterStatusPlaceholder: '筛选状态',
        refresh: '刷新',
        noDescription: '无描述',
        total: '总数',
        passed: '通过',
        failed: '失败',
        error: '错误',
        viewReport: '查看报告',
        cancel: '取消',
        delete: '删除',
        suiteName: '测试套件',
        status: '状态',
        statistics: '统计',
        passRate: '通过率',
        duration: '执行时长',
        executor: '执行人',
        createdAt: '创建时间',
        actions: '操作',
        fetchExecutionsFailed: '获取执行历史失败',
        fetchExecutionsError: '获取执行历史时发生错误',
        confirmCancelTitle: '确认取消',
        confirmCancelContent: (name: string) => `确定要取消 "${name}" 的执行吗?`,
        cancelSubmitted: '取消请求已发送',
        cancelExecutionFailed: '取消执行失败',
        cancelExecutionError: '取消执行时发生错误',
        deleteBlocked: (status: string) => `无法删除状态为"${status}"的执行记录，请先取消执行`,
        confirmDeleteTitle: '确认删除',
        confirmDeleteContent: (name: string) => `确定要删除测试套件"${name}"的执行记录吗？此操作不可恢复。`,
        confirmDeleteOk: '确认删除',
        deleteExecutionSuccess: '执行记录已删除',
        deleteExecutionFailed: '删除执行记录失败',
        deleteExecutionError: '删除执行记录时发生错误',
        allStatuses: '全部状态',
        statusPending: '等待中',
        statusRunning: '执行中',
        statusCompleted: '已完成',
        statusFailed: '失败',
        statusCancelled: '已取消',
        secondsUnit: '秒',
        minutesUnit: '分',
      }
));

const statusOptions = computed(() => [
  { value: '', label: pageText.value.allStatuses },
  { value: 'pending', label: pageText.value.statusPending },
  { value: 'running', label: pageText.value.statusRunning },
  { value: 'completed', label: pageText.value.statusCompleted },
  { value: 'failed', label: pageText.value.statusFailed },
  { value: 'cancelled', label: pageText.value.statusCancelled },
]);

// 响应式数据
const loading = ref(false);
const searchKeyword = ref('');
const statusFilter = ref('');
const executionData = ref<TestExecution[]>([]);
const showReport = ref(false);
const selectedExecutionId = ref<number | null>(null);
let refreshInterval: number | undefined;

// 分页配置
const paginationConfig = reactive({
  total: 0,
  current: 1,
  pageSize: 10,
  showTotal: true,
  showPageSize: true,
});

// 表格列定义
const columns = computed(() => [
  { title: 'ID', dataIndex: 'id', width: 50, align: 'center' as const },
  { title: pageText.value.suiteName, slotName: 'suite', width: 200, align: 'center' as const },
  { title: pageText.value.status, slotName: 'status', width: 80, align: 'center' as const },
  { title: pageText.value.statistics, slotName: 'statistics', width: 210, align: 'center' as const },
  { title: pageText.value.passRate, slotName: 'pass-rate', width: 90, align: 'center' as const },
  { title: pageText.value.duration, slotName: 'duration', width: 110, align: 'center' as const },
  {
    title: pageText.value.executor,
    dataIndex: 'executor_detail',
    render: ({ record }: { record: TestExecution }) => record.executor_detail?.username || '-',
    width: 100,
    align: 'center' as const,
  },
  {
    title: pageText.value.createdAt,
    dataIndex: 'created_at',
    render: ({ record }: { record: TestExecution }) => formatDate(record.created_at),
    width: 180,
    align: 'center' as const,
  },
  { title: pageText.value.actions, slotName: 'actions', width: 220, fixed: 'right' as const, align: 'center' as const },
]);

// 获取执行列表
const fetchExecutions = async () => {
  if (!currentProjectId.value) return;

  loading.value = true;
  try {
    const response = await getTestExecutionList(currentProjectId.value, {
      search: searchKeyword.value,
      ordering: '-created_at',
    });

    if (response.success && response.data) {
      // 筛选状态
      const filteredData = statusFilter.value
        ? response.data.filter(item => item.status === statusFilter.value)
        : response.data;
      
      executionData.value = filteredData;
      paginationConfig.total = filteredData.length;
    } else {
      Message.error(response.error || pageText.value.fetchExecutionsFailed);
      executionData.value = [];
    }
  } catch (error) {
    console.error('获取执行历史出错:', error);
    Message.error(pageText.value.fetchExecutionsError);
    executionData.value = [];
  } finally {
    loading.value = false;
  }
};

// 搜索处理
const handleSearch = () => {
  paginationConfig.current = 1;
  fetchExecutions();
};

// 分页处理
const handlePageChange = (page: number) => {
  paginationConfig.current = page;
};

const handlePageSizeChange = (pageSize: number) => {
  paginationConfig.pageSize = pageSize;
  paginationConfig.current = 1;
};

// 刷新
const handleRefresh = () => {
  fetchExecutions();
};

// 查看报告
const handleViewReport = (execution: TestExecution) => {
  selectedExecutionId.value = execution.id;
  showReport.value = true;
};

// 取消执行
const handleCancel = (execution: TestExecution) => {
  if (!currentProjectId.value) return;

  Modal.confirm({
    title: pageText.value.confirmCancelTitle,
    content: pageText.value.confirmCancelContent(execution.suite_detail?.name || '-'),
    onOk: async () => {
      try {
        const response = await cancelTestExecution(currentProjectId.value!, execution.id);
        if (response.success) {
          Message.success(pageText.value.cancelSubmitted);
          fetchExecutions();
        } else {
          Message.error(response.error || pageText.value.cancelExecutionFailed);
        }
      } catch (error) {
        Message.error(pageText.value.cancelExecutionError);
      }
    },
  });
};

// 删除执行记录
const handleDelete = (execution: TestExecution) => {
  if (!currentProjectId.value) return;

  // 检查执行状态
  if (execution.status === 'running' || execution.status === 'pending') {
    Message.warning(pageText.value.deleteBlocked(getStatusText(execution.status)));
    return;
  }

  Modal.confirm({
    title: pageText.value.confirmDeleteTitle,
    content: pageText.value.confirmDeleteContent(execution.suite_detail?.name || '-'),
    okText: pageText.value.confirmDeleteOk,
    okButtonProps: {
      status: 'danger',
    },
    onOk: async () => {
      try {
        const response = await deleteTestExecution(currentProjectId.value!, execution.id);
        if (response.success) {
          Message.success(response.message || pageText.value.deleteExecutionSuccess);
          fetchExecutions();
        } else {
          Message.error(response.error || pageText.value.deleteExecutionFailed);
        }
      } catch (error) {
        console.error('删除执行记录出错:', error);
        Message.error(pageText.value.deleteExecutionError);
      }
    },
  });
};

// 获取状态颜色
const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: 'gray',
    running: 'blue',
    completed: 'green',
    failed: 'red',
    cancelled: 'orange',
  };
  return colors[status] || 'gray';
};

// 获取状态文本
const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: pageText.value.statusPending,
    running: pageText.value.statusRunning,
    completed: pageText.value.statusCompleted,
    failed: pageText.value.statusFailed,
    cancelled: pageText.value.statusCancelled,
  };
  return texts[status] || status;
};

// 获取通过率颜色
const getPassRateColor = (rate: number) => {
  if (rate >= 90) return '#00b42a';
  if (rate >= 70) return '#ff7d00';
  return '#f53f3f';
};

// 格式化时长
const formatDuration = (seconds: number) => {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}${pageText.value.secondsUnit}`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return isEnglish.value
    ? `${minutes}${pageText.value.minutesUnit} ${remainingSeconds.toFixed(0)}${pageText.value.secondsUnit}`
    : `${minutes}${pageText.value.minutesUnit}${remainingSeconds.toFixed(0)}${pageText.value.secondsUnit}`;
};

// 启动定时刷新
const startRefresh = () => {
  // 如果已经有定时器，先清除
  if (refreshInterval) {
    clearInterval(refreshInterval);
  }
  // 每10秒刷新一次
  refreshInterval = window.setInterval(() => {
    // 只有当有任务在执行中时才刷新
    const hasRunningTasks = executionData.value.some(e => e.status === 'running');
    if (hasRunningTasks) {
      fetchExecutions();
    } else {
      // 如果没有运行中的任务，停止刷新
      stopRefresh();
    }
  }, 10000);
};

// 停止定时刷新
const stopRefresh = () => {
  if (refreshInterval) {
    clearInterval(refreshInterval);
    refreshInterval = undefined;
  }
};

watch(currentProjectId, () => {
  searchKeyword.value = '';
  statusFilter.value = '';
  paginationConfig.current = 1;
  if (currentProjectId.value) {
    fetchExecutions().then(() => {
      startRefresh();
    });
  } else {
    stopRefresh();
  }
});

onMounted(() => {
  if (currentProjectId.value) {
    fetchExecutions().then(() => {
      startRefresh();
    });
  }
});

onUnmounted(() => {
  stopRefresh();
});
</script>

<style scoped>
.test-execution-history-view {
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

.suite-name {
  color: #1890ff;
  cursor: pointer;
  font-weight: 500;
  transition: color 0.2s;
}

.suite-name:hover {
  color: #40a9ff;
  text-decoration: underline;
}

.statistics {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.pass-rate {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.rate-text {
  font-weight: 500;
  font-size: 12px;
  color: var(--color-text-2, #4e5969);
}
</style>
