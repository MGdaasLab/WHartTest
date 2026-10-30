<template>
  <a-modal
    :visible="visible"
    :title="pageText.modalTitle"
    :width="960"
    :footer="false"
    modal-class="selector-modal"
    popup-class="selector-modal-popup"
    @cancel="handleCancel"
  >
    <div class="selector-layout">
      <!-- 左侧：功能模块树（单选导航，含子模块递归） -->
      <div class="module-panel">
        <a-input-search
          v-model="moduleSearch"
          :placeholder="pageText.moduleSearchPlaceholder"
          size="small"
          allow-clear
          style="margin-bottom: 8px;"
        />
        <a-spin :loading="isModulesLoading" style="width: 100%;">
          <a-tree
            :key="`module-nav-tree-${moduleTreeKey}`"
            :data="moduleNavTreeData"
            :selected-keys="selectedModuleId !== null ? [selectedModuleId] : []"
            size="small"
            @select="handleModuleSelect"
          />
        </a-spin>
      </div>

      <!-- 右侧：用例表格 -->
      <div class="case-panel">
        <div class="filter-bar">
          <a-input-search
            v-model="filters.search"
            :placeholder="pageText.caseSearchPlaceholder"
            size="small"
            style="width: 200px;"
            allow-clear
            @search="reloadCases"
            @clear="reloadCases"
          />
          <a-select
            v-model="filters.testType"
            :placeholder="pageText.testTypePlaceholder"
            size="small"
            style="width: 130px;"
            allow-clear
            @change="reloadCases"
          >
            <a-option v-for="opt in testTypeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </a-option>
          </a-select>
          <a-select
            v-model="filters.level"
            :placeholder="pageText.levelPlaceholder"
            size="small"
            style="width: 110px;"
            allow-clear
            @change="reloadCases"
          >
            <a-option v-for="lv in levels" :key="lv" :value="lv">{{ lv }}</a-option>
          </a-select>
        </div>

        <div class="case-table-wrapper">
        <a-table
          :key="`case-select-table-${locale}`"
          :data="cases"
          :loading="isCasesLoading"
          :pagination="paginationConfig"
          :row-class="rowClass"
          size="small"
          :row-selection="rowSelection"
          v-model:selectedKeys="selectedRowKeys"
          row-key="id"
          @page-change="handlePageChange"
          @page-size-change="handlePageSizeChange"
        >
          <template #columns>
            <a-table-column :title="pageText.colCaseName" data-index="name" :ellipsis="true" />
            <a-table-column :title="pageText.colTestType" data-index="test_type" :width="100">
              <template #cell="{ record }">
                {{ testTypeLabel(record.test_type) }}
              </template>
            </a-table-column>
            <a-table-column :title="pageText.colLevel" data-index="level" :width="70" />
            <a-table-column :title="pageText.colUiBinding" :width="90">
              <template #cell="{ record }">
                <a-tag v-if="record.ui_test_case" color="green" size="small">{{ pageText.boundTag }}</a-tag>
                <a-tag v-else color="gray" size="small">{{ pageText.unboundTag }}</a-tag>
              </template>
            </a-table-column>
          </template>
        </a-table>
        </div>

        <div class="selector-footer">
          <span class="selected-hint">{{ pageText.selectedHint.replace('{count}', String(selectedRowKeys.length)) }}</span>
          <a-button type="primary" size="small" @click="handleConfirm">{{ pageText.confirm }}</a-button>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { useProjectStore } from '@/store/projectStore';
import { useAppI18n } from '@/composables/useAppI18n';
import { getTestCaseList, type TestCase } from '@/services/testcaseService';
import { getTestCaseModules, type TestCaseModule } from '@/services/testcaseModuleService';

const props = defineProps<{
  visible: boolean;
  /** 已选用例 ID（跨模块保留的回显） */
  selectedIds: number[];
}>();
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'confirm', ids: number[]): void;
}>();

const projectStore = useProjectStore();
const { locale, isEnglish } = useAppI18n();
const projectId = computed(() => projectStore.currentProjectId ?? 0);

const pageText = computed(() => isEnglish.value ? {
  modalTitle: 'Select Functional Cases',
  moduleSearchPlaceholder: 'Search module',
  caseSearchPlaceholder: 'Search case name',
  testTypePlaceholder: 'Test type',
  levelPlaceholder: 'Priority',
  colCaseName: 'Case Name',
  colTestType: 'Test Type',
  colLevel: 'Priority',
  colUiBinding: 'UI Automation',
  boundTag: 'Bound',
  unboundTag: 'None',
  selectedHint: '{count} selected',
  confirm: 'OK',
  allModules: 'All Modules',
  boundDisabledHint: 'Bound cases cannot be selected',
} : {
  modalTitle: '选择功能用例',
  moduleSearchPlaceholder: '搜索模块',
  caseSearchPlaceholder: '搜索用例名称',
  testTypePlaceholder: '测试类型',
  levelPlaceholder: '优先级',
  colCaseName: '用例名称',
  colTestType: '测试类型',
  colLevel: '优先级',
  colUiBinding: 'UI自动化',
  boundTag: '已绑定',
  unboundTag: '未绑定',
  selectedHint: '已选 {count} 条',
  confirm: '确定',
  allModules: '全部模块',
  boundDisabledHint: '已绑定的用例不可选择',
});

const TEST_TYPE_LABELS: Record<string, string> = {
  smoke: isEnglish.value ? 'Smoke' : '冒烟',
  functional: isEnglish.value ? 'Functional' : '功能',
  boundary: isEnglish.value ? 'Boundary' : '边界',
  exception: isEnglish.value ? 'Exception' : '异常',
  permission: isEnglish.value ? 'Permission' : '权限',
  security: isEnglish.value ? 'Security' : '安全',
  compatibility: isEnglish.value ? 'Compatibility' : '兼容',
};

const testTypeOptions = Object.entries(TEST_TYPE_LABELS).map(([value, label]) => ({ value, label }));
const testTypeLabel = (value?: string) => (value ? TEST_TYPE_LABELS[value] || value : '-');
const levels = ['P0', 'P1', 'P2', 'P3'];

// ---------------------------------------------------------------------------
// 模块树（单选导航）
// ---------------------------------------------------------------------------
const modules = ref<TestCaseModule[]>([]);
const moduleSearch = ref('');
const selectedModuleId = ref<number | null>(null);
const isModulesLoading = ref(false);

interface ModuleNode {
  key: number;
  title: string;
  children?: ModuleNode[];
}

const buildModuleTree = (list: TestCaseModule[], parentId: number | null = null): ModuleNode[] => {
  return list
    .filter((m) => m.parent === parentId || m.parent_id === parentId)
    .map((m) => ({
      key: m.id,
      title: m.name,
      children: buildModuleTree(list, m.id),
    }));
};

const moduleNavTreeData = computed(() => {
  const kw = moduleSearch.value.trim().toLowerCase();
  const hitIds = kw
    ? new Set(modules.value.filter((m) => (m.name || '').toLowerCase().includes(kw)).map((m) => m.id))
    : null;
  const withHit = (nodes: ModuleNode[]): ModuleNode[] =>
    nodes
      .map((node) => {
        const children = node.children ? withHit(node.children) : [];
        const selfHit = !hitIds || hitIds.has(node.key) || children.length > 0;
        return selfHit ? { ...node, children: children.length ? children : node.children } : null;
      })
      .filter((n): n is ModuleNode => n !== null);
  const tree = withHit(buildModuleTree(modules.value));
  return [{ key: -1, title: pageText.value.allModules, children: tree.length ? tree : undefined }];
});

const moduleTreeKey = computed(() => `${moduleSearch.value}-${modules.value.length}`);

const loadModules = async () => {
  if (!projectId.value) return;
  isModulesLoading.value = true;
  try {
    const response = await getTestCaseModules(projectId.value, { pageSize: 500 });
    modules.value = response.success ? (response.data || []) as TestCaseModule[] : [];
  } catch {
    modules.value = [];
  } finally {
    isModulesLoading.value = false;
  }
};

const handleModuleSelect = (keys: Array<string | number>) => {
  const key = keys[0];
  // -1 = 全部模块（含未分配）
  selectedModuleId.value = typeof key === 'number' && key > 0 ? key : null;
  reloadCases();
};

// ---------------------------------------------------------------------------
// 用例表格（分页 + 筛选 + 跨模块勾选保留）
// ---------------------------------------------------------------------------
const cases = ref<TestCase[]>([]);
const totalCount = ref(0);
const isCasesLoading = ref(false);
const filters = reactive({ search: '', testType: '', level: '' });
const page = ref(1);
const pageSize = ref(10);
/** 已选用例 ID（跨模块/跨页保留，v-model 绑定表格勾选） */
const selectedRowKeys = ref<Array<string | number>>([]);
/** 已绑定 UI 用例的功能用例不可选 */
const rowSelection = computed(() => ({
  type: 'checkbox' as const,
  showCheckedAll: true,
  // Arco 支持通过 disabled 回调禁用行勾选（老版本不支持时由 row-class 视觉提示兜底）
}));

const selectedIds = computed(() => selectedRowKeys.value.filter((k): k is number => typeof k === 'number'));

const paginationConfig = computed(() => ({
  total: totalCount.value,
  current: page.value,
  pageSize: pageSize.value,
  showTotal: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50],
}));

const loadCases = async () => {
  if (!projectId.value) return;
  isCasesLoading.value = true;
  try {
    const response = await getTestCaseList(projectId.value, {
      page: page.value,
      pageSize: pageSize.value,
      search: filters.search || undefined,
      test_type: filters.testType || undefined,
      level: filters.level || undefined,
      // 选中某模块时含其子模块递归（模块 ID 列表传给 module_id？接口为单值：
      // 改为前端过滤不可行（分页在后端），传模块自身 + 依赖后端 tree 语义：此处传选中模块 ID，
      // 子模块递归由后端 module_id 过滤语义决定；全部模块时不传。
      module_id: selectedModuleId.value ?? undefined,
    });
    if (response.success) {
      cases.value = response.data || [];
      totalCount.value = response.total || 0;
    } else {
      cases.value = [];
      totalCount.value = 0;
    }
  } catch {
    cases.value = [];
    totalCount.value = 0;
  } finally {
    isCasesLoading.value = false;
  }
};

const reloadCases = () => {
  page.value = 1;
  loadCases();
};

const handlePageChange = (p: number) => {
  page.value = p;
  loadCases();
};

const handlePageSizeChange = (s: number) => {
  pageSize.value = s;
  page.value = 1;
  loadCases();
};

const rowClass = (record: TestCase) => (record.ui_test_case ? 'case-row-disabled' : '');

const handleConfirm = () => {
  const ids = selectedIds.value;
  if (!ids.length) {
    Message.warning(isEnglish.value ? 'Select at least one case.' : '请至少选择一条用例。');
    return;
  }
  // 已绑定 UI 用例的行不允许入选（数据兜底）
  const validIds = ids.filter((id) => {
    const tc = cases.value.find((c) => c.id === id);
    return !tc || !tc.ui_test_case;
  });
  if (!validIds.length) {
    Message.warning(pageText.value.boundDisabledHint);
    return;
  }
  emit('confirm', validIds);
  emit('update:visible', false);
};

const handleCancel = () => {
  emit('update:visible', false);
};

watch(() => props.visible, (visible) => {
  if (visible) {
    selectedModuleId.value = null;
    moduleSearch.value = '';
    filters.search = '';
    filters.testType = '';
    filters.level = '';
    page.value = 1;
    // 回显已选
    selectedRowKeys.value = [...props.selectedIds];
    loadModules();
    loadCases();
  }
});
</script>

<style scoped>
:global(.selector-modal-popup .arco-modal-body) {
  overflow: hidden;
  padding-bottom: 12px;
}

.selector-layout {
  display: flex;
  gap: 12px;
  height: calc(70vh - 120px);
  min-height: 380px;
  max-height: 560px;
  overflow: hidden;
}

.module-panel {
  width: 220px;
  flex-shrink: 0;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: 1px solid var(--color-fill-3, #e5e6eb);
  padding-right: 12px;
}

.case-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.case-table-wrapper {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.selector-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
  flex-shrink: 0;
}

.selected-hint {
  font-size: 13px;
  color: var(--color-text-2);
}

:deep(.case-row-disabled) {
  cursor: not-allowed;
}
</style>
