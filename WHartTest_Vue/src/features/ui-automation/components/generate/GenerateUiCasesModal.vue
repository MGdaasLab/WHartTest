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

      <!-- 功能用例选择（生成依据） -->
      <div class="form-row">
        <span class="form-row-label required">{{ pageText.functionalCases }}</span>
        <div class="case-select-area">
          <a-button type="outline" size="small" @click="isSelectorVisible = true">
            {{ pageText.selectCasesButton }}
          </a-button>
          <span v-if="formState.selectedFunctionalCaseIds.length" class="selected-count-inline">
            {{ pageText.selectedCount.replace('{count}', String(formState.selectedFunctionalCaseIds.length)) }}
          </span>
          <div class="field-hint">{{ pageText.casesHint }}</div>
        </div>
      </div>

      <!-- 功能用例选择子弹窗 -->
      <SelectFunctionalCasesModal
        v-model:visible="isSelectorVisible"
        :selected-ids="formState.selectedFunctionalCaseIds"
        @confirm="handleCasesConfirmed"
      />

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
import { KnowledgeService } from '@/features/knowledge/services/knowledgeService';
import type { KnowledgeBase } from '@/features/knowledge/types/knowledge';
import type { UiModule, UiEnvironmentConfig, UiAuthState } from '../../types';
import SelectFunctionalCasesModal from './SelectFunctionalCasesModal.vue';
import {
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
  functionalCases: 'Functional Cases',
  selectCasesButton: 'Select functional cases',
  selectedCount: '{count} case(s) selected',
  casesHint: 'Cases already bound to a UI case are disabled. Each selected case generates one UI case, replay-verified, then bound back.',
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
  knowledgeBase: 'Knowledge Base',
  useKnowledgeBase: 'Search knowledge base for business flows',
  selectPlaceholder: 'Select',
  businessNotes: 'Business Notes',
  businessNotesPlaceholder: 'Optional. Describe business rules, page states, dependencies...',
} : {
  modalTitle: 'AI 生成 UI 自动化测试用例',
  currentProject: '当前项目',
  functionalCases: '功能用例',
  selectCasesButton: '选择功能用例',
  selectedCount: '已选 {count} 条用例',
  casesHint: '已绑定 UI 用例的功能用例不可选；每条选中用例生成一条 UI 用例，试跑通过后自动回写绑定。',
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
  knowledgeBase: '知识库',
  useKnowledgeBase: '检索知识库补充业务流程',
  selectPlaceholder: '请选择',
  businessNotes: '业务描述',
  businessNotesPlaceholder: '可选。描述业务规则、页面状态、依赖关系等',
});

const currentProjectName = computed(() => projectStore.currentProject?.name || '');
const projectId = computed(() => projectStore.currentProjectId ?? 0);

interface FormState {
  selectedFunctionalCaseIds: number[];
  targetModuleId: number | null;
  envConfigId: number | null;
  authMode: 'auth_state' | 'credentials' | 'none';
  authStateId: number | null;
  username: string;
  password: string;
  useKnowledgeBase: boolean;
  knowledgeBaseId: string | null;
  businessNotes: string;
}

const formState = ref<FormState>({
  selectedFunctionalCaseIds: [],
  targetModuleId: null,
  envConfigId: null,
  authMode: 'auth_state',
  authStateId: null,
  username: '',
  password: '',
  useKnowledgeBase: false,
  knowledgeBaseId: null,
  businessNotes: '',
});

const isSubmitting = ref(false);
const isSelectorVisible = ref(false);
const moduleTree = ref<UiModule[]>([]);
const envConfigs = ref<UiEnvironmentConfig[]>([]);
const authStates = ref<UiAuthState[]>([]);
const knowledgeBases = ref<KnowledgeBase[]>([]);
const isCasesLoading = ref(false);
const isModuleTreeLoading = ref(false);
const isEnvLoading = ref(false);
const isAuthStateLoading = ref(false);
const isKbLoading = ref(false);

const handleCasesConfirmed = (ids: number[]) => {
  formState.value.selectedFunctionalCaseIds = ids;
};

const moduleTreeData = computed(() =>
  flattenModuleTree(moduleTree.value).map((item) => ({ key: item.id, title: item.label }))
);

const selectedEnvBaseUrl = computed(() =>
  envConfigs.value.find((env) => env.id === formState.value.envConfigId)?.base_url || ''
);

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
  if (!formState.value.selectedFunctionalCaseIds.length) {
    return isEnglish.value ? 'Select at least one functional case.' : '请至少选择一条功能用例。';
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
      selectedFunctionalCaseIds: [...formState.value.selectedFunctionalCaseIds],
      targetModuleId: formState.value.targetModuleId,
      envConfigId: formState.value.envConfigId,
      authMode: formState.value.authMode,
      authStateId: formState.value.authMode === 'auth_state' ? formState.value.authStateId : null,
      username: formState.value.authMode === 'credentials' ? formState.value.username.trim() : '',
      password: formState.value.authMode === 'credentials' ? formState.value.password : '',
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
    formState.value.selectedFunctionalCaseIds = [];
    formState.value.targetModuleId = null;
    formState.value.authStateId = null;
    formState.value.username = '';
    formState.value.password = '';
    formState.value.businessNotes = '';
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

.case-select-area,
.env-area,
.auth-area,
.kb-area {
  flex: 1;
  max-width: 520px;
}

.selected-count-inline {
  margin-left: 10px;
  font-size: 13px;
  color: var(--color-text-2);
}


.field-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-3);
}
</style>
