<template>
  <div class="task-center">
    <div v-if="!canViewTaskCenter" class="no-permission">
      <a-result
        status="403"
        :title="pageText.restrictedTitle"
        :subtitle="pageText.restrictedSubtitle"
      />
    </div>

    <div v-else-if="!currentProjectId" class="no-project">
      <a-empty :description="pageText.selectProjectFirst">
        <template #image>
          <icon-schedule style="font-size: 48px; color: #c2c7d0;" />
        </template>
      </a-empty>
    </div>

    <template v-else>
      <div class="page-header">
        <h1 class="page-title">{{ pageText.title }}</h1>
        <a-button v-if="canCreateTask" type="primary" @click="handleCreate">
          <template #icon><icon-plus /></template>
          {{ pageText.createTask }}
        </a-button>
      </div>

      <div class="content-container">
        <div class="filter-row">
          <a-input-search
            v-model="searchKeyword"
            :placeholder="pageText.searchTaskName"
            allow-clear
            style="width: 260px"
            @search="handleSearch"
            @clear="handleSearch"
          />
          <a-select
            v-model="statusFilter"
            :placeholder="pageText.filterStatus"
            allow-clear
            style="width: 120px"
            @change="handleSearch"
          >
            <a-option value="disabled">{{ pageText.disabled }}</a-option>
            <a-option value="running">{{ pageText.enabled }}</a-option>
          </a-select>
          <a-select
            v-model="moduleFilter"
            :placeholder="pageText.filterModule"
            allow-clear
            style="width: 140px"
            @change="handleSearch"
          >
            <a-option value="ui_automation">{{ pageText.uiAutomation }}</a-option>
            <a-option value="test_suite">{{ pageText.testSuite }}</a-option>
          </a-select>
        </div>

        <a-table
          :key="`task-center-table-${locale}`"
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
              {{ getModuleLabel(record.module) }}
            </a-tag>
          </template>

          <template #schedule="{ record }">
            {{ formatScheduleDisplay(record) }}
          </template>

          <template #status="{ record }">
            <a-switch
              v-if="canEditTask"
              :model-value="record.status === 'running'"
              size="small"
              @change="(val: string | number | boolean) => handleToggleStatus(record, !!val)"
            />
            <a-tag v-else :color="taskStatusColorMap[record.status] || 'gray'">
              {{ taskStatusTextMap[record.status] || record.status }}
            </a-tag>
          </template>

          <template #last_run_at="{ record }">
            {{ record.last_run_at ? formatDate(record.last_run_at) : emptyPlaceholder }}
          </template>

          <template #actions="{ record }">
            <a-space v-if="hasTaskActions" :size="4">
              <a-button
                v-if="canEditTask"
                type="text"
                size="small"
                @click="handleRunNow(record)"
              >
                {{ pageText.runNow }}
              </a-button>
              <a-button
                v-if="canViewExecutionRecords"
                type="text"
                size="small"
                @click="handleViewExecutions(record)"
              >
                {{ pageText.records }}
              </a-button>
              <a-button
                v-if="canEditTask"
                type="text"
                size="small"
                @click="handleEdit(record)"
              >
                {{ pageText.edit }}
              </a-button>
              <a-popconfirm
                v-if="canDeleteTask"
                :content="pageText.deleteTaskConfirm"
                @ok="handleDelete(record)"
              >
                <a-button type="text" size="small" status="danger">{{ pageText.delete }}</a-button>
              </a-popconfirm>
            </a-space>
            <span v-else class="action-placeholder">{{ emptyPlaceholder }}</span>
          </template>
        </a-table>
      </div>

      <a-drawer
        v-if="canViewExecutionRecords"
        v-model:visible="executionDrawerVisible"
        :title="executionDrawerTitle"
        :width="isEnglish ? 980 : 900"
        :footer="false"
      >
        <a-table
          :key="`task-execution-table-${locale}`"
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
              <a-button type="text" size="small" @click="handleViewLog(record)">{{ pageText.log }}</a-button>
              <a-popconfirm
                v-if="canDeleteExecution"
                :content="pageText.deleteExecutionConfirm"
                @ok="handleDeleteExecution(record)"
              >
                <a-button type="text" size="small" status="danger">{{ pageText.delete }}</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </a-table>
      </a-drawer>
    </template>

    <TaskFormModal ref="formModalRef" :project-id="currentProjectId!" @success="fetchTasks" />
    <LogViewModal ref="logModalRef" :project-id="currentProjectId!" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconPlus, IconSchedule } from '@arco-design/web-vue/es/icon';
import { useAuthStore } from '@/store/authStore';
import { useProjectStore } from '@/store/projectStore';
import { useAppI18n } from '@/composables/useAppI18n';
import {
  getTaskList, enableTask, disableTask, runTaskNow,
  deleteTask, getTaskExecutions, deleteExecution,
  type ScheduledTask, type TaskExecution,
} from '../services/taskService';
import { normalizeListPayload } from '@/features/api-testing/services/responseHelpers';
import TaskFormModal from '../components/TaskFormModal.vue';
import LogViewModal from '../components/LogViewModal.vue';

const authStore = useAuthStore();
const projectStore = useProjectStore();
const { locale, isEnglish } = useAppI18n();

const pageText = computed(() => (
  isEnglish.value
    ? {
        restrictedTitle: 'Task Center access denied',
        restrictedSubtitle: 'Contact an administrator to get Task Center view permission.',
        selectProjectFirst: 'Select a project from the top bar first',
        title: 'Task Center',
        createTask: 'Create task',
        searchTaskName: 'Search task name',
        filterStatus: 'Filter status',
        filterModule: 'Filter module',
        disabled: 'Disabled',
        enabled: 'Enabled',
        uiAutomation: 'UI Automation',
        testSuite: 'Test Suite',
        runNow: 'Run now',
        records: 'Records',
        edit: 'Edit',
        delete: 'Delete',
        deleteTaskConfirm: 'Delete this task?',
        executionRecords: 'Execution Records',
        executionRecordsFor: (name: string) => `Execution Records - ${name}`,
        log: 'Log',
        deleteExecutionConfirm: 'Delete this record?',
        running: 'Running',
        success: 'Success',
        failed: 'Failed',
        scheduled: 'Scheduled',
        manual: 'Manual',
        api: 'API',
        taskName: 'Task Name',
        module: 'Module',
        schedule: 'Schedule',
        status: 'Status',
        creator: 'Created by',
        lastRun: 'Last Run',
        actions: 'Actions',
        executionId: 'Execution ID',
        triggerType: 'Trigger',
        startTime: 'Started At',
        duration: 'Duration',
        loadTasksFailed: 'Failed to load task list',
        loadExecutionsFailed: 'Failed to load execution records',
        noCreatePermission: 'You do not have permission to create tasks',
        noEditPermission: 'You do not have permission to edit tasks',
        noTogglePermission: 'You do not have permission to change task status',
        taskEnabled: 'Task enabled',
        taskDisabled: 'Task disabled',
        operationFailed: 'Operation failed',
        noRunPermission: 'You do not have permission to run tasks',
        taskSubmitted: 'Task submitted for execution',
        runFailed: 'Execution failed',
        noDeletePermission: 'You do not have permission to delete tasks',
        taskDeleted: 'Task deleted',
        deleteFailed: 'Delete failed',
        noViewExecutionPermission: 'You do not have permission to view execution records',
        noDeleteExecutionPermission: 'You do not have permission to delete execution records',
        recordDeleted: 'Record deleted',
        scheduleOnce: 'Once',
        scheduleOnceMissing: 'Once (time not set)',
        scheduleDaily: 'Daily',
        scheduleWeekly: 'Weekly',
        scheduleHourly: 'Hourly',
        scheduleHourlyMinute: (minute: number) => `Every hour at minute ${minute}`,
      }
    : {
        restrictedTitle: '无权限访问任务中心',
        restrictedSubtitle: '请联系管理员分配任务中心查看权限',
        selectProjectFirst: '请在顶部选择一个项目',
        title: '任务中心',
        createTask: '新建任务',
        searchTaskName: '搜索任务名称',
        filterStatus: '状态筛选',
        filterModule: '模块筛选',
        disabled: '未启用',
        enabled: '已启用',
        uiAutomation: 'UI 自动化',
        testSuite: '测试套件',
        runNow: '立即执行',
        records: '记录',
        edit: '编辑',
        delete: '删除',
        deleteTaskConfirm: '确定要删除此任务吗？',
        executionRecords: '执行记录',
        executionRecordsFor: (name: string) => `执行记录 - ${name}`,
        log: '日志',
        deleteExecutionConfirm: '确定删除此记录？',
        running: '执行中',
        success: '成功',
        failed: '失败',
        scheduled: '定时调度',
        manual: '手动执行',
        api: 'API 触发',
        taskName: '任务名称',
        module: '模块',
        schedule: '调度策略',
        status: '状态',
        creator: '创建人',
        lastRun: '最近执行',
        actions: '操作',
        executionId: '执行ID',
        triggerType: '触发方式',
        startTime: '开始时间',
        duration: '耗时',
        loadTasksFailed: '加载任务列表失败',
        loadExecutionsFailed: '加载执行记录失败',
        noCreatePermission: '您没有创建任务的权限',
        noEditPermission: '您没有编辑任务的权限',
        noTogglePermission: '您没有修改任务的权限',
        taskEnabled: '任务已启用',
        taskDisabled: '任务已关闭',
        operationFailed: '操作失败',
        noRunPermission: '您没有执行任务的权限',
        taskSubmitted: '任务已提交执行',
        runFailed: '执行失败',
        noDeletePermission: '您没有删除任务的权限',
        taskDeleted: '任务已删除',
        deleteFailed: '删除失败',
        noViewExecutionPermission: '您没有查看执行记录的权限',
        noDeleteExecutionPermission: '您没有删除执行记录的权限',
        recordDeleted: '记录已删除',
        scheduleOnce: '一次性',
        scheduleOnceMissing: '一次性（未设置时间）',
        scheduleDaily: '每天',
        scheduleWeekly: '每周',
        scheduleHourly: '每小时',
        scheduleHourlyMinute: (minute: number) => `每小时第 ${minute} 分钟`,
      }
));

const currentProjectId = computed(() => projectStore.currentProjectId);
const canViewTaskCenter = computed(() => authStore.hasPermission('task_center.view_scheduledtask'));
const canCreateTask = computed(() => authStore.hasPermission('task_center.add_scheduledtask'));
const canEditTask = computed(() => authStore.hasPermission('task_center.change_scheduledtask'));
const canDeleteTask = computed(() => authStore.hasPermission('task_center.delete_scheduledtask'));
const canViewExecutionRecords = computed(() => authStore.hasPermission('task_center.view_taskexecution'));
const canDeleteExecution = computed(() => authStore.hasPermission('task_center.delete_taskexecution'));
const hasTaskActions = computed(() => (
  canEditTask.value || canDeleteTask.value || canViewExecutionRecords.value
));

const taskList = ref<ScheduledTask[]>([]);
const loading = ref(false);
const searchKeyword = ref('');
const statusFilter = ref<string | undefined>(undefined);
const moduleFilter = ref<string | undefined>(undefined);
const page = ref(1);
const pageSize = ref(10);
const total = ref(0);

const executionDrawerVisible = ref(false);
const currentTask = ref<ScheduledTask | null>(null);
const executionList = ref<TaskExecution[]>([]);
const executionLoading = ref(false);
const executionPage = ref(1);
const executionTotal = ref(0);

const formModalRef = ref<InstanceType<typeof TaskFormModal> | null>(null);
const logModalRef = ref<InstanceType<typeof LogViewModal> | null>(null);

const taskStatusColorMap: Record<string, string> = {
  running: 'green',
  disabled: 'gray',
};

const execStatusColorMap: Record<string, string> = {
  running: 'blue',
  success: 'green',
  failed: 'red',
};

const taskStatusTextMap = computed<Record<string, string>>(() => ({
  running: pageText.value.enabled,
  disabled: pageText.value.disabled,
}));

const execStatusTextMap = computed<Record<string, string>>(() => ({
  running: pageText.value.running,
  success: pageText.value.success,
  failed: pageText.value.failed,
}));

const triggerTextMap = computed<Record<string, string>>(() => ({
  scheduled: pageText.value.scheduled,
  manual: pageText.value.manual,
  api: pageText.value.api,
}));

const emptyPlaceholder = '—';

const weekDayLabels = computed(() => (
  isEnglish.value
    ? ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    : ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
));

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

const columns = computed(() => [
  { title: pageText.value.taskName, slotName: 'name', width: 220, align: 'center' as const },
  { title: pageText.value.module, slotName: 'module', width: 130, align: 'center' as const },
  { title: pageText.value.schedule, slotName: 'schedule', width: isEnglish.value ? 240 : 190, align: 'center' as const },
  { title: pageText.value.status, slotName: 'status', width: 100, align: 'center' as const },
  { title: pageText.value.creator, dataIndex: 'creator_name', width: 110, align: 'center' as const },
  { title: pageText.value.lastRun, slotName: 'last_run_at', width: 180, align: 'center' as const },
  { title: pageText.value.actions, slotName: 'actions', width: isEnglish.value ? 300 : 260, align: 'center' as const, fixed: 'right' as const },
]);

const executionColumns = computed(() => [
  { title: pageText.value.executionId, dataIndex: 'execution_id', width: 220, ellipsis: true },
  { title: pageText.value.triggerType, slotName: 'trigger_type', width: 120, align: 'center' as const },
  { title: pageText.value.status, slotName: 'status', width: 100, align: 'center' as const },
  { title: pageText.value.startTime, slotName: 'started_at', width: 180, align: 'center' as const },
  { title: pageText.value.duration, dataIndex: 'duration', width: 100, align: 'center' as const },
  { title: pageText.value.actions, slotName: 'actions', width: isEnglish.value ? 150 : 120, align: 'center' as const },
]);

const executionDrawerTitle = computed(() => (
  currentTask.value
    ? pageText.value.executionRecordsFor(currentTask.value.name)
    : pageText.value.executionRecords
));

const getModuleLabel = (module: ScheduledTask['module']) => (
  module === 'ui_automation' ? pageText.value.uiAutomation : pageText.value.testSuite
);

const formatDate = (dateStr: string) => {
  const date = new Date(dateStr);
  return date.toLocaleString(isEnglish.value ? 'en-US' : 'zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
};

const formatTimeValue = (value: string | null | undefined) => {
  if (!value) return '';
  return value.slice(0, 5);
};

const formatScheduleDisplay = (task: ScheduledTask) => {
  switch (task.schedule_type) {
    case 'once':
      return task.once_datetime
        ? `${pageText.value.scheduleOnce} ${formatDate(task.once_datetime)}`
        : pageText.value.scheduleOnceMissing;
    case 'daily':
      return task.daily_time
        ? `${pageText.value.scheduleDaily} ${formatTimeValue(task.daily_time)}`
        : pageText.value.scheduleDaily;
    case 'weekly': {
      const days = (task.weekly_days || [])
        .filter((day) => day >= 0 && day <= 6)
        .sort((a, b) => a - b)
        .map((day) => weekDayLabels.value[day])
        .join(isEnglish.value ? ', ' : '、');
      const timeText = formatTimeValue(task.weekly_time);
      return [pageText.value.scheduleWeekly, days, timeText].filter(Boolean).join(' ');
    }
    case 'hourly':
      return task.hourly_minute != null
        ? pageText.value.scheduleHourlyMinute(task.hourly_minute)
        : pageText.value.scheduleHourly;
    default:
      return task.schedule_display || task.schedule_type;
  }
};

const fetchTasks = async () => {
  if (!canViewTaskCenter.value || !currentProjectId.value) return;
  loading.value = true;
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize.value };
    if (searchKeyword.value) params.search = searchKeyword.value;
    if (statusFilter.value) params.status = statusFilter.value;
    if (moduleFilter.value) params.module = moduleFilter.value;

    const res = await getTaskList(currentProjectId.value, params);
    const { results, count } = normalizeListPayload<ScheduledTask>(res);
    taskList.value = results;
    total.value = count;
  } catch (error: any) {
    Message.error(error.response?.data?.detail || pageText.value.loadTasksFailed);
  } finally {
    loading.value = false;
  }
};

const fetchExecutions = async () => {
  if (!canViewExecutionRecords.value || !currentProjectId.value || !currentTask.value) return;
  executionLoading.value = true;
  try {
    const res = await getTaskExecutions(
      currentProjectId.value,
      currentTask.value.id,
      { page: executionPage.value }
    );
    const { results, count } = normalizeListPayload<TaskExecution>(res);
    executionList.value = results;
    executionTotal.value = count;
  } catch {
    Message.error(pageText.value.loadExecutionsFailed);
  } finally {
    executionLoading.value = false;
  }
};

const handleSearch = () => {
  page.value = 1;
  fetchTasks();
};

const onPageChange = (nextPage: number) => {
  page.value = nextPage;
  fetchTasks();
};

const onPageSizeChange = (nextPageSize: number) => {
  pageSize.value = nextPageSize;
  page.value = 1;
  fetchTasks();
};

const onExecutionPageChange = (nextPage: number) => {
  executionPage.value = nextPage;
  fetchExecutions();
};

const handleCreate = () => {
  if (!canCreateTask.value) {
    Message.warning(pageText.value.noCreatePermission);
    return;
  }
  formModalRef.value?.open();
};

const handleEdit = (task: ScheduledTask) => {
  if (!canEditTask.value) {
    Message.warning(pageText.value.noEditPermission);
    return;
  }
  formModalRef.value?.open(task);
};

const handleToggleStatus = async (task: ScheduledTask, enabled: boolean) => {
  if (!canEditTask.value) {
    Message.warning(pageText.value.noTogglePermission);
    return;
  }

  try {
    if (enabled) {
      await enableTask(currentProjectId.value!, task.id);
      Message.success(pageText.value.taskEnabled);
    } else {
      await disableTask(currentProjectId.value!, task.id);
      Message.success(pageText.value.taskDisabled);
    }
    fetchTasks();
  } catch (error: any) {
    Message.error(error.response?.data?.error || pageText.value.operationFailed);
  }
};

const handleRunNow = async (task: ScheduledTask) => {
  if (!canEditTask.value) {
    Message.warning(pageText.value.noRunPermission);
    return;
  }

  try {
    await runTaskNow(currentProjectId.value!, task.id);
    Message.success(pageText.value.taskSubmitted);
    fetchTasks();
  } catch (error: any) {
    Message.error(error.response?.data?.error || pageText.value.runFailed);
  }
};

const handleDelete = async (task: ScheduledTask) => {
  if (!canDeleteTask.value) {
    Message.warning(pageText.value.noDeletePermission);
    return;
  }

  try {
    await deleteTask(currentProjectId.value!, task.id);
    Message.success(pageText.value.taskDeleted);
    fetchTasks();
  } catch {
    Message.error(pageText.value.deleteFailed);
  }
};

const handleViewExecutions = (task: ScheduledTask) => {
  if (!canViewExecutionRecords.value) {
    Message.warning(pageText.value.noViewExecutionPermission);
    return;
  }

  currentTask.value = task;
  executionPage.value = 1;
  executionDrawerVisible.value = true;
  fetchExecutions();
};

const handleViewLog = (execution: TaskExecution) => {
  logModalRef.value?.open(execution.id);
};

const handleDeleteExecution = async (execution: TaskExecution) => {
  if (!canDeleteExecution.value) {
    Message.warning(pageText.value.noDeleteExecutionPermission);
    return;
  }

  try {
    await deleteExecution(currentProjectId.value!, execution.id);
    Message.success(pageText.value.recordDeleted);
    fetchExecutions();
  } catch {
    Message.error(pageText.value.deleteFailed);
  }
};

watch(currentProjectId, (newId, oldId) => {
  if (newId !== oldId && canViewTaskCenter.value) {
    page.value = 1;
    searchKeyword.value = '';
    statusFilter.value = undefined;
    moduleFilter.value = undefined;
    fetchTasks();
  }
}, { immediate: false });

watch(canViewTaskCenter, (canView) => {
  if (canView && currentProjectId.value) {
    fetchTasks();
  }
});

onMounted(() => {
  if (canViewTaskCenter.value && currentProjectId.value) {
    fetchTasks();
  }
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

.no-permission {
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
  gap: 12px;
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

.action-placeholder {
  color: var(--color-text-3);
}

@media (max-width: 768px) {
  .task-center {
    padding: 12px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .page-title {
    font-size: 20px;
  }
}
</style>
