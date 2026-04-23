<template>
  <a-modal
    :visible="visible"
    title="AI 生成测试用例"
    @cancel="handleCancel"
    @ok="handleOk"
    :width="800"
    :confirm-loading="isLoading"
  >
    <a-form :model="formState" :label-col-props="{ span: 5 }" :wrapper-col-props="{ span: 19 }">
      <!-- 当前项目和生成模式在一行 -->
      <div class="header-row">
        <div class="header-item">
          <span class="header-label">当前项目</span>
          <a-input v-model="currentProjectName" disabled style="width: 200px;" />
        </div>
        <div class="header-item">
          <span class="header-label">生成模式</span>
          <a-radio-group v-model="formState.generateMode" type="button" @change="handleModeChange">
            <a-radio value="full">完整生成</a-radio>
            <a-radio value="title_only">标题生成</a-radio>
            <a-radio value="kb_complete">知识库补全</a-radio>
            <a-radio value="kb_generate">知识生成</a-radio>
          </a-radio-group>
        </div>
      </div>

      <!-- 测试类型选择（所有模式通用） -->
      <div class="form-row test-type-row">
        <a-checkbox-group v-model="formState.testTypes" class="test-type-checkboxes">
          <a-checkbox value="smoke">冒烟测试</a-checkbox>
          <a-checkbox value="functional">功能测试</a-checkbox>
          <a-checkbox value="boundary">边界测试</a-checkbox>
          <a-checkbox value="exception">异常测试</a-checkbox>
          <a-checkbox value="permission">权限测试</a-checkbox>
          <a-checkbox value="security">安全测试</a-checkbox>
          <a-checkbox value="compatibility">兼容性测试</a-checkbox>
        </a-checkbox-group>
      </div>

      <!-- 需求文档和需求模块在一行显示 -->
      <div v-if="showRequirementFields" class="form-row">
        <div class="form-row-item">
          <span class="form-row-label required">需求文档</span>
          <a-select
            v-model="formState.requirementDocumentId"
            placeholder="请选择"
            :loading="isDocLoading"
            style="width: 100%;"
            @change="handleDocumentChange"
          >
            <a-option v-for="doc in requirementDocuments" :key="doc.id" :value="doc.id">
              {{ doc.title }}
            </a-option>
          </a-select>
        </div>
        <div class="form-row-item">
          <span class="form-row-label required">
            需求模块
            <a-tooltip content="全选">
              <icon-select-all
                class="select-all-icon"
                :class="{ active: formState.requirementModuleIds.length === requirementModules.length && requirementModules.length > 0 }"
                @click="toggleSelectAllModules"
              />
            </a-tooltip>
          </span>
          <a-select
            v-model="formState.requirementModuleIds"
            placeholder="请先选择需求文档"
            :loading="isReqModuleLoading"
            :disabled="!formState.requirementDocumentId"
            multiple
            style="width: 100%;"
          >
            <a-option v-for="module in requirementModules" :key="module.id" :value="module.id">
              {{ module.title }}
            </a-option>
          </a-select>
        </div>
      </div>

      <!-- 完整生成/标题生成模式：提示词、知识库、保存模块在一行 -->
      <div v-if="showSaveModuleField" class="form-row form-row-3">
        <div class="form-row-item">
          <span class="form-row-label required">选择提示词</span>
          <a-select
            v-model="formState.promptId"
            placeholder="请选择"
            :loading="isPromptsLoading"
            style="width: 100%;"
          >
            <a-option v-for="prompt in prompts" :key="prompt.id" :value="prompt.id">
              {{ prompt.name }}
            </a-option>
            <template #not-found>
              <div style="padding: 10px; text-align: center;">
                <a-empty description="没有可用的通用提示词，请先创建。" />
              </div>
            </template>
          </a-select>
        </div>
        <div class="form-row-item">
          <span class="form-row-label">知识库</span>
          <a-select
            v-model="formState.knowledgeBaseId"
            placeholder="不使用知识库"
            :loading="isKbLoading"
            allow-clear
            style="width: 100%;"
            @clear="formState.useKnowledgeBase = false"
            @change="(val: any) => formState.useKnowledgeBase = !!val"
          >
            <a-option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
              {{ kb.name }}
            </a-option>
          </a-select>
        </div>
        <div class="form-row-item">
          <span class="form-row-label required">保存模块</span>
          <a-tree-select
            v-model="formState.testCaseModuleId"
            :data="testCaseModuleTree"
            placeholder="请选择"
            allow-clear
            style="width: 100%;"
          />
        </div>
      </div>

      <!-- 知识库补全/知识生成模式：提示词、知识库在一行 -->
      <div v-else class="form-row">
        <div class="form-row-item">
          <span class="form-row-label required">选择提示词</span>
          <a-select
            v-model="formState.promptId"
            placeholder="请选择"
            :loading="isPromptsLoading"
            style="width: 100%;"
          >
            <a-option v-for="prompt in prompts" :key="prompt.id" :value="prompt.id">
              {{ prompt.name }}
            </a-option>
            <template #not-found>
              <div style="padding: 10px; text-align: center;">
                <a-empty description="没有可用的通用提示词，请先创建。" />
              </div>
            </template>
          </a-select>
        </div>
        <div class="form-row-item">
          <span class="form-row-label required">关联知识库</span>
          <a-select
            v-model="formState.knowledgeBaseId"
            placeholder="请选择知识库"
            :loading="isKbLoading"
            allow-clear
            style="width: 100%;"
          >
            <a-option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
              {{ kb.name }}
            </a-option>
          </a-select>
        </div>
      </div>

      <!-- 用例选择表格：知识库补全、知识生成模式显示 -->
      <div v-if="showTestCaseSelector" class="testcase-selector-section">
        <div class="section-label">选择用例</div>
        <div class="testcase-selector-wrapper">
          <div class="selector-header">
            <a-input-search
              v-model="searchKeyword"
              placeholder="搜索用例名称"
              allow-clear
              style="width: 180px;"
              @search="handleSearch"
            />
            <a-select
              v-model="selectedModule"
              placeholder="筛选模块"
              allow-clear
              :loading="modulesLoading"
              style="width: 140px; margin-left: 12px;"
              @change="handleModuleFilterChange"
            >
              <a-option v-for="module in flatModuleList" :key="module.id" :value="module.id">
                {{ module.indentName }}
              </a-option>
            </a-select>
            <a-select
              v-model="selectedLevel"
              placeholder="优先级"
              allow-clear
              style="width: 100px; margin-left: 12px;"
              @change="handleLevelFilterChange"
            >
              <a-option value="P0">P0</a-option>
              <a-option value="P1">P1</a-option>
              <a-option value="P2">P2</a-option>
              <a-option value="P3">P3</a-option>
            </a-select>
            <span class="selected-count">
              已选 <strong>{{ selectedTestCaseIds.length }}</strong> 个
            </span>
          </div>

          <a-table
            :columns="testCaseColumns"
            :data="testCaseData"
            :pagination="paginationConfig"
            :loading="testCaseLoading"
            :scroll="{ y: 260 }"
            :bordered="{ cell: true }"
            row-key="id"
            size="small"
            @page-change="onPageChange"
            @page-size-change="onPageSizeChange"
          >
            <template #selection="{ record }">
              <a-checkbox
                :model-value="selectedTestCaseIds.includes(record.id)"
                @change="(checked: boolean) => handleCheckboxChange(record.id, checked)"
              />
            </template>
            <template #selectAll>
              <a-checkbox
                :model-value="isCurrentPageAllSelected"
                :indeterminate="isCurrentPageIndeterminate"
                @change="handleSelectCurrentPage"
              />
            </template>
            <template #level="{ record }">
              <a-tag :color="getLevelColor(record.level)">{{ record.level }}</a-tag>
            </template>
          </a-table>
        </div>
      </div>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue';
import type { PropType } from 'vue';
import { useProjectStore } from '@/store/projectStore';
import type { TreeNodeData } from '@arco-design/web-vue';
import { Message } from '@arco-design/web-vue';
import { RequirementDocumentService } from '@/features/requirements/services/requirementService';
import type { RequirementDocument, DocumentModule } from '@/features/requirements/types';
import { getUserPrompts } from '@/features/prompts/services/promptService';
import type { UserPrompt, UserPromptListResponseData } from '@/features/prompts/types/prompt';
import { KnowledgeService } from '@/features/knowledge/services/knowledgeService';
import type { KnowledgeBase } from '@/features/knowledge/types/knowledge';
import { getTestCaseList, type TestCase } from '@/services/testcaseService';
import { getTestCaseModules, type TestCaseModule } from '@/services/testcaseModuleService';
import { getLevelColor } from '@/utils/formatters';

// 生成模式类型
type GenerateMode = 'full' | 'title_only' | 'kb_complete' | 'kb_generate';

const props = defineProps({
  visible: {
    type: Boolean,
    required: true,
  },
  testCaseModuleTree: {
    type: Array as PropType<TreeNodeData[]>,
    default: () => [],
  },
});

const emit = defineEmits(['update:visible', 'submit']);

const projectStore = useProjectStore();
const isLoading = ref(false);
const isDocLoading = ref(false);
const isReqModuleLoading = ref(false);
const isPromptsLoading = ref(false);
const isKbLoading = ref(false);

const requirementDocuments = ref<RequirementDocument[]>([]);
const requirementModules = ref<DocumentModule[]>([]);
const prompts = ref<UserPrompt[]>([]);
const knowledgeBases = ref<KnowledgeBase[]>([]);

// 用例选择相关状态
const testCaseLoading = ref(false);
const modulesLoading = ref(false);
const testCaseData = ref<TestCase[]>([]);
const moduleList = ref<TestCaseModule[]>([]);
const selectedTestCaseIds = ref<number[]>([]);
const searchKeyword = ref('');
const selectedModule = ref<number | undefined>(undefined);
const selectedLevel = ref<string>('');

const paginationConfig = reactive({
  total: 0,
  current: 1,
  pageSize: 10,
  showTotal: true,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50],
});

const testCaseColumns = [
  { title: '选择', slotName: 'selection', width: 50, titleSlotName: 'selectAll', align: 'center' as const },
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: '用例名称', dataIndex: 'name', width: 180, ellipsis: true, tooltip: true },
  { title: '优先级', dataIndex: 'level', slotName: 'level', width: 70 },
  { title: '所属模块', dataIndex: 'module_detail', width: 100, ellipsis: true },
];

const formState = reactive({
  generateMode: 'full' as GenerateMode,
  requirementDocumentId: null as string | null,
  requirementModuleIds: [] as string[],
  promptId: null as number | null,
  useKnowledgeBase: false,
  knowledgeBaseId: null as string | null,
  testCaseModuleId: null,
  testTypes: ['functional'] as string[],
});

const currentProjectName = computed(() => projectStore.currentProject?.name || '未命名项目');

// 是否显示需求文档相关字段
const showRequirementFields = computed(() => {
  return ['full', 'title_only', 'kb_generate'].includes(formState.generateMode);
});

// 是否显示保存模块字段
const showSaveModuleField = computed(() => {
  return ['full', 'title_only'].includes(formState.generateMode);
});

// 是否显示用例选择器
const showTestCaseSelector = computed(() => {
  return ['kb_complete', 'kb_generate'].includes(formState.generateMode);
});

// 将树形模块列表扁平化为带缩进的列表
const flatModuleList = computed(() => {
  const flatList: Array<TestCaseModule & { indentName: string }> = [];
  const flatten = (modules: TestCaseModule[], level: number = 0) => {
    modules.forEach((module) => {
      const indent = '　'.repeat(level);
      flatList.push({ ...module, indentName: `${indent}${module.name}` });
      if (module.children && module.children.length > 0) {
        flatten(module.children, level + 1);
      }
    });
  };
  flatten(moduleList.value);
  return flatList;
});

// 当前页是否全选
const isCurrentPageAllSelected = computed(() => {
  if (testCaseData.value.length === 0) return false;
  return testCaseData.value.every((item) => selectedTestCaseIds.value.includes(item.id));
});

// 当前页是否半选状态
const isCurrentPageIndeterminate = computed(() => {
  const count = testCaseData.value.filter((item) => selectedTestCaseIds.value.includes(item.id)).length;
  return count > 0 && count < testCaseData.value.length;
});

const handleCancel = () => {
  emit('update:visible', false);
};

const handleOk = () => {
  // 验证测试类型
  if (!formState.testTypes || formState.testTypes.length === 0) {
    Message.error('请至少选择一种测试类型');
    return;
  }

  // 验证提示词
  if (!formState.promptId) {
    Message.error('请选择提示词');
    return;
  }

  // 根据模式验证必填项
  if (['full', 'title_only'].includes(formState.generateMode)) {
    if (!formState.requirementDocumentId || formState.requirementModuleIds.length === 0 || !formState.testCaseModuleId) {
      Message.error('请填写所有必填项');
      return;
    }
  }

  if (formState.generateMode === 'kb_generate') {
    if (!formState.requirementDocumentId || formState.requirementModuleIds.length === 0) {
      Message.error('请选择需求文档和模块');
      return;
    }
  }

  // 知识库补全和知识生成模式：知识库必选
  if (['kb_complete', 'kb_generate'].includes(formState.generateMode)) {
    if (!formState.knowledgeBaseId) {
      Message.error('请选择知识库');
      return;
    }
    if (selectedTestCaseIds.value.length === 0) {
      Message.error('请至少选择一个测试用例');
      return;
    }
  }

  // 完整生成/标题生成模式：如果启用了知识库，必须选择知识库ID
  if (['full', 'title_only'].includes(formState.generateMode) && formState.useKnowledgeBase && !formState.knowledgeBaseId) {
    Message.error('启用知识库后必须选择一个知识库');
    return;
  }

  const selectedReqModules = requirementModules.value.filter(m => formState.requirementModuleIds.includes(m.id));
  const selectedTestCases = testCaseData.value.filter(tc => selectedTestCaseIds.value.includes(tc.id));

  emit('submit', {
    ...formState,
    selectedModules: selectedReqModules,
    selectedTestCaseIds: selectedTestCaseIds.value,
    selectedTestCases: selectedTestCases,
  });
};

// 模式切换处理
const handleModeChange = () => {
  // 清空用例选择
  selectedTestCaseIds.value = [];
  // 如果切换到需要用例选择的模式，加载用例
  if (showTestCaseSelector.value) {
    fetchTestCases();
    fetchModules();
  }
};

const toggleSelectAllModules = () => {
  if (requirementModules.value.length === 0) return;
  if (formState.requirementModuleIds.length === requirementModules.value.length) {
    formState.requirementModuleIds = [];
  } else {
    formState.requirementModuleIds = requirementModules.value.map(m => m.id);
  }
};

const fetchRequirementDocuments = async () => {
  if (!projectStore.currentProjectId) return;
  isDocLoading.value = true;
  try {
    const response = await RequirementDocumentService.getDocumentList({ project: String(projectStore.currentProjectId) });
    if (response.status === 'success' && Array.isArray(response.data)) {
      requirementDocuments.value = response.data;
    } else if (response.status === 'success' && 'results' in response.data) {
       requirementDocuments.value = response.data.results;
    } else {
      Message.error('加载需求文档列表失败');
      requirementDocuments.value = [];
    }
  } catch (error) {
    Message.error('加载需求文档列表时发生错误');
    requirementDocuments.value = [];
  } finally {
    isDocLoading.value = false;
  }
};

const fetchRequirementModules = async (documentId: string) => {
  isReqModuleLoading.value = true;
  requirementModules.value = [];
  formState.requirementModuleIds = [];
  try {
    const response = await RequirementDocumentService.getDocumentDetail(documentId);
    if (response.status === 'success' && response.data?.modules) {
      requirementModules.value = response.data.modules;
    } else {
      Message.error('加载需求模块失败');
    }
  } catch (error) {
    Message.error('加载需求模块时发生错误');
  } finally {
    isReqModuleLoading.value = false;
  }
};

const handleDocumentChange = (value: any) => {
  if (value) {
    fetchRequirementModules(value);
  } else {
    requirementModules.value = [];
    formState.requirementModuleIds = [];
  }
};

const fetchPrompts = async () => {
  isPromptsLoading.value = true;
  try {
    // 获取 "general" 类型的提示词
    const response = await getUserPrompts({ prompt_type: 'general' });
    if (response.status === 'success') {
       // 根据您提供的实际返回，data可能直接是数组
       if (Array.isArray(response.data)) {
           prompts.value = response.data;
       }
       // 兼容旧的或分页的格式
       else if ((response.data as UserPromptListResponseData)?.results) {
           prompts.value = (response.data as UserPromptListResponseData).results;
       }
       else {
           // 接口成功但数据格式不符或为空
           prompts.value = [];
       }
    } else {
      Message.error(response.message || '加载提示词列表失败');
      prompts.value = [];
    }
  } catch (error) {
    Message.error('加载提示词列表时发生错误');
    prompts.value = [];
  } finally {
    isPromptsLoading.value = false;
  }
};

const fetchKnowledgeBases = async () => {
  if (!projectStore.currentProjectId) return;
  isKbLoading.value = true;
  try {
    const response = await KnowledgeService.getKnowledgeBases({ project: projectStore.currentProjectId });
    if (Array.isArray(response)) {
       knowledgeBases.value = response;
    } else {
       knowledgeBases.value = response.results;
    }
  } catch (error) {
    Message.error('加载知识库列表失败');
    knowledgeBases.value = [];
  } finally {
    isKbLoading.value = false;
  }
};

// 用例选择相关函数
const fetchTestCases = async () => {
  if (!projectStore.currentProjectId) {
    testCaseData.value = [];
    paginationConfig.total = 0;
    return;
  }

  testCaseLoading.value = true;
  try {
    const response = await getTestCaseList(projectStore.currentProjectId, {
      page: paginationConfig.current,
      pageSize: paginationConfig.pageSize,
      search: searchKeyword.value,
      level: selectedLevel.value || undefined,
      module_id: selectedModule.value,
    });

    if (response.success && response.data) {
      testCaseData.value = response.data;
      paginationConfig.total = response.total || response.data.length;
    } else {
      Message.error(response.error || '获取测试用例列表失败');
      testCaseData.value = [];
      paginationConfig.total = 0;
    }
  } catch (error) {
    Message.error('获取测试用例列表时发生错误');
    testCaseData.value = [];
    paginationConfig.total = 0;
  } finally {
    testCaseLoading.value = false;
  }
};

const fetchModules = async () => {
  if (!projectStore.currentProjectId) {
    moduleList.value = [];
    return;
  }

  modulesLoading.value = true;
  try {
    const response = await getTestCaseModules(projectStore.currentProjectId);
    if (response.success && response.data) {
      moduleList.value = response.data;
    } else {
      moduleList.value = [];
    }
  } catch (error) {
    moduleList.value = [];
  } finally {
    modulesLoading.value = false;
  }
};

const handleCheckboxChange = (id: number, checked: boolean) => {
  if (checked) {
    if (!selectedTestCaseIds.value.includes(id)) {
      selectedTestCaseIds.value.push(id);
    }
  } else {
    const index = selectedTestCaseIds.value.indexOf(id);
    if (index > -1) {
      selectedTestCaseIds.value.splice(index, 1);
    }
  }
};

const handleSelectCurrentPage = (checked: boolean) => {
  if (checked) {
    testCaseData.value.forEach((item) => {
      if (!selectedTestCaseIds.value.includes(item.id)) {
        selectedTestCaseIds.value.push(item.id);
      }
    });
  } else {
    const currentPageIds = testCaseData.value.map((item) => item.id);
    selectedTestCaseIds.value = selectedTestCaseIds.value.filter((id) => !currentPageIds.includes(id));
  }
};

const handleSearch = () => {
  paginationConfig.current = 1;
  fetchTestCases();
};

const handleModuleFilterChange = () => {
  paginationConfig.current = 1;
  fetchTestCases();
};

const handleLevelFilterChange = () => {
  paginationConfig.current = 1;
  fetchTestCases();
};

const onPageChange = (page: number) => {
  paginationConfig.current = page;
  fetchTestCases();
};

const onPageSizeChange = (pageSize: number) => {
  paginationConfig.pageSize = pageSize;
  paginationConfig.current = 1;
  fetchTestCases();
};

watch(() => props.visible, (newVal) => {
  if (newVal) {
    // 每次打开弹窗时重置表单
    formState.generateMode = 'full';
    formState.requirementDocumentId = null;
    formState.requirementModuleIds = [];
    formState.promptId = null;
    formState.useKnowledgeBase = false;
    formState.knowledgeBaseId = null;
    formState.testCaseModuleId = null;
    formState.testTypes = ['functional'];
    requirementDocuments.value = [];
    requirementModules.value = [];
    prompts.value = [];
    knowledgeBases.value = [];
    // 重置用例选择状态
    selectedTestCaseIds.value = [];
    searchKeyword.value = '';
    selectedModule.value = undefined;
    selectedLevel.value = '';
    paginationConfig.current = 1;
    testCaseData.value = [];
    moduleList.value = [];
    // 加载数据
    fetchRequirementDocuments();
    fetchPrompts();
    fetchKnowledgeBases();
  }
});

</script>

<style scoped>
.header-row {
  display: flex;
  align-items: center;
  gap: 48px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border-2);
}

.header-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-label {
  font-size: 14px;
  color: var(--color-text-2);
  white-space: nowrap;
}

.form-row {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
}

.form-row-3 {
  gap: 16px;
}

.form-row-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-row-label {
  font-size: 14px;
  color: var(--color-text-1);
  display: flex;
  align-items: center;
  gap: 4px;
}

.form-row-label.required::before {
  content: '*';
  color: rgb(var(--danger-6));
  margin-right: 4px;
}

.select-all-icon {
  cursor: pointer;
  font-size: 16px;
  color: var(--color-text-3);
  transition: color 0.2s;
}

.select-all-icon:hover {
  color: rgb(var(--primary-6));
}

.select-all-icon.active {
  color: rgb(var(--primary-6));
}

.testcase-selector-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-2);
}

.section-label {
  font-size: 14px;
  color: var(--color-text-1);
  margin-bottom: 12px;
}

.testcase-selector-wrapper {
  width: 100%;
}

.selector-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px 0;
}

.selected-count {
  margin-left: auto;
  font-size: 13px;
  color: var(--color-text-2);
}

.test-type-row {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--color-border-2);
}

.test-type-checkboxes {
  display: flex;
  width: 100%;
  justify-content: space-between;
}

.test-type-checkboxes :deep(.arco-checkbox) {
  margin-right: 0;
  white-space: nowrap;
}
</style>
