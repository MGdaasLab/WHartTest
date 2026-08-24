<template>
  <a-modal
    :visible="visible"
    :title="tl('操作日志自动清理设置')"
    :ok-loading="saving"
    :ok-button-props="{ disabled: !canEdit }"
    :cancel-button-props="{ disabled: saving }"
    @ok="handleSave"
    @cancel="closeModal"
  >
    <a-spin :loading="loading" style="width: 100%">
      <div class="cleanup-settings-modal">
        <a-alert type="info" show-icon class="settings-alert">
          {{ tl('系统会每天凌晨 3 点自动清理超过保留天数的操作日志，默认保留 7 天。') }}
        </a-alert>

        <a-form layout="vertical">
          <a-form-item :label="tl('自动清理保留天数')">
            <a-radio-group v-model="retentionMode" direction="vertical" :disabled="!canEdit || loading">
              <a-radio :value="7">{{ tl('7天（默认）') }}</a-radio>
              <a-radio :value="15">{{ tl('15天') }}</a-radio>
              <a-radio :value="30">{{ tl('30天') }}</a-radio>
              <a-radio value="custom">{{ tl('自定义') }}</a-radio>
            </a-radio-group>
          </a-form-item>

          <a-form-item v-if="retentionMode === 'custom'" :label="tl('自定义保留天数')">
            <a-input-number
              v-model="customRetentionDays"
              :min="1"
              :max="3650"
              :disabled="!canEdit || loading"
              mode="button"
              style="width: 180px"
            />
          </a-form-item>
        </a-form>

        <div class="current-setting-text">
          {{ tl('当前生效保留天数：') }}
          <strong>{{ effectiveRetentionDays }}</strong>
          {{ tl('天') }}
        </div>

        <a-alert v-if="!canEdit" type="warning" show-icon class="readonly-alert">
          {{ tl('您当前仅有查看权限，不能修改自动清理设置。') }}
        </a-alert>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { useAppI18n } from '@/composables/useAppI18n';
import { getOperationLogSettings, updateOperationLogSettings } from '@/services/operationLogService';

const props = defineProps<{
  visible: boolean;
  canEdit: boolean;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
  saved: [days: number];
}>();

const { tl } = useAppI18n();
const loading = ref(false);
const saving = ref(false);
const retentionMode = ref<number | 'custom'>(7);
const customRetentionDays = ref(7);
const effectiveRetentionDays = computed(() => (
  retentionMode.value === 'custom' ? customRetentionDays.value : retentionMode.value
));

const applyRetentionDays = (days?: number) => {
  const normalizedDays = Number(days || 7);
  if ([7, 15, 30].includes(normalizedDays)) {
    retentionMode.value = normalizedDays;
  } else {
    retentionMode.value = 'custom';
    customRetentionDays.value = normalizedDays;
  }
};

const loadSettings = async () => {
  loading.value = true;
  try {
    const response = await getOperationLogSettings();
    if (response.success && response.data) {
      applyRetentionDays(response.data.retention_days);
      return;
    }
    Message.error(response.error || tl('加载自动清理设置失败'));
  } catch (error: any) {
    Message.error(error.message || tl('加载自动清理设置失败'));
  } finally {
    loading.value = false;
  }
};

const closeModal = () => {
  emit('update:visible', false);
};

const handleSave = async () => {
  if (!props.canEdit) {
    closeModal();
    return;
  }

  const retentionDays = effectiveRetentionDays.value;
  if (!retentionDays || retentionDays < 1) {
    Message.warning(tl('请填写有效的保留天数'));
    return;
  }

  saving.value = true;
  try {
    const response = await updateOperationLogSettings({ retention_days: retentionDays });
    if (response.success && response.data) {
      applyRetentionDays(response.data.retention_days);
      Message.success(tl('操作日志自动清理设置已保存'));
      emit('saved', response.data.retention_days);
      closeModal();
      return;
    }
    Message.error(response.error || tl('保存自动清理设置失败'));
  } catch (error: any) {
    Message.error(error.message || tl('保存自动清理设置失败'));
  } finally {
    saving.value = false;
  }
};

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      loadSettings();
    }
  },
);
</script>

<style scoped>
.cleanup-settings-modal {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-alert,
.readonly-alert {
  border-radius: 8px;
}

.current-setting-text {
  color: var(--color-text-2);
  font-size: 14px;
}
</style>
