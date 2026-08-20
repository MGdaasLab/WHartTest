<script setup lang="ts">
import { ref, computed, onMounted, watch, provide } from 'vue'
import { useEnvironmentStore } from '../../stores/environmentStore'
import { useProjectStore } from '@/store/projectStore'
import type { CreateTestCaseData, TestCaseStep } from '../../services/testcaseService'
import type { ApiExtractPayload, ApiInterface } from '../../types/interface'
import type { ApiModule } from '../../types/module'
import { interfaceService } from '../../services/interfaceService'
import { testcaseService } from '../../services/testcaseService'
import TestCaseRequestHeader from './TestCaseRequestHeader.vue'
import { Message } from '@arco-design/web-vue'
import TestCaseStepResponse from './TestCaseStepResponse.vue'
import TestCaseParamsConfig from './TestCaseParamsConfig.vue'
import TestCaseHeadersConfig from './TestCaseHeadersConfig.vue'
import TestCaseBodyConfig from './TestCaseBodyConfig.vue'
import TestCaseSetupHooksConfig from './TestCaseSetupHooksConfig.vue'
import TestCaseTeardownHooksConfig from './TestCaseTeardownHooksConfig.vue'
import TestCaseExtractConfig from './TestCaseExtractConfig.vue'
import TestCaseAssertConfig from './TestCaseAssertConfig.vue'
import { updateTestCaseStep, addTestCaseSteps, getTestCaseById } from '../../services/testcaseService'
import { useDraggable } from '@vueuse/core'
import { showExtractPersistenceNotice } from '../../utils/extractPersistence'

// 定义KeyValuePair类型
interface KeyValuePair {
  key: string
  value: string
  enabled: boolean
  description?: string
}

// 定义ApiBody类型，用于处理请求体
interface ApiBody {
  type: 'none' | 'form-data' | 'x-www-form-urlencoded' | 'raw' | 'binary'
  content: string | KeyValuePair[] | null | Record<string, any>
}

// 使用TestCaseStep类型别名
type Step = TestCaseStep

interface Props {
  modelValue: Step
  modules?: ApiModule[]
  readonly?: boolean
  testCaseId?: number
  interfaceCaseMode?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false,
  testCaseId: 0,
  interfaceCaseMode: false,
  modules: () => [],
  modelValue: () => ({
    id: 0,
    name: '',
    order: 0,
    interface_info: {
      id: 0,
      name: '',
      method: 'GET',
      url: '',
      module: { id: 0, name: '' },
      module_info: { id: 0, name: '' },
      project: { id: 0, name: '' }
    },
    interface_data: {
      method: 'GET',
      url: '',
      headers: {},
      params: {},
      body: {},
      validators: [],
      extract: {},
      extract_meta: {},
      setup_hooks: [],
      teardown_hooks: [],
      variables: {}
    },
    config: {
      variables: {},
      validators: [],
      extract: {},
      extract_meta: {},
      setup_hooks: [],
      teardown_hooks: []
    },
    sync_fields: [],
    last_sync_time: null
  })
})

const emit = defineEmits(['update:modelValue', 'refresh-test-case', 'save-interface-case-step'])

type RequestHeaderData = {
  method: string
  url: string
  name: string
  module?: number | string | null
}

type CurrentStepData = {
  params: any
  headers: any
  body: any
  setupHooks: any[]
  teardownHooks: any[]
  extractPayload: ApiExtractPayload
  assertRules: any[]
}

// 获取环境store
const environmentStore = useEnvironmentStore()

// 获取项目store
const projectStore = useProjectStore()

// 组件引用
const paramsRef = ref()
const headersRef = ref()
const bodyRef = ref()
const setupHooksRef = ref()
const teardownHooksRef = ref()
const extractRef = ref()
const assertRef = ref()

// 为ID持久化创建专用的ref
const lastSavedStepId = ref<number>(0)

// 存储测试用例名称
const testCaseName = ref(`测试用例_${props.testCaseId}`)

// 响应数据
const response = ref<{
  status: number | null
  time: number | null
  size: number | null
  data: any
  request: any
  response: any
  validation_results: any
  extracted_variables: any
} | null>(null)

// 提供响应数据给子组件
provide('apiResponse', response)

// 模块选择相关
const modules = computed(() => normalizeModuleTree(props.modules || []))

const normalizeModuleId = (moduleValue: unknown): number | null => {
  if (moduleValue === null || moduleValue === undefined || moduleValue === '') {
    return null
  }

  if (typeof moduleValue === 'object') {
    const valueWithId = moduleValue as { id?: unknown }
    if (valueWithId.id !== undefined) {
      return normalizeModuleId(valueWithId.id)
    }
    return null
  }

  const normalizedId = Number(moduleValue)
  return Number.isFinite(normalizedId) && normalizedId > 0 ? normalizedId : null
}

const normalizeModuleTree = (moduleTree: ApiModule[]): ApiModule[] => {
  return moduleTree.map((module) => ({
    ...module,
    id: Number(module.id),
    parent: module.parent === null || module.parent === undefined ? null : Number(module.parent),
    children: module.children ? normalizeModuleTree(module.children) : []
  }))
}

const findModuleById = (moduleId: number | null | undefined, moduleTree: ApiModule[]): ApiModule | undefined => {
  if (!moduleId) {
    return undefined
  }

  for (const module of moduleTree) {
    if (Number(module.id) === moduleId) {
      return module
    }

    if (module.children?.length) {
      const matchedModule = findModuleById(moduleId, module.children)
      if (matchedModule) {
        return matchedModule
      }
    }
  }

  return undefined
}

const savingLoading = ref(false)
const sendingLoading = ref(false)
const canSaveStandaloneStep = computed(() => Boolean(props.testCaseId))
const showSaveStepButton = computed(() => canSaveStandaloneStep.value || props.interfaceCaseMode)
const sendTooltip = computed(() =>
  props.interfaceCaseMode
    ? '运行前自动保存到当前接口用例，不同步到接口管理'
    : canSaveStandaloneStep.value
    ? '使用当前配置运行调试；无接口引用时会先保存接口并添加为用例步骤'
    : '运行当前配置'
)

const getExtractPayload = (): ApiExtractPayload => {
  return extractRef.value?.getExtractRules() ?? {
    extract: props.modelValue.interface_data.extract ?? {},
    extractMeta: props.modelValue.interface_data.extract_meta ?? {},
  }
}

const collectCurrentStepData = (): CurrentStepData => ({
  params: paramsRef.value?.getParams() ?? props.modelValue.interface_data.params ?? [],
  headers: headersRef.value?.getHeaders() ?? props.modelValue.interface_data.headers ?? [],
  body: bodyRef.value?.getBody() ?? props.modelValue.interface_data.body ?? { type: 'none', content: null },
  setupHooks: setupHooksRef.value?.getHooks() ?? props.modelValue.interface_data.setup_hooks ?? [],
  teardownHooks: teardownHooksRef.value?.getHooks() ?? props.modelValue.interface_data.teardown_hooks ?? [],
  extractPayload: getExtractPayload(),
  assertRules: assertRef.value?.getAssertRules() ?? props.modelValue.interface_data.validators ?? []
})

const updateStep = (newStep: Step) => {
  console.log('更新步骤数据:', newStep)
  emit('update:modelValue', newStep)
}

const buildCurrentStepSnapshot = (
  requestData: RequestHeaderData,
  currentData: CurrentStepData
): Step => {
  const normalizedModuleId = normalizeModuleId(requestData.module)
  const foundModule = findModuleById(normalizedModuleId, modules.value)
  const moduleObj = foundModule
    ? { id: foundModule.id, name: foundModule.name }
    : normalizedModuleId != null
      ? { id: normalizedModuleId, name: '' }
      : { id: 0, name: '' }
  const defaultProject = {
    id: Number(projectStore.currentProjectId),
    name: ''
  }

  return {
    ...props.modelValue,
    name: requestData.name,
    interface_info: {
      ...props.modelValue.interface_info,
      name: requestData.name,
      method: requestData.method,
      url: requestData.url,
      module: moduleObj,
      module_info: moduleObj,
      project: props.modelValue.interface_info.project || defaultProject
    },
    interface_data: {
      ...props.modelValue.interface_data,
      method: requestData.method,
      url: requestData.url,
      module: normalizedModuleId,
      headers: currentData.headers ?? [],
      params: currentData.params ?? [],
      body: currentData.body ?? { type: 'none', content: null },
      setup_hooks: currentData.setupHooks ?? [],
      teardown_hooks: currentData.teardownHooks ?? [],
      extract: currentData.extractPayload.extract,
      extract_meta: currentData.extractPayload.extractMeta,
      validators: currentData.assertRules ?? []
    }
  }
}

const saveInterfaceCaseStepSnapshot = (step: Step) => new Promise<boolean>((resolve) => {
  emit('save-interface-case-step', step, (success?: boolean) => resolve(Boolean(success)))
})

// 组件挂载时获取测试用例名称
onMounted(async () => {
  // 如果有测试用例ID，尝试获取测试用例名称
  if (props.testCaseId && projectStore.currentProjectId) {
    try {
      const res = await testcaseService.get(projectStore.currentProjectId, props.testCaseId)
      if (res.success && res.data) {
        testCaseName.value = (res.data as any).name || testCaseName.value
        console.log('初始化时获取到测试用例名称:', testCaseName.value)
      }
    } catch (error) {
      console.error('获取测试用例名称失败，使用默认名称:', error)
    }
  }
})

// 当前步骤的接口信息
const stepInterface = computed({
  get: () => {
    console.log('获取接口数据 - 当前 modelValue:', props.modelValue)
    const normalizedModuleId =
      normalizeModuleId(props.modelValue.interface_info?.module_info?.id) ??
      normalizeModuleId(props.modelValue.interface_info?.module) ??
      normalizeModuleId(props.modelValue.interface_data?.module)

    const interfaceData = {
      method: props.modelValue.interface_data.method || props.modelValue.interface_info.method || 'GET',
      url: props.modelValue.interface_data.url || props.modelValue.interface_info.url || '',
      name: props.modelValue.name || '',
      module: normalizedModuleId,
      interface: null as ApiInterface | null
    }

    // 如果有完整的接口信息，则转换为ApiInterface类型
    if (props.modelValue.interface_info.id) {
      const headers = Array.isArray(props.modelValue.interface_data.headers)
        ? props.modelValue.interface_data.headers
        : Object.entries(props.modelValue.interface_data.headers || {}).map(([key, value]) => ({
            key,
            value: String(value),
            enabled: true
          }))

      const params = Array.isArray(props.modelValue.interface_data.params)
        ? props.modelValue.interface_data.params
        : Object.entries(props.modelValue.interface_data.params || {}).map(([key, value]) => ({
            key,
            value: String(value),
            enabled: true
          }))

      const defaultBody: ApiBody = { type: 'none', content: null }
      const body = props.modelValue.interface_data.body && 'type' in props.modelValue.interface_data.body
        ? props.modelValue.interface_data.body as ApiBody
        : defaultBody

      interfaceData.interface = {
        id: props.modelValue.interface_info.id,
        name: props.modelValue.interface_info.name,
        method: props.modelValue.interface_info.method,
        url: props.modelValue.interface_info.url,
        project: props.modelValue.interface_info.project.id,
        module: normalizedModuleId,
        headers,
        params,
        body: body as any,
        setup_hooks: props.modelValue.interface_data.setup_hooks || [],
        teardown_hooks: props.modelValue.interface_data.teardown_hooks || [],
        variables: props.modelValue.interface_data.variables || {},
        validators: props.modelValue.interface_data.validators || [],
        extract: props.modelValue.interface_data.extract || {}
      } as unknown as ApiInterface
    }
    return interfaceData
  },
  set: (value: any) => {
    if (value) {
      console.log('设置接口数据:', value)

      const normalizedModuleId = normalizeModuleId(value.module)
      const foundModule = findModuleById(normalizedModuleId, modules.value)
      const moduleObj = foundModule
        ? { id: foundModule.id, name: foundModule.name }
        : normalizedModuleId != null
          ? { id: normalizedModuleId, name: '' }
          : { id: 0, name: '' }
      const defaultProject = {
        id: Number(projectStore.currentProjectId),
        name: ''
      }

      const newStep: TestCaseStep = {
        ...props.modelValue,
        name: value.name,
        interface_info: {
          ...props.modelValue.interface_info,
          method: value.method,
          url: value.url,
          module: moduleObj,
          module_info: moduleObj,
          project: props.modelValue.interface_info.project || defaultProject
        },
        interface_data: {
          ...props.modelValue.interface_data,
          method: value.method,
          url: value.url,
          module: normalizedModuleId
        }
      }
      console.log('更新后的步骤数据:', newStep)
      updateStep(newStep)
    }
  }
})

const getCurrentRequestData = (): RequestHeaderData => ({
  method: stepInterface.value.method || props.modelValue.interface_data.method || 'GET',
  url: stepInterface.value.url || props.modelValue.interface_data.url || '',
  name: stepInterface.value.name || props.modelValue.name || '',
  module: normalizeModuleId(stepInterface.value.module)
})

const getCurrentStepSnapshot = () => buildCurrentStepSnapshot(
  getCurrentRequestData(),
  collectCurrentStepData()
)

const flushCurrentStepSnapshot = () => {
  const snapshot = getCurrentStepSnapshot()
  updateStep(snapshot)
  return snapshot
}

// 处理发送请求
const handleSend = async (requestData: RequestHeaderData) => {
  try {
    let currentInterfaceId = props.modelValue.interface_info.id;

    // 普通测试用例中，如果接口未保存，先保存接口并添加为用例步骤。
    if (!currentInterfaceId && props.testCaseId) {
      Message.info('正在自动保存接口...');
      savingLoading.value = true;

      const saveResult = await handleSave(requestData);
      savingLoading.value = false;

      if (!saveResult) {
        Message.error('保存接口失败，无法继续调试');
        return;
      }

      // 获取保存后的接口ID
      if (saveResult?.success && saveResult.data && (saveResult.data as any).id) {
        currentInterfaceId = Number((saveResult.data as any).id);
        console.log('从响应获取到接口ID:', currentInterfaceId);
      }

      if (!currentInterfaceId) {
        Message.error('无法获取保存的接口ID，调试失败');
        return;
      }

      // 如果在测试用例环境中，则引用新保存的接口作为步骤
      if (props.testCaseId) {
        try {
          Message.info('正在自动添加接口引用步骤...');

          const autoSaveExtractPayload = getExtractPayload()

          // 直接使用与TestCaseStepList.vue中相同的代码
          const testCaseData: CreateTestCaseData = {
            name: testCaseName.value,
            priority: 'P3',
            project: Number(projectStore.currentProjectId),
            description: '',
            group: undefined,
            tags: [],
            config: {
              base_url: '',
              variables: {},
              parameters: {},
              export: []
            },
            steps_info: [{
              name: requestData.name,
              order: props.modelValue.order || 1,
              interface_id: currentInterfaceId,
              interface_data: {
                method: requestData.method,
                url: requestData.url,
                headers: headersRef.value?.getHeaders() || [],
                params: paramsRef.value?.getParams() || [],
                body: bodyRef.value?.getBody() || { type: 'none', content: null },
                validators: assertRef.value?.getAssertRules() || [],
                extract: autoSaveExtractPayload.extract,
                extract_meta: autoSaveExtractPayload.extractMeta,
                setup_hooks: setupHooksRef.value?.getHooks() || [],
                teardown_hooks: teardownHooksRef.value?.getHooks() || [],
                variables: {}
              }
            }]
          };

          const response = await addTestCaseSteps(props.testCaseId, testCaseData);
          Message.success('添加步骤成功');

          // 如果有步骤返回，则使用新步骤数据更新
          if (response?.data?.steps?.length > 0) {
            const newStep = response.data.steps[response.data.steps.length - 1];
            console.log('获取到新添加的步骤:', newStep);

            // 确保这一步更新了modelValue，特别是步骤ID
            if (newStep && newStep.id) {
              console.log('更新步骤ID:', newStep.id);

              // 使用深拷贝确保引用被更新
              const updatedStep = JSON.parse(JSON.stringify(newStep));

              // 立即更新props.modelValue的ID，确保数据同步
              props.modelValue.id = newStep.id;

              // 重要：同时保存到ref，确保其他函数也能获取此ID
              lastSavedStepId.value = newStep.id;

              // 通过emit更新父组件的值
              updateStep(updatedStep);

              // 重要：将ID直接设置到步骤上，避免后续操作中ID丢失
              setTimeout(() => {
                console.log('延迟检查 - 当前步骤ID:', props.modelValue.id);
                if (!props.modelValue.id) {
                  props.modelValue.id = lastSavedStepId.value || newStep.id;
                  console.log('重新应用ID:', props.modelValue.id);
                }
              }, 100);

              Message.success('添加步骤成功，ID已保存');
            } else {
              console.warn('新添加的步骤缺少ID信息，尝试获取正确ID:', newStep);

              // 尝试获取当前测试用例的所有步骤
              try {
                Message.info('正在尝试获取正确的步骤ID...');

                // 延迟一下，确保后端已处理完添加步骤的请求
                await new Promise(resolve => setTimeout(resolve, 500));

                const testCaseResponse = await getTestCaseById(props.testCaseId);
                if (testCaseResponse?.data?.steps?.length) {
                  // 找到最后添加的步骤
                  const latestStep = testCaseResponse.data.steps[testCaseResponse.data.steps.length - 1];
                  if (latestStep?.id) {
                    console.log('找到最新添加的步骤ID:', latestStep.id);

                    // 更新步骤ID
                    props.modelValue.id = latestStep.id;
                    Message.success('已自动修复步骤ID');

                    // 更新步骤对象
                    updateStep({
                      ...props.modelValue,
                      id: latestStep.id
                    });
                  } else {
                    Message.error('无法找到步骤ID，但步骤可能已添加成功');
                  }
                }
              } catch (fetchError) {
                console.error('尝试修复步骤ID失败:', fetchError);
                Message.error('步骤添加成功，但无法获取步骤ID，可能需要刷新页面');
              }
            }
          } else {
            console.warn('API返回中没有找到步骤信息:', response?.data);

            // 尝试获取当前测试用例的所有步骤
            try {
              Message.info('尝试确认步骤是否已添加...');

              // 延迟一下，确保后端已处理完添加步骤的请求
              await new Promise(resolve => setTimeout(resolve, 500));

              const testCaseResponse = await getTestCaseById(props.testCaseId);
              if (testCaseResponse?.data?.steps?.length) {
                // 检查是否有步骤名称匹配
                const matchedStep = testCaseResponse.data.steps.find(
                  (step: any) => step.name === requestData.name
                );

                if (matchedStep?.id) {
                  console.log('找到匹配名称的步骤:', matchedStep.id);
                  Message.success('步骤已成功添加');

                  // 更新步骤ID
                  props.modelValue.id = matchedStep.id;

                  // 更新步骤对象
                  updateStep(matchedStep);
                } else {
                  Message.warning('API返回中没有找到步骤信息，但步骤可能已添加');
                }
              } else {
                Message.error('API返回中没有找到步骤信息，可能添加失败');
              }
            } catch (fetchError) {
              console.error('检查步骤是否添加失败:', fetchError);
              Message.error('无法确认步骤是否添加成功，请刷新页面查看');
            }
          }

          // 立即刷新整个测试用例数据，确保步骤ID正确
          await refreshTestCaseData();
        } catch (error) {
          console.error('Failed to add steps:', error);
          Message.error('添加步骤失败');
        }
      }

      Message.info('即将开始调试...');
      // 等待一下UI更新和用户感知
      await new Promise(resolve => setTimeout(resolve, 300));
    }

    // 开始调试接口
    sendingLoading.value = true;
    const currentData = collectCurrentStepData()
    const {
      params,
      headers,
      body,
      setupHooks,
      teardownHooks,
      extractPayload,
      assertRules
    } = currentData

    if (props.interfaceCaseMode) {
      Message.info('正在自动保存到接口用例...');
      savingLoading.value = true;
      const snapshot = buildCurrentStepSnapshot(requestData, currentData)
      updateStep(snapshot)
      const saved = await saveInterfaceCaseStepSnapshot(snapshot)
      savingLoading.value = false;
      if (!saved) {
        Message.error('自动保存到接口用例失败，无法继续调试');
        return;
      }
      Message.success('已保存到接口用例');
    }

    // 再次检查接口ID是否存在
    if (!currentInterfaceId && props.testCaseId) {
      console.error('无法获取接口ID，调试失败', {
        propsId: props.modelValue.interface_info.id,
        currentId: currentInterfaceId
      });
      Message.error('接口ID不存在，无法调试');
      return;
    }

    console.log('准备调试接口，使用ID:', currentInterfaceId);

    const debugData: Record<string, any> = {
      environment_id: environmentStore.currentEnvironmentId ? Number(environmentStore.currentEnvironmentId) : undefined,
      method: requestData.method,
      url: requestData.url,
      headers,
      params,
      body,
      setup_hooks: setupHooks,
      teardown_hooks: teardownHooks,
      extract: extractPayload.extract,
      extract_meta: extractPayload.extractMeta,
      validators: assertRules
    };
    if (currentInterfaceId) {
      debugData.interface_id = currentInterfaceId
    }

    Message.info('正在调试接口...');
    try {
      const debugRes = await interfaceService.quickDebug(Number(projectStore.currentProjectId), {
        ...debugData
      });
      if (debugRes.success && debugRes.data) {
        const data = debugRes.data as any;
        showExtractPersistenceNotice(data.extract_persistence)
        response.value = {
          status: data.response?.status_code || null,
          time: data.elapsed || null,
          size: data.response?.content?.length || null,
          data: data,
          request: data.request,
          response: data.response,
          validation_results: data.validation_results,
          extracted_variables: data.extracted_variables
        };
        Message.success('接口调试成功');
      } else {
        Message.error(debugRes.error || '调试接口失败');
      }
    } catch (debugError: any) {
      console.error('调试接口失败:', debugError);
      Message.error(debugError.message || '调试接口失败');
    }
  } catch (error: any) {
    console.error('处理过程失败:', error);
    Message.error(error.message || '调试过程失败');
  } finally {
    sendingLoading.value = false;
  }
};

// 处理保存用例
const handleSave = async (requestData: RequestHeaderData) => {
  const moduleId = normalizeModuleId(requestData.module)
  if (!moduleId) {
    Message.warning('请选择模块')
    return null;
  }

  if (!requestData.name) {
    Message.warning('请输入步骤名称')
    return null;
  }

  if (!requestData.url) {
    Message.warning('请输入请求路径')
    return null;
  }

  try {
    savingLoading.value = true
    const params = paramsRef.value?.getParams() ?? props.modelValue.interface_data.params ?? []
    const headers = headersRef.value?.getHeaders() ?? props.modelValue.interface_data.headers ?? []
    const body = bodyRef.value?.getBody() ?? props.modelValue.interface_data.body ?? { type: 'none', content: null }
    const setupHooks = setupHooksRef.value?.getHooks() ?? props.modelValue.interface_data.setup_hooks ?? []
    const teardownHooks = teardownHooksRef.value?.getHooks() ?? props.modelValue.interface_data.teardown_hooks ?? []
    const extractPayload = getExtractPayload()
    const assertRules = assertRef.value?.getAssertRules() ?? props.modelValue.interface_data.validators ?? []

    const interfaceData: any = {
      name: requestData.name,
      method: requestData.method,
      url: requestData.url,
      module: moduleId,
      project: Number(projectStore.currentProjectId),
      headers,
      params,
      body,
      setup_hooks: setupHooks,
      teardown_hooks: teardownHooks,
      extract: extractPayload.extract,
      extract_meta: extractPayload.extractMeta,
      validators: assertRules,
      variables: props.modelValue.interface_data.variables ?? {}
    }

    console.log('准备保存接口数据:', interfaceData)
    console.log('当前接口信息:', props.modelValue.interface_info)

    let result
    if (props.modelValue.interface_info.id) {
      // 更新现有接口
      console.log(`更新接口，ID: ${props.modelValue.interface_info.id}`)
      result = await interfaceService.update(Number(projectStore.currentProjectId), props.modelValue.interface_info.id, interfaceData)
      console.log('更新接口响应:', result)
    } else {
      // 创建新接口
      console.log('创建新接口')
      result = await interfaceService.create(Number(projectStore.currentProjectId), interfaceData)
      console.log('创建接口响应:', result)
    }

    console.log('API响应完整内容:', result)

    // 获取接口数据 - WHartTest API pattern
    let savedInterface: any = null

    if (result?.success && result.data) {
      savedInterface = result.data
      console.log('从响应提取数据:', savedInterface)
    }

    // 如果获取到有效的接口数据
    if (savedInterface) {
      console.log('保存成功，接口数据:', savedInterface)
      const selectedModule = findModuleById(moduleId, modules.value)

      const updatedStep = {
        ...props.modelValue,
        name: requestData.name,
        interface_info: {
          ...savedInterface,
          module: {
            id: moduleId,
            name: selectedModule?.name || ''
          },
          module_info: {
            id: moduleId,
            name: selectedModule?.name || ''
          },
          project: {
            id: Number(projectStore.currentProjectId),
            name: ''
          }
        },
        interface_data: {
          ...interfaceData,
          module: moduleId
        }
      }

      // 更新步骤数据
      updateStep(updatedStep)

      if (props.interfaceCaseMode) {
        const caseSaved = await saveInterfaceCaseStepSnapshot(updatedStep)
        if (!caseSaved) {
          Message.error('接口已同步，但保存到接口用例失败')
          return null
        }
      }

      // 显示成功消息
      const operationType = props.modelValue.interface_info.id ? '更新' : '创建'
      Message.success(props.interfaceCaseMode ? `${operationType}接口成功，已保存到当前接口用例` : `${operationType}接口成功`)
      console.log(`${operationType}接口成功消息已显示`)

      return result
    } else {
      console.warn('无法解析的API响应:', result)
      Message.warning('接口保存可能成功，但响应格式不符合预期')
      return result
    }
  } catch (error: any) {
    console.error('保存接口失败:', error)
    Message.error(error.message || '保存失败')
    return null;
  } finally {
    savingLoading.value = false
  }
}

const updateStepData = ref(false)

// 保存步骤前进行ID预检查，确保步骤ID正确
const ensureStepId = async (): Promise<boolean> => {
  // 如果ID存在且不为0，直接返回成功
  if (props.modelValue.id && props.modelValue.id !== 0) {
    console.log('ID预检查: 当前步骤ID有效', props.modelValue.id, '父组件modelValue.id:', props.modelValue?.id);
    return true;
  }

  // 检查是否有保存在ref中的ID
  if (lastSavedStepId.value) {
    console.log('ID预检查: 从lastSavedStepId恢复ID', lastSavedStepId.value, '之前的ID:', props.modelValue?.id);
    props.modelValue.id = lastSavedStepId.value;
    return true;
  }

  // 如果没有ID但有接口ID，尝试通过接口ID查找步骤
  if (props.testCaseId && props.modelValue.interface_info?.id) {
    try {
      console.log('ID预检查: 尝试通过接口ID查找步骤', props.modelValue.interface_info.id);
      const testCaseResponse = await getTestCaseById(props.testCaseId);

      if (testCaseResponse?.data?.steps?.length) {
        // 尝试匹配接口ID
        const matchedStep = testCaseResponse.data.steps.find(
          (step: any) => step.interface_info?.id === props.modelValue.interface_info.id
        );

        if (matchedStep?.id) {
          console.log('ID预检查: 匹配到步骤ID', matchedStep.id, '通过接口ID:', props.modelValue.interface_info.id);
          props.modelValue.id = matchedStep.id;
          lastSavedStepId.value = matchedStep.id;
          return true;
        }

        // 尝试匹配名称
        const nameMatchedStep = testCaseResponse.data.steps.find(
          (step: any) => step.name === props.modelValue.name
        );

        if (nameMatchedStep?.id) {
          console.log('ID预检查: 通过名称匹配到步骤ID', nameMatchedStep.id, '步骤名:', props.modelValue.name);
          props.modelValue.id = nameMatchedStep.id;
          lastSavedStepId.value = nameMatchedStep.id;
          return true;
        }
      }
    } catch (error) {
      console.error('ID预检查: 查找步骤失败', error);
    }
  }

  // 无法找到有效ID
  console.log('ID预检查: 无法找到有效ID，可能需要创建新步骤');
  return false;
};

const handleSaveToInterfaceCase = async (requestData: RequestHeaderData) => {
  if (!requestData.name) {
    Message.warning('请输入步骤名称')
    return false
  }

  if (!requestData.url) {
    Message.warning('请输入请求路径')
    return false
  }

  try {
    savingLoading.value = true
    const snapshot = buildCurrentStepSnapshot(requestData, collectCurrentStepData())
    updateStep(snapshot)
    const saved = await saveInterfaceCaseStepSnapshot(snapshot)
    if (!saved) {
      Message.error('保存到接口用例失败')
      return false
    }
    Message.success('已保存到当前接口用例')
    return true
  } catch (error: any) {
    console.error('保存到接口用例失败:', error)
    Message.error(error.message || '保存到接口用例失败')
    return false
  } finally {
    savingLoading.value = false
  }
}

// 处理保存测试用例步骤
const handleStepSave = async (requestData: RequestHeaderData) => {
  // 确保有测试用例ID
  if (!props.testCaseId) {
    Message.warning('无法获取测试用例ID');
    return null;
  }

  // 确保有步骤名称
  if (!requestData.name) {
    Message.warning('请输入步骤名称');
    return null;
  }

  try {
    savingLoading.value = true;

    // 先检查ID状态，尝试修复ID问题
    await ensureStepId();

    // 获取最新的接口配置
    const params = paramsRef.value?.getParams() ?? props.modelValue.interface_data.params ?? [];
    const headers = headersRef.value?.getHeaders() ?? props.modelValue.interface_data.headers ?? [];

    // 获取body
    let body: any = bodyRef.value?.getBody() ?? props.modelValue.interface_data.body ?? { type: 'none', content: null };

    const setupHooks = setupHooksRef.value?.getHooks() ?? props.modelValue.interface_data.setup_hooks ?? [];
    const teardownHooks = teardownHooksRef.value?.getHooks() ?? props.modelValue.interface_data.teardown_hooks ?? [];
    const extractPayload = getExtractPayload();
    const assertRules = assertRef.value?.getAssertRules() ?? props.modelValue.interface_data.validators ?? [];

    // 获取当前步骤ID并进行有效性检查
    console.log('当前步骤ID状态:', {
      propsId: props.modelValue.id,
      directId: props.modelValue.id
    });

    // 步骤ID零值检查 - 防止ID丢失
    if (props.modelValue.id === 0 || !props.modelValue.id) {
      console.log('ID检查: 步骤ID为0或未定义，检查是否需要修复');

      // 如果在过去保存过，可能拥有接口ID，尝试使用接口ID查找关联步骤
      if (props.modelValue.interface_info && props.modelValue.interface_info.id) {
        try {
          // 尝试查找关联的步骤
          console.log('正在尝试通过接口ID查找关联步骤:', props.modelValue.interface_info.id);
          const testCaseResponse = await getTestCaseById(props.testCaseId);

          if (testCaseResponse?.data?.steps?.length) {
            // 尝试通过接口ID匹配步骤
            const matchedStep = testCaseResponse.data.steps.find(
              (step: any) => step.interface_info?.id === props.modelValue.interface_info.id
            );

            if (matchedStep?.id) {
              console.log('成功找到匹配的步骤ID:', matchedStep.id);
              // 恢复正确的步骤ID
              props.modelValue.id = matchedStep.id;
              Message.info('已自动修复步骤ID');
            }
          }
        } catch (error) {
          console.error('ID修复尝试失败:', error);
        }
      }
    }

    // 准备步骤数据，确保ID不为0
    if (!props.modelValue.id) {
      Message.warning('步骤ID不存在，将创建新步骤');

      // 使用addTestCaseSteps添加新步骤
      const testCaseData: CreateTestCaseData = {
        name: testCaseName.value,
        priority: 'P3',
        project: Number(projectStore.currentProjectId),
        description: '',
        group: undefined,
        tags: [],
        config: {
          base_url: '',
          variables: {},
          parameters: {},
          export: []
        },
        steps_info: [{
          name: requestData.name,
          order: props.modelValue.order || 1,
          interface_id: props.modelValue.interface_info.id || 0,
          interface_data: {
            method: requestData.method,
            url: requestData.url,
            headers,
            params,
            body,
            validators: assertRules,
            extract: extractPayload.extract,
            extract_meta: extractPayload.extractMeta,
            setup_hooks: setupHooks,
            teardown_hooks: teardownHooks,
            variables: props.modelValue.interface_data.variables ?? {}
          }
        }]
      };

      Message.info('创建新步骤中...');
      try {
        const response = await addTestCaseSteps(props.testCaseId, testCaseData);
        console.log('添加步骤响应:', response);

        if (response?.data?.steps?.length > 0) {
          const newStep = response.data.steps[response.data.steps.length - 1];
          console.log('获取到新创建的步骤:', newStep);

          // 使用深拷贝确保引用被更新
          const updatedStep = JSON.parse(JSON.stringify(newStep));

          // 强制保存ID到多个位置，确保不会丢失
          if (newStep.id) {
            // 1. 直接更新组件内ID
            props.modelValue.id = newStep.id;

            // 2. 通过ref变量保存ID
            lastSavedStepId.value = newStep.id;
            console.log('ID已保存到ref:', lastSavedStepId.value);

            // 3. 更新父组件
            updateStep(updatedStep);

            // 4. 设置延迟检查，确保ID被正确保存
            setTimeout(() => {
              console.log('延迟ID检查 - 当前ID:', props.modelValue.id);
              // 如果ID仍然丢失，尝试从ref恢复
              if (!props.modelValue.id && lastSavedStepId.value) {
                props.modelValue.id = lastSavedStepId.value;
                console.log('已从ref恢复ID:', props.modelValue.id);
              }
            }, 200);

            // 5. 重要：刷新整个测试用例数据
            setTimeout(async () => {
              console.log('开始刷新步骤数据，步骤ID:', props.modelValue.id);
              await refreshTestCaseData();
              console.log('刷新完成，当前步骤ID:', props.modelValue.id, 'lastSavedStepId:', lastSavedStepId.value);
            }, 500);
          }

          Message.success('创建新步骤成功');
          return response;
        }
      } catch (addError: any) {
        console.error('创建新步骤失败:', addError);
        Message.error(addError.message || '创建步骤失败');
        return null;
      }
    } else {
      // 更新现有步骤
      console.log('更新现有步骤, ID:', props.modelValue.id);
      // 自动打印步骤对象，便于问题诊断
      console.log('步骤对象详情:', JSON.stringify(props.modelValue, null, 2));
      const stepData: any = {
        step_id: props.modelValue.id, // 使用现有步骤ID
        name: requestData.name,
        interface_data: {
          method: requestData.method,
          url: requestData.url,
          headers,
          params,
          body,
          validators: assertRules,
          extract: extractPayload.extract,
          extract_meta: extractPayload.extractMeta,
          setup_hooks: setupHooks,
          teardown_hooks: teardownHooks,
          variables: props.modelValue.interface_data.variables ?? {}
        },
        config: props.modelValue.config,
        sync_fields: props.modelValue.sync_fields
      };

      Message.info('更新步骤中...');
      try {
        const result = await updateTestCaseStep(props.testCaseId, stepData);
        console.log('更新步骤响应:', result);

        // 获取步骤数据，处理不同的响应结构
        let updatedStep: any = null;

        // 情况1：标准响应格式，包含status和data
        if ((result?.data as any)?.status === 'success' && (result.data as any).data) {
          console.log('从标准格式提取步骤数据');
          updatedStep = (result.data as any).data;
        }
        // 情况2：直接返回步骤对象
        else if (result?.data && typeof result.data === 'object') {
          console.log('直接使用返回对象作为步骤数据');
          updatedStep = result.data;
        }

        if (updatedStep) {
          // 确保保存ID
          if (updatedStep.id) {
            lastSavedStepId.value = updatedStep.id;
          }

          // 更新步骤数据
          updateStep(updatedStep as TestCaseStep);
          updateStepData.value = true;
          console.log('步骤数据已更新，保留步骤ID:', updatedStep.id);

          // 添加保存成功提示消息
          Message.success((result?.data as any)?.message || '更新测试步骤成功');

          // 重要：刷新整个测试用例数据
          setTimeout(async () => {
            console.log('开始刷新步骤数据，步骤ID:', props.modelValue.id);
            await refreshTestCaseData();
            console.log('刷新完成，当前步骤ID:', props.modelValue.id, 'lastSavedStepId:', lastSavedStepId.value);
          }, 500);

          return result;
        } else {
          console.warn('未能从API响应中提取步骤数据:', result);
          Message.warning('步骤可能已更新，但无法解析响应数据');
          return result; // 即使无法解析也返回原始结果
        }
      } catch (updateError: any) {
        console.error('更新步骤失败:', updateError);
        // 检查是否是因为步骤ID不存在
        if (updateError.response?.status === 400 &&
            (updateError.response?.data?.errors?.step_id ||
             updateError.response?.data?.message?.includes('step_id'))) {

          console.warn('步骤ID不存在或无效，尝试获取正确的步骤ID');
          Message.info('正在尝试修复步骤ID...');

          try {
            // 获取当前测试用例的所有步骤
            const testCaseResponse = await getTestCaseById(props.testCaseId);
            if (testCaseResponse?.data?.steps?.length) {
              console.log('获取到测试用例步骤列表:', testCaseResponse.data.steps);

              // 策略1：尝试通过名称精确匹配找到正确的步骤
              let matchedStep = testCaseResponse.data.steps.find(
                (step: any) => step.name === requestData.name
              );

              // 策略2：如果名称匹配失败，尝试通过顺序匹配
              if (!matchedStep) {
                matchedStep = testCaseResponse.data.steps.find(
                  (step: any) => step.order === props.modelValue.order
                );
                console.log('通过顺序匹配到步骤:', matchedStep);
              }

              // 策略3：如果以上都失败，检查是否有接口ID匹配的步骤
              if (!matchedStep && props.modelValue.interface_info?.id) {
                matchedStep = testCaseResponse.data.steps.find(
                  (step: any) => step.interface_info?.id === props.modelValue.interface_info.id
                );
                console.log('通过接口ID匹配到步骤:', matchedStep);
              }

              if (matchedStep?.id) {
                console.log('找到匹配的步骤ID:', matchedStep.id);
                Message.success('已找到正确的步骤ID，正在重新保存...');

                // 更新步骤ID
                props.modelValue.id = matchedStep.id;

                // 重新调用保存方法
                return handleStepSave(requestData);
              } else {
                console.warn('无法找到匹配的步骤，全部步骤:', testCaseResponse.data.steps);
              }
            }

            Message.warning('无法找到正确的步骤ID，请添加为新步骤');
            props.modelValue.id = 0; // 重置ID为0，作为新步骤添加
            return handleStepSave(requestData);
          } catch (fetchError) {
            console.error('获取测试用例步骤失败:', fetchError);
            Message.error('无法获取测试用例步骤，请刷新页面后再试');
            return null;
          }
        }

        Message.error(updateError.message || '更新步骤失败');
        return null;
      }
    }
  } catch (error: any) {
    console.error('处理步骤保存过程失败:', error);
    Message.error(error.message || '保存步骤失败');
    return null;
  } finally {
    savingLoading.value = false;
  }
};

const handleSaveStepAction = async (requestData: RequestHeaderData) => {
  if (props.interfaceCaseMode) {
    return handleSaveToInterfaceCase(requestData)
  }
  return handleStepSave(requestData)
}

// 监听 modelValue 变化
watch(() => props.modelValue, (newValue) => {
  console.log('步骤详情接收到的完整数据:', {
    id: newValue.id,
    name: newValue.name,
    interface_info: newValue.interface_info,
    interface_data: newValue.interface_data
  })
}, { immediate: true, deep: true })

// 添加 activeTab 的响应式变量
const activeTab = ref('headers')

// 更新接口数据
const updateInterfaceData = (field: string, value: any) => {
  console.log(`更新接口数据 - ${field}:`, value)
  updateStep({
    ...props.modelValue,
    interface_data: {
      ...props.modelValue.interface_data,
      [field]: value
    }
  })
}

// 添加响应卡片高度控制
const responseCardHeight = ref(44)
const resizeDragHandle = ref<HTMLElement | null>(null)

// 使用useDraggable实现可拖动调整大小
useDraggable(resizeDragHandle, {
  axis: 'y',
  initialValue: { x: 0, y: 0 },
  onStart: () => {
    document.body.style.userSelect = 'none'
  },
  onMove: ({ y }) => {
    // 计算新的高度百分比，限制在10%到90%之间
    const containerHeight = window.innerHeight
    const newHeightPercent = (containerHeight - y) / containerHeight * 100
    responseCardHeight.value = Math.min(Math.max(newHeightPercent, 10), 99)
    return false // 阻止默认拖动行为
  },
  onEnd: () => {
    document.body.style.userSelect = ''
  }
})

// 刷新测试用例数据的函数
const refreshTestCaseData = async () => {
  if (!props.testCaseId || !projectStore.currentProjectId) {
    console.warn('无法刷新测试用例，ID不存在');
    return false;
  }

  try {
    console.log('正在刷新测试用例数据，测试用例ID:', props.testCaseId);

    const res = await testcaseService.get(projectStore.currentProjectId, props.testCaseId);

    if (!res.success || !res.data) {
      console.error('获取测试用例数据失败');
      return false;
    }

    const testCaseData = res.data as any;
    console.log('成功获取最新测试用例数据:', testCaseData);

    // 通知父组件刷新数据
    emit('refresh-test-case', testCaseData);
    console.log('已通知父组件刷新测试用例数据');

    // 在测试用例数据中查找当前步骤，确保ID正确
    if (testCaseData.steps && testCaseData.steps.length > 0) {
      let matchedStep = null;

      // 如果当前步骤有ID，通过ID查找
      if (props.modelValue.id) {
        matchedStep = testCaseData.steps.find((step: any) => step.id === props.modelValue.id);
        if (matchedStep) {
          console.log('刷新数据：通过ID找到匹配步骤:', matchedStep.id);
          lastSavedStepId.value = matchedStep.id;
        }
      }
      // 如果没有ID但有接口ID，通过接口ID查找
      if (!matchedStep && props.modelValue.interface_info?.id) {
        matchedStep = testCaseData.steps.find(
          (step: any) => step.interface_info?.id === props.modelValue.interface_info.id
        );
        if (matchedStep) {
          console.log('刷新数据：通过接口ID找到匹配步骤:', matchedStep.id);
          props.modelValue.id = matchedStep.id;
          lastSavedStepId.value = matchedStep.id;
        }
      }

      // 如果找到匹配的步骤，更新当前步骤数据
      if (matchedStep) {
        // 使用深拷贝防止引用问题
        const updatedStep = JSON.parse(JSON.stringify(matchedStep));

        // 通过emit通知父组件更新当前步骤
        updateStep(updatedStep);

        // 更新步骤ID
        props.modelValue.id = matchedStep.id;
        lastSavedStepId.value = matchedStep.id;

        console.log('刷新数据：已更新当前步骤数据，ID:', matchedStep.id);
      } else {
        console.warn('刷新数据：未找到匹配的步骤');
      }
    }

    return true;
  } catch (error) {
    console.error('刷新测试用例数据失败:', error);
    return false;
  }
};

defineExpose({
  getCurrentStepSnapshot,
  flushCurrentStepSnapshot
})
</script>

<template>
  <div class="testcase-step-detail h-full flex flex-col gap-2 p-2 overflow-hidden">
    <!-- 顶部接口信息卡片 -->
    <div class="mx-0.5 flex-shrink-0 card-bg rounded-lg shadow-lg overflow-hidden">
      <div class="px-4 py-3">
        <test-case-request-header
          v-model="stepInterface"
          :modules="modules"
          :saving-loading="savingLoading"
          :sending-loading="sendingLoading"
          :show-save-step="showSaveStepButton"
          :save-step-label="props.interfaceCaseMode ? '保存到用例' : '更新步骤'"
          :save-step-requires-module="!props.interfaceCaseMode"
          :send-tooltip="sendTooltip"
          @send="handleSend"
          @save="handleSave"
          @save-step="handleSaveStepAction"
        />
      </div>
    </div>

    <!-- 中间请求配置卡片 -->
    <div class="mx-0.5 flex-1 min-h-0 card-bg rounded-lg shadow-lg overflow-hidden">
      <a-tabs v-model:active-key="activeTab" class="h-full">
        <a-tab-pane key="headers" title="Headers">
          <test-case-headers-config
            ref="headersRef"
            :headers="modelValue.interface_data.headers"
          />
        </a-tab-pane>
        <a-tab-pane key="params" title="Params">
          <test-case-params-config
            ref="paramsRef"
            :params="modelValue.interface_data.params"
          />
        </a-tab-pane>
        <a-tab-pane key="body" title="Body">
          <test-case-body-config
            ref="bodyRef"
            :body="modelValue.interface_data.body as any"
          />
        </a-tab-pane>
        <a-tab-pane key="setup_hooks" title="Setup Hooks">
          <test-case-setup-hooks-config
            ref="setupHooksRef"
            :hooks="modelValue.interface_data.setup_hooks"
            @update:hooks="val => updateInterfaceData('setup_hooks', val)"
          />
        </a-tab-pane>
        <a-tab-pane key="teardown_hooks" title="Teardown Hooks">
          <test-case-teardown-hooks-config
            ref="teardownHooksRef"
            :hooks="modelValue.interface_data.teardown_hooks"
            @update:hooks="val => updateInterfaceData('teardown_hooks', val)"
          />
        </a-tab-pane>
        <a-tab-pane key="extract" title="Extract">
          <test-case-extract-config
            ref="extractRef"
            :extract="modelValue.interface_data.extract"
            :extract-meta="modelValue.interface_data.extract_meta"
          />
        </a-tab-pane>
        <a-tab-pane key="assert" title="Assert">
          <test-case-assert-config
            ref="assertRef"
            :validators="modelValue.interface_data.validators"
          />
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 拖动条 -->
    <div
      ref="resizeDragHandle"
      class="resize-handle mx-0.5 h-3 cursor-row-resize transition-colors flex items-center justify-center gap-1"
    >
      <div class="resize-handle__bar w-6 h-[2px] rounded-full"></div>
      <div class="resize-handle__bar w-6 h-[2px] rounded-full"></div>
      <div class="resize-handle__bar w-6 h-[2px] rounded-full"></div>
    </div>

    <!-- 底部响应结果卡片 -->
    <div
      class="mx-0.5 card-bg rounded-lg shadow-lg overflow-hidden"
      :style="{ height: `${responseCardHeight}%` }"
    >
      <test-case-step-response
        :response="response"
      />
    </div>
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
.testcase-step-detail {
  color: var(--tcf-text-muted);
}

:deep(.arco-tabs) {
  @apply h-full flex flex-col;

  .arco-tabs-content {
    @apply flex-1 min-h-0 overflow-auto;
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
    &::-webkit-scrollbar {
      display: none !important;
    }
  }

  .arco-tabs-nav {
    @apply flex-shrink-0;
  }

  .arco-tabs-header {
    border-bottom: 1px solid var(--tcf-panel-border) !important;
  }

  .arco-tabs-nav-tab {
    @apply border-b-0;
  }

  .arco-tabs-tab {
    color: var(--tcf-text-subtle) !important;

    &.arco-tabs-tab-active {
      color: rgb(59, 130, 246) !important;
    }
  }
}

.card-bg {
  background: var(--tcf-section-bg);
}

.cursor-row-resize {
  cursor: row-resize;
  user-select: none;
}

:deep(.menu-item) {
  box-shadow: inset 0 1px 0 0 rgba(148, 163, 184, 0.2) !important;
  background-color: var(--tcf-control-bg) !important;
  border: 1px solid var(--tcf-control-border) !important;

  :deep(.arco-input-wrapper) {
    background-color: transparent !important;
  }

  :deep(.arco-input) {
    background-color: transparent !important;
    color: var(--tcf-text) !important;
  }

  :deep(.arco-input-prefix) {
    margin-right: 4px;
    padding-right: 8px;
    border-right: 1px solid var(--tcf-control-border);
  }
}

/* 请求方法按钮样式 */
.method-button {
  @apply flex items-center justify-center rounded text-white font-medium text-sm cursor-pointer;
  width: 108px;
  height: 32px;
  font-size: 13px;
  letter-spacing: 0.5px;
}

/* 请求方法下拉菜单样式 */
.method-dropdown {
  @apply flex flex-col items-center;
  min-width: 82px;
}

.method-dropdown .method-button {
  height: 28px;
  padding: 0;
  width: 65px !important;
  margin: 2px 1px 2px 0 !important;
}

:deep(.arco-dropdown-list) {
  background: var(--tcf-card-bg) !important;
  border-radius: 12px !important;
  padding: 2px 0 !important;
  width: 80px !important;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2) !important;
  border: 1px solid var(--tcf-panel-border) !important;
}

/* 选择器样式 */
:deep(.arco-select) {
  background: var(--tcf-control-bg) !important;

  .arco-select-view {
    background: transparent !important;
    border: 0 !important;
  }

  input {
    color: var(--tcf-text) !important;
    background: transparent !important;
    &::placeholder {
      color: var(--tcf-text-subtle) !important;
    }
  }
}

:deep(.arco-select-dropdown) {
  background: var(--tcf-card-bg) !important;
  border-color: var(--tcf-panel-border) !important;
  border-radius: 12px !important;

  .arco-select-option {
    color: var(--tcf-text-muted) !important;

    &:hover {
      background: var(--tcf-section-hover) !important;
    }

    &.arco-select-option-active {
      background: rgba(59, 130, 246, 0.12) !important;
      color: rgb(59, 130, 246) !important;
    }
  }
}

.resize-handle {
  background: var(--tcf-resize-bg);

  &:hover {
    background: var(--tcf-resize-hover);
  }
}

.resize-handle__bar {
  background: var(--tcf-text-subtle);
}
</style>
