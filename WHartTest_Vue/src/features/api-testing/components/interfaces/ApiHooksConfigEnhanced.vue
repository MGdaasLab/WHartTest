<script setup lang="ts">
import { ref, onMounted, watch, computed, onBeforeUnmount } from 'vue'
import { getFunctions, type Function } from '../../services/functionService'
import { toArray } from '../../services/responseHelpers'
import { useProjectStore } from '@/store/projectStore'
import ApiSqlHookEditor from './ApiSqlHookEditor.vue'
import { onClickOutside } from '@vueuse/core'
import {
  IconPlus,
  IconCode,
  IconStorage,
  IconInfoCircle,
  IconSearch
} from '@arco-design/web-vue/es/icon'
import { Message } from '@arco-design/web-vue'

// 自定义 FunctionItem 类型
interface FunctionItem {
  id: number;
  name: string;
  description?: string | null;
  // 其他属性...
}

interface Props {
  hooks?: string[] | any[]
  type?: 'setup' | 'teardown'
  allowEdit?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['update:hooks'])

// 获取 project store
const projectStore = useProjectStore()

interface HookItem {
  type: 'function' | 'sql'
  id: string | any
  name: string
}

interface State {
  hooks: HookItem[]
  functions: FunctionItem[]
  loading: boolean
  dropdownVisible: boolean
  editingSqlHook: string | null
  sqlEditorVisible: boolean
  editingSqlIndex: number | null
}

const state = ref<State>({
  hooks: [],
  functions: [],
  loading: false,
  dropdownVisible: false,
  editingSqlHook: null,
  sqlEditorVisible: false,
  editingSqlIndex: null
})

// 函数选择对话框
const functionSelectorVisible = ref(false)
const selectedFunctionId = ref<number | null>(null)

// 下拉菜单引用
const dropdownRef = ref(null)

// 点击外部时关闭下拉菜单
onClickOutside(dropdownRef, () => {
  state.value.dropdownVisible = false
})

// 翻译钩子类型
const hookTypeText = computed(() => props.type === 'setup' ? '前置' : '后置')

// 加载函数列表
const loadFunctions = async () => {
  if (!projectStore.currentProjectId) return

  state.value.loading = true
  try {
    const response = await getFunctions({
      project_id: Number(projectStore.currentProjectId),
      page: 1,
      page_size: 100
    })
    state.value.functions = toArray<FunctionItem>(response.data?.results ?? response.data)

    // 如果有初始 hooks，设置选中状态
    if (props.hooks && props.hooks.length > 0) {
      // 解析初始 hooks 数据
      parseInitialHooks(props.hooks)
    }
  } catch (error) {
    console.error('Failed to load functions:', error)
  } finally {
    state.value.loading = false
  }
}

// 解析初始钩子配置
const parseInitialHooks = (hooks: string[] | any[]) => {
  console.log('开始解析钩子:', hooks);

  try {
    state.value.hooks = hooks.map((hookData, index) => {
      console.log(`解析钩子[${index}]:`, hookData);

      // 解析钩子数据，尝试提取名称和类型
      const parsedHook = parseHookData(hookData);

      return parsedHook;
    });

    console.log('钩子解析结果:', state.value.hooks);
  } catch (e) {
    console.error('钩子解析失败:', e);
    state.value.hooks = [];
  }
}

// 解析钩子数据，尝试提取名称和类型
const parseHookData = (hookData: string | object): HookItem => {
  console.log('解析钩子数据:', hookData);

  // 处理对象形式的钩子
  if (typeof hookData === 'object' && hookData !== null) {
    console.log('钩子是对象格式:', hookData);

    // 检查是否是SQL钩子对象
    if ('type' in hookData && hookData.type === 'sql') {
      const sqlHook = hookData as any;
      console.log('发现SQL钩子对象:', sqlHook);

      // 展示名称优先顺序：var_name > db_id > db_key
      const displayName = sqlHook.var_name
        ? `${sqlHook.var_name} = SQL查询`
        : sqlHook.db_id
          ? `SQL查询(ID:${sqlHook.db_id})`
          : `SQL查询(${sqlHook.db_key || 'default'})`;

      return {
        type: 'sql',
        id: hookData,
        name: displayName
      } as HookItem;
    }

    // 普通函数
    return {
      type: 'function',
      id: hookData,
      name: '自定义函数'
    } as HookItem;
  }

  // 处理字符串形式的钩子
  if (typeof hookData === 'string') {
    // 检查是否是JSON对象字符串（以{开始，以}结束）
    if (typeof hookData === 'string' && hookData.startsWith('{') && hookData.endsWith('}')) {
      try {
        // 尝试解析JSON
        const jsonObj = JSON.parse(hookData);
        if (jsonObj.type === 'sql') {
          console.log('发现JSON格式SQL钩子:', jsonObj);

          // 展示名称优先顺序：var_name > db_id > db_key
          const displayName = jsonObj.var_name
            ? `${jsonObj.var_name} = SQL查询`
            : jsonObj.db_id
              ? `SQL查询(ID:${jsonObj.db_id})`
              : `SQL查询(${jsonObj.db_key || 'default'})`;

          return {
            type: 'sql',
            id: hookData,
            name: displayName
          } as HookItem;
        }
      } catch (e) {
        console.error('解析钩子对象失败:', e);
      }
    }

    // 检查是否是Python函数代码（以def开头的函数定义）
    if (safeStartsWith(hookData, 'def ')) {
      console.log('发现Python函数格式钩子');
      // 从注释或函数名中提取名称
      const nameMatch = hookData.match(/def\s+(\w+)\(/);
      const functionName = nameMatch ? nameMatch[1] : 'sql_hook';

      // 检查是否包含JSON格式的钩子配置
      const jsonMatch = hookData.match(/hook\(({[\s\S]*?})\)/) || hookData.match(/\(({[\s\S]*?})\)/);
      if (jsonMatch && jsonMatch[1]) {
        try {
          const jsonObj = JSON.parse(jsonMatch[1]);
          if (jsonObj.type === 'sql') {
            console.log('发现JSON格式SQL钩子配置:', jsonObj);
            // 这是新格式的SQL钩子
            const displayName = jsonObj.var_name
              ? `${jsonObj.var_name} = SQL查询`
              : `SQL查询(${jsonObj.db_key})`;

            return {
              type: 'sql',
              id: hookData,
              name: displayName
            } as HookItem;
          }
        } catch (e) {
          // JSON解析失败，继续使用默认处理
          console.error('解析SQL钩子配置失败:', e);
        }
      }

      // 检查是否有内部注释，用于UI展示
      const commentMatch = hookData.match(/# sql:(.*?):(.*)/);
      if (commentMatch) {
        console.log('发现注释格式SQL钩子');
        // 使用注释中保存的原始格式
        return {
          type: 'sql',
          id: hookData,
          name: commentMatch[1] || functionName
        } as HookItem;
      }

      return {
        type: 'sql',
        id: hookData,
        name: functionName
      } as HookItem;
    }
    // 检查是否为旧格式的SQL钩子（以sql:开头）
    else if (safeStartsWith(hookData, 'sql:')) {
      console.log('发现旧格式SQL钩子');
      const [_, name, ...sqlParts] = hookData.split(':');
      return {
        type: 'sql',
        id: hookData,
        name: name || '未命名SQL'
      } as HookItem;
    }
    else {
      console.log('发现函数类型钩子');
      // 函数类型钩子
      const functionId = String(hookData);
      const func = state.value.functions.find(f => String(f.id) === functionId);
      return {
        type: 'function',
        id: functionId,
        name: func?.name || `函数${functionId}`
      } as HookItem;
    }
  }

  // 默认返回空对象
  return {
    type: 'sql',
    id: null,
    name: '未命名SQL'
  } as HookItem;
}

// 监听项目变化
watch(() => projectStore.currentProjectId, () => {
  loadFunctions()
})

// 监听 hooks 变化
watch(() => props.hooks, (newHooks) => {
  if (newHooks && newHooks.length > 0) {
    // 确保函数列表已加载
    if (state.value.functions.length === 0) {
      loadFunctions();
    } else {
      parseInitialHooks(newHooks);
    }
  } else {
    state.value.hooks = [];
  }
}, { immediate: true, deep: true })

// 添加钩子
const addHook = (hookData: HookItem) => {
  state.value.hooks.push(hookData)
}

// 切换下拉菜单
const toggleDropdown = () => {
  state.value.dropdownVisible = !state.value.dropdownVisible
}

// 处理选择函数
const handleSelectFunction = () => {
  state.value.dropdownVisible = false
  // 打开函数选择对话框
  functionSelectorVisible.value = true
}

// 处理选择SQL
const handleSelectSql = () => {
  state.value.dropdownVisible = false
  addSqlHook()
}

// 选择函数项
const selectFunctionItem = (func: FunctionItem) => {
  addHook({
    type: 'function',
    id: String(func.id),
    name: func.name
  })
  functionSelectorVisible.value = false
}

// 删除钩子
const removeHook = (index: number) => {
  state.value.hooks.splice(index, 1)
}

// 添加SQL钩子
const addSqlHook = async () => {
  // 检查是否有可用的数据库配置
  try {
    const projectId = Number(projectStore.currentProjectId);
    if (!projectId) {
      Message.warning('请先选择项目');
      return;
    }

    const { getDatabaseConfigs } = await import('../../services/databaseConfigService');
    const response = await getDatabaseConfigs(projectId);

    const dbConfigs = toArray(response.data?.results ?? response.data);

    if (dbConfigs.length === 0) {
      Message.warning('未找到可用的数据库配置，请先在环境管理中添加');
      return;
    }

    // 有可用的数据库配置，继续打开SQL编辑器
    state.value.editingSqlHook = `sql:未命名SQL:SELECT 1`;
    state.value.editingSqlIndex = null;
    state.value.sqlEditorVisible = true;
  } catch (error) {
    console.error('检查数据库配置失败:', error);
    Message.error('检查数据库配置失败');
  }
}

// 一个辅助函数，用于安全地检查字符串的startsWith方法
const safeStartsWith = (str: any, prefix: string): boolean => {
  if (typeof str !== 'string') return false;
  return str.startsWith(prefix);
}

// 编辑SQL钩子
const editSqlHook = (hook: HookItem) => {
  console.log('开始编辑SQL钩子:', hook);

  if (hook.type !== 'sql') {
    return;
  }

  try {
    // 判断hook.id是否为对象(不是字符串)
    if (typeof hook.id === 'object' && hook.id !== null) {
      console.log('处理对象格式的SQL钩子:', hook.id);
      // 直接使用对象
      const sqlHookObj = hook.id;

      state.value.editingSqlHook = JSON.stringify(sqlHookObj);
      state.value.editingSqlIndex = state.value.hooks.indexOf(hook);
      state.value.sqlEditorVisible = true;
      return;
    }

    // 尝试解析JSON字符串
    if (typeof hook.id === 'string' && hook.id.startsWith('{') && hook.id.endsWith('}')) {
      try {
        console.log('解析JSON字符串格式的SQL钩子');
        const sqlHookObj = JSON.parse(hook.id);

        state.value.editingSqlHook = hook.id;
        state.value.editingSqlIndex = state.value.hooks.indexOf(hook);
        state.value.sqlEditorVisible = true;
        return;
      } catch (e) {
        console.error('解析SQL钩子JSON失败:', e);
      }
    }

    // 处理Python函数格式
    if (typeof hook.id === 'string') {
      console.log('处理Python函数或旧格式的SQL钩子');
      // 从Python函数中提取SQL数据

      // 检查是否包含JSON配置
      const jsonMatch = hook.id.match(/hook\(({[\s\S]*?})\)/) || hook.id.match(/\(({[\s\S]*?})\)/);
      if (jsonMatch && jsonMatch[1]) {
        try {
          console.log('从Python函数中提取JSON配置');
          const jsonStr = jsonMatch[1];
          state.value.editingSqlHook = jsonStr;
          state.value.editingSqlIndex = state.value.hooks.indexOf(hook);
          state.value.sqlEditorVisible = true;
          return;
        } catch (e) {
          console.error('解析Python函数中的JSON配置失败:', e);
        }
      }

      // 检查旧格式
      if (safeStartsWith(hook.id, 'sql:')) {
        console.log('处理旧格式SQL钩子');
        // 旧格式: sql:name:db_key:sql
        const [_, name, db_key, ...sqlParts] = hook.id.split(':');
        const sql = sqlParts.join(':');

        // 创建旧格式对应的新格式对象
        const sqlHookObj = {
          type: 'sql',
          var_name: name,
          db_key: db_key,
          sql: sql
        };

        state.value.editingSqlHook = JSON.stringify(sqlHookObj);
        state.value.editingSqlIndex = state.value.hooks.indexOf(hook);
        state.value.sqlEditorVisible = true;
        return;
      }

      // 还是没有处理成功，尝试按Python代码处理
      console.log('以Python代码格式处理SQL钩子');
      state.value.editingSqlHook = hook.id;
      state.value.editingSqlIndex = state.value.hooks.indexOf(hook);
      state.value.sqlEditorVisible = true;
    }
  } catch (e) {
    console.error('编辑SQL钩子时出错:', e);
    // 默认处理，直接将hook.id传递给编辑器
    state.value.editingSqlHook = typeof hook.id === 'object'
      ? JSON.stringify(hook.id)
      : String(hook.id);
    state.value.editingSqlIndex = state.value.hooks.indexOf(hook);
    state.value.sqlEditorVisible = true;
  }
}

// 处理SQL编辑器确认
const handleSqlEditorConfirm = (value: any) => {
  console.log('SQL编辑器确认, 值:', value);

  if (state.value.editingSqlIndex !== undefined && state.value.editingSqlIndex !== null) {
    // 编辑现有SQL钩子
    try {
      const oldHook = state.value.hooks[state.value.editingSqlIndex];
      console.log('编辑现有SQL钩子:', oldHook);

      // 确定value的类型和格式
      let newHookId;

      // 检查是否为Python函数字符串
      if (safeStartsWith(value, 'def ')) {
        console.log('处理Python函数格式的SQL钩子');
        newHookId = value;
      }
      // 检查是否为JSON字符串
      else if (typeof value === 'string' && value.startsWith('{') && value.endsWith('}')) {
        console.log('处理JSON字符串格式的SQL钩子');
        // 尝试解析JSON字符串为对象
        try {
          const jsonObj = JSON.parse(value);
          if (jsonObj && jsonObj.type === 'sql') {
            // 使用解析后的对象
            console.log('成功解析SQL钩子JSON对象:', jsonObj);
            newHookId = jsonObj;
          } else {
            // 如果不是SQL对象，保持字符串形式
            newHookId = value;
          }
        } catch (e) {
          console.error('无法解析JSON字符串:', e);
          newHookId = value; // 回退到字符串形式
        }
      }
      // 检查是否为对象
      else if (typeof value === 'object') {
        console.log('处理对象格式的SQL钩子');
        newHookId = value;
      }
      // 默认处理
      else {
        console.log('处理其他格式的SQL钩子');
        newHookId = value;
      }

      // 提取名称以进行显示
      let hookName = '';

      try {
        if (typeof newHookId === 'object') {
          // 从对象中提取名称，优先使用var_name，然后是db_id，最后是db_key
          hookName = newHookId.var_name
            ? `${newHookId.var_name} = SQL查询`
            : newHookId.db_id
              ? `SQL查询(ID:${newHookId.db_id})`
              : `SQL查询(${newHookId.db_key || 'default'})`;
        } else if (typeof newHookId === 'string' && newHookId.startsWith('{')) {
          // 尝试从JSON字符串中提取名称
          const jsonObj = JSON.parse(newHookId);
          hookName = jsonObj.var_name
            ? `${jsonObj.var_name} = SQL查询`
            : jsonObj.db_id
              ? `SQL查询(ID:${jsonObj.db_id})`
              : `SQL查询(${jsonObj.db_key || 'default'})`;
        } else if (safeStartsWith(newHookId, 'def ')) {
          // 从Python函数名称中提取
          const nameMatch = newHookId.match(/def\s+(\w+)\(/);
          hookName = nameMatch && nameMatch[1] ? nameMatch[1] : '未命名SQL查询';
        } else if (safeStartsWith(newHookId, 'sql:')) {
          // 从旧格式中提取
          const parts = newHookId.split(':');
          hookName = parts.length > 1 ? parts[1] : '未命名SQL查询';
        } else {
          hookName = '未命名SQL查询';
        }
      } catch (e) {
        console.error('提取SQL钩子名称失败:', e);
        hookName = '未命名SQL查询';
      }

      // 更新钩子
      state.value.hooks[state.value.editingSqlIndex] = {
        type: 'sql',
        id: newHookId,
        name: hookName
      };

      console.log('更新后的SQL钩子:', state.value.hooks[state.value.editingSqlIndex]);
    } catch (e) {
      console.error('更新SQL钩子失败:', e);
      Message.error('更新SQL钩子失败');
    }
  } else {
    // 添加新SQL钩子
    try {
      console.log('添加新SQL钩子, 值:', value);

      // 确定value的类型和格式
      let newHookId;

      // 如果是JSON字符串，尝试解析为对象
      if (typeof value === 'string' && value.startsWith('{') && value.endsWith('}')) {
        try {
          const jsonObj = JSON.parse(value);
          if (jsonObj && jsonObj.type === 'sql') {
            // 使用解析后的对象
            console.log('添加钩子: 成功解析SQL钩子JSON对象:', jsonObj);
            newHookId = jsonObj;
          } else {
            newHookId = value;
          }
        } catch (e) {
          console.error('添加钩子: 无法解析JSON字符串:', e);
          newHookId = value;
        }
      } else {
        newHookId = value;
      }

      // 提取名称以进行显示
      let hookName = '';

      try {
        if (typeof newHookId === 'object' && newHookId !== null) {
          // 从对象中提取名称，优先使用var_name，然后是db_id，最后是db_key
          hookName = newHookId.var_name
            ? `${newHookId.var_name} = SQL查询`
            : newHookId.db_id
              ? `SQL查询(ID:${newHookId.db_id})`
              : `SQL查询(${newHookId.db_key || 'default'})`;
        } else if (typeof newHookId === 'string') {
          if (newHookId.startsWith('{')) {
            // 尝试从JSON字符串中提取名称
            try {
              const jsonObj = JSON.parse(newHookId);
              hookName = jsonObj.var_name
                ? `${jsonObj.var_name} = SQL查询`
                : jsonObj.db_id
                  ? `SQL查询(ID:${jsonObj.db_id})`
                  : `SQL查询(${jsonObj.db_key || 'default'})`;
            } catch (e) {
              hookName = '未命名SQL查询';
            }
          } else if (newHookId.startsWith('def ')) {
            // 从Python函数名称中提取
            const nameMatch = newHookId.match(/def\s+(\w+)\(/);
            hookName = nameMatch && nameMatch[1] ? nameMatch[1] : '未命名SQL查询';
          } else if (newHookId.startsWith('sql:')) {
            // 从旧格式中提取
            const parts = newHookId.split(':');
            hookName = parts.length > 1 ? parts[1] : '未命名SQL查询';
          } else {
            hookName = '未命名SQL查询';
          }
        } else {
          hookName = '未命名SQL查询';
        }
      } catch (e) {
        console.error('提取SQL钩子名称失败:', e);
        hookName = '未命名SQL查询';
      }

      // 添加新钩子
      state.value.hooks.push({
        type: 'sql',
        id: newHookId,
        name: hookName
      });

      console.log('添加的SQL钩子:', state.value.hooks[state.value.hooks.length - 1]);
    } catch (e) {
      console.error('添加SQL钩子失败:', e);
      Message.error('添加SQL钩子失败');
    }
  }

  // 重置编辑状态
  state.value.sqlEditorVisible = false;
  state.value.editingSqlHook = null;
  state.value.editingSqlIndex = null;

  // 触发值更新
  updateModelValue();
};

// SQL编辑器值（添加计算属性，避免类型错误）
const sqlEditorValue = computed({
  get: () => {
    return state.value.editingSqlHook || '';
  },
  set: (val) => {
    console.log('设置编辑器值:', val);
    state.value.editingSqlHook = val;
  }
})

// 全局错误处理函数
const handleTypeError = (err: any, context: string) => {
  if (err instanceof TypeError && err.message.includes('startsWith')) {
    console.error(`在${context}中出现类型错误: hook.id 不是字符串，无法调用 startsWith 方法`, err);
    return true; // 错误已处理
  }
  return false; // 需要继续抛出错误
};

// 向父组件暴露数据
defineExpose({
  getHooks: () => {
    if (state.value.hooks.length > 0) {
      return state.value.hooks.map(hook => {
        // 如果是函数类型，直接返回ID
        if (hook.type === 'function') {
          return hook.id;
        }

        // 如果是SQL类型
        if (hook.type === 'sql') {
          // 如果hook.id是对象，直接返回对象
          if (typeof hook.id === 'object' && hook.id !== null) {
            console.log('返回对象格式的SQL钩子:', hook.id);
            return hook.id;
          }

          // 确保hook.id是字符串后再使用字符串方法
          if (typeof hook.id === 'string') {
            // 如果是JSON字符串格式，解析为对象后返回
            if (hook.id.startsWith('{') && hook.id.endsWith('}')) {
              try {
                // 尝试解析JSON字符串为对象
                const jsonObj = JSON.parse(hook.id);
                if (jsonObj.type === 'sql') {
                  // 返回解析后的SQL钩子对象
                  console.log('从JSON字符串解析SQL钩子对象:', jsonObj);
                  return jsonObj;
                }
              } catch (e) {
                console.error('解析JSON字符串失败:', e);
              }
            }

            // 如果是Python函数定义格式（新格式）
            if (hook.id.startsWith('def ')) {
              // 尝试提取JSON对象
              const jsonMatch = hook.id.match(/hook\(({[\s\S]*?})\)/) || hook.id.match(/\(({[\s\S]*?})\)/);
              if (jsonMatch && jsonMatch[1]) {
                try {
                  // 尝试解析JSON
                  const jsonObj = JSON.parse(jsonMatch[1]);
                  if (jsonObj.type === 'sql') {
                    // 返回SQL钩子对象
                    return jsonObj;
                  }
                } catch (e) {
                  console.error('解析SQL钩子配置失败:', e);
                }
              }
            }
          }

          // 默认返回原始ID（可能是字符串或其他类型）
          return hook.id;
        }

        return hook.id;
      });
    }
    return [];
  }
})

// 组件加载时获取函数列表
onMounted(() => {
  loadFunctions();

  // 添加全局错误处理
  window.addEventListener('error', (event) => {
    if (handleTypeError(event.error, '全局错误处理器')) {
      event.preventDefault();
    }
  });
})

// 组件卸载时移除事件监听
onBeforeUnmount(() => {
  window.removeEventListener('error', () => {});
})

// 更新模型值函数
const updateModelValue = () => {
  const hooksValue = state.value.hooks.map(hook => {
    // 检查是否是对象类型的SQL钩子
    if (hook.type === 'sql') {
      // 如果是对象类型，直接返回原始对象
      if (typeof hook.id === 'object' && hook.id !== null) {
        return hook.id;
      }

      // 如果是JSON字符串，解析为对象后返回
      if (typeof hook.id === 'string' && hook.id.startsWith('{') && hook.id.endsWith('}')) {
        try {
          const jsonObj = JSON.parse(hook.id);
          if (jsonObj.type === 'sql') {
            console.log('从JSON字符串解析SQL钩子对象用于更新:', jsonObj);
            return jsonObj;
          }
        } catch (e) {
          console.error('解析JSON字符串失败:', e);
        }
      }
    }

    // 否则返回原始ID（字符串或其他格式）
    return hook.id;
  });

  console.log('更新钩子值:', hooksValue);
  emit('update:hooks', hooksValue);
};
</script>

<template>
  <div class="hooks-enhanced h-full flex flex-col p-4 gap-4">
    <!-- 添加按钮和下拉菜单 -->
    <div class="relative" ref="dropdownRef">
      <!-- 添加按钮 -->
      <div
        @click="toggleDropdown"
        class="hooks-add-trigger w-full h-12 flex items-center justify-center border border-dashed rounded-md cursor-pointer transition-colors"
      >
        <IconPlus class="mr-2" />
        添加{{ hookTypeText }}函数
      </div>

      <!-- 下拉菜单 -->
      <div
        v-if="state.dropdownVisible"
        class="hooks-dropdown absolute left-1/2 transform -translate-x-1/2 top-full mt-1 rounded-md shadow-lg z-10 overflow-hidden w-38"
      >
        <!-- 自定义函数选项 -->
        <div
          class="hooks-dropdown-item hooks-dropdown-item--bordered py-3 px-2 cursor-pointer transition-colors flex items-center gap-2 border-b"
          @click="handleSelectFunction"
        >
          <div class="hooks-dropdown-icon-shell flex items-center justify-center w-5 h-5 rounded-md">
            <IconCode class="text-blue-500 text-sm" />
          </div>
          <div class="hooks-dropdown-label text-sm">自定义函数</div>
        </div>

        <!-- SQL控制器选项 -->
        <div
          class="hooks-dropdown-item py-3 px-2 cursor-pointer transition-colors flex items-center gap-2"
          @click="handleSelectSql"
        >
          <div class="hooks-dropdown-icon-shell flex items-center justify-center w-5 h-5 rounded-md">
            <IconStorage class="text-green-500 text-sm" />
          </div>
          <div class="hooks-dropdown-label text-sm">SQL控制器</div>
        </div>
      </div>
    </div>

    <!-- 已选择钩子列表 -->
    <div v-if="state.hooks.length > 0" class="flex flex-col gap-2 mt-2">
      <div class="hooks-helper-text text-sm">已选择的{{ hookTypeText }}钩子：</div>
      <div class="flex flex-col gap-2">
        <a-tag
          v-for="(hook, index) in state.hooks"
          :key="index"
          closable
          :color="hook.type === 'function' ? 'blue' : 'green'"
          @close="removeHook(index)"
          @click="hook.type === 'sql' && editSqlHook(hook)"
          :class="{ 'hook-sql-tag': hook.type === 'sql' }"
        >
          <template #icon>
            <IconCode v-if="hook.type === 'function'" />
            <IconStorage v-else />
          </template>
          {{ hook.name }}
        </a-tag>
      </div>
    </div>

    <div v-else class="hooks-empty flex items-center justify-center h-32">
      <div class="text-center">
        <div class="text-4xl mb-2"><IconInfoCircle /></div>
        <div>暂无{{ hookTypeText }}钩子</div>
      </div>
    </div>

    <!-- 函数选择对话框 -->
    <a-modal
      v-model:visible="functionSelectorVisible"
      title="选择自定义函数"
      modal-class="hooks-function-modal"
      @cancel="functionSelectorVisible = false"
      :footer="false"
      :unmount-on-close="false"
      width="600px"
    >
      <div class="p-2">
        <!-- 搜索框 -->
        <div class="mb-3">
          <a-input
            placeholder="搜索函数"
            allow-clear
          >
            <template #prefix>
              <IconSearch />
            </template>
          </a-input>
        </div>

        <!-- 函数列表 -->
        <div class="hooks-function-list max-h-96 overflow-y-auto border rounded-md">
          <div
            v-for="func in state.functions"
            :key="func.id"
            class="hooks-function-item p-3 cursor-pointer transition-colors flex items-center gap-3 border-b"
            @click="() => selectFunctionItem(func)"
          >
            <div class="hooks-function-icon-shell flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-md">
              <IconCode class="text-blue-500" />
            </div>
            <div class="flex-1 min-w-0">
              <div class="hooks-function-name font-medium truncate">{{ func.name }}</div>
              <div class="hooks-function-desc text-xs truncate">{{ func.description || '无描述' }}</div>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="state.functions.length === 0" class="hooks-empty-text p-6 text-center">
            <div v-if="state.loading">
              <a-spin />
              <div class="mt-2">加载中...</div>
            </div>
            <div v-else>
              <IconInfoCircle class="text-2xl mb-2" />
              <div>暂无可用函数</div>
            </div>
          </div>
        </div>
      </div>
    </a-modal>

    <!-- SQL编辑器对话框 -->
    <ApiSqlHookEditor
      v-model:visible="state.sqlEditorVisible"
      v-model:value="sqlEditorValue"
      :type="props.type"
      @confirm="handleSqlEditorConfirm"
    />
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";
.hooks-enhanced {
  --hooks-muted: var(--color-text-3);
  --hooks-empty: rgba(100, 116, 139, 0.9);
  --hooks-add-border: rgba(59, 130, 246, 0.4);
  --hooks-add-text: rgb(59, 130, 246);
  --hooks-add-bg-hover: rgba(59, 130, 246, 0.08);
  --hooks-dropdown-bg: rgba(255, 255, 255, 0.98);
  --hooks-dropdown-item-bg: rgba(248, 250, 252, 0.98);
  --hooks-dropdown-item-border: rgba(148, 163, 184, 0.18);
  --hooks-dropdown-item-hover: rgba(241, 245, 249, 1);
  --hooks-dropdown-icon-bg: rgba(226, 232, 240, 0.92);
  --hooks-dropdown-text: var(--color-text-2);
  --hooks-list-border: rgba(148, 163, 184, 0.18);
  --hooks-list-item-hover: rgba(241, 245, 249, 1);
  --hooks-function-name: var(--color-text-2);
  --hooks-function-desc: var(--color-text-3);
}

.hooks-add-trigger {
  border-color: var(--hooks-add-border);
  color: var(--hooks-add-text);
}

.hooks-add-trigger:hover {
  background: var(--hooks-add-bg-hover);
}

.hooks-dropdown {
  background: var(--hooks-dropdown-bg);
}

.hooks-dropdown-item {
  background: var(--hooks-dropdown-item-bg);
}

.hooks-dropdown-item:hover,
.hooks-function-item:hover {
  background: var(--hooks-dropdown-item-hover);
}

.hooks-dropdown-item--bordered,
.hooks-function-item,
.hooks-function-list {
  border-color: var(--hooks-list-border);
}

.hooks-dropdown-icon-shell,
.hooks-function-icon-shell {
  background: var(--hooks-dropdown-icon-bg);
}

.hooks-dropdown-label,
.hooks-function-name {
  color: var(--hooks-dropdown-text);
}

.hooks-helper-text,
.hooks-function-desc,
.hooks-empty,
.hooks-empty-text {
  color: var(--hooks-muted);
}

:global(body.api-testing-theme) .hooks-enhanced {
  --hooks-muted: rgb(156, 163, 175);
  --hooks-empty: rgb(107, 114, 128);
  --hooks-add-border: rgba(59, 130, 246, 0.5);
  --hooks-add-text: rgb(147, 197, 253);
  --hooks-add-bg-hover: rgba(59, 130, 246, 0.1);
  --hooks-dropdown-bg: #1d2639;
  --hooks-dropdown-item-bg: #192133;
  --hooks-dropdown-item-border: #313e59;
  --hooks-dropdown-item-hover: rgb(55, 65, 81);
  --hooks-dropdown-icon-bg: #313e59;
  --hooks-dropdown-text: rgb(229, 231, 235);
  --hooks-list-border: rgb(55, 65, 81);
  --hooks-list-item-hover: rgb(55, 65, 81);
}

:deep(.arco-select-view) {
  @apply bg-white border-[color:var(--color-border-2)];

  input {
    @apply text-[color:var(--color-text-1)] bg-transparent;
    &::placeholder {
      @apply text-[color:var(--color-text-3)];
    }
  }
}

:global(body.api-testing-theme) :deep(.arco-select-view) {
  @apply bg-gray-900/60 border-gray-700;

  input {
    @apply text-gray-200 bg-transparent;
    &::placeholder {
      @apply text-gray-500;
    }
  }
}

:global(body.api-testing-theme .arco-select-dropdown) {
  @apply bg-gray-800 border-gray-700;

  .arco-select-option {
    @apply text-gray-300;

    &:hover {
      @apply bg-gray-700;
    }

    &.arco-select-option-active {
      @apply bg-blue-500/20 text-blue-500;
    }
  }
}

:deep(.arco-tag) {
  border-color: rgba(59, 130, 246, 0.22);

  &[color="blue"] {
    @apply bg-blue-500/10 border-blue-500/30 text-blue-600;
  }

  &[color="green"] {
    @apply bg-green-500/10 border-green-500/30 text-green-600;
  }
}

.hook-sql-tag {
  @apply cursor-pointer;

  &:hover {
    @apply bg-green-500/20;
  }
}

:global(body.api-testing-theme) .hooks-enhanced :deep(.arco-tag) {
  border-color: rgb(75 85 99 / 0.5);

  &[color="blue"] {
    @apply bg-blue-500/20 border-blue-500 text-blue-500;
  }

  &[color="green"] {
    @apply bg-green-500/20 border-green-500 text-green-500;
  }
}

:deep(.arco-btn) {
  &[status="primary"] {
    @apply border-blue-500/40 text-blue-600 border-dashed bg-transparent;

    &:hover {
      @apply bg-blue-500/10 border-blue-500/60;
    }
  }
}

:global(body.api-testing-theme) .hooks-enhanced :deep(.arco-btn) {
  &[status="primary"] {
    @apply bg-[#1d2331] border-blue-500/50 text-blue-300 border-dashed;

    &:hover {
      @apply bg-blue-500/10 border-blue-500/60;
    }
  }
}

:global(.hooks-function-modal .arco-modal) {
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

:global(.hooks-function-modal .arco-modal-header) {
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

:global(.hooks-function-modal .arco-modal-title) {
  color: var(--color-text-1);
}

:global(.hooks-function-modal .arco-modal-close-btn) {
  color: var(--color-text-3);
}

:global(body.api-testing-theme .hooks-function-modal .arco-modal) {
  @apply bg-gray-800 border border-gray-700;

  .arco-modal-header {
    @apply border-b border-gray-700;
  }

  .arco-modal-title {
    @apply text-gray-200;
  }

  .arco-modal-close-btn {
    @apply text-gray-400;

    &:hover {
      @apply text-gray-200;
    }
  }

  .arco-modal-footer {
    @apply border-t border-gray-700;

    .arco-btn {
      @apply bg-gray-700 border-gray-600 text-gray-200;

      &:hover {
        @apply bg-gray-600 border-gray-500;
      }

      &.arco-btn-primary {
        @apply bg-blue-500 border-blue-500 text-white;

        &:hover {
          @apply bg-blue-600 border-blue-600;
        }
      }
    }
  }
}

:deep(.arco-input-wrapper) {
  @apply bg-white border-[color:var(--color-border-2)];

  input {
    @apply text-[color:var(--color-text-1)] bg-transparent;
    &::placeholder {
      @apply text-[color:var(--color-text-3)];
    }
  }
}

:global(body.api-testing-theme) :deep(.arco-input-wrapper) {
  @apply bg-gray-900/60 border-gray-700;

  input {
    @apply text-gray-200 bg-transparent;
    &::placeholder {
      @apply text-gray-500;
    }
  }
}
</style>
