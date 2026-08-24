<template>
  <a-modal
    v-model:visible="visible"
    :title="modalText.title"
    :width="700"
    :mask-closable="false"
    @cancel="handleCancel"
  >
    <template #footer>
      <a-space>
        <span class="selected-count">{{ selectedCountText }}</span>
        <a-button @click="handleCancel">{{ modalText.cancel }}</a-button>
        <a-button type="primary" @click="handleConfirm" :disabled="selectedKeys.length === 0">{{ modalText.confirm }}</a-button>
      </a-space>
    </template>

    <div class="filter-row">
      <a-input-search
        v-model="searchText"
        :placeholder="modalText.searchCaseName"
        allow-clear
        style="width: 220px"
        @search="loadData"
        @clear="loadData"
      />
      <a-select
        v-model="moduleFilter"
        :placeholder="modalText.filterModule"
        allow-clear
        style="width: 160px"
        @change="loadData"
      >
        <a-option v-for="module in modules" :key="module.id" :value="module.id">{{ module.name }}</a-option>
      </a-select>
    </div>

    <a-table
      :key="`ui-case-select-table-${locale}`"
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
import { ref, reactive, computed } from 'vue';
import { testCaseApi, moduleApi } from '@/features/ui-automation/api';
import { useAppI18n } from '@/composables/useAppI18n';
import { normalizeListPayload } from '@/features/api-testing/services/responseHelpers';

const props = defineProps<{
  projectId: number;
}>();

const emit = defineEmits<{
  (e: 'confirm', ids: number[]): void;
}>();

const { locale, isEnglish } = useAppI18n();

const modalText = computed(() => (
  isEnglish.value
    ? {
        title: 'Select UI Cases',
        selectedCount: (count: number) => `${count} case(s) selected`,
        cancel: 'Cancel',
        confirm: 'Confirm',
        searchCaseName: 'Search case name',
        filterModule: 'Filter module',
        caseName: 'Case Name',
        module: 'Module',
        level: 'Level',
      }
    : {
        title: '选择UI用例',
        selectedCount: (count: number) => `已选 ${count} 个用例`,
        cancel: '取消',
        confirm: '确定',
        searchCaseName: '搜索用例名称',
        filterModule: '筛选模块',
        caseName: '用例名称',
        module: '模块',
        level: '级别',
      }
));

const visible = ref(false);
const loading = ref(false);
const testCases = ref<any[]>([]);
const modules = ref<{ id: number; name: string }[]>([]);
const selectedKeys = ref<number[]>([]);
const searchText = ref('');
const moduleFilter = ref<number | undefined>(undefined);
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showTotal: true });

const levelColors: Record<string, string> = {
  P0: 'red',
  P1: 'orangered',
  P2: 'orange',
  P3: 'blue',
};

const selectedCountText = computed(() => modalText.value.selectedCount(selectedKeys.value.length));

const columns = computed(() => [
  { title: modalText.value.caseName, dataIndex: 'name', ellipsis: true },
  { title: modalText.value.module, dataIndex: 'module_name', width: 120 },
  { title: modalText.value.level, slotName: 'level', width: 80 },
]);

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
    const { results, count } = normalizeListPayload(data);
    testCases.value = results;
    pagination.total = count;
  } catch {
    testCases.value = [];
    pagination.total = 0;
  } finally {
    loading.value = false;
  }
};

const loadModules = async () => {
  try {
    const res = await moduleApi.list({ project: props.projectId });
    const data = (res as any).data?.data;
    const list = data?.results || (Array.isArray(data) ? data : []);
    modules.value = list.map((module: any) => ({ id: module.id, name: module.name }));
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
  flex-wrap: wrap;
}

.selected-count {
  color: var(--color-text-3);
  font-size: 13px;
  margin-right: 8px;
}
</style>
