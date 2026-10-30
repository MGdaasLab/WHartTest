<template>
  <a-modal
    v-model:visible="visible"
    :title="modalTitle"
    :width="720"
    :mask-closable="false"
    @cancel="handleClose"
  >
    <template #footer>
      <a-space>
        <a-button @click="handleClose">{{ modalText.cancel }}</a-button>
        <a-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ modalText.save }}
        </a-button>
      </a-space>
    </template>

    <div class="form-scroll-area">
      <a-form :model="form" layout="vertical" ref="formRef" size="small">
        <a-form-item :label="modalText.taskName" field="name" :rules="[{ required: true, message: modalText.enterTaskName }]">
          <a-input v-model="form.name" :placeholder="modalText.taskNamePlaceholder" :max-length="50" show-word-limit />
        </a-form-item>

        <a-form-item :label="modalText.taskDescription" field="description">
          <a-textarea v-model="form.description" :placeholder="modalText.taskDescriptionPlaceholder" :max-length="200" :auto-size="{ minRows: 2, maxRows: 3 }" />
        </a-form-item>

        <div class="form-row">
          <a-form-item :label="modalText.module" field="module" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-select v-model="form.module" :placeholder="modalText.selectModule" @change="onModuleChange">
              <a-option value="ui_automation">{{ modalText.uiAutomation }}</a-option>
              <a-option value="test_suite">{{ modalText.testSuite }}</a-option>
            </a-select>
          </a-form-item>

          <a-form-item
            v-if="form.module === 'ui_automation'"
            :label="modalText.selectUiCase"
            field="ui_testcase_ids"
            :rules="[{ required: true, message: modalText.selectAtLeastOneUiCase }]"
          >
            <a-button type="outline" size="small" @click="openCaseSelectModal">
              <template #icon><icon-select-all /></template>
              {{ selectedUiCasesText }}
            </a-button>
          </a-form-item>

          <a-form-item
            v-if="form.module === 'test_suite'"
            :label="modalText.selectTestSuite"
            field="test_suite"
            :rules="[{ required: true, message: modalText.selectTestSuiteRequired }]"
          >
            <a-select
              v-model="form.test_suite"
              :placeholder="modalText.selectValue"
              :loading="loadingSuites"
              allow-search
              @popup-visible-change="(v: boolean) => v && loadTestSuites()"
            >
              <a-option v-for="suite in testSuites" :key="suite.id" :value="suite.id">{{ suite.name }}</a-option>
            </a-select>
          </a-form-item>
        </div>

        <div v-if="form.module === 'ui_automation'" class="form-row-3">
          <a-form-item
            :label="modalText.actuator"
            field="actuator_id"
            :rules="[{ required: true, message: modalText.selectActuatorRequired }]"
          >
            <a-select
              v-model="form.actuator_id"
              :placeholder="modalText.selectActuator"
              :loading="loadingActuators"
              allow-search
              @popup-visible-change="(v: boolean) => v && loadActuators()"
            >
              <a-option v-for="actuator in actuators" :key="actuator.id" :value="actuator.id">
                {{ actuator.name || actuator.id }} ({{ actuator.ip }})
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item :label="modalText.scheduleType" field="schedule_type" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-select v-model="form.schedule_type" :placeholder="modalText.selectValue">
              <a-option v-for="option in scheduleOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'once'" :label="modalText.executionTime" field="once_datetime" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-date-picker v-model="form.once_datetime" show-time format="YYYY-MM-DD HH:mm" :placeholder="modalText.selectTime" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'daily'" :label="modalText.executionTime" field="daily_time" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-time-picker v-model="form.daily_time" format="HH:mm" :placeholder="modalText.selectTime" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'hourly'" :label="modalText.hourlyMinute" field="hourly_minute" :rules="[{ required: true, message: modalText.enterValue }]">
            <a-input-number v-model="form.hourly_minute" :min="0" :max="59" placeholder="0-59" style="width: 100%">
              <template #suffix>{{ modalText.minuteSuffix }}</template>
            </a-input-number>
          </a-form-item>
        </div>

        <div v-if="form.module !== 'ui_automation'" class="form-row">
          <a-form-item :label="modalText.scheduleType" field="schedule_type" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-select v-model="form.schedule_type" :placeholder="modalText.selectValue">
              <a-option v-for="option in scheduleOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'once'" :label="modalText.executionTime" field="once_datetime" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-date-picker v-model="form.once_datetime" show-time format="YYYY-MM-DD HH:mm" :placeholder="modalText.selectTime" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'daily'" :label="modalText.executionTime" field="daily_time" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-time-picker v-model="form.daily_time" format="HH:mm" :placeholder="modalText.selectTime" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'hourly'" :label="modalText.hourlyMinute" field="hourly_minute" :rules="[{ required: true, message: modalText.enterValue }]">
            <a-input-number v-model="form.hourly_minute" :min="0" :max="59" placeholder="0-59" style="width: 100%">
              <template #suffix>{{ modalText.minuteSuffix }}</template>
            </a-input-number>
          </a-form-item>
        </div>

        <template v-if="form.schedule_type === 'weekly'">
          <a-form-item :label="modalText.selectWeekdays" field="weekly_days" :rules="[{ required: true, message: modalText.selectAtLeastOneDay }]">
            <a-checkbox-group v-model="form.weekly_days">
              <a-checkbox v-for="day in weekDayOptions" :key="day.value" :value="day.value">{{ day.label }}</a-checkbox>
            </a-checkbox-group>
          </a-form-item>
          <a-form-item :label="modalText.executionTime" field="weekly_time" :rules="[{ required: true, message: modalText.selectValue }]">
            <a-time-picker v-model="form.weekly_time" format="HH:mm" :placeholder="modalText.selectTime" style="width: 100%" />
          </a-form-item>
        </template>

        <a-form-item :label="modalText.retryOnFailure">
          <a-switch v-model="form.retry_enabled" />
        </a-form-item>
        <div v-if="form.retry_enabled" class="retry-config">
          <a-form-item :label="modalText.retryCount">
            <a-input-number v-model="form.retry_count" :min="1" :max="5" style="width: 100%" />
          </a-form-item>
          <a-form-item :label="modalText.retryInterval">
            <a-input-number v-model="form.retry_interval" :min="1" :max="30" style="width: 100%">
              <template #suffix>{{ modalText.minuteSuffix }}</template>
            </a-input-number>
          </a-form-item>
        </div>

        <template v-if="form.module === 'ui_automation'">
          <a-form-item :label="modalText.autoHeal">
            <a-switch v-model="form.auto_heal_enabled" />
          </a-form-item>
          <div v-if="form.auto_heal_enabled" class="retry-config">
            <a-form-item :label="modalText.healCaseLimit" :help="modalText.healCaseLimitHelp">
              <a-input-number v-model="form.heal_case_limit" :min="1" :max="20" style="width: 100%" />
            </a-form-item>
          </div>
        </template>
      </a-form>
    </div>
  </a-modal>
  <UiTestCaseSelectModal ref="caseSelectModal" :project-id="projectId" @confirm="onCaseSelected" />
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconSelectAll } from '@arco-design/web-vue/es/icon';
import axios from 'axios';
import { API_BASE_URL } from '@/config/api';
import { useAuthStore } from '@/store/authStore';
import { useAppI18n } from '@/composables/useAppI18n';
import { getCurrentServerLanguage } from '@/utils/installLocaleAdapters';
import { createTask, updateTask, type TaskFormData, type ScheduledTask } from '../services/taskService';
import { actuatorApi, type ActuatorInfo } from '@/features/ui-automation/api';
import UiTestCaseSelectModal from './UiTestCaseSelectModal.vue';

const props = defineProps<{
  projectId: number;
}>();

const emit = defineEmits<{
  (e: 'success'): void;
}>();

const { isEnglish } = useAppI18n();

const modalText = computed(() => (
  isEnglish.value
    ? {
        editTask: 'Edit Scheduled Task',
        createTask: 'Create Scheduled Task',
        cancel: 'Cancel',
        save: 'Save',
        taskName: 'Task Name',
        enterTaskName: 'Enter task name',
        taskNamePlaceholder: 'Example: UI-Login-Daily',
        taskDescription: 'Task Description',
        taskDescriptionPlaceholder: 'Describe what this task is for',
        module: 'Module',
        selectModule: 'Select module',
        selectValue: 'Select',
        enterValue: 'Enter a value',
        uiAutomation: 'UI Automation',
        testSuite: 'Test Suite',
        selectUiCase: 'Select UI Cases',
        selectAtLeastOneUiCase: 'Select at least one UI case',
        selectedUiCases: (count: number) => `${count} case(s) selected`,
        chooseCases: 'Choose cases',
        selectTestSuite: 'Select Test Suite',
        selectTestSuiteRequired: 'Select a test suite',
        actuator: 'Actuator',
        selectActuator: 'Select actuator',
        selectActuatorRequired: 'Select an actuator',
        scheduleType: 'Schedule',
        once: 'Once',
        daily: 'Daily',
        weekly: 'Weekly',
        hourly: 'Hourly',
        executionTime: 'Execution Time',
        selectTime: 'Select time',
        hourlyMinute: 'Minute of the Hour',
        minuteSuffix: 'min',
        selectWeekdays: 'Weekdays',
        selectAtLeastOneDay: 'Select at least one day',
        retryOnFailure: 'Retry on Failure',
        retryCount: 'Retry Count',
        retryInterval: 'Retry Interval',
        autoHeal: 'Auto Self-Healing',
        healCaseLimit: 'Heal Case Limit',
        healCaseLimitHelp: 'Max failed cases to heal per run (extra failures are listed for manual handling)',
        monday: 'Mon',
        tuesday: 'Tue',
        wednesday: 'Wed',
        thursday: 'Thu',
        friday: 'Fri',
        saturday: 'Sat',
        sunday: 'Sun',
        taskUpdated: 'Task updated',
        taskCreated: 'Task created',
        operationFailed: 'Operation failed',
      }
    : {
        editTask: '编辑定时任务',
        createTask: '新建定时任务',
        cancel: '取消',
        save: '保存',
        taskName: '任务名称',
        enterTaskName: '请输入任务名称',
        taskNamePlaceholder: '如 UI-登录页-每日',
        taskDescription: '任务描述',
        taskDescriptionPlaceholder: '用于说明任务目的',
        module: '所属模块',
        selectModule: '请选择模块',
        selectValue: '请选择',
        enterValue: '请输入',
        uiAutomation: 'UI 自动化',
        testSuite: '测试套件',
        selectUiCase: '选择UI用例',
        selectAtLeastOneUiCase: '请选择至少一个UI用例',
        selectedUiCases: (count: number) => `已选 ${count} 个用例`,
        chooseCases: '选择用例',
        selectTestSuite: '选择测试套件',
        selectTestSuiteRequired: '请选择测试套件',
        actuator: '执行器',
        selectActuator: '请选择执行器',
        selectActuatorRequired: '请选择执行器',
        scheduleType: '调度策略',
        once: '仅一次',
        daily: '每天',
        weekly: '每周',
        hourly: '每小时',
        executionTime: '执行时间',
        selectTime: '选择时间',
        hourlyMinute: '第几分钟执行',
        minuteSuffix: '分',
        selectWeekdays: '选择星期',
        selectAtLeastOneDay: '请至少选一天',
        retryOnFailure: '失败重试',
        retryCount: '重试次数',
        retryInterval: '重试间隔',
        autoHeal: '失败自愈',
        healCaseLimit: '单次自愈用例数上限',
        healCaseLimitHelp: '一次执行最多自愈的失败用例数，超出的失败用例列入待人工确认清单',
        monday: '周一',
        tuesday: '周二',
        wednesday: '周三',
        thursday: '周四',
        friday: '周五',
        saturday: '周六',
        sunday: '周日',
        taskUpdated: '任务已更新',
        taskCreated: '任务已创建',
        operationFailed: '操作失败',
      }
));

const visible = ref(false);
const submitting = ref(false);
const isEditing = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref();

const loadingSuites = ref(false);
const loadingActuators = ref(false);
const testSuites = ref<{ id: number; name: string }[]>([]);
const actuators = ref<ActuatorInfo[]>([]);
const caseSelectModal = ref<InstanceType<typeof UiTestCaseSelectModal>>();

const scheduleOptions = computed(() => [
  { value: 'once', label: modalText.value.once },
  { value: 'daily', label: modalText.value.daily },
  { value: 'weekly', label: modalText.value.weekly },
  { value: 'hourly', label: modalText.value.hourly },
]);

const weekDayOptions = computed(() => [
  { value: 0, label: modalText.value.monday },
  { value: 1, label: modalText.value.tuesday },
  { value: 2, label: modalText.value.wednesday },
  { value: 3, label: modalText.value.thursday },
  { value: 4, label: modalText.value.friday },
  { value: 5, label: modalText.value.saturday },
  { value: 6, label: modalText.value.sunday },
]);

const defaultForm = (): TaskFormData => ({
  name: '',
  description: '',
  module: 'ui_automation',
  execution_target: 'actuator',
  schedule_type: 'daily',
  once_datetime: null,
  daily_time: null,
  weekly_days: [],
  weekly_time: null,
  hourly_minute: null,
  retry_enabled: false,
  retry_count: 3,
  retry_interval: 2,
  auto_heal_enabled: false,
  heal_case_limit: 5,
  test_suite: null,
  ui_testcase_ids: [],
  actuator_id: '',
});

const form = reactive<TaskFormData>(defaultForm());

const modalTitle = computed(() => (
  isEditing.value ? modalText.value.editTask : modalText.value.createTask
));

const selectedUiCasesText = computed(() => (
  form.ui_testcase_ids.length
    ? modalText.value.selectedUiCases(form.ui_testcase_ids.length)
    : modalText.value.chooseCases
));

const getHeaders = () => {
  const authStore = useAuthStore();
  return {
    Authorization: `Bearer ${authStore.getAccessToken}`,
    'Accept-Language': getCurrentServerLanguage(),
  };
};

const loadTestSuites = async () => {
  loadingSuites.value = true;
  try {
    const response = await axios.get(`${API_BASE_URL}/projects/${props.projectId}/test-suites/`, {
      headers: getHeaders(),
    });
    const responseData = response.data;
    let list: any[] = [];
    if (responseData?.status === 'success') {
      list = Array.isArray(responseData.data) ? responseData.data : responseData.data?.results || [];
    } else {
      list = responseData?.results || responseData?.data || [];
    }
    testSuites.value = list.map((suite: any) => ({ id: suite.id, name: suite.name }));
  } catch {
    testSuites.value = [];
  } finally {
    loadingSuites.value = false;
  }
};

const loadActuators = async () => {
  loadingActuators.value = true;
  try {
    const res = await actuatorApi.list();
    const innerData = (res as any).data?.data?.data;
    actuators.value = (innerData?.items || []).filter((actuator: ActuatorInfo) => actuator.is_open);
  } catch {
    actuators.value = [];
  } finally {
    loadingActuators.value = false;
  }
};

const onModuleChange = () => {
  form.test_suite = null;
  form.ui_testcase_ids = [];
  form.actuator_id = '';
  // 失败自愈仅支持 UI 自动化任务，切换模块时关闭避免残留无效配置
  form.auto_heal_enabled = false;
};

const resetForm = () => {
  Object.assign(form, defaultForm());
};

const openCaseSelectModal = () => {
  caseSelectModal.value?.open(form.ui_testcase_ids);
};

const onCaseSelected = (ids: number[]) => {
  form.ui_testcase_ids = ids;
};

const open = (task?: ScheduledTask) => {
  resetForm();

  if (task) {
    isEditing.value = true;
    editingId.value = task.id;
    Object.assign(form, {
      name: task.name,
      description: task.description,
      module: task.module,
      execution_target: task.execution_target,
      schedule_type: task.schedule_type,
      once_datetime: task.once_datetime,
      daily_time: task.daily_time,
      weekly_days: task.weekly_days || [],
      weekly_time: task.weekly_time,
      hourly_minute: task.hourly_minute,
      retry_enabled: task.retry_enabled,
      retry_count: task.retry_count,
      retry_interval: task.retry_interval,
      auto_heal_enabled: task.auto_heal_enabled ?? false,
      heal_case_limit: task.heal_case_limit ?? 5,
      test_suite: task.test_suite,
      ui_testcase_ids: task.ui_testcase_ids || [],
      actuator_id: task.actuator_id || '',
    });
  } else {
    isEditing.value = false;
    editingId.value = null;
  }
  visible.value = true;
};

const handleSubmit = async () => {
  const errors = await formRef.value?.validate();
  if (errors) return;

  submitting.value = true;
  try {
    if (isEditing.value && editingId.value) {
      await updateTask(props.projectId, editingId.value, { ...form });
      Message.success(modalText.value.taskUpdated);
    } else {
      await createTask(props.projectId, { ...form });
      Message.success(modalText.value.taskCreated);
    }
    visible.value = false;
    emit('success');
  } catch (error: any) {
    const message = error.response?.data?.detail || error.response?.data?.error || modalText.value.operationFailed;
    Message.error(typeof message === 'string' ? message : JSON.stringify(message));
  } finally {
    submitting.value = false;
  }
};

const handleClose = () => {
  visible.value = false;
  resetForm();
};

defineExpose({ open });
</script>

<style scoped>
.form-scroll-area {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.form-row-3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}

.retry-config {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding: 12px;
  background: var(--color-fill-1);
  border-radius: 8px;
  margin-bottom: 16px;
}

.retry-config :deep(.arco-form-item) {
  margin-bottom: 0;
}

.form-scroll-area :deep(.arco-form-item) {
  margin-bottom: 12px;
}
</style>
