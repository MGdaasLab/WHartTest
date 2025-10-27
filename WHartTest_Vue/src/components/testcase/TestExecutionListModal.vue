<template>
  <a-modal
    v-model:visible="modalVisible"
    title="测试执行历史"
    :width="1400"
    :footer="false"
    :mask-closable="false"
    unmount-on-close
  >
    <div class="execution-list-container">
      <!-- 搜索和筛选 -->
      <div class="filter-section">
        <a-space>
          <a-input
            v-model="searchKeyword"
            placeholder="搜索套件名称"
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
            placeholder="筛选状态"
            style="width: 150px;"
            allow-clear
            @change="handleSearch"
          >
            <a-option value="">全部状态</a-option>
            <a-option value="pending">等待中</a-option>
            <a-option value="running">执行中</a-option>
            <a-option value="completed">已完成</a-option>
            <a-option value="failed">失败</a-option>
            <a-option value="cancelled">已取消</a-option>
          </a-select>

          <a-button @click="handleRefresh">
            <template #icon>
              <icon-refresh />
            </template>
            刷新
          </a-button>
        </a-space>
      </div>

      <!-- 执行列表 -->
      <a-table
        :data="executionData"
        :loading="loading"
        :pagination="false"
        :columns="columns"
        row-key="id"
        stripe
        :scroll="{ y: 500 }"
      >
        <!-- 套件名称 -->
        <template #suite="{ record }">
          <a-tooltip :content="record.suite_detail?.description || '无描述'">
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
            <a-tag color="blue">总数: {{ record.total_count }}</a-tag>
            <a-tag color="green">通过: {{ record.passed_count }}</a-tag>
            <a-tag v-if="record.failed_count > 0" color="red">失败: {{ record.failed_count }}</a-tag>
            <a-tag v-if="record.error_count > 0" color="orange">错误: {{ record.error_count }}</a-tag>
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
              查看报告
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
              取消
            </a-button>

            <a-button
              type="text"
              size="small"
              @click="handleDelete(record)"
              status="danger"
            >
              删除
            </a-button>
          </a-space>
        </template>
      </a-table>
    </div>

    <!-- 报告查看模态框 -->
    <TestExecutionReportModal
      v-model:visible="showReport"
      :current-project-id="currentProjectId"
      :execution-id="selectedExecutionId"
    />
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue';
import { Message, Modal } from '@arco-design/web-vue';
import {
  IconSearch,
  IconRefresh,
  IconFile,
  IconClose,
} from '@arco-design/web-vue/es/icon';
import {
  getTestExecutionList,
  cancelTestExecution,
  deleteTestExecution,
  type TestExecution,
} from '@/services/testExecutionService';
import { formatDate } from '@/utils/formatters';
import TestExecutionReportModal from './TestExecutionReportModal.vue';

// Props
interface Props {
  visible: boolean;
  currentProjectId: number | null;
}

const props = defineProps<Props>();

// Emits
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

// 响应式数据
const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
});

const loading = ref(false);
const searchKeyword = ref('');
const statusFilter = ref('');
const executionData = ref<TestExecution[]>([]);
const showReport = ref(false);
const selectedExecutionId = ref<number | null>(null);
let refreshInterval: number | undefined;

// 表格列定义
const columns = [
  { title: 'ID', dataIndex: 'id', width: 60, align: 'center' as const },
  { title: '测试套件', slotName: 'suite', width: 200, align: 'center' as const },
  { title: '状态', slotName: 'status', width: 100, align: 'center' as const },
  { title: '统计', slotName: 'statistics', width: 280, align: 'center' as const },
  { title: '通过率', slotName: 'pass-rate', width: 80, align: 'center' as const },
  { title: '执行时长', slotName: 'duration', width: 100, align: 'center' as const },
  {
    title: '执行人',
    dataIndex: 'executor_detail',
    render: ({ record }: { record: TestExecution }) => record.executor_detail?.username || '-',
    width: 100,
    align: 'center' as const,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    render: ({ record }: { record: TestExecution }) => formatDate(record.created_at),
    width: 160,
    align: 'center' as const,
  },
  { title: '操作', slotName: 'actions', width: 200, fixed: 'right', align: 'center' as const },
];

// 获取执行列表
const fetchExecutions = async () => {
  if (!props.currentProjectId) return;

  loading.value = true;
  try {
    const response = await getTestExecutionList(props.currentProjectId, {
      search: searchKeyword.value,
      ordering: '-created_at',
    });

    if (response.success && response.data) {
      // 筛选状态
      executionData.value = statusFilter.value
        ? response.data.filter(item => item.status === statusFilter.value)
        : response.data;
    } else {
      Message.error(response.error || '获取执行历史失败');
      executionData.value = [];
    }
  } catch (error) {
    console.error('获取执行历史出错:', error);
    Message.error('获取执行历史时发生错误');
    executionData.value = [];
  } finally {
    loading.value = false;
  }
};

// 搜索处理
const handleSearch = () => {
  fetchExecutions();
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
  if (!props.currentProjectId) return;

  Modal.confirm({
    title: '确认取消',
    content: `确定要取消 "${execution.suite_detail?.name}" 的执行吗?`,
    okText: '确认',
    cancelText: '取消',
    onOk: async () => {
      try {
        const response = await cancelTestExecution(props.currentProjectId!, execution.id);
        if (response.success) {
          Message.success('取消请求已发送');
          fetchExecutions();
        } else {
          Message.error(response.error || '取消执行失败');
        }
      } catch (error) {
        Message.error('取消执行时发生错误');
      }
    },
  });
};

// 删除执行记录
const handleDelete = (execution: TestExecution) => {
  if (!props.currentProjectId) return;

  // 检查执行状态
  if (execution.status === 'running' || execution.status === 'pending') {
    Message.warning(`无法删除状态为"${getStatusText(execution.status)}"的执行记录，请先取消执行`);
    return;
  }

  Modal.confirm({
    title: '确认删除',
    content: `确定要删除测试套件"${execution.suite_detail?.name}"的执行记录吗？此操作不可恢复。`,
    okText: '确认删除',
    cancelText: '取消',
    okButtonProps: {
      status: 'danger',
    },
    onOk: async () => {
      try {
        const response = await deleteTestExecution(props.currentProjectId!, execution.id);
        if (response.success) {
          Message.success(response.message || '执行记录已删除');
          fetchExecutions();
        } else {
          Message.error(response.error || '删除执行记录失败');
        }
      } catch (error) {
        console.error('删除执行记录出错:', error);
        Message.error('删除执行记录时发生错误');
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
    pending: '等待中',
    running: '执行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
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
    return `${seconds.toFixed(1)}秒`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}分${remainingSeconds.toFixed(0)}秒`;
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

// 监听visible变化
watch(
  () => props.visible,
  (newVal) => {
    if (newVal && props.currentProjectId) {
      fetchExecutions().then(() => {
        startRefresh(); // 加载完数据后启动定时刷新
      });
    } else {
      stopRefresh(); // 关闭模态框时停止刷新
    }
  }
);

onUnmounted(() => {
  stopRefresh(); // 组件卸载时确保停止刷新
});
</script>

<style scoped>
.execution-list-container {
  padding: 16px 0;
}

.filter-section {
  margin-bottom: 16px;
}

.suite-name {
  color: #1d39c4;
  cursor: pointer;
  font-weight: 500;
}

.suite-name:hover {
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
  color: #4e5969;
}
</style>