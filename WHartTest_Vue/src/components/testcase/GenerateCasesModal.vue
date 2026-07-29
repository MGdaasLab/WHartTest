<template>
  <a-modal
    :visible="visible"
    :title="pageText.modalTitle"
    @cancel="handleCancel"
    @ok="handleOk"
    :width="800"
    :confirm-loading="isLoading"
  >
    <a-form :model="formState" :label-col-props="{ span: 5 }" :wrapper-col-props="{ span: 19 }">
      <!-- 当前项目和生成模式在一行 -->
      <div class="header-row">
        <div class="header-item">
          <span class="header-label">{{ pageText.currentProject }}</span>
          <a-input v-model="currentProjectName" disabled style="width: 200px;" />
        </div>
        <div class="header-item">
          <span class="header-label">{{ pageText.generateMode }}</span>
          <a-radio-group v-model="formState.generateMode" type="button" @change="handleModeChange">
            <a-radio v-for="option in generateModeOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </a-radio>
          </a-radio-group>
        </div>
      </div>

      <!-- 测试类型选择（所有模式通用） -->
      <div class="form-row test-type-row">
        <a-checkbox-group v-model="formState.testTypes" class="test-type-checkboxes">
          <a-checkbox v-for="option in testTypeOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </a-checkbox>
        </a-checkbox-group>
      </div>

      <!-- 需求文档和需求模块在一行显示 -->
      <div v-if="showRequirementFields" class="form-row">
        <div class="form-row-item">
          <span class="form-row-label required">{{ pageText.requirementDocument }}</span>
          <a-select
            v-model="formState.requirementDocumentId"
            :placeholder="pageText.selectPlaceholder"
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
            {{ pageText.requirementModule }}
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
            :placeholder="pageText.requirementModulePlaceholder"
            :loading="isReqModuleLoading"
            :disabled="!formState.requirementDocumentId"
            multiple
            style="width: 100%;"
            allow-clear
            allow-search
            :max-tag-count="2"
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
          <span class="form-row-label required">{{ pageText.selectPrompt }}</span>
          <a-select
            v-model="formState.promptId"
            :placeholder="pageText.selectPlaceholder"
            :loading="isPromptsLoading"
            style="width: 100%;"
          >
            <a-option v-for="prompt in prompts" :key="prompt.id" :value="prompt.id">
              {{ prompt.name }}
            </a-option>
            <template #not-found>
              <div style="padding: 10px; text-align: center;">
                <a-empty :description="pageText.noGeneralPrompts" />
              </div>
            </template>
          </a-select>
        </div>
        <div class="form-row-item">
          <span class="form-row-label">{{ pageText.knowledgeBase }}</span>
          <a-select
            v-model="formState.knowledgeBaseId"
            :placeholder="pageText.noKnowledgeBase"
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
          <span class="form-row-label required">{{ pageText.saveModule }}</span>
          <a-tree-select
            v-model="formState.testCaseModuleId"
            :data="testCaseModuleTree"
            :placeholder="pageText.selectPlaceholder"
            allow-clear
            style="width: 100%;"
          />
        </div>
      </div>

      <!-- 知识库补全/知识生成模式：提示词、知识库在一行 -->
      <div v-else class="form-row">
        <div class="form-row-item">
          <span class="form-row-label required">{{ pageText.selectPrompt }}</span>
          <a-select
            v-model="formState.promptId"
            :placeholder="pageText.selectPlaceholder"
            :loading="isPromptsLoading"
            style="width: 100%;"
          >
            <a-option v-for="prompt in prompts" :key="prompt.id" :value="prompt.id">
              {{ prompt.name }}
            </a-option>
            <template #not-found>
              <div style="padding: 10px; text-align: center;">
                <a-empty :description="pageText.noGeneralPrompts" />
              </div>
            </template>
          </a-select>
        </div>
        <div class="form-row-item">
          <span class="form-row-label required">{{ pageText.linkedKnowledgeBase }}</span>
          <a-select
            v-model="formState.knowledgeBaseId"
            :placeholder="pageText.selectKnowledgeBase"
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
        <div class="section-label">{{ pageText.selectCases }}</div>
        <div class="testcase-selector-wrapper">
          <div class="selector-header">
            <a-input-search
              v-model="searchKeyword"
              :placeholder="pageText.searchCaseName"
              allow-clear
              style="width: 180px;"
              @search="handleSearch"
            />
            <a-select
              v-model="selectedModule"
              :placeholder="pageText.filterModule"
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
              :placeholder="pageText.priority"
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
              {{ pageText.selectedCountPrefix }}
              <strong>{{ selectedTestCaseIds.length }}</strong>
              {{ pageText.selectedCountSuffix }}
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
import { toArray } from '@/features/api-testing/services/responseHelpers';
import { useAppI18n } from '@/composables/useAppI18n';
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
const { isEnglish } = useAppI18n();
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

const pageText = computed(() => (
  isEnglish.value
    ? {
        modalTitle: 'AI generate cases',
        currentProject: 'Project',
        generateMode: 'Mode',
        requirementDocument: 'Req. document',
        requirementModule: 'Req. module',
        selectPrompt: 'Prompt',
        knowledgeBase: 'Knowledge base',
        linkedKnowledgeBase: 'Knowledge base',
        saveModule: 'Save to',
        selectCases: 'Select cases',
        selectPlaceholder: 'Please select',
        requirementModulePlaceholder: 'Select a document first, then choose modules',
        noGeneralPrompts: 'No prompts yet. Create one first.',
        noKnowledgeBase: 'None',
        selectKnowledgeBase: 'Select knowledge base',
        searchCaseName: 'Search case',
        filterModule: 'Module',
        priority: 'Priority',
        selectedCountPrefix: 'Selected',
        selectedCountSuffix: '',
        select: 'Select',
        caseName: 'Case name',
        module: 'Module',
        unnamedProject: 'Unnamed project',
        testTypeRequired: 'Select at least one test type',
        promptRequired: 'Select a prompt',
        requiredFieldsMissing: 'Fill in all required fields',
        requirementSelectionRequired: 'Select a requirement document and at least one requirement module',
        knowledgeBaseRequired: 'Select a knowledge base',
        testCaseRequired: 'Select at least one test case',
        knowledgeBaseMustBeSelected: 'Select a knowledge base when knowledge-base mode is enabled',
        loadRequirementDocumentsFailed: 'Failed to load requirement documents',
        loadRequirementDocumentsError: 'An error occurred while loading requirement documents',
        loadRequirementModulesFailed: 'Failed to load requirement modules',
        loadRequirementModulesError: 'An error occurred while loading requirement modules',
        loadPromptsFailed: 'Failed to load prompts',
        loadPromptsError: 'An error occurred while loading prompts',
        loadKnowledgeBasesFailed: 'Failed to load knowledge bases',
        loadTestCasesFailed: 'Failed to fetch test cases',
        loadTestCasesError: 'An error occurred while fetching test cases',
      }
    : {
        modalTitle: 'AI 生成测试用例',
        currentProject: '当前项目',
        generateMode: '生成模式',
        requirementDocument: '需求文档',
        requirementModule: '需求模块',
        selectPrompt: '选择提示词',
        knowledgeBase: '知识库',
        linkedKnowledgeBase: '关联知识库',
        saveModule: '保存模块',
        selectCases: '选择用例',
        selectPlaceholder: '请选择',
        requirementModulePlaceholder: '请先选择需求文档后多选需求模块',
        noGeneralPrompts: '没有可用的通用提示词，请先创建。',
        noKnowledgeBase: '不使用知识库',
        selectKnowledgeBase: '请选择知识库',
        searchCaseName: '搜索用例名称',
        filterModule: '筛选模块',
        priority: '优先级',
        selectedCountPrefix: '已选',
        selectedCountSuffix: '个',
        select: '选择',
        caseName: '用例名称',
        module: '所属模块',
        unnamedProject: '未命名项目',
        testTypeRequired: '请至少选择一种测试类型',
        promptRequired: '请选择提示词',
        requiredFieldsMissing: '请填写所有必填项',
        requirementSelectionRequired: '请选择需求文档和至少一个需求模块',
        knowledgeBaseRequired: '请选择知识库',
        testCaseRequired: '请至少选择一个测试用例',
        knowledgeBaseMustBeSelected: '启用知识库后必须选择一个知识库',
        loadRequirementDocumentsFailed: '加载需求文档列表失败',
        loadRequirementDocumentsError: '加载需求文档列表时发生错误',
        loadRequirementModulesFailed: '加载需求模块失败',
        loadRequirementModulesError: '加载需求模块时发生错误',
        loadPromptsFailed: '加载提示词列表失败',
        loadPromptsError: '加载提示词列表时发生错误',
        loadKnowledgeBasesFailed: '加载知识库列表失败',
        loadTestCasesFailed: '获取测试用例列表失败',
        loadTestCasesError: '获取测试用例列表时发生错误',
      }
));

const generateModeOptions = computed(() => (
  isEnglish.value
    ? [
        { value: 'full', label: 'Full' },
        { value: 'title_only', label: 'Title only' },
        { value: 'kb_complete', label: 'KB complete' },
        { value: 'kb_generate', label: 'KB generate' },
      ]
    : [
        { value: 'full', label: '完整生成' },
        { value: 'title_only', label: '标题生成' },
        { value: 'kb_complete', label: '知识库补全' },
        { value: 'kb_generate', label: '知识生成' },
      ]
));

const testTypeOptions = computed(() => (
  isEnglish.value
    ? [
        { value: 'smoke', label: 'Smoke' },
        { value: 'functional', label: 'Functional' },
        { value: 'boundary', label: 'Boundary' },
        { value: 'exception', label: 'Exception' },
        { value: 'permission', label: 'Permission' },
        { value: 'security', label: 'Security' },
        { value: 'compatibility', label: 'Compatibility' },
      ]
    : [
        { value: 'smoke', label: '冒烟测试' },
        { value: 'functional', label: '功能测试' },
        { value: 'boundary', label: '边界测试' },
        { value: 'exception', label: '异常测试' },
        { value: 'permission', label: '权限测试' },
        { value: 'security', label: '安全测试' },
        { value: 'compatibility', label: '兼容性测试' },
      ]
));

const testCaseColumns = computed(() => [
  { title: pageText.value.select, slotName: 'selection', width: 50, titleSlotName: 'selectAll', align: 'center' as const },
  { title: 'ID', dataIndex: 'id', width: 60 },
  { title: pageText.value.caseName, dataIndex: 'name', width: 180, ellipsis: true, tooltip: true },
  { title: pageText.value.priority, dataIndex: 'level', slotName: 'level', width: 70 },
  { title: pageText.value.module, dataIndex: 'module_detail', width: 100, ellipsis: true },
]);

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

const currentProjectName = computed(() => projectStore.currentProject?.name || pageText.value.unnamedProject);

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
    Message.error(pageText.value.testTypeRequired);
    return;
  }

  // 验证提示词
  if (!formState.promptId) {
    Message.error(pageText.value.promptRequired);
    return;
  }

  // 根据模式验证必填项
  if (['full', 'title_only'].includes(formState.generateMode)) {
    if (!formState.requirementDocumentId || formState.requirementModuleIds.length === 0 || !formState.testCaseModuleId) {
      Message.error(pageText.value.requiredFieldsMissing);
      return;
    }
  }

  if (formState.generateMode === 'kb_generate') {
    if (!formState.requirementDocumentId || formState.requirementModuleIds.length === 0) {
      Message.error(pageText.value.requirementSelectionRequired);
      return;
    }
  }

  // 知识库补全和知识生成模式：知识库必选
  if (['kb_complete', 'kb_generate'].includes(formState.generateMode)) {
    if (!formState.knowledgeBaseId) {
      Message.error(pageText.value.knowledgeBaseRequired);
      return;
    }
    if (selectedTestCaseIds.value.length === 0) {
      Message.error(pageText.value.testCaseRequired);
      return;
    }
  }

  // 完整生成/标题生成模式：如果启用了知识库，必须选择知识库ID
  if (['full', 'title_only'].includes(formState.generateMode) && formState.useKnowledgeBase && !formState.knowledgeBaseId) {
    Message.error(pageText.value.knowledgeBaseMustBeSelected);
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
    if (response.status === 'success') {
      requirementDocuments.value = toArray<RequirementDocument>((response.data as any)?.results ?? response.data);
    } else {
      Message.error(pageText.value.loadRequirementDocumentsFailed);
      requirementDocuments.value = [];
    }
  } catch (error) {
    Message.error(pageText.value.loadRequirementDocumentsError);
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
      Message.error(pageText.value.loadRequirementModulesFailed);
    }
  } catch (error) {
    Message.error(pageText.value.loadRequirementModulesError);
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
       prompts.value = toArray<UserPrompt>((response.data as UserPromptListResponseData)?.results ?? response.data);
    } else {
      Message.error(response.message || pageText.value.loadPromptsFailed);
      prompts.value = [];
    }
  } catch (error) {
    Message.error(pageText.value.loadPromptsError);
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
    knowledgeBases.value = toArray<KnowledgeBase>((response as any)?.results ?? response);
  } catch (error) {
    Message.error(pageText.value.loadKnowledgeBasesFailed);
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
      Message.error(response.error || pageText.value.loadTestCasesFailed);
      testCaseData.value = [];
      paginationConfig.total = 0;
    }
  } catch (error) {
    Message.error(pageText.value.loadTestCasesError);
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
