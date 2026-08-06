<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { Message } from '@arco-design/web-vue'
import type { ApiInterface, TestCase, TestStep } from '../../services/syncService'
import { syncApi } from '../../services/syncService'
import { toArray } from '../../services/responseHelpers'
import { useAppI18n } from '@/composables/useAppI18n'
import { useProjectStore } from '@/store/projectStore'
import { useThemeStore } from '@/store/themeStore'

const projectStore = useProjectStore()
const themeStore = useThemeStore()
const { isEnglish } = useAppI18n()
const isDarkTheme = computed(() => themeStore.isBlack)

const props = defineProps<{
  visible: boolean
  loading: boolean
  isEditing: boolean
  fieldOptions: { label: string; value: string }[]
  currentConfig?: any
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'submit', data: any): void
}>()

interface FormModel {
  name: string
  description: string
  interface: number | undefined
  testcase: number | undefined
  step: number | undefined
  sync_fields: string[]
  sync_enabled: boolean
  sync_mode: 'manual' | 'auto'
  sync_trigger: {
    fields_to_watch: string[]
  }
}

const formModel = reactive<FormModel>({
  name: '',
  description: '',
  interface: undefined,
  testcase: undefined,
  step: undefined,
  sync_fields: [],
  sync_enabled: true,
  sync_mode: 'manual',
  sync_trigger: {
    fields_to_watch: []
  }
})

const resetForm = () => {
  isLoadingStepsFromConfig.value = false
  formModel.name = ''
  formModel.description = ''
  formModel.interface = undefined
  formModel.testcase = undefined
  formModel.step = undefined
  formModel.sync_fields = []
  formModel.sync_enabled = true
  formModel.sync_mode = 'manual'
  formModel.sync_trigger.fields_to_watch = []
  teststeps.value = []
}

const modalVisible = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value)
})

const text = computed(() => isEnglish.value
  ? {
      editSyncConfig: 'Edit Sync Config',
      createSyncConfig: 'Create Sync Config',
      configName: 'Config Name',
      enterConfigName: 'Enter config name',
      configDescription: 'Config Description',
      enterConfigDescription: 'Enter config description',
      selectInterface: 'Select Interface',
      selectAnInterface: 'Select an interface',
      selectTestCase: 'Select Test Case',
      selectATestCase: 'Select a test case',
      selectStep: 'Select Step',
      selectAStep: 'Select a step',
      syncFields: 'Sync Fields',
      selectSyncFields: 'Select sync fields',
      syncMode: 'Sync Mode',
      manualSync: 'Manual Sync',
      autoSync: 'Auto Sync',
      watchFields: 'Watch Fields',
      selectFieldsToWatch: 'Select fields to watch',
      enableSync: 'Enable Sync',
      fillRequired: 'Please fill in required fields',
      selectProjectFirst: 'Please select a project first',
      fetchInterfacesFailed: 'Failed to fetch interfaces',
      fetchTestCasesFailed: 'Failed to fetch test cases',
      fetchStepsFailed: 'Failed to fetch test steps',
      stepPrefix: 'Step',
    }
  : {
      editSyncConfig: '编辑同步配置',
      createSyncConfig: '新建同步配置',
      configName: '配置名称',
      enterConfigName: '请输入配置名称',
      configDescription: '配置描述',
      enterConfigDescription: '请输入配置描述',
      selectInterface: '选择接口',
      selectAnInterface: '请选择接口',
      selectTestCase: '选择用例',
      selectATestCase: '请选择用例',
      selectStep: '选择步骤',
      selectAStep: '请选择步骤',
      syncFields: '同步字段',
      selectSyncFields: '请选择同步字段',
      syncMode: '同步模式',
      manualSync: '手动同步',
      autoSync: '自动同步',
      watchFields: '监视字段',
      selectFieldsToWatch: '请选择需要监视的字段',
      enableSync: '启用同步',
      fillRequired: '请填写必填项',
      selectProjectFirst: '请先选择项目',
      fetchInterfacesFailed: '获取接口列表失败',
      fetchTestCasesFailed: '获取用例列表失败',
      fetchStepsFailed: '获取步骤列表失败',
      stepPrefix: '步骤',
    }
)

const fieldLabelMap: Record<string, string> = {
  '请求方法': 'Request Method',
  'URL': 'URL',
  '请求头': 'Headers',
  '查询参数': 'Query Params',
  '请求体': 'Request Body',
  '前置钩子': 'Setup Hooks',
  '后置钩子': 'Teardown Hooks',
  '变量定义': 'Variables',
  '断言规则': 'Validators',
  '提取变量': 'Extract Variables',
}

const localizedFieldOptions = computed(() => {
  if (!isEnglish.value) {
    return props.fieldOptions
  }

  return props.fieldOptions.map(option => ({
    ...option,
    label: fieldLabelMap[option.label] || option.label,
  }))
})

const getStepOptionLabel = (item: TestStep) => (
  isEnglish.value ? `${item.name} (${text.value.stepPrefix} ${item.order})` : `${item.name} (${text.value.stepPrefix}${item.order})`
)

// 添加接口、用例和步骤的列表数据
const interfaces = ref<ApiInterface[]>([])
const testcases = ref<TestCase[]>([])
const teststeps = ref<TestStep[]>([])

// 添加加载状态
const loadingInterfaces = ref(false)
const loadingTestcases = ref(false)
const loadingTestSteps = ref(false)

// 添加一个标志位，用于避免重复请求
const isLoadingStepsFromConfig = ref(false);

// 获取接口列表
const fetchInterfaces = async () => {
  if (!projectStore.currentProject?.id) {
    Message.error(text.value.selectProjectFirst)
    return
  }

  try {
    loadingInterfaces.value = true
    const { data } = await syncApi.getInterfaces(projectStore.currentProject.id)
    interfaces.value = toArray<ApiInterface>(data?.results ?? data)
  } catch (error) {
    Message.error(text.value.fetchInterfacesFailed)
    console.error(error)
  } finally {
    loadingInterfaces.value = false
  }
}

// 获取用例列表
const fetchTestCases = async () => {
  if (!projectStore.currentProject?.id) {
    Message.error(text.value.selectProjectFirst)
    return
  }

  try {
    loadingTestcases.value = true
    const { data } = await syncApi.getTestCases(projectStore.currentProject.id)
    testcases.value = toArray<TestCase>(data?.results ?? data)
  } catch (error) {
    Message.error(text.value.fetchTestCasesFailed)
    console.error(error)
  } finally {
    loadingTestcases.value = false
  }
}

// 获取步骤列表
const fetchTestSteps = async () => {
  if (!formModel.testcase) {
    teststeps.value = []
    return
  }
  
  try {
    loadingTestSteps.value = true
    const { data } = await syncApi.getTestSteps(formModel.testcase)
    // 适配新的API返回格式
    teststeps.value = data.steps?.map(step => ({
      id: step.id,
      name: step.name,
      order: step.order,
      interface_info: step.interface_info
    })) || []
  } catch (error) {
    console.error('获取步骤列表失败:', error)
    Message.error(text.value.fetchStepsFailed)
    teststeps.value = []
  } finally {
    loadingTestSteps.value = false
  }
}

// 监听用例选择变化
watch(() => formModel.testcase, (newTestcaseId) => {
  // 如果是从配置加载步骤，则不重复请求
  if (isLoadingStepsFromConfig.value) {
    return;
  }
  
  formModel.step = undefined;
  teststeps.value = [];
  if (newTestcaseId) {
    fetchTestSteps();
  }
})

// 监听currentConfig变化，用于编辑时回显数据
watch(() => props.currentConfig, async (newConfig) => {
  if (props.isEditing && newConfig) {
    // 设置标志位，避免重复请求
    isLoadingStepsFromConfig.value = true;
    
    try {
      // 先加载接口和用例列表
      await Promise.all([fetchInterfaces(), fetchTestCases()]);
      
      // 填充表单数据
      formModel.name = newConfig.name || '';
      formModel.description = newConfig.description || '';
      
      // 设置接口、用例和步骤ID
      // 确保使用正确的ID
      formModel.interface = newConfig.interface;
      formModel.testcase = newConfig.testcase;
      
      // 检查接口是否在列表中
      const interfaceExists = interfaces.value && interfaces.value.some(item => item.id === formModel.interface);
      if (!interfaceExists && newConfig.interface_info) {
        console.warn('警告：当前接口ID不在接口列表中，添加接口到列表');
        interfaces.value = interfaces.value || [];
        interfaces.value.push({
          id: newConfig.interface,
          name: newConfig.interface_info.name,
          method: newConfig.interface_info.method,
          url: newConfig.interface_info.url
        });
      }
      
      // 检查用例是否在列表中
      const testcaseExists = testcases.value && testcases.value.some(item => item.id === formModel.testcase);
      if (!testcaseExists && newConfig.testcase_info) {
        console.warn('警告：当前用例ID不在用例列表中，添加用例到列表');
        testcases.value = testcases.value || [];
        testcases.value.push({
          id: newConfig.testcase,
          name: newConfig.testcase_info.name
        });
      }
      
      // 先获取步骤列表，然后再设置步骤值
      if (formModel.testcase) {
        await fetchTestSteps();
        
        // 在步骤列表加载完成后设置步骤值
        formModel.step = newConfig.step;
        
        // 检查步骤是否在列表中
        const stepExists = teststeps.value && teststeps.value.some(step => step.id === newConfig.step);
        if (!stepExists && newConfig.step_info) {
          console.warn('警告：当前步骤ID不在步骤列表中，添加步骤到列表');
          
          // 如果步骤不在列表中，添加它到列表中
          teststeps.value = teststeps.value || [];
          teststeps.value.push({
            id: newConfig.step,
            name: newConfig.step_info.name,
            order: newConfig.step_info.order
          });
        }
      }
      
      // 设置同步字段
      formModel.sync_fields = Array.isArray(newConfig.sync_fields) ? [...newConfig.sync_fields] : [];
      formModel.sync_enabled = newConfig.sync_enabled === true;
      formModel.sync_mode = newConfig.sync_mode || 'manual';
      
      // 设置同步触发器
      if (newConfig.sync_mode === 'auto' && newConfig.sync_trigger && newConfig.sync_trigger.fields_to_watch) {
        formModel.sync_trigger.fields_to_watch = [...newConfig.sync_trigger.fields_to_watch];
      } else {
        formModel.sync_trigger.fields_to_watch = [];
      }

    } catch (error) {
    } finally {
      // 重置标志位
      isLoadingStepsFromConfig.value = false;
    }
  }
}, { immediate: true })

// 监听visible变化，当弹窗打开时获取数据
watch(() => props.visible, (newVisible) => {
  if (newVisible) {
    if (!props.isEditing) {
      fetchInterfaces()
      fetchTestCases()
    }
  } else {
    resetForm()
  }
}, { immediate: true })

const handleSubmit = () => {
  const { interface: interfaceId, testcase: testcaseId, step: stepId } = formModel
  if (!interfaceId || !testcaseId || !stepId) {
    Message.error(text.value.fillRequired)
    return
  }

  emit('submit', {
    name: formModel.name,
    description: formModel.description,
    interface: interfaceId,
    testcase: testcaseId,
    step: stepId,
    sync_fields: formModel.sync_fields,
    sync_enabled: formModel.sync_enabled,
    sync_mode: formModel.sync_mode,
    sync_trigger: formModel.sync_mode === 'auto' ? formModel.sync_trigger : undefined
  })
}

defineExpose({
  formModel
})
</script>

<template>
  <a-modal
    v-model:visible="modalVisible"
    :title="isEditing ? text.editSyncConfig : text.createSyncConfig"
    :width="780"
    :modal-class="isDarkTheme ? 'api-config-form-modal api-config-form-modal--dark' : 'api-config-form-modal api-config-form-modal--light'"
    @ok="handleSubmit"
  >
    <a-form :model="formModel" layout="vertical">
      <a-form-item field="name" :label="text.configName" required>
        <a-input
          v-model="formModel.name"
          :placeholder="text.enterConfigName"
          allow-clear
        />
      </a-form-item>

      <a-form-item field="description" :label="text.configDescription">
        <a-textarea
          v-model="formModel.description"
          :placeholder="text.enterConfigDescription"
          allow-clear
        />
      </a-form-item>

      <a-form-item field="interface" :label="text.selectInterface" required>
        <a-select
          v-model="formModel.interface"
          :placeholder="text.selectAnInterface"
          :loading="loadingInterfaces"
        >
          <a-option
            v-for="item in interfaces"
            :key="item.id"
            :value="item.id"
            :label="item.name"
          />
        </a-select>
      </a-form-item>

      <a-form-item field="testcase" :label="text.selectTestCase" required>
        <a-select
          v-model="formModel.testcase"
          :placeholder="text.selectATestCase"
          :loading="loadingTestcases"
        >
          <a-option
            v-for="item in testcases"
            :key="item.id"
            :value="item.id"
            :label="item.name"
          />
        </a-select>
      </a-form-item>

      <a-form-item field="step" :label="text.selectStep" required>
        <a-select
          v-model="formModel.step"
          :placeholder="text.selectAStep"
          :loading="loadingTestSteps"
        >
          <a-option
            v-for="item in teststeps"
            :key="item.id"
            :value="item.id"
            :label="getStepOptionLabel(item)"
          />
        </a-select>
      </a-form-item>

      <a-form-item field="sync_fields" :label="text.syncFields" required>
        <a-select
          v-model="formModel.sync_fields"
          :placeholder="text.selectSyncFields"
          multiple
        >
          <a-option
            v-for="option in localizedFieldOptions"
            :key="option.value"
            :value="option.value"
            :label="option.label"
          />
        </a-select>
      </a-form-item>

      <a-form-item field="sync_mode" :label="text.syncMode" required>
        <a-radio-group v-model="formModel.sync_mode">
          <a-radio value="manual">{{ text.manualSync }}</a-radio>
          <a-radio value="auto">{{ text.autoSync }}</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item
        v-if="formModel.sync_mode === 'auto'"
        field="sync_trigger.fields_to_watch"
        :label="text.watchFields"
      >
        <a-select
          v-model="formModel.sync_trigger.fields_to_watch"
          :placeholder="text.selectFieldsToWatch"
          multiple
        >
          <a-option
            v-for="option in localizedFieldOptions"
            :key="option.value"
            :value="option.value"
            :label="option.label"
          />
        </a-select>
      </a-form-item>

      <div class="modal-divider flex justify-between items-center mt-4 pt-4 border-t">
        <a-checkbox v-model="formModel.sync_enabled">
          <template #default>
            <span class="sync-enabled-text">{{ text.enableSync }}</span>
          </template>
        </a-checkbox>
      </div>
    </a-form>
  </a-modal>
</template>

<style scoped>
@reference "tailwindcss";
:deep(.api-config-form-modal--light) {
  --api-form-bg: rgba(255, 255, 255, 0.98);
  --api-form-border: rgba(148, 163, 184, 0.18);
  --api-form-text: var(--color-text-1);
  --api-form-subtle: var(--color-text-3);
  --api-form-input-bg: #ffffff;
  --api-form-input-border: rgba(148, 163, 184, 0.22);
}

:deep(.api-config-form-modal--dark) {
  --api-form-bg: rgba(31, 41, 55, 1);
  --api-form-border: rgba(55, 65, 81, 1);
  --api-form-text: rgb(229, 231, 235);
  --api-form-subtle: rgb(156, 163, 175);
  --api-form-input-bg: rgba(55, 65, 81, 1);
  --api-form-input-border: rgba(75, 85, 99, 1);
}

:deep(.api-config-form-modal .arco-modal) {
  background: var(--api-form-bg);
  border: 1px solid var(--api-form-border);
}

:deep(.api-config-form-modal .arco-modal-header) {
  background: var(--api-form-bg);
  border-color: var(--api-form-border);
  padding-bottom: 1rem;
}

:deep(.api-config-form-modal .arco-modal-title) {
  color: var(--api-form-text);
  font-size: 1.125rem;
  font-weight: 500;
}

:deep(.api-config-form-modal .arco-modal-footer) {
  background: var(--api-form-bg);
  border-color: var(--api-form-border);
  margin-top: 1.5rem;
}

:deep(.api-config-form-modal .arco-modal-body) {
  padding: 1rem;
}

:deep(.api-config-form-modal .arco-form-item-label-col),
:deep(.api-config-form-modal .arco-form-item-label-col > label),
:deep(.api-config-form-modal .arco-radio),
:deep(.api-config-form-modal .arco-checkbox) {
  color: var(--api-form-text);
}

:deep(.api-config-form-modal .arco-input-wrapper),
:deep(.api-config-form-modal .arco-textarea-wrapper),
:deep(.api-config-form-modal .arco-select-view) {
  background: var(--api-form-input-bg);
  border-color: var(--api-form-input-border);
}

:deep(.api-config-form-modal .arco-input-wrapper:hover),
:deep(.api-config-form-modal .arco-textarea-wrapper:hover),
:deep(.api-config-form-modal .arco-select-view:hover),
:deep(.api-config-form-modal .arco-input-wrapper:focus-within),
:deep(.api-config-form-modal .arco-textarea-wrapper:focus-within),
:deep(.api-config-form-modal .arco-select-view:focus-within) {
  border-color: rgb(var(--primary-6));
}

:deep(.api-config-form-modal .arco-input),
:deep(.api-config-form-modal .arco-textarea),
:deep(.api-config-form-modal .arco-select-view-value) {
  color: var(--api-form-text);
  background: transparent;
}

:deep(.api-config-form-modal .arco-input::placeholder),
:deep(.api-config-form-modal .arco-textarea::placeholder),
:deep(.api-config-form-modal .arco-select-view-placeholder) {
  color: var(--api-form-subtle);
}

.modal-divider {
  border-color: var(--api-form-border);
}

.sync-enabled-text {
  color: var(--api-form-text);
}
</style> 
