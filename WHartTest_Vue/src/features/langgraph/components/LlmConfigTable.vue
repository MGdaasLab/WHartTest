<template>
  <div>
    <a-table
      :columns="columns"
      :data="configs"
      :loading="loading"
      row-key="id"
      :pagination="pagination"
      @page-change="(page: number) => emit('page-change', page)"
      @page-size-change="(pageSize: number) => emit('page-size-change', pageSize)"
    >
      <template #systemPrompt="{ record }">
        <span v-if="record.system_prompt" :title="record.system_prompt">
          {{ record.system_prompt.length > 50 ? record.system_prompt.substring(0, 50) + '...' : record.system_prompt }}
        </span>
        <span v-else class="text-gray-400">{{ text.notSet }}</span>
      </template>
      <template #isActive="{ record }">
        <a-switch
          :model-value="record.is_active"
          :disabled="loading"
          @change="(value) => emit('toggle-active', record.id, !!value)"
        >
          <template #checked>{{ text.active }}</template>
          <template #unchecked>{{ text.inactive }}</template>
        </a-switch>
      </template>
      <template #actions="{ record }">
        <a-space>
          <a-button type="primary" size="small" @click="emit('edit', record)">
            <template #icon><icon-edit /></template>
            {{ text.edit }}
          </a-button>
          <a-popconfirm
            :content="text.deleteConfirm"
            type="warning"
            @ok="emit('delete', record.id)"
          >
            <a-button type="primary" status="danger" size="small">
              <template #icon><icon-delete /></template>
              {{ text.delete }}
            </a-button>
          </a-popconfirm>
        </a-space>
      </template>
      <template #createdAt="{ record }">
        {{ formatDateTime(record.created_at) }}
      </template>
      <template #updatedAt="{ record }">
        {{ formatDateTime(record.updated_at) }}
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import {
  Table as ATable,
  Button as AButton,
  Space as ASpace,
  Popconfirm as APopconfirm,
  Switch as ASwitch,
  type TableColumnData,
  type PaginationProps,
} from '@arco-design/web-vue';
import { IconEdit, IconDelete } from '@arco-design/web-vue/es/icon';
import { useAppI18n } from '@/composables/useAppI18n';
import type { LlmConfig } from '@/features/langgraph/types/llmConfig';
import { formatDateTime } from '@/utils/formatters';

interface Props {
  configs: LlmConfig[];
  loading: boolean;
  pagination?: PaginationProps;
}

withDefaults(defineProps<Props>(), {
  configs: () => [],
  loading: false,
  pagination: () => ({
    current: 1,
    pageSize: 10,
    total: 0,
    showTotal: true,
    showPageSize: true,
  }),
});

const emit = defineEmits<{
  (e: 'edit', config: LlmConfig): void;
  (e: 'delete', configId: number): void;
  (e: 'toggle-active', configId: number, isActive: boolean): void;
  (e: 'page-change', page: number): void;
  (e: 'page-size-change', pageSize: number): void;
}>();

const { isEnglish } = useAppI18n();

const text = computed(() => (
  isEnglish.value
    ? {
        id: 'ID',
        configName: 'Config Name',
        modelName: 'Model Name',
        apiUrl: 'API URL',
        systemPrompt: 'System Prompt',
        status: 'Status',
        createdAt: 'Created At',
        updatedAt: 'Updated At',
        actions: 'Actions',
        active: 'Active',
        inactive: 'Inactive',
        edit: 'Edit',
        delete: 'Delete',
        deleteConfirm: 'Delete this config? This action cannot be undone.',
        notSet: 'Not set',
      }
    : {
        id: 'ID',
        configName: '配置名称',
        modelName: '模型名称',
        apiUrl: 'API URL',
        systemPrompt: '系统提示词',
        status: '状态',
        createdAt: '创建时间',
        updatedAt: '更新时间',
        actions: '操作',
        active: '已激活',
        inactive: '未激活',
        edit: '编辑',
        delete: '删除',
        deleteConfirm: '确定要删除此配置吗？此操作不可撤销。',
        notSet: '未设置',
      }
));

const columns = computed<TableColumnData[]>(() => [
  { title: text.value.id, dataIndex: 'id', width: isEnglish.value ? 90 : 80, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: text.value.configName, dataIndex: 'config_name', width: 170, ellipsis: true, tooltip: true },
  { title: text.value.modelName, dataIndex: 'name', width: 170, ellipsis: true, tooltip: true },
  { title: text.value.apiUrl, dataIndex: 'api_url', width: 220, ellipsis: true, tooltip: true },
  { title: text.value.systemPrompt, dataIndex: 'system_prompt', slotName: 'systemPrompt', width: 220, ellipsis: true, tooltip: true },
  { title: text.value.status, dataIndex: 'is_active', slotName: 'isActive', width: 110, align: 'center' as const },
  { title: text.value.createdAt, dataIndex: 'created_at', slotName: 'createdAt', width: 170, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: text.value.updatedAt, dataIndex: 'updated_at', slotName: 'updatedAt', width: 170, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: text.value.actions, slotName: 'actions', width: isEnglish.value ? 250 : 220, align: 'center', fixed: 'right' as const },
]);
</script>

<style scoped>
.text-gray-400 {
  color: var(--color-text-3);
}
</style>
