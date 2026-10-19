<template>
  <a-modal
    :visible="visible"
    :title="tl('选择功能用例')"
    :width="900"
    :ok-loading="false"
    @cancel="handleCancel"
    @ok="handleConfirm"
  >
    <div class="picker-layout">
      <!-- 左侧：功能模块树（单选导航） -->
      <div class="picker-tree">
        <a-input-search
          v-model="moduleSearch"
          :placeholder="tl('搜索模块')"
          size="small"
          allow-clear
          style="margin-bottom: 8px;"
        />
        <a-spin :loading="isModulesLoading" style="width: 100%;">
          <a-tree
            v-if="moduleTreeData.length"
            :key="moduleTreeKey"
            :data="moduleTreeData"
            :default-expand-all="true"
            :selected-keys="selectedModuleKeys"
            @select="handleModuleSelect"
          />
          <a-empty v-else-if="!isModulesLoading" :description="tl('暂无模块')" />
        </a-spin>
      </div>

      <!-- 右侧：用例列表（复选 + 三条件查询 + 分页） -->
      <div class="picker-list">
        <div class="picker-filters">
          <a-input-search
            v-model="filters.name"
            :placeholder="tl('用例名称')"
            size="small"
            allow-clear
            style="width: 180px;"
            @search="handleSearch"
            @press-enter="handleSearch"
          />
          <a-select
            v-model="filters.test_type"
            :placeholder="tl('测试类型')"
            size="small"
            allow-clear
            style="width: 130px;"
          >
            <a-option v-for="opt in testTypeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </a-option>
          </a-select>
          <a-select
            v-model="filters.level"
            :placeholder="tl('优先级')"
            size="small"
            allow-clear
            style="width: 100px;"
          >
            <a-option v-for="lv in ['P0', 'P1', 'P2', 'P3']" :key="lv" :value="lv">{{ lv }}</a-option>
          </a-select>
          <a-button size="small" type="primary" @click="handleSearch">{{ tl('查询') }}</a-button>
        </div>

        <div class="picker-table">
          <a-spin :loading="isCasesLoading" style="width: 100%;">
            <a-table
              :data="cases"
              :pagination="paginationConfig"
              :row-selection="{ type: 'checkbox', showCheckedAll: false, selectedRowKeys: selectedKeys, onlyCurrent: false }"
              row-key="id"
              :scroll="{ y: 300 }"
              @selection-change="handleSelectionChange"
              @page-change="handlePageChange"
              @page-size-change="handlePageSizeChange"
            >
              <template #columns>
                <a-table-column title="用例名称" data-index="name" ellipsis tooltip />
                <a-table-column title="测试类型" data-index="test_type" :width="110">
                  <template #cell="{ record }">
                    <a-tag size="small">{{ testTypeLabel(record.test_type) }}</a-tag>
                  </template>
                </a-table-column>
                <a-table-column title="优先级" data-index="level" :width="80" />
              </template>
            </a-table>
          </a-spin>
        </div>

        <div class="picker-footer-info">{{ tl('已选') }} {{ selectedCases.length }} {{ tl('条功能用例') }}</div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { useAppI18n } from '@/composables/useAppI18n';
import { useProjectStore } from '@/store/projectStore';
import { getTestCaseModules, type TestCaseModule } from '@/services/testcaseModuleService';
import { getTestCaseList } from '@/services/testcaseService';
import type { ApiModule } from '../../types/module';

const props = defineProps<{
  visible: boolean;
  initialSelected?: FunctionalCaseRef[];
}>();
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'confirm', cases: FunctionalCaseRef[]): void;
}>();

const { tl } = useAppI18n();
const projectStore = useProjectStore();

export interface FunctionalCaseRef {
  case_id: number;
  module_name: string;
  name: string;
  test_type: string;
  level: string;
}

const projectId = computed(() => projectStore.currentProjectId ?? 0);
const modules = ref<TestCaseModule[]>([]);
const isModulesLoading = ref(false);
const cases = ref<any[]>([]);
const isCasesLoading = ref(false);
const selectedModuleKeys = ref<string[]>([]);
const selectedModuleId = ref<number | null>(null);
const selectedModuleName = ref('');

const filters = reactive({ name: '', test_type: null as string | null, level: null as string | null });
const paginationConfig = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50],
});

// 跨模块保留已选：id -> 用例摘要
const selectedMap = ref(new Map<number, FunctionalCaseRef>());
const selectedCases = computed(() => Array.from(selectedMap.value.values()));
const selectedKeys = computed(() => Array.from(selectedMap.value.keys()));

const testTypeOptions = [
  { value: 'smoke', label: '冒烟测试' },
  { value: 'functional', label: '功能测试' },
  { value: 'boundary', label: '边界测试' },
  { value: 'exception', label: '异常测试' },
  { value: 'permission', label: '权限测试' },
  { value: 'security', label: '安全测试' },
  { value: 'compatibility', label: '兼容性测试' },
];

const testTypeLabel = (value: string) =>
  testTypeOptions.find(opt => opt.value === value)?.label || value;

// 模块树：扁平转树
interface TreeBtn {
  key: string;
  title: string;
  children?: TreeBtn[];
}
const moduleSearch = ref('');

const buildModuleTree = (): TreeBtn[] => {
  const map = new Map<number, TreeBtn>();
  const roots: TreeBtn[] = [];
  const items = modules.value;
  items.forEach(m => map.set(m.id, { key: `m-${m.id}`, title: m.name, children: [] }));
  items.forEach(m => {
    const node = map.get(m.id)!;
    if (m.parent && map.has(m.parent)) {
      map.get(m.parent)!.children!.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
};

const moduleTreeData = computed<TreeBtn[]>(() => {
  const kw = moduleSearch.value.trim().toLowerCase();
  const hitIds = kw
    ? new Set(modules.value.filter(m => (m.name || '').toLowerCase().includes(kw)).map(m => m.id))
    : null;
  const withHit = (nodes: TreeBtn[]): TreeBtn[] =>
    nodes
      .map(node => {
        const children = node.children ? withHit(node.children) : [];
        const selfHit = !hitIds || hitIds.has(Number(node.key.replace('m-', ''))) || children.length > 0;
        if (!selfHit) return null;
        const kept: TreeBtn = { key: node.key, title: node.title };
        if (children.length) kept.children = children;
        else if (node.children && node.children.length) kept.children = node.children;
        return kept;
      })
      .filter((n): n is TreeBtn => n !== null);
  const tree = withHit(buildModuleTree());
  // 根节点"全部模块"：默认选中，展示项目全部用例
  return [{ key: 'm-all', title: tl('全部模块'), children: tree.length ? tree : undefined }];
});

const moduleTreeKey = computed(() => `${moduleSearch.value}-${modules.value.length}`);

const fetchModules = async () => {
  isModulesLoading.value = true;
  try {
    const { getTestCaseModules } = await import('@/services/testcaseModuleService');
    const response = await getTestCaseModules(projectId.value, { page: 1, pageSize: 200 });
    if (response.success && response.data) {
      modules.value = response.data;
    }
  } catch {
    modules.value = [];
  } finally {
    isModulesLoading.value = false;
  }
};

const fetchCases = async () => {
  isCasesLoading.value = true;
  try {
    const { getTestCaseList } = await import('@/services/testcaseService');
    const response = await getTestCaseList(projectId.value, {
      page: paginationConfig.current,
      pageSize: paginationConfig.pageSize,
      search: filters.name,
      module_id: selectedModuleId.value ?? undefined,
      test_type: filters.test_type || undefined,
      level: filters.level || undefined,
    });
    if (response.success && response.data) {
      const payload: any = Array.isArray(response.data) ? response.data : (response.data as any).results || [];
      cases.value = payload;
      paginationConfig.total = (response.data as any)?.count ?? response.total ?? payload.length;
    } else {
      cases.value = [];
      paginationConfig.total = 0;
    }
  } catch {
    cases.value = [];
    paginationConfig.total = 0;
  } finally {
    isCasesLoading.value = false;
  }
};

const handleModuleSelect = (keys: Array<string | number>) => {
  const key = String(keys[0] || '');
  if (!key.startsWith('m-')) return;
  selectedModuleKeys.value = [key];
  // 'm-all' = 全部模块：不按模块过滤
  selectedModuleId.value = key === 'm-all' ? null : Number(key.replace('m-', ''));
  const mod = modules.value.find(m => m.id === selectedModuleId.value);
  selectedModuleName.value = mod?.name || '';
  paginationConfig.current = 1;
  fetchCases();
};

const handleSearch = () => {
  paginationConfig.current = 1;
  fetchCases();
};

const handlePageChange = (page: number) => {
  paginationConfig.current = page;
  fetchCases();
};

const handlePageSizeChange = (size: number) => {
  paginationConfig.pageSize = size;
  paginationConfig.current = 1;
  fetchCases();
};

const handleSelectionChange = (rowKeys: Array<string | number>) => {
  const next = new Map<number, FunctionalCaseRef>();
  // 保留其他模块已选（不在当前页的）
  const currentIds = new Set(cases.value.map(c => c.id));
  selectedMap.value.forEach((value, key) => {
    if (!currentIds.has(key)) next.set(key, value);
  });
  // 合并当前页勾选
  cases.value.forEach(c => {
    if (rowKeys.includes(c.id)) {
      next.set(c.id, {
        case_id: c.id,
        module_name: selectedModuleName.value || '',
        name: c.name,
        test_type: c.test_type,
        level: c.level,
      });
    }
  });
  selectedMap.value = next;
};

const handleConfirm = () => {
  if (!selectedCases.value.length) {
    Message.warning(tl('请至少选择一条功能用例'));
    return;
  }
  emit('confirm', selectedCases.value);
  emit('update:visible', false);
};

const handleCancel = () => {
  emit('update:visible', false);
};

watch(() => props.visible, visible => {
  if (visible) {
    // 保留用户之前勾选的用例：从父级传入的已选列表恢复勾选状态
    const restored = new Map<number, FunctionalCaseRef>();
    for (const item of props.initialSelected || []) {
      restored.set(item.case_id, item);
    }
    selectedMap.value = restored;
    selectedModuleId.value = null;
    selectedModuleName.value = '';
    filters.name = '';
    filters.test_type = null;
    filters.level = null;
    paginationConfig.current = 1;
    fetchModules().then(() => {
      // 默认选中"全部模块"节点并加载全部用例
      selectedModuleKeys.value = ['m-all'];
      fetchCases();
    });
  }
});
</script>

<style scoped>
.picker-layout {
  display: flex;
  gap: 12px;
  height: 440px;
}
.picker-tree {
  width: 200px;
  flex-shrink: 0;
  border: 1px solid var(--color-border-2);
  border-radius: 4px;
  padding: 6px;
  overflow-y: auto;
}
.picker-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.picker-filters {
  display: flex;
  gap: 8px;
  align-items: center;
}
.picker-table {
  flex: 1;
  overflow: hidden;
}
.picker-footer-info {
  font-size: 12px;
  color: var(--color-text-3);
}
</style>
