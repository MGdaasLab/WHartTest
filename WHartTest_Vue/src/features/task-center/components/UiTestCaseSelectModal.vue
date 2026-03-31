<template>
  <a-modal v-model:visible="visible" title="选择UI用例" :width="700" :mask-closable="false" @cancel="handleCancel">
    <template #footer>
      <a-space>
        <span class="selected-count">已选 {{ selectedKeys.length }} 个用例</span>
        <a-button @click="handleCancel">取消</a-button>
        <a-button type="primary" @click="handleConfirm" :disabled="selectedKeys.length === 0">确定</a-button>
      </a-space>
    </template>

    <!-- 搜索和筛选 -->
    <div class="filter-row">
      <a-input-search
        v-model="searchText"
        placeholder="搜索用例名称"
        allow-clear
        style="width: 220px"
        @search="loadData"
        @clear="loadData"
      />
      <a-select
        v-model="moduleFilter"
        placeholder="筛选模块"
        allow-clear
        style="width: 160px"
        @change="loadData"
      >
        <a-option v-for="m in modules" :key="m.id" :value="m.id">{{ m.name }}</a-option>
      </a-select>
    </div>

    <a-table
      :columns="columns"
      :data="testCases"
      :loading="loading"
      :pagination="pagination"
      :row-selection="{ type: 'checkbox', showCheckedAll: true }"
      v-model:selectedKeys="selectedKeys"
      row-key="id"
      size="small"
      @page-change="onPageChange"
    >
      <template #level="{ record }">
        <a-tag size="small" :color="levelColors[record.level]">{{ record.level }}</a-tag>
      </template>
    </a-table>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { testCaseApi, moduleApi } from '@/features/ui-automation/api';

const props = defineProps<{
  projectId: number;
}>();

const emit = defineEmits<{
  (e: 'confirm', ids: number[]): void;
}>();

const visible = ref(false);
const loading = ref(false);
const testCases = ref<any[]>([]);
const modules = ref<{ id: number; name: string }[]>([]);
const selectedKeys = ref<number[]>([]);
const searchText = ref('');
const moduleFilter = ref<number | undefined>(undefined);
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true });

const levelColors: Record<string, string> = {
  P0: 'red', P1: 'orangered', P2: 'orange', P3: 'blue',
};

const columns = [
  { title: '用例名称', dataIndex: 'name', ellipsis: true },
  { title: '模块', dataIndex: 'module_name', width: 120 },
  { title: '级别', slotName: 'level', width: 80 },
];

const loadData = async () => {
  loading.value = true;
  try {
    const params: Record<string, any> = { project: props.projectId };
    if (searchText.value) params.search = searchText.value;
    if (moduleFilter.value) params.module = moduleFilter.value;
    params.page = pagination.current;
    params.page_size = pagination.pageSize;

    const res = await testCaseApi.list(params);
    const data = (res as any).data?.data;
    if (data?.results) {
      testCases.value = data.results;
      pagination.total = data.count || 0;
    } else if (Array.isArray(data)) {
      testCases.value = data;
      pagination.total = data.length;
    }
  } catch {
    testCases.value = [];
  } finally {
    loading.value = false;
  }
};

const loadModules = async () => {
  try {
    const res = await moduleApi.list({ project: props.projectId });
    const data = (res as any).data?.data;
    const list = data?.results || (Array.isArray(data) ? data : []);
    modules.value = list.map((m: any) => ({ id: m.id, name: m.name }));
  } catch {
    modules.value = [];
  }
};

const onPageChange = (page: number) => {
  pagination.current = page;
  loadData();
};

const handleCancel = () => {
  visible.value = false;
};

const handleConfirm = () => {
  emit('confirm', [...selectedKeys.value]);
  visible.value = false;
};

const open = (preSelectedIds?: number[]) => {
  selectedKeys.value = preSelectedIds ? [...preSelectedIds] : [];
  pagination.current = 1;
  searchText.value = '';
  moduleFilter.value = undefined;
  visible.value = true;
  loadData();
  loadModules();
};

defineExpose({ open });
</script>

<style scoped>
.filter-row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.selected-count {
  color: var(--color-text-3);
  font-size: 13px;
  margin-right: 8px;
}
</style>
