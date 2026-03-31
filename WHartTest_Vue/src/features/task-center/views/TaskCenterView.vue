<template>
  <div class="task-center">
    <div v-if="!currentProjectId" class="no-project">
      <a-empty description="请在顶部选择一个项目">
        <template #image>
          <icon-schedule style="font-size: 48px; color: #c2c7d0;" />
        </template>
      </a-empty>
    </div>

    <template v-else>
      <div class="page-header">
        <h1 class="page-title">任务中心</h1>
        <a-button type="primary" @click="handleCreate">
          <template #icon><icon-plus /></template>
          新建任务
        </a-button>
      </div>

      <div class="content-container">
        <!-- 筛选区域 -->
        <div class="filter-row">
          <a-input-search
            v-model="searchKeyword"
            placeholder="搜索任务名称"
            allow-clear
            style="width: 260px"
            @search="handleSearch"
            @clear="handleSearch"
          />
          <a-select
            v-model="statusFilter"
            placeholder="状态筛选"
            allow-clear
            style="width: 120px"
            @change="handleSearch"
          >
            <a-option value="disabled">未启用</a-option>
            <a-option value="running">已启用</a-option>
          </a-select>
          <a-select
            v-model="moduleFilter"
            placeholder="模块筛选"
            allow-clear
            style="width: 130px"
            @change="handleSearch"
          >
            <a-option value="ui_automation">UI 自动化</a-option>
            <a-option value="test_suite">测试套件</a-option>
          </a-select>
        </div>

        <!-- 任务列表 -->
        <a-table
          :columns="columns"
          :data="taskList"
          :loading="loading"
          :pagination="paginationConfig"
          row-key="id"
          @page-change="onPageChange"
          @page-size-change="onPageSizeChange"
        >
          <template #name="{ record }">
            <span class="task-name-text">{{ record.name }}</span>
          </template>

          <template #module="{ record }">
            <a-tag :color="record.module === 'ui_automation' ? 'arcoblue' : 'purple'">
              {{ record.module === 'ui_automation' ? 'UI 自动化' : '测试套件' }}
            </a-tag>
          </template>

          <template #schedule="{ record }">
            {{ record.schedule_display }}
          </template>

          <template #status="{ record }">
            <a-switch
              :model-value="record.status === 'running'"
              size="small"
              @change="(val: string | number | boolean) => handleToggleStatus(record, !!val)"
            />
          </template>

          <template #last_run_at="{ record }">
            {{ record.last_run_at ? formatDate(record.last_run_at) : '—' }}
          </template>

          <template #actions="{ record }">
            <a-space :size="4">
              <!-- 立即执行 -->
              <a-button
                type="text" size="small"
                @click="handleRunNow(record)"
              >
                立即执行
              </a-button>
              <!-- 执行记录 -->
              <a-button type="text" size="small" @click="handleViewExecutions(record)">
                记录
              </a-button>
              <!-- 编辑 -->
              <a-button
                type="text" size="small"
                @click="handleEdit(record)"
              >
                编辑
              </a-button>
              <!-- 删除 -->
              <a-popconfirm content="确定要删除此任务吗？" @ok="handleDelete(record)">
                <a-button type="text" size="small" status="danger">删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </a-table>
      </div>

      <!-- 执行记录抽屉 -->
      <a-drawer
        v-model:visible="executionDrawerVisible"
        :title="`执行记录 - ${currentTask?.name || ''}`"
        :width="900"
        :footer="false"
      >
        <a-table
          :columns="executionColumns"
          :data="executionList"
          :loading="executionLoading"
          :pagination="executionPagination"
          row-key="id"
          size="small"
          @page-change="onExecutionPageChange"
        >
          <template #status="{ record }">
            <a-tag :color="execStatusColorMap[record.status]">
              {{ execStatusTextMap[record.status] }}
            </a-tag>
          </template>
          <template #trigger_type="{ record }">
            {{ triggerTextMap[record.trigger_type] }}
          </template>
          <template #started_at="{ record }">
            {{ formatDate(record.started_at) }}
          </template>
          <template #actions="{ record }">
            <a-space :size="4">
              <a-button type="text" size="small" @click="handleViewLog(record)">日志</a-button>
              <a-popconfirm content="确定删除此记录？" @ok="handleDeleteExecution(record)">
                <a-button type="text" size="small" status="danger">删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </a-table>
      </a-drawer>
    </template>

    <!-- 新建/编辑弹窗 -->
    <TaskFormModal ref="formModalRef" :project-id="currentProjectId!" @success="fetchTasks" />

    <!-- 日志弹窗 -->
    <LogViewModal ref="logModalRef" :project-id="currentProjectId!" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconPlus, IconSchedule } from '@arco-design/web-vue/es/icon';
import { useProjectStore } from '@/store/projectStore';
import {
  getTaskList, enableTask, disableTask, runTaskNow,
  deleteTask, getTaskExecutions, deleteExecution,
  type ScheduledTask, type TaskExecution,
} from '../services/taskService';
import TaskFormModal from '../components/TaskFormModal.vue';
import LogViewModal from '../components/LogViewModal.vue';

const projectStore = useProjectStore();
const currentProjectId = computed(() => projectStore.currentProjectId);

// 任务列表状态
const taskList = ref<ScheduledTask[]>([]);
const loading = ref(false);
const searchKeyword = ref('');
const statusFilter = ref<string | undefined>(undefined);
const moduleFilter = ref<string | undefined>(undefined);
const page = ref(1);
const pageSize = ref(10);
const total = ref(0);

// 执行记录状态
const executionDrawerVisible = ref(false);
const currentTask = ref<ScheduledTask | null>(null);
const executionList = ref<TaskExecution[]>([]);
const executionLoading = ref(false);
const executionPage = ref(1);
const executionTotal = ref(0);

// 组件引用
const formModalRef = ref<InstanceType<typeof TaskFormModal> | null>(null);
const logModalRef = ref<InstanceType<typeof LogViewModal> | null>(null);

// 映射
const execStatusColorMap: Record<string, string> = {
  running: 'blue', success: 'green', failed: 'red',
};
const execStatusTextMap: Record<string, string> = {
  running: '执行中', success: '成功', failed: '失败',
};
const triggerTextMap: Record<string, string> = {
  scheduled: '定时调度', manual: '手动执行', api: 'API 触发',
};

// 分页配置
const paginationConfig = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showTotal: true,
  showPageSize: true,
}));

const executionPagination = computed(() => ({
  current: executionPage.value,
  pageSize: 10,
  total: executionTotal.value,
  showTotal: true,
}));

// 表格列
const columns = [
  { title: '任务名称', slotName: 'name', width: 180, align: 'center' as const },
  { title: '模块', slotName: 'module', width: 110, align: 'center' as const },
  { title: '调度策略', slotName: 'schedule', width: 180, align: 'center' as const },
  { title: '状态', slotName: 'status', width: 90, align: 'center' as const },
  { title: '创建人', dataIndex: 'creator_name', width: 100, align: 'center' as const },
  { title: '最近执行', slotName: 'last_run_at', width: 150, align: 'center' as const },
  { title: '操作', slotName: 'actions', width: 260, align: 'center' as const, fixed: 'right' as const },
];

const executionColumns = [
  { title: '执行ID', dataIndex: 'execution_id', width: 180, ellipsis: true },
  { title: '触发方式', slotName: 'trigger_type', width: 90, align: 'center' as const },
  { title: '状态', slotName: 'status', width: 80, align: 'center' as const },
  { title: '开始时间', slotName: 'started_at', width: 150, align: 'center' as const },
  { title: '耗时', dataIndex: 'duration', width: 80, align: 'center' as const },
  { title: '操作', slotName: 'actions', width: 120, align: 'center' as const },
];

// 工具函数
const formatDate = (dateStr: string) => {
  const d = new Date(dateStr);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

// 数据加载
const fetchTasks = async () => {
  if (!currentProjectId.value) return;
  loading.value = true;
  try {
    const params: Record<string, any> = { page: page.value };
    if (searchKeyword.value) params.search = searchKeyword.value;
    if (statusFilter.value) params.status = statusFilter.value;
    if (moduleFilter.value) params.module = moduleFilter.value;

    const res = await getTaskList(currentProjectId.value, params);
    taskList.value = res.results;
    total.value = res.count;
  } catch (e: any) {
    Message.error(e.response?.data?.detail || '加载任务列表失败');
  } finally {
    loading.value = false;
  }
};

const fetchExecutions = async () => {
  if (!currentProjectId.value || !currentTask.value) return;
  executionLoading.value = true;
  try {
    const res = await getTaskExecutions(
      currentProjectId.value, currentTask.value.id,
      { page: executionPage.value }
    );
    executionList.value = res.results;
    executionTotal.value = res.count;
  } catch {
    Message.error('加载执行记录失败');
  } finally {
    executionLoading.value = false;
  }
};

// 搜索和分页
const handleSearch = () => { page.value = 1; fetchTasks(); };
const onPageChange = (p: number) => { page.value = p; fetchTasks(); };
const onPageSizeChange = (s: number) => { pageSize.value = s; page.value = 1; fetchTasks(); };
const onExecutionPageChange = (p: number) => { executionPage.value = p; fetchExecutions(); };

// 操作
const handleCreate = () => formModalRef.value?.open();
const handleEdit = (task: ScheduledTask) => formModalRef.value?.open(task);

const handleToggleStatus = async (task: ScheduledTask, enabled: boolean) => {
  try {
    if (enabled) {
      await enableTask(currentProjectId.value!, task.id);
      Message.success('任务已启用');
    } else {
      await disableTask(currentProjectId.value!, task.id);
      Message.success('任务已关闭');
    }
    fetchTasks();
  } catch (e: any) {
    Message.error(e.response?.data?.error || '操作失败');
  }
};

const handleRunNow = async (task: ScheduledTask) => {
  try {
    await runTaskNow(currentProjectId.value!, task.id);
    Message.success('任务已提交执行');
    fetchTasks();
  } catch (e: any) {
    Message.error(e.response?.data?.error || '执行失败');
  }
};

const handleDelete = async (task: ScheduledTask) => {
  try {
    await deleteTask(currentProjectId.value!, task.id);
    Message.success('任务已删除');
    fetchTasks();
  } catch {
    Message.error('删除失败');
  }
};

const handleViewExecutions = (task: ScheduledTask) => {
  currentTask.value = task;
  executionPage.value = 1;
  executionDrawerVisible.value = true;
  fetchExecutions();
};

const handleViewLog = (execution: TaskExecution) => {
  logModalRef.value?.open(execution.id);
};

const handleDeleteExecution = async (execution: TaskExecution) => {
  try {
    await deleteExecution(currentProjectId.value!, execution.id);
    Message.success('记录已删除');
    fetchExecutions();
  } catch {
    Message.error('删除失败');
  }
};

// 监听项目切换
watch(currentProjectId, (newId, oldId) => {
  if (newId !== oldId) {
    page.value = 1;
    searchKeyword.value = '';
    statusFilter.value = undefined;
    moduleFilter.value = undefined;
    fetchTasks();
  }
}, { immediate: false });

onMounted(() => {
  if (currentProjectId.value) fetchTasks();
});
</script>

<style scoped>
.task-center {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
  box-sizing: border-box;
}

.no-project {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-title {
  font-size: 24px;
  font-weight: bold;
  margin: 0;
}

.content-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.filter-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.task-name-text {
  font-weight: 500;
}

@media (max-width: 768px) {
  .task-center {
    padding: 12px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .page-title {
    font-size: 20px;
  }
}
</style>
