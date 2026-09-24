<template>
  <a-modal
    :visible="visible"
    :title="pageText.modalTitle"
    :width="820"
    :confirm-loading="isSubmitting"
    @cancel="handleCancel"
    @ok="handleSubmit"
  >
    <a-form :model="formState" :label-col-props="{ span: 5 }" :wrapper-col-props="{ span: 19 }">
      <div class="form-row">
        <span class="form-row-label">{{ pageText.currentProject }}</span>
        <a-input :model-value="currentProjectName" disabled style="width: 200px;" />
      </div>

      <!-- 需求模块（文档级联单选） -->
      <div class="form-row">
        <span class="form-row-label required">{{ pageText.requirementModule }}</span>
        <div class="cascade-area">
          <a-select
            v-model="formState.requirementDocumentId"
            :placeholder="pageText.selectDocument"
            :loading="isDocsLoading"
            allow-search
            style="width: 100%;"
            @change="handleDocumentChange"
          >
            <a-option v-for="doc in requirementDocuments" :key="doc.id" :value="doc.id">
              {{ doc.title }}
            </a-option>
          </a-select>
          <a-select
            v-model="formState.requirementModuleId"
            :placeholder="pageText.selectModule"
            :loading="isModulesLoading"
            :disabled="!formState.requirementDocumentId"
            allow-search
            style="width: 100%; margin-top: 8px;"
          >
            <a-option v-for="mod in requirementModules" :key="mod.id" :value="mod.id">
              {{ mod.title }}
            </a-option>
          </a-select>
          <div class="field-hint">{{ pageText.requirementModuleHint }}</div>
        </div>
      </div>

      <!-- 保存目标模块 -->
      <div class="form-row">
        <span class="form-row-label required">{{ pageText.targetModule }}</span>
        <a-tree-select
          v-model="formState.targetModuleId"
          :data="moduleTreeData"
          :placeholder="pageText.selectModuleTree"
          :loading="isModuleTreeLoading"
          allow-search
          style="width: 360px;"
        />
      </div>

      <!-- 环境配置 -->
      <div class="form-row">
        <span class="form-row-label required">{{ pageText.envConfig }}</span>
        <div class="env-area">
          <a-select
            v-model="formState.envConfigId"
            :placeholder="pageText.selectEnv"
            :loading="isEnvLoading"
            allow-search
            style="width: 360px;"
            @change="handleEnvChange"
          >
            <a-option v-for="env in envConfigs" :key="env.id" :value="env.id">
              {{ env.name }}{{ env.base_url ? ` (${env.base_url})` : '' }}
            </a-option>
          </a-select>
          <div class="field-hint">{{ selectedEnvBaseUrl || pageText.envNoUrlHint }}</div>
        </div>
      </div>

      <!-- 认证方式 -->
      <div class="form-row">
        <span class="form-row-label">{{ pageText.authMode }}</span>
        <div class="auth-area">
          <a-radio-group v-model="formState.authMode" direction="vertical">
            <a-radio value="auth_state" :disabled="!formState.envConfigId || authStates.length === 0">
              {{ pageText.authByState }}
            </a-radio>
            <a-radio value="credentials">{{ pageText.authByCredentials }}</a-radio>
            <a-radio value="none">{{ pageText.authNone }}</a-radio>
          </a-radio-group>
          <a-select
            v-if="formState.authMode === 'auth_state'"
            v-model="formState.authStateId"
            :placeholder="pageText.selectAuthState"
            :loading="isAuthStateLoading"
            style="width: 360px; margin-top: 8px;"
          >
            <a-option v-for="state in authStates" :key="state.id" :value="state.id">
              {{ state.name }}
            </a-option>
          </a-select>
          <template v-if="formState.authMode === 'credentials'">
            <a-input
              v-model="formState.username"
              :placeholder="pageText.username"
              style="width: 360px; margin-top: 8px;"
              allow-clear
            />
            <a-input-password
              v-model="formState.password"
              :placeholder="pageText.password"
              style="width: 360px; margin-top: 8px;"
            />
            <div class="field-hint">{{ pageText.credentialsHint }}</div>
          </template>
        </div>
      </div>

      <!-- 生成深度 + 条数上限 -->
      <div class="form-row">
        <span class="form-row-label required">{{ pageText.depth }}</span>
        <a-radio-group v-model="formState.depth">
          <a-radio value="positive">
            {{ pageText.depthPositive }}
            <a-tooltip :content="pageText.depthPositiveTip" position="top">
              <icon-question-circle class="depth-tip-icon" />
            </a-tooltip>
          </a-radio>
          <a-radio value="full">
            {{ pageText.depthFull }}
            <a-tooltip :content="pageText.depthFullTip" position="top">
              <icon-question-circle class="depth-tip-icon" />
            </a-tooltip>
          </a-radio>
        </a-radio-group>
        <span class="form-row-label" style="margin-left: 24px;">{{ pageText.caseLimit }}</span>
        <a-input-number v-model="formState.caseLimit" :min="1" :max="30" style="width: 110px;" />
      </div>

      <!-- 知识库 -->
      <div class="form-row">
        <span class="form-row-label">{{ pageText.knowledgeBase }}</span>
        <div class="kb-area">
          <a-checkbox v-model="formState.useKnowledgeBase">
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
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { useProjectStore } from '@/store/projectStore';
import { useAppI18n } from '@/composables/useAppI18n';
import { moduleApi } from '../../api';
import { KnowledgeService } from '@/features/knowledge/services/knowledgeService';
import type { KnowledgeBase } from '@/features/knowledge/types/knowledge';
import type { UiModule, UiEnvironmentConfig, UiAuthState } from '../../types';
import type { DocumentModule } from '@/features/requirements/types';
import {
  fetchRequirementDocuments,
  fetchRequirementModules,
  fetchEnvConfigs,
  fetchAuthStates,
  fetchModuleTree,
  flattenModuleTree,
  type UiGenerationFormData,
} from '../../services/uiCaseGeneration';

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
  (e: 'submit', payload: UiGenerationFormData): void;
}>();

const projectStore = useProjectStore();
const { isEnglish } = useAppI18n();

const pageText = computed(() => isEnglish.value ? {
  modalTitle: 'AI Generate UI Test Cases',
  currentProject: 'Project',
  requirementModule: 'Requirement Module',
  selectDocument: 'Select requirement document (module-split)',
  selectModule: 'Select requirement module',
  requirementModuleHint: 'Single module per generation to keep the business scope focused.',
  targetModule: 'Save to Module',
  selectModuleTree: 'Select target module',
  envConfig: 'Environment',
  selectEnv: 'Select environment',
  envNoUrlHint: 'No base URL configured on this environment.',
  authMode: 'Authentication',
  authByState: 'Use saved login state (recommended)',
  authByCredentials: 'Username & password login',
  authNone: 'No authentication',
  selectAuthState: 'Select login state',
  username: 'Username',
  password: 'Password',
  credentialsHint: 'Credentials are injected platform-side via environment variables; never shown in conversation.',
  depth: 'Coverage',
  depthPositive: 'Positive main flow',
  depthPositiveTip: 'Only end-to-end normal flows that verify the module works as expected.',
  depthFull: 'Full coverage',
  depthFullTip: 'Adds form validation, boundaries, exceptions and page state transitions on top of the main flows.',
  caseLimit: 'Case Limit',
  knowledgeBase: 'Knowledge Base',
  useKnowledgeBase: 'Search knowledge base for business flows',
  selectPlaceholder: 'Select',
  businessNotes: 'Business Notes',
  businessNotesPlaceholder: 'Optional. Describe business rules, page states, dependencies...',
} : {
  modalTitle: 'AI 生成 UI 自动化测试用例',
  currentProject: '当前项目',
  requirementModule: '需求模块',
  selectDocument: '请选择需求文档（已拆分模块）',
  selectModule: '请选择需求模块',
  requirementModuleHint: '每次仅选择一个模块，避免一次生成跨过多业务面。',
  targetModule: '保存模块',
  selectModuleTree: '请选择保存目标模块',
  envConfig: '环境配置',
  selectEnv: '请选择环境配置',
  envNoUrlHint: '该环境未配置 base_url。',
  authMode: '认证方式',
  authByState: '使用已有登录态（推荐）',
  authByCredentials: '账号密码登录',
  authNone: '无鉴权',
  selectAuthState: '请选择登录态',
  username: '账号',
  password: '密码',
  credentialsHint: '账密由平台侧通过环境变量注入，对话中不会显示明文。',
  depth: '生成深度',
  depthPositive: '正向主流程',
  depthPositiveTip: '仅生成验证业务正常走通的端到端主流程用例。',
  depthFull: '完整覆盖',
  depthFullTip: '在正向主流程之上，追加表单校验、边界条件、异常场景与页面状态流转用例。',
  caseLimit: '条数上限',
  knowledgeBase: '知识库',
  useKnowledgeBase: '检索知识库补充业务流程',
  selectPlaceholder: '请选择',
  businessNotes: '业务描述',
  businessNotesPlaceholder: '可选。描述业务规则、页面状态、依赖关系等',
});

const currentProjectName = computed(() => projectStore.currentProject?.name || '');
const projectId = computed(() => projectStore.currentProjectId ?? 0);

interface FormState {
  requirementDocumentId: string | null;
  requirementModuleId: string | null;
  targetModuleId: number | null;
  envConfigId: number | null;
  authMode: 'auth_state' | 'credentials' | 'none';
  authStateId: number | null;
  username: string;
  password: string;
  depth: 'positive' | 'full';
  caseLimit: number;
  useKnowledgeBase: boolean;
  knowledgeBaseId: string | null;
  businessNotes: string;
}

const formState = ref<FormState>({
  requirementDocumentId: null,
  requirementModuleId: null,
  targetModuleId: null,
  envConfigId: null,
  authMode: 'auth_state',
  authStateId: null,
  username: '',
  password: '',
  depth: 'positive',
  caseLimit: 6,
  useKnowledgeBase: false,
  knowledgeBaseId: null,
  businessNotes: '',
});

const isSubmitting = ref(false);
const requirementDocuments = ref<Array<{ id: string; title: string }>>([]);
const requirementModules = ref<DocumentModule[]>([]);
const moduleTree = ref<UiModule[]>([]);
const envConfigs = ref<UiEnvironmentConfig[]>([]);
const authStates = ref<UiAuthState[]>([]);
const knowledgeBases = ref<KnowledgeBase[]>([]);
const isDocsLoading = ref(false);
const isModulesLoading = ref(false);
const isModuleTreeLoading = ref(false);
const isEnvLoading = ref(false);
const isAuthStateLoading = ref(false);
const isKbLoading = ref(false);

const moduleTreeData = computed(() =>
  flattenModuleTree(moduleTree.value).map((item) => ({ key: item.id, title: item.label }))
);

const selectedEnvBaseUrl = computed(() =>
  envConfigs.value.find((env) => env.id === formState.value.envConfigId)?.base_url || ''
);

const loadRequirementDocuments = async () => {
  if (!projectId.value) return;
  isDocsLoading.value = true;
  try {
    requirementDocuments.value = await fetchRequirementDocuments(projectId.value);
  } catch {
    requirementDocuments.value = [];
  } finally {
    isDocsLoading.value = false;
  }
};

const handleDocumentChange = async (documentId: string | number | boolean | Record<string, any> | (string | number | boolean | Record<string, any>)[] | undefined) => {
  formState.value.requirementModuleId = null;
  requirementModules.value = [];
  if (!documentId || typeof documentId !== 'string') return;
  isModulesLoading.value = true;
  try {
    requirementModules.value = await fetchRequirementModules(documentId);
  } catch {
    requirementModules.value = [];
  } finally {
    isModulesLoading.value = false;
  }
};

const loadModuleTree = async () => {
  if (!projectId.value) return;
  isModuleTreeLoading.value = true;
  try {
    moduleTree.value = await fetchModuleTree(projectId.value);
  } catch {
    moduleTree.value = [];
  } finally {
    isModuleTreeLoading.value = false;
  }
};

const loadEnvConfigs = async () => {
  if (!projectId.value) return;
  isEnvLoading.value = true;
  try {
    envConfigs.value = await fetchEnvConfigs(projectId.value);
    // 默认选中默认环境
    if (!formState.value.envConfigId) {
      const defaultEnv = envConfigs.value.find((env) => env.is_default) || envConfigs.value[0];
      if (defaultEnv) {
        formState.value.envConfigId = defaultEnv.id;
        await loadAuthStates(defaultEnv.id);
      }
    }
  } catch {
    envConfigs.value = [];
  } finally {
    isEnvLoading.value = false;
  }
};

const loadAuthStates = async (envConfigId: number) => {
  isAuthStateLoading.value = true;
  try {
    authStates.value = await fetchAuthStates(envConfigId);
    if (!authStates.value.length) {
      formState.value.authStateId = null;
      if (formState.value.authMode === 'auth_state') {
        formState.value.authMode = 'credentials';
      }
    } else if (!formState.value.authStateId) {
      formState.value.authStateId = authStates.value[0].id;
    }
  } catch {
    authStates.value = [];
  } finally {
    isAuthStateLoading.value = false;
  }
};

const handleEnvChange = async (envId: string | number | boolean | Record<string, any> | (string | number | boolean | Record<string, any>)[] | undefined) => {
  formState.value.authStateId = null;
  if (typeof envId === 'number') {
    await loadAuthStates(envId);
  } else {
    authStates.value = [];
  }
};

const loadKnowledgeBases = async () => {
  if (!projectId.value) return;
  isKbLoading.value = true;
  try {
    const response = await KnowledgeService.getKnowledgeBases({ project: projectId.value });
    knowledgeBases.value = Array.isArray(response) ? response : (response as any).results || [];
  } catch {
    knowledgeBases.value = [];
  } finally {
    isKbLoading.value = false;
  }
};

const validate = (): string => {
  if (!formState.value.requirementModuleId) {
    return isEnglish.value ? 'Select a requirement module.' : '请选择需求模块。';
  }
  if (!formState.value.targetModuleId) {
    return isEnglish.value ? 'Select a target module.' : '请选择保存目标模块。';
  }
  if (!formState.value.envConfigId) {
    return isEnglish.value ? 'Select an environment.' : '请选择环境配置。';
  }
  if (formState.value.authMode === 'auth_state' && !formState.value.authStateId) {
    return isEnglish.value ? 'Select a login state or switch auth mode.' : '请选择登录态，或切换认证方式。';
  }
  if (formState.value.authMode === 'credentials' && (!formState.value.username.trim() || !formState.value.password)) {
    return isEnglish.value ? 'Username and password are required.' : '账号密码登录需填写账号与密码。';
  }
  if (formState.value.useKnowledgeBase && !formState.value.knowledgeBaseId && knowledgeBases.value.length) {
    return isEnglish.value ? 'Select a knowledge base.' : '请选择知识库。';
  }
  return '';
};

const handleSubmit = () => {
  const error = validate();
  if (error) {
    Message.warning(error);
    return;
  }
  isSubmitting.value = true;
  try {
    emit('submit', {
      requirementDocumentId: formState.value.requirementDocumentId,
      requirementModuleId: formState.value.requirementModuleId,
      targetModuleId: formState.value.targetModuleId,
      envConfigId: formState.value.envConfigId,
      authMode: formState.value.authMode,
      authStateId: formState.value.authMode === 'auth_state' ? formState.value.authStateId : null,
      username: formState.value.authMode === 'credentials' ? formState.value.username.trim() : '',
      password: formState.value.authMode === 'credentials' ? formState.value.password : '',
      depth: formState.value.depth,
      caseLimit: formState.value.caseLimit,
      useKnowledgeBase: formState.value.useKnowledgeBase,
      knowledgeBaseId: formState.value.useKnowledgeBase ? formState.value.knowledgeBaseId : null,
      businessNotes: formState.value.businessNotes.trim(),
    });
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
    formState.value.requirementDocumentId = null;
    formState.value.requirementModuleId = null;
    formState.value.targetModuleId = null;
    formState.value.authStateId = null;
    formState.value.username = '';
    formState.value.password = '';
    formState.value.businessNotes = '';
    requirementModules.value = [];
    loadRequirementDocuments();
    loadModuleTree();
    loadEnvConfigs();
    loadKnowledgeBases();
  }
});
</script>

<style scoped>
.form-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 18px;
}

.form-row-label {
  flex-shrink: 0;
  width: 110px;
  padding-top: 6px;
  color: var(--color-text-2);
  font-size: 14px;
}

.form-row-label.required::before {
  content: '*';
  margin-right: 4px;
  color: rgb(var(--red-6));
}

.cascade-area,
.env-area,
.auth-area,
.kb-area {
  flex: 1;
  max-width: 520px;
}

.field-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-3);
}

.depth-tip-icon {
  margin-left: 2px;
  color: var(--color-text-3);
  cursor: help;
}
</style>
