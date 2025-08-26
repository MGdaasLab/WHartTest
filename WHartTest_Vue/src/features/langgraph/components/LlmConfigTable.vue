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
        <span v-else class="text-gray-400">未设置</span>
      </template>
      <template #provider="{ record }">
        <a-tag :color="getProviderColor(record.provider)">
          {{ getProviderLabel(record.provider) }}
        </a-tag>
      </template>
      <template #isActive="{ record }">
        <a-tag :color="record.is_active ? 'green' : 'red'">
          {{ record.is_active ? '已激活' : '未激活' }}
        </a-tag>
      </template>
      <template #actions="{ record }">
        <a-space>
          <a-button type="primary" size="small" @click="emit('edit', record)">
            <template #icon><icon-edit /></template>
            编辑
          </a-button>
          <a-popconfirm
            content="确定要删除此配置吗？此操作不可撤销。"
            type="warning"
            @ok="emit('delete', record.id)"
          >
            <a-button type="primary" status="danger" size="small">
              <template #icon><icon-delete /></template>
              删除
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
import { computed, ref, onMounted } from 'vue';
import {
  Table as ATable,
  Tag as ATag,
  Button as AButton,
  Space as ASpace,
  Popconfirm as APopconfirm,
  type TableColumnData,
  type PaginationProps,
} from '@arco-design/web-vue';
import { IconEdit, IconDelete } from '@arco-design/web-vue/es/icon';
import type { LlmConfig } from '@/features/langgraph/types/llmConfig';
import { formatDateTime } from '@/utils/formatters';
import { getProviders, type ProviderOption } from '@/features/langgraph/services/llmConfigService';

interface Props {
  configs: LlmConfig[];
  loading: boolean;
  pagination?: PaginationProps; // 可选的分页配置
}

const props = withDefaults(defineProps<Props>(), {
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
  (e: 'page-change', page: number): void;
  (e: 'page-size-change', pageSize: number): void;
}>();

const providerOptions = ref<ProviderOption[]>([]);

const getProviderLabel = (providerValue: string): string => {
  const option = providerOptions.value.find(opt => opt.value === providerValue);
  return option ? option.label : providerValue;
};

const getProviderColor = (providerValue: string): string => {
  const colorMap: Record<string, string> = {
    openai: 'blue',
    anthropic: 'purple',
    ollama: 'orange',
    gemini: 'green',
    openai_compatible: 'gray'
  };
  return colorMap[providerValue] || 'gray';
};

const loadProviders = async () => {
  try {
    const response = await getProviders();
    if (response.status === 'success' && response.data) {
      providerOptions.value = response.data.choices;
    }
  } catch (error) {
    console.error('Failed to load providers:', error);
  }
};

onMounted(() => {
  loadProviders();
});

const columns: TableColumnData[] = [
  { title: 'ID', dataIndex: 'id', width: 80, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '配置名称', dataIndex: 'config_name', width: 150, ellipsis: true, tooltip: true },
  { title: '供应商', dataIndex: 'provider', slotName: 'provider', width: 120, align: 'center' },
  { title: '模型名称', dataIndex: 'name', width: 150, ellipsis: true, tooltip: true },
  { title: 'API URL', dataIndex: 'api_url', width: 200, ellipsis: true, tooltip: true },
  { title: '系统提示词', dataIndex: 'system_prompt', slotName: 'systemPrompt', width: 200, ellipsis: true, tooltip: true },
  { title: '状态', dataIndex: 'is_active', slotName: 'isActive', width: 100, align: 'center' },
  { title: '创建时间', dataIndex: 'created_at', slotName: 'createdAt', width: 150, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '更新时间', dataIndex: 'updated_at', slotName: 'updatedAt', width: 150, sortable: { sortDirections: ['ascend', 'descend'] } },
  { title: '操作', slotName: 'actions', width: 180, align: 'center', fixed: 'right' },
];

</script>

<style scoped>
/* 可以在这里添加特定于此组件的样式 */
</style>