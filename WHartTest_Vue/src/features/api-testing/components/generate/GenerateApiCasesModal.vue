<template>
  <a-modal
    :visible="visible"
    :title="pageText.modalTitle"
    :width="860"
    :confirm-loading="isSubmitting"
    @cancel="handleCancel"
    @ok="handleSubmit"
  >
    <a-form :model="formState" :label-col-props="{ span: 5 }" :wrapper-col-props="{ span: 19 }">
      <div class="form-row">
        <span class="form-row-label">{{ pageText.currentProject }}</span>
        <a-input :model-value="currentProjectName" disabled style="width: 200px;" />
      </div>
      <div class="form-row">
        <span class="form-row-label">{{ pageText.caseType }}</span>
        <a-radio-group v-model="formState.caseType" type="button" @change="handleCaseTypeChange">
          <a-radio value="interface_case">{{ pageText.interfaceCase }}</a-radio>
          <a-radio value="scenario">{{ pageText.scenarioCase }}</a-radio>
        </a-radio-group>
      </div>

      <!-- 生成维度（单接口模式） -->
      <div v-if="formState.caseType === 'interface_case'" class="form-row">
        <span class="form-row-label required">{{ pageText.dimensions }}</span>
        <a-checkbox-group v-model="formState.dimensions" class="dimension-checkboxes">
          <a-checkbox value="D1" disabled>{{ pageText.dimD1 }}</a-checkbox>
          <a-checkbox value="D2">{{ pageText.dimD2 }}</a-checkbox>
          <a-checkbox value="D3">{{ pageText.dimD3 }}</a-checkbox>
          <a-checkbox value="D4">{{ pageText.dimD4 }}</a-checkbox>
        </a-checkbox-group>
      </div>

      <!-- 场景原型（场景模式） -->
      <div v-else class="form-row">
        <span class="form-row-label required">{{ pageText.archetypes }}</span>
        <a-checkbox-group v-model="formState.archetypes" class="dimension-checkboxes">
          <a-checkbox v-for="option in archetypeOptions" :key="option.value" :value="option.value">
            {{ option.label }}
            <a-tooltip :content="option.tip" position="top">
              <icon-question-circle class="archetype-tip-icon" />
            </a-tooltip>
          </a-checkbox>
        </a-checkbox-group>
      </div>

      <!-- 接口选择（模块树级联 + 搜索） -->
      <div class="form-row interface-select-row">
        <span class="form-row-label required">{{ pageText.selectInterfaces }}</span>
        <div class="interface-select-area">
          <a-input-search
            v-model="interfaceSearch"
            :placeholder="pageText.searchPlaceholder"
            size="small"
            class="interface-search"
            allow-clear
          />
          <div class="interface-tree-wrapper">
            <a-spin :loading="isInterfacesLoading" style="width: 100%;">
              <a-tree
                v-if="interfaceTreeData.length"
                :key="interfaceTreeKey"
                :data="interfaceTreeData"
                :checkable="true"
                :check-strictly="false"
                :default-expanded-keys="expandedModuleKeys"
                :selected-keys="[]"
                @check="handleInterfaceCheck"
              />
              <a-empty v-else-if="!isInterfacesLoading" :description="pageText.noInterfaces" />
            </a-spin>
          </div>
          <div class="selected-count">{{ pageText.selectedCount.replace('{count}', String(selectedInterfaceIds.length)) }}</div>
        </div>
      </div>

      <!-- 上传接口文档 -->
      <div class="form-row">
        <span class="form-row-label">{{ pageText.uploadDocument }}</span>
        <div class="upload-area">
          <a-upload
            :auto-upload="false"
            :show-file-list="false"
            :limit="1"
            :file-list="documentFileList"
            @change="handleDocumentChange"
          >
            <template #upload-button>
              <a-button type="outline" size="small">
                <template #icon><icon-upload /></template>
                {{ pageText.selectFile }}
              </a-button>
            </template>
          </a-upload>
          <div v-if="documentFileList.length" class="upload-file-item">
            <icon-file class="upload-file-icon" />
            <span class="upload-file-name" :title="documentFileList[0]?.name">{{ documentFileList[0]?.name }}</span>
            <a-button type="text" size="mini" status="danger" @click="removeDocumentFile">
              <template #icon><icon-delete /></template>
            </a-button>
          </div>
          <div v-else class="upload-hint">{{ pageText.uploadHint }}</div>
        </div>
      </div>

      <!-- 登录接口（单接口/场景模式共用，候选为项目全部 HTTP 接口） -->
      <div class="form-row">
        <span class="form-row-label">{{ pageText.loginInterface }}</span>
        <div class="login-select-area">
          <a-select
            v-model="formState.loginInterfaceId"
            :placeholder="pageText.loginAutoDetect"
            allow-clear
            allow-search
            :loading="isInterfacesLoading"
            style="width: 360px;"
          >
            <a-option v-for="option in loginCandidates" :key="option.id" :value="option.id" class="login-option">
              {{ option.label }}
            </a-option>
          </a-select>
          <div class="login-hint">{{ pageText.loginHint }}</div>
        </div>
      </div>

      <!-- 知识库 -->
      <div class="form-row">
        <span class="form-row-label">{{ pageText.knowledgeBase }}</span>
        <div class="kb-area">
          <a-checkbox v-model="formState.useKnowledgeBase" :disabled="kbCheckboxLocked">
            {{ pageText.useKnowledgeBase }}
          </a-checkbox>
          <a-select
            v-if="formState.useKnowledgeBase"
            v-model="formState.knowledgeBaseId"
            :placeholder="pageText.selectPlaceholder"
            :loading="isKbLoading"
            style="margin-top: 8px;"
            allow-clear
          >
            <a-option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
              {{ kb.name }}
            </a-option>
          </a-select>
        </div>
      </div>

      <!-- 业务描述 -->
      <div class="form-row">
        <span class="form-row-label">{{ pageText.businessNotes }}</span>
        <a-textarea
          v-model="formState.businessNotes"
          :placeholder="pageText.businessNotesPlaceholder"
          :max-length="2000"
          :auto-size="{ minRows: 3, maxRows: 6 }"
        />
      </div>


      <!-- 目标分组（仅场景模式） -->
      <div v-if="formState.caseType === 'scenario'" class="form-row">
        <span class="form-row-label">{{ pageText.targetGroup }}</span>
        <a-select
          v-model="formState.groupId"
          :placeholder="groupLoadFailed ? pageText.groupLoadFailedText : pageText.groupPlaceholder"
          allow-clear
          :loading="isGroupsLoading"
          style="width: 260px;"
        >
          <template #empty>
            <div class="group-empty-hint">
              {{ groupLoadFailed ? pageText.groupLoadFailedText : (isEnglish ? 'No groups yet. Create one in the group manager, or leave ungrouped.' : '项目下暂无分组，可到分组管理新建，或留空保存为未分组。') }}
            </div>
          </template>
          <a-option v-for="group in groupOptions" :key="group.id" :value="group.id">
            {{ group.name }}
          </a-option>
        </a-select>
      </div>

      <!-- DB 校验 + 条数上限 -->
      <div class="form-row">
        <span class="form-row-label">{{ pageText.dbVerification }}</span>
        <div class="db-area">
          <a-switch v-model="formState.dbVerification" @change="handleDbSwitchChange" />
          <span v-if="formState.dbVerification && dbCheckWarning" class="db-warning">{{ dbCheckWarning }}</span>
        </div>
        <span class="form-row-label" style="margin-left: 24px;">{{ pageText.caseLimit }}</span>
        <a-input-number
          v-model="formState.caseLimit"
          :min="1"
          :max="30"
          style="width: 120px;"
        />
      </div>

    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { useProjectStore } from '@/store/projectStore';
import { useAppI18n } from '@/composables/useAppI18n';
import { getModuleTree } from '../../services/moduleService';
import { getInterfaces } from '../../services/interfaceService';
import { testcaseGroupService } from '../../services/testcaseGroupService';
import { environmentService } from '../../services/environmentService';
import { KnowledgeService } from '@/features/knowledge/services/knowledgeService';
import type { KnowledgeBase } from '@/features/knowledge/types/knowledge';
import type { ApiModule } from '../../types/module';
import type { ApiTestCaseGroup } from '../../types/testcase';
import type { ApiInterface } from '../../types/interface';
import type { GenerationFormData } from '../../services/apiCaseGeneration';

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'submit', payload: GenerationFormData): void;
}>();

const projectStore = useProjectStore();
const { isEnglish, tl } = useAppI18n();

const pageText = computed(() => isEnglish.value ? {
  modalTitle: 'AI Generate API Test Cases',
  currentProject: 'Project',
  caseType: 'Case Type',
  interfaceCase: 'Single-Interface Cases',
  scenarioCase: 'Scenario Cases',
  dimensions: 'Generation Scope',
  dimD1: 'D1 Happy Path',
  dimD2: 'D2 Param Validation',
  dimD3: 'D3 Exceptions',
  dimD4: 'D4 Business Logic',
  archetypes: 'Generation Scope',
  archS1: 'S1 Lifecycle',
  archS2: 'S2 Data Passing',
  archS3: 'S3 Branch Flows',
  archS4: 'S4 State Setup',
  archTipS1: 'Full lifecycle chain: create -> query -> update -> delete',
  archTipS2: 'Producer-consumer relation (e.g. create returns id -> consumed by detail/update/delete)',
  archTipS3: 'Conditional flows from business notes or knowledge base (e.g. amount threshold routing)',
  archTipS4: 'Cross-interface state setup (e.g. interface A makes interface B usable/unusable)',
  selectInterfaces: 'Interfaces',
  searchPlaceholder: 'Search interface name / path',
  noInterfaces: 'No HTTP interfaces',
  selectedCount: '{count} interface(s) selected',
  uploadDocument: 'API Document',
  selectFile: 'Select File',
  uploadHint: 'Optional. OpenAPI/Swagger/Apifox/Postman etc. Used to extract parameter constraints for better boundary cases.',
  loginInterface: 'Login Interface',
  loginAutoDetect: 'Select login interface (optional)',
  loginHint: 'Optional. Used as login precondition for authenticated cases.',
  knowledgeBase: 'Knowledge Base',
  useKnowledgeBase: 'Search knowledge base for business context',
  selectPlaceholder: 'Select',
  businessNotes: 'Business Notes',
  businessNotesPlaceholder: 'Optional. Describe business rules, state preconditions, conditional flows, dependencies... e.g. "amount > 500k goes to approver A"',
  dbVerification: 'DB Verification',
  targetGroup: 'Target Group',
  groupPlaceholder: 'Ungrouped',
  groupLoadFailedText: 'Group list failed to load',
  caseLimit: 'Case Limit',
  promptTemplate: 'Prompt',
} : {
  modalTitle: 'AI 生成接口测试用例',
  currentProject: '当前项目',
  caseType: '用例类型',
  interfaceCase: '单接口用例',
  scenarioCase: '场景用例',
  dimensions: '生成范围',
  dimD1: 'D1 基本功能',
  dimD2: 'D2 参数验证',
  dimD3: 'D3 异常场景',
  dimD4: 'D4 业务逻辑',
  archetypes: '生成范围',
  archS1: 'S1 生命周期',
  archS2: 'S2 数据传递',
  archS3: 'S3 业务分支',
  archS4: 'S4 状态前置',
  archTipS1: '生成完整链路（创建→查询→修改→删除）',
  archTipS2: '生产者-消费者关系（如创建返回 id → 详情/更新/删除消费 id）',
  archTipS3: '用户业务描述或知识库命中的条件流转（如金额阈值分流）',
  archTipS4: '跨接口构造前置状态（如接口 A 操作使接口 B 进入可/不可用状态）',
  selectInterfaces: '选择接口',
  searchPlaceholder: '搜索接口名称 / 路径',
  noInterfaces: '暂无 HTTP 接口',
  selectedCount: '已选 {count} 个接口',
  uploadDocument: '接口文档',
  selectFile: '选择文件',
  uploadHint: '可选。支持 OpenAPI/Swagger/Apifox/Postman 等，提取参数约束用于边界值用例设计。',
  loginInterface: '登录接口',
  loginAutoDetect: '请选择登录接口（可选）',
  loginHint: '可选。作为鉴权用例的登录前置步骤。',
  knowledgeBase: '知识库',
  useKnowledgeBase: '检索知识库补充业务上下文',
  selectPlaceholder: '请选择',
  businessNotes: '业务描述',
  businessNotesPlaceholder: '可选。描述业务规则、状态前置、条件流转、依赖关系等，如"金额>50万流转A审核"',
  dbVerification: 'DB 校验',
  targetGroup: '目标分组',
  groupPlaceholder: '未分组',
  groupLoadFailedText: '分组列表加载失败',
  caseLimit: '条数上限',
  promptTemplate: '提示词',
});

const currentProjectName = computed(() => projectStore.currentProject?.name || '');

interface FormState {
  caseType: 'interface_case' | 'scenario';
  dimensions: string[];
  archetypes: string[];
  selectedInterfaceIds: number[];
  documentFile: File | null;
  loginInterfaceId: number | null;
  useKnowledgeBase: boolean;
  knowledgeBaseId: string | null;
  businessNotes: string;
  dbVerification: boolean;
  groupId: number | null;
  caseLimit: number;
  promptId: number | null;
}

const formState = ref<FormState>({
  caseType: 'interface_case',
  dimensions: ['D1'],
  archetypes: ['S1'],
  selectedInterfaceIds: [],
  documentFile: null,
  loginInterfaceId: null,
  useKnowledgeBase: false,
  knowledgeBaseId: null,
  businessNotes: '',
  dbVerification: false,
  groupId: null,
  caseLimit: 12,
  promptId: null,
});

const isSubmitting = ref(false);
const interfaces = ref<ApiInterface[]>([]);
const modules = ref<ApiModule[]>([]);
const isInterfacesLoading = ref(false);
const isGroupsLoading = ref(false);
const groupLoadFailed = ref(false);
const isKbLoading = ref(false);
const knowledgeBases = ref<KnowledgeBase[]>([]);
const groups = ref<ApiTestCaseGroup[]>([]);
const interfaceSearch = ref('');
const dbCheckWarning = ref('');
const documentFileList = ref<any[]>([]);

// 知识库复选框：场景模式默认开启且可取消；单接口模式勾了 D3/D4 才展示
const kbCheckboxLocked = computed(() => false);

// 场景模式默认勾选知识库
const handleCaseTypeChange = () => {
  formState.value.caseLimit = formState.value.caseType === 'scenario' ? 6 : 12;
  formState.value.promptId = null;
  if (formState.value.caseType === 'scenario') {
    formState.value.useKnowledgeBase = true;
  } else {
    // 单接口用例按主接口归属，不使用分组
    formState.value.groupId = null;
  }
};

// ---------------------------------------------------------------------------
// 数据加载
// ---------------------------------------------------------------------------

const flatModules = ref<ApiModule[]>([]);

const flattenModules = (list: ApiModule[], depth = 0): ApiModule[] => {
  const result: ApiModule[] = [];
  for (const item of list) {
    result.push(item);
    if (item.children && item.children.length && depth < 10) {
      result.push(...flattenModules(item.children, depth + 1));
    }
  }
  return result;
};

const fetchData = async () => {
  if (!projectStore.currentProjectId) return;
  isInterfacesLoading.value = true;
  try {
    const pid = projectStore.currentProjectId ?? 0;
    const [moduleRes, interfaceRes] = await Promise.all([
      getModuleTree(),
      getInterfaces({ project_id: pid, page_size: 200 }),
    ]);
    // 包装函数返回 { data: { results, count }, status }，无 success 字段
    const moduleList: ApiModule[] = (moduleRes as any)?.data?.results
      ?? (Array.isArray((moduleRes as any)?.data) ? (moduleRes as any).data : []);
    modules.value = moduleList;
    flatModules.value = flattenModules(moduleList);

    const interfacePayload: any = (interfaceRes as any)?.data;
    const interfaceList: ApiInterface[] = Array.isArray(interfacePayload)
      ? interfacePayload
      : interfacePayload?.results || [];
    interfaces.value = interfaceList.filter((item: ApiInterface) => item.type !== 'sql');
  } finally {
    isInterfacesLoading.value = false;
  }
  fetchGroups();
  fetchKnowledgeBases();
};

const fetchGroups = async () => {
  if (!projectStore.currentProjectId) return;
  isGroupsLoading.value = true;
  groupLoadFailed.value = false;
  try {
    const res = await testcaseGroupService.tree(projectStore.currentProjectId);
    // 与 TestCaseFilter 相同的判断方式：res.success && res.data
    if (res.success && res.data) {
      const list: ApiTestCaseGroup[] = Array.isArray(res.data)
        ? res.data
        : (res.data as any).results || [];
      groups.value = list;
    } else {
      groups.value = [];
      groupLoadFailed.value = true;
    }
  } catch {
    groups.value = [];
    groupLoadFailed.value = true;
  } finally {
    isGroupsLoading.value = false;
  }
};

const fetchKnowledgeBases = async () => {
  if (!projectStore.currentProjectId) return;
  isKbLoading.value = true;
  try {
    const response = await KnowledgeService.getKnowledgeBases({ project: projectStore.currentProjectId });
    knowledgeBases.value = Array.isArray(response) ? response : (response as any).results || [];
  } catch {
    knowledgeBases.value = [];
  } finally {
    isKbLoading.value = false;
  }
};

// ---------------------------------------------------------------------------
// 接口树
// ---------------------------------------------------------------------------

interface InterfaceTreeNode {
  key: string;
  title: string;
  isLeaf: boolean;
  children?: InterfaceTreeNode[];
}

const moduleAbsolutePath = (moduleId: number | null | undefined): string => {
  const map = new Map<number, ApiModule>();
  flatModules.value.forEach(m => map.set(m.id, m));
  const parts: string[] = [];
  let current = moduleId ? map.get(moduleId) : undefined;
  let guard = 0;
  while (current && guard < 10) {
    parts.unshift(current.name);
    current = current.parent ? map.get(current.parent) : undefined;
    guard += 1;
  }
  return parts.join(' / ');
};

const buildModuleNode = (module: ApiModule, keyword: string, depth: number): InterfaceTreeNode => {
  const moduleInterfaces = interfaces.value.filter(item => item.module === module.id);
  const interfaceNodes: InterfaceTreeNode[] = moduleInterfaces
    .filter(item => !keyword
      || item.name.toLowerCase().includes(keyword)
      || (item.url || '').toLowerCase().includes(keyword))
    .map(item => ({
      key: `iface-${item.id}`,
      title: `${item.method || ''} ${item.name}`.trim(),
      isLeaf: true,
    }));
  // 递归包含子模块，保证二级及更深模块下的接口可见可选
  const childModuleNodes: InterfaceTreeNode[] = depth < 10
    ? (module.children || []).map(child => buildModuleNode(child, keyword, depth + 1))
    : [];
  return {
    key: `module-${module.id}`,
    title: module.name,
    isLeaf: false,
    children: [...childModuleNodes, ...interfaceNodes],
  };
};

const matchKeyword = (node: InterfaceTreeNode, hasKeyword: boolean): boolean => {
  if (!hasKeyword) return true;
  if (node.isLeaf) return true; // 叶子节点在构建时已按关键字过滤
  return (node.children || []).some(child => matchKeyword(child, hasKeyword));
};

const interfaceTreeData = computed<InterfaceTreeNode[]>(() => {
  const keyword = interfaceSearch.value.trim().toLowerCase();
  const hasKeyword = !!keyword;
  const nodes = modules.value.map(module => buildModuleNode(module, keyword, 0));
  // 附加"未分组"节点：归属模块为空的接口也能选择
  const unmatched = interfaces.value.filter(item => !item.module || !flatModules.value.some(m => m.id === item.module));
  if (unmatched.length) {
    const unmatchedNode: InterfaceTreeNode = {
      key: 'module-ungrouped',
      title: isEnglish.value ? 'Ungrouped' : '未分组',
      isLeaf: false,
      children: unmatched
        .filter(item => !hasKeyword
          || item.name.toLowerCase().includes(keyword)
          || (item.url || '').toLowerCase().includes(keyword))
        .map(item => ({
          key: `iface-${item.id}`,
          title: `${item.method || ''} ${item.name}`.trim(),
          isLeaf: true,
        })),
    };
    nodes.push(unmatchedNode);
  }
  return nodes.filter(node => matchKeyword(node, hasKeyword) && (node.children && node.children.length ? true : !hasKeyword));
});

const interfaceTreeKey = computed(() => `tree-${projectStore.currentProjectId}-${interfaceSearch.value ? 'search' : 'full'}`);

const expandedModuleKeys = computed(() =>
  modules.value.slice(0, 3).map(module => `module-${module.id}`),
);

const selectedInterfaceIds = computed(() => formState.value.selectedInterfaceIds);

const handleInterfaceCheck = (checkedKeys: Array<string | number>) => {
  formState.value.selectedInterfaceIds = checkedKeys
    .map(key => String(key))
    .filter(key => key.startsWith('iface-'))
    .map(key => Number(key.replace('iface-', '')));
};

// 登录接口自动识别
const loginCandidates = computed(() => {
  // 候选为项目全部 HTTP 接口：单接口场景下登录接口通常不在业务接口集合内
  return interfaces.value.map(item => ({
    id: item.id,
    label: `${item.method || ''} ${item.name} ${moduleAbsolutePath(item.module) ? `(${moduleAbsolutePath(item.module)})` : ''}`.trim(),
  }));
});

const archetypeOptions = computed(() => [
  { value: 'S1', label: pageText.value.archS1, tip: pageText.value.archTipS1 },
  { value: 'S2', label: pageText.value.archS2, tip: pageText.value.archTipS2 },
  { value: 'S3', label: pageText.value.archS3, tip: pageText.value.archTipS3 },
  { value: 'S4', label: pageText.value.archS4, tip: pageText.value.archTipS4 },
]);

const groupOptions = computed(() => {
  const options: { id: number; name: string }[] = [];
  const walk = (list: ApiTestCaseGroup[], prefix: string, depth: number) => {
    if (depth > 8) return;
    for (const group of list) {
      const label = prefix ? `${prefix} / ${group.name}` : group.name;
      options.push({ id: group.id, name: label });
      if (group.children && group.children.length) {
        walk(group.children, label, depth + 1);
      }
    }
  };
  walk(groups.value, '', 0);
  return options;
});

// ---------------------------------------------------------------------------
// 文档与 DB 校验
// ---------------------------------------------------------------------------

const handleDocumentChange = (fileList: any[]) => {
  documentFileList.value = fileList.slice(-1);
  const fileItem = fileList[fileList.length - 1];
  formState.value.documentFile = fileItem?.file instanceof File ? fileItem.file : null;
};

const removeDocumentFile = () => {
  documentFileList.value = [];
  formState.value.documentFile = null;
};

const hasActiveDbConfig = async (): Promise<boolean> => {
  try {
    const pid = projectStore.currentProjectId ?? 0;
    const response = await environmentService.list(pid, {});
    const environments: any[] = Array.isArray(response)
      ? response
      : (response as any)?.data?.results || (response as any)?.data || [];
    return environments.some(env => env.database_config);
  } catch {
    return false;
  }
};

const handleDbSwitchChange = async (value: boolean | string | number) => {
  if (!value) {
    dbCheckWarning.value = '';
    return;
  }
  const ok = await hasActiveDbConfig();
  if (!ok) {
    dbCheckWarning.value = isEnglish.value
      ? 'No environment with database config found; generated SQL steps may fail at runtime.'
      : '未检测到配置了数据库连接的环境，生成的 SQL 步骤运行时可能失败。';
  } else {
    dbCheckWarning.value = '';
  }
};

// ---------------------------------------------------------------------------
// 提交
// ---------------------------------------------------------------------------

const validate = (): string => {
  if (!selectedInterfaceIds.value.length) {
    return pageText.value.selectedCount.replace('{count}', '0');
  }
  if (formState.value.caseType === 'scenario' && selectedInterfaceIds.value.length < 2) {
    return isEnglish.value
      ? 'Scenario cases need at least 2 interfaces selected.'
      : '场景用例至少需要选择 2 个接口。';
  }
  if (formState.value.caseType === 'interface_case' && formState.value.dimensions.length === 0) {
    return isEnglish.value ? 'Select at least one dimension.' : '至少选择一个生成维度。';
  }
  if (formState.value.caseType === 'scenario' && formState.value.archetypes.length === 0) {
    return isEnglish.value ? 'Select at least one archetype.' : '至少选择一个场景原型。';
  }
  if (formState.value.useKnowledgeBase && !formState.value.knowledgeBaseId && knowledgeBases.value.length) {
    return isEnglish.value ? 'Select a knowledge base.' : '请选择知识库。';
  }
  return '';
};

const handleSubmit = async () => {
  const error = validate();
  if (error) {
    Message.warning(error);
    return;
  }
  isSubmitting.value = true;
  try {
    const payload: GenerationFormData = {
      caseType: formState.value.caseType,
      dimensions: [...formState.value.dimensions],
      archetypes: [...formState.value.archetypes],
      interfaceIds: [...selectedInterfaceIds.value],
      loginInterfaceId: formState.value.loginInterfaceId,
      useKnowledgeBase: formState.value.useKnowledgeBase,
      knowledgeBaseId: formState.value.knowledgeBaseId,
      businessNotes: formState.value.businessNotes.trim(),
      dbVerification: formState.value.dbVerification,
      groupId: formState.value.groupId,
      caseLimit: formState.value.caseLimit,
      promptId: formState.value.promptId,
    };
    emit('submit', payload);
    emit('update:visible', false);
  } finally {
    isSubmitting.value = false;
  }
};

const handleCancel = () => {
  emit('update:visible', false);
};

watch(() => props.visible, (visible) => {
  if (visible) {
    formState.value.selectedInterfaceIds = [];
    interfaceSearch.value = '';
    dbCheckWarning.value = '';
    fetchData();
  }
});

// 供父组件使用：约束提取前需要文件
defineExpose({
  getDocumentFile: () => formState.value.documentFile,
});
</script>

<style scoped>
.login-option {
  max-width: 360px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}
.form-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 8px;
}
.form-row-label {
  width: 96px;
  flex-shrink: 0;
  font-weight: 500;
  text-align: right;
  color: var(--color-text-1);
  line-height: 32px;
}
.form-row-label.required::before {
  content: '*';
  color: rgb(var(--danger-6));
  margin-right: 2px;
}
.archetype-tip-icon {
  margin-left: 2px;
  color: var(--color-text-3);
  cursor: help;
}
.dimension-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  line-height: 32px;
}
.interface-select-row {
  align-items: stretch;
}
.interface-select-area {
  flex: 1;
  border: 1px solid var(--color-border-2);
  border-radius: 4px;
  padding: 8px;
}
.interface-search {
  margin-bottom: 8px;
}
.interface-tree-wrapper {
  max-height: 240px;
  overflow-y: auto;
}
.selected-count {
  margin-top: 6px;
  font-size: 12px;
  color: var(--color-text-3);
}
.upload-area {
  flex: 1;
}
.upload-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-3);
}
.kb-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.db-area {
  display: flex;
  align-items: center;
  gap: 12px;
  line-height: 32px;
}
.db-warning {
  font-size: 12px;
  color: rgb(var(--orange-6));
}
.group-empty-hint {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--color-text-3);
  white-space: normal;
  line-height: 1.5;
}
.upload-file-item {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  padding: 4px 8px;
  border: 1px solid var(--color-border-2);
  border-radius: 4px;
  background-color: var(--color-fill-1);
}
.upload-file-icon {
  color: var(--color-text-2);
  flex-shrink: 0;
}
.upload-file-name {
  flex: 1;
  font-size: 12px;
  color: var(--color-text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.login-select-area {
  flex: 1;
}
.login-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-3);
}
</style>
