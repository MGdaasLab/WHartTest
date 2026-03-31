<template>
  <a-modal
    v-model:visible="visible"
    :title="isEditing ? '编辑定时任务' : '新建定时任务'"
    :width="720"
    :mask-closable="false"
    @cancel="handleClose"
  >
    <template #footer>
      <a-space>
        <a-button @click="handleClose">取消</a-button>
        <a-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ isEditing ? '保存' : '保存，默认未启用' }}
        </a-button>
      </a-space>
    </template>

    <div class="form-scroll-area">
      <a-form :model="form" layout="vertical" ref="formRef" size="small">
        <a-form-item label="任务名称" field="name" :rules="[{ required: true, message: '请输入任务名称' }]">
          <a-input v-model="form.name" placeholder="如 UI-登录页-每日" :max-length="50" show-word-limit />
        </a-form-item>

        <a-form-item label="任务描述" field="description">
          <a-textarea v-model="form.description" placeholder="用于说明任务目的" :max-length="200" :auto-size="{ minRows: 2, maxRows: 3 }" />
        </a-form-item>

        <!-- 所属模块 + UI用例选择 同行 -->
        <div class="form-row">
          <a-form-item label="所属模块" field="module" :rules="[{ required: true, message: '请选择' }]">
            <a-select v-model="form.module" placeholder="请选择模块" @change="onModuleChange">
              <a-option value="ui_automation">UI 自动化</a-option>
              <a-option value="test_suite">测试套件</a-option>
            </a-select>
          </a-form-item>

          <a-form-item
            v-if="form.module === 'ui_automation'"
            label="选择UI用例"
            field="ui_testcase_ids"
            :rules="[{ required: true, message: '请选择至少一个UI用例' }]"
          >
            <a-button type="outline" size="small" @click="openCaseSelectModal">
              <template #icon><icon-select-all /></template>
              {{ form.ui_testcase_ids.length ? `已选 ${form.ui_testcase_ids.length} 个用例` : '选择用例' }}
            </a-button>
          </a-form-item>

          <a-form-item
            v-if="form.module === 'test_suite'"
            label="选择测试套件"
            field="test_suite"
            :rules="[{ required: true, message: '请选择测试套件' }]"
          >
            <a-select v-model="form.test_suite" placeholder="请选择" :loading="loadingSuites" allow-search @popup-visible-change="(v: boolean) => v && loadTestSuites()">
              <a-option v-for="s in testSuites" :key="s.id" :value="s.id">{{ s.name }}</a-option>
            </a-select>
          </a-form-item>
        </div>

        <!-- 执行器 + 调度策略 + 执行时间 同行 -->
        <div v-if="form.module === 'ui_automation'" class="form-row-3">
          <a-form-item
            label="执行器"
            field="actuator_id"
            :rules="[{ required: true, message: '请选择执行器' }]"
          >
            <a-select v-model="form.actuator_id" placeholder="请选择执行器" :loading="loadingActuators" allow-search @popup-visible-change="(v: boolean) => v && loadActuators()">
              <a-option v-for="a in actuators" :key="a.id" :value="a.id">
                {{ a.name || a.id }} ({{ a.ip }})
              </a-option>
            </a-select>
          </a-form-item>
          <a-form-item label="调度策略" field="schedule_type" :rules="[{ required: true, message: '请选择' }]">
            <a-select v-model="form.schedule_type" placeholder="请选择">
              <a-option value="once">仅一次</a-option>
              <a-option value="daily">每天</a-option>
              <a-option value="weekly">每周</a-option>
              <a-option value="hourly">每小时</a-option>
            </a-select>
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'once'" label="执行时间" field="once_datetime" :rules="[{ required: true, message: '请选择' }]">
            <a-date-picker v-model="form.once_datetime" show-time format="YYYY-MM-DD HH:mm" placeholder="选择时间" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'daily'" label="执行时间" field="daily_time" :rules="[{ required: true, message: '请选择' }]">
            <a-time-picker v-model="form.daily_time" format="HH:mm" placeholder="选择时间" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'hourly'" label="第几分钟执行" field="hourly_minute" :rules="[{ required: true, message: '请输入' }]">
            <a-input-number v-model="form.hourly_minute" :min="0" :max="59" placeholder="0-59" style="width: 100%">
              <template #suffix>分</template>
            </a-input-number>
          </a-form-item>
        </div>

        <!-- 非UI自动化模块：调度策略 + 执行时间 同行 -->
        <div v-if="form.module !== 'ui_automation'" class="form-row">
          <a-form-item label="调度策略" field="schedule_type" :rules="[{ required: true, message: '请选择' }]">
            <a-select v-model="form.schedule_type" placeholder="请选择">
              <a-option value="once">仅一次</a-option>
              <a-option value="daily">每天</a-option>
              <a-option value="weekly">每周</a-option>
              <a-option value="hourly">每小时</a-option>
            </a-select>
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'once'" label="执行时间" field="once_datetime" :rules="[{ required: true, message: '请选择' }]">
            <a-date-picker v-model="form.once_datetime" show-time format="YYYY-MM-DD HH:mm" placeholder="选择时间" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'daily'" label="执行时间" field="daily_time" :rules="[{ required: true, message: '请选择' }]">
            <a-time-picker v-model="form.daily_time" format="HH:mm" placeholder="选择时间" style="width: 100%" />
          </a-form-item>
          <a-form-item v-if="form.schedule_type === 'hourly'" label="第几分钟执行" field="hourly_minute" :rules="[{ required: true, message: '请输入' }]">
            <a-input-number v-model="form.hourly_minute" :min="0" :max="59" placeholder="0-59" style="width: 100%">
              <template #suffix>分</template>
            </a-input-number>
          </a-form-item>
        </div>
        <!-- 每周额外显示星期选择和时间 -->
        <template v-if="form.schedule_type === 'weekly'">
          <a-form-item label="选择星期" field="weekly_days" :rules="[{ required: true, message: '请至少选一天' }]">
            <a-checkbox-group v-model="form.weekly_days">
              <a-checkbox v-for="day in weekDayOptions" :key="day.value" :value="day.value">{{ day.label }}</a-checkbox>
            </a-checkbox-group>
          </a-form-item>
          <a-form-item label="执行时间" field="weekly_time" :rules="[{ required: true, message: '请选择' }]">
            <a-time-picker v-model="form.weekly_time" format="HH:mm" placeholder="选择时间" style="width: 100%" />
          </a-form-item>
        </template>

        <!-- 重试策略 -->
        <a-form-item label="失败重试">
          <a-switch v-model="form.retry_enabled" />
        </a-form-item>
        <div v-if="form.retry_enabled" class="retry-config">
          <a-form-item label="重试次数">
            <a-input-number v-model="form.retry_count" :min="1" :max="5" style="width: 100%" />
          </a-form-item>
          <a-form-item label="重试间隔">
            <a-input-number v-model="form.retry_interval" :min="1" :max="30" style="width: 100%">
              <template #suffix>分</template>
            </a-input-number>
          </a-form-item>
        </div>
      </a-form>
    </div>
  </a-modal>
  <UiTestCaseSelectModal ref="caseSelectModal" :project-id="projectId" @confirm="onCaseSelected" />
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { Message } from '@arco-design/web-vue';
import axios from 'axios';
import { API_BASE_URL } from '@/config/api';
import { useAuthStore } from '@/store/authStore';
import { createTask, updateTask, type TaskFormData, type ScheduledTask } from '../services/taskService';
import { actuatorApi, type ActuatorInfo } from '@/features/ui-automation/api';
import UiTestCaseSelectModal from './UiTestCaseSelectModal.vue';

const props = defineProps<{
  projectId: number;
}>();

const emit = defineEmits<{
  (e: 'success'): void;
}>();

const visible = ref(false);
const submitting = ref(false);
const isEditing = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref();

// 下拉数据
const loadingSuites = ref(false);
const loadingActuators = ref(false);
const testSuites = ref<{ id: number; name: string }[]>([]);
const actuators = ref<ActuatorInfo[]>([]);
const caseSelectModal = ref<InstanceType<typeof UiTestCaseSelectModal>>();

const weekDayOptions = [
  { value: 0, label: '周一' },
  { value: 1, label: '周二' },
  { value: 2, label: '周三' },
  { value: 3, label: '周四' },
  { value: 4, label: '周五' },
  { value: 5, label: '周六' },
  { value: 6, label: '周日' },
];

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
  test_suite: null,
  ui_testcase_ids: [],
  actuator_id: '',
});

const form = reactive<TaskFormData>(defaultForm());

const getHeaders = () => {
  const authStore = useAuthStore();
  return { Authorization: `Bearer ${authStore.getAccessToken}` };
};

const loadTestSuites = async () => {
  loadingSuites.value = true;
  try {
    const response = await axios.get(`${API_BASE_URL}/projects/${props.projectId}/test-suites/`, {
      headers: getHeaders(),
    });
    const resData = response.data;
    let list: any[] = [];
    if (resData?.status === 'success') {
      list = Array.isArray(resData.data) ? resData.data : resData.data?.results || [];
    } else {
      list = resData?.results || resData?.data || [];
    }
    testSuites.value = list.map((s: any) => ({ id: s.id, name: s.name }));
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
    actuators.value = (innerData?.items || []).filter((a: ActuatorInfo) => a.is_open);
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
      Message.success('任务已更新');
    } else {
      await createTask(props.projectId, { ...form });
      Message.success('任务已创建');
    }
    visible.value = false;
    emit('success');
  } catch (error: any) {
    const msg = error.response?.data?.detail || error.response?.data?.error || '操作失败';
    Message.error(typeof msg === 'string' ? msg : JSON.stringify(msg));
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

.flex-1 {
  flex: 1;
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
