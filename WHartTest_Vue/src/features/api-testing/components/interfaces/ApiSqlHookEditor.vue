<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue';
import { Message } from '@arco-design/web-vue';
import { getDatabaseConfigs, type DatabaseConfig } from '../../services/databaseConfigService';
import { toArray } from '../../services/responseHelpers';
import { useProjectStore } from '@/store/projectStore';

interface Props {
  value?: string;
  visible?: boolean;
  type?: 'setup' | 'teardown';
}

const props = defineProps<Props>();
const emits = defineEmits(['update:value', 'update:visible', 'confirm', 'cancel']);

const sqlNameRef = ref('');
const sqlContentRef = ref('');
const selectedDbConfigRef = ref('');
const varNameRef = ref('');

// 使用projectStore获取当前项目ID
const projectStore = useProjectStore();

// 数据库配置列表
const dbConfigs = ref<DatabaseConfig[]>([]);
const loading = ref(false);

// 加载数据库配置列表
const loadDbConfigs = async () => {
  if (!projectStore.currentProjectId) {
    Message.warning('请先选择项目');
    return;
  }
  
  try {
    loading.value = true;
    const response = await getDatabaseConfigs(Number(projectStore.currentProjectId));
    
    dbConfigs.value = toArray<DatabaseConfig>(response.data?.results ?? response.data);
    
    if (dbConfigs.value.length > 0) {
      selectedDbConfigRef.value = String(dbConfigs.value[0].id);
    }
    // 不自动显示警告消息，只在用户实际尝试使用SQL钩子时才显示
  } catch (error) {
    console.error('获取数据库配置失败:', error);
    Message.error('获取数据库配置失败');
    dbConfigs.value = [];
  } finally {
    loading.value = false;
  }
};

// 获取钩子类型的中文描述
const hookTypeText = computed(() => props.type === 'setup' ? '前置' : '后置');

// 获取钩子函数名称
const getHookFunctionName = () => {
  return props.type === 'setup' ? 'setup_sql' : 'teardown_sql';
};

// 获取钩子函数参数
const getHookFunctionParam = () => {
  return props.type === 'setup' ? 'request' : 'response';
};

// 生成Python函数代码（更新为新格式）
const generatePythonCode = (sqlStatement: string, dbConfigId: string, varName: string) => {
  const functionName = getHookFunctionName();
  const paramName = getHookFunctionParam();
  
  // 使用db_id替代db_key
  const jsonObj = {
    type: 'sql',
    db_id: Number(dbConfigId), // 使用数字类型的db_id
    sql: sqlStatement,
    var_name: varName || ''
  };
  
  // 为了兼容后端，统一使用紧凑型JSON字符串（无空格、换行）
  const jsonStr = JSON.stringify(jsonObj);
  
  return `def ${functionName}(${paramName}):\n    return ${paramName}.${props.type === 'setup' ? 'setup_hook' : 'teardown_hook'}(${jsonStr})`;
};

// 从Python代码中提取SQL语句和数据库配置
const extractFromPythonCode = (code: string) => {
  try {
    console.log('解析Python代码:', code);
    
    // 尝试直接解析整个字符串作为JSON对象
    if (code.startsWith('{') && code.endsWith('}')) {
      try {
        console.log('尝试直接解析JSON字符串');
        const jsonObj = JSON.parse(code);
        if (jsonObj && jsonObj.type === 'sql') {
          console.log('成功解析为SQL钩子对象:', jsonObj);
          return {
            sql: jsonObj.sql || '',
            dbId: jsonObj.db_id, // 优先使用db_id
            dbKey: jsonObj.db_key || 'default', // 向后兼容
            varName: jsonObj.var_name || '',
            isNewFormat: true
          };
        }
      } catch (e) {
        console.error('直接解析JSON失败:', e);
      }
    }
    
    // 尝试提取JSON对象 - 支持多种模式匹配
    const jsonMatches = [
      // 标准hook函数模式
      code.match(/setup_hook\(({[\s\S]*?})\)/),
      code.match(/teardown_hook\(({[\s\S]*?})\)/),
      // 自定义函数调用模式
      code.match(/hook\(({[\s\S]*?})\)/),
      // 直接参数模式
      code.match(/\(({[\s\S]*?})\)/)
    ];
    
    for (const match of jsonMatches) {
      if (match && match[1]) {
        try {
          const jsonStr = match[1].trim();
          console.log('从Python代码提取的JSON字符串:', jsonStr);
          const jsonObj = JSON.parse(jsonStr);
          console.log('解析后的JSON对象:', jsonObj);
          
          if (jsonObj.type === 'sql') {
            return {
              sql: jsonObj.sql || '',
              dbId: jsonObj.db_id, // 优先使用db_id
              dbKey: jsonObj.db_key || 'default', // 向后兼容
              varName: jsonObj.var_name || '',
              isNewFormat: true
            };
          }
        } catch (e) {
          console.error('JSON解析失败:', e);
          // 继续尝试下一个匹配
        }
      }
    }
    
    // 尝试旧格式
    const oldStyleSqlMatch = code.match(/sql\('([^']+)'/) || [];
    const oldStyleDbKeyMatch = code.match(/db_key=['"](.*?)['"]/i) || [];
    const oldStyleVarNameMatch = code.match(/var_name=['"](.*?)['"]/i) || [];
    
    if (oldStyleSqlMatch[1]) {
      console.log('检测到旧格式SQL钩子');
      return {
        sql: oldStyleSqlMatch[1] || '',
        dbKey: oldStyleDbKeyMatch[1] || 'default',
        varName: oldStyleVarNameMatch[1] || '',
        isNewFormat: false
      };
    }
    
    // sql: 格式
    if (code.startsWith('sql:')) {
      console.log('检测到sql:格式的SQL钩子');
      const parts = code.split(':');
      if (parts.length >= 3) {
        return {
          sql: parts.slice(2).join(':') || '',
          dbKey: 'default',
          varName: parts[1] || '',
          isNewFormat: false
        };
      }
    }
    
    console.warn('无法从代码中提取SQL数据:', code);
    return {
      sql: '',
      dbKey: 'default',
      varName: '',
      isNewFormat: false
    };
  } catch (error) {
    console.error('解析Python代码失败:', error);
    return {
      sql: '',
      dbKey: 'default',
      varName: '',
      isNewFormat: false
    };
  }
};

// 初始化表单
const initForm = () => {
  console.log('初始化SQL表单, value:', props.value);
  
  if (!props.value) {
    // 没有提供值，使用默认值
    sqlNameRef.value = `${hookTypeText.value}SQL`;
    sqlContentRef.value = '';
    varNameRef.value = '';
    
    // 如果有数据库配置，默认选第一个
    if (dbConfigs.value.length > 0) {
      selectedDbConfigRef.value = String(dbConfigs.value[0].id);
    }
    
    return;
  }
  
  // 检查是否是直接的JSON对象
  if (typeof props.value === 'object') {
    try {
      console.log('处理对象格式的SQL钩子:', props.value);
      const jsonObj = props.value as any;
      
      if (jsonObj && jsonObj.type === 'sql') {
        console.log('直接传入的SQL对象:', jsonObj);
        sqlContentRef.value = jsonObj.sql || '';
        varNameRef.value = jsonObj.var_name || '';
        
        // 优先使用db_id来匹配数据库配置
        if (jsonObj.db_id) {
          console.log('使用db_id匹配数据库配置:', jsonObj.db_id);
          selectedDbConfigRef.value = String(jsonObj.db_id);
          sqlNameRef.value = `SQL查询_ID${jsonObj.db_id}`;
        } 
        // 向后兼容，尝试使用db_key来匹配
        else if (jsonObj.db_key) {
          console.log('使用db_key匹配数据库配置:', jsonObj.db_key);
          sqlNameRef.value = `SQL查询_${jsonObj.db_key}`;
          
          // 查找匹配的数据库配置
          const matchedConfig = dbConfigs.value.find(config => 
            config.database === jsonObj.db_key || config.name === jsonObj.db_key
          );
          
          if (matchedConfig) {
            selectedDbConfigRef.value = String(matchedConfig.id);
          } else if (dbConfigs.value.length > 0) {
            selectedDbConfigRef.value = String(dbConfigs.value[0].id);
          }
        } else {
          // 没有提供db_id和db_key，使用默认值
          sqlNameRef.value = `SQL查询`;
          if (dbConfigs.value.length > 0) {
            selectedDbConfigRef.value = String(dbConfigs.value[0].id);
          }
        }
        
        return;
      }
    } catch (e) {
      console.error('处理对象格式SQL钩子失败:', e);
    }
  }
  
  // 处理字符串形式的值
  if (typeof props.value === 'string') {
    // 尝试从字符串解析JSON对象
    if (props.value.startsWith('{') && props.value.endsWith('}')) {
      try {
        const jsonObj = JSON.parse(props.value);
        if (jsonObj && jsonObj.type === 'sql') {
          sqlContentRef.value = jsonObj.sql || '';
          varNameRef.value = jsonObj.var_name || '';
          
          // 优先使用db_id来匹配数据库配置
          if (jsonObj.db_id) {
            console.log('使用db_id匹配数据库配置:', jsonObj.db_id);
            selectedDbConfigRef.value = String(jsonObj.db_id);
            sqlNameRef.value = `SQL查询_ID${jsonObj.db_id}`;
          } 
          // 向后兼容，尝试使用db_key来匹配
          else if (jsonObj.db_key) {
            console.log('使用db_key匹配数据库配置:', jsonObj.db_key);
            sqlNameRef.value = `SQL查询_${jsonObj.db_key}`;
            
            // 查找匹配的数据库配置
            const matchedConfig = dbConfigs.value.find(config => 
              config.database === jsonObj.db_key || config.name === jsonObj.db_key
            );
            
            if (matchedConfig) {
              selectedDbConfigRef.value = String(matchedConfig.id);
            } else if (dbConfigs.value.length > 0) {
              selectedDbConfigRef.value = String(dbConfigs.value[0].id);
            }
          } else {
            // 没有提供db_id和db_key，使用默认值
            sqlNameRef.value = `SQL查询`;
            if (dbConfigs.value.length > 0) {
              selectedDbConfigRef.value = String(dbConfigs.value[0].id);
            }
          }
          
          return;
        }
      } catch (e) {
        console.error('解析JSON字符串失败:', e);
      }
    }

    // Python函数代码格式
    if (props.value.startsWith('def ')) {
      console.log('处理Python函数格式的SQL钩子');
      // 从Python函数中提取SQL和配置
      const { sql, dbKey, varName } = extractFromPythonCode(props.value);
      
      sqlContentRef.value = sql;
      varNameRef.value = varName;
      sqlNameRef.value = varName 
        ? `${varName} = SQL查询` 
        : `SQL查询_${dbKey || 'default'}`;
      
      // 查找匹配的数据库配置
      const matchedConfig = dbConfigs.value.find(config => {
        return config.database === dbKey || 
               config.name.toLowerCase().includes(dbKey.toLowerCase());
      });
      
      if (matchedConfig) {
        selectedDbConfigRef.value = String(matchedConfig.id);
      } else if (dbConfigs.value.length > 0) {
        selectedDbConfigRef.value = String(dbConfigs.value[0].id);
      }
      
      return;
    }
    
    // 旧格式: sql:name:db_key:sql
    if (props.value.startsWith('sql:')) {
      console.log('处理旧格式SQL钩子:', props.value);
      const parts = props.value.split(':');
      
      if (parts.length >= 3) {
        const name = parts[1];
        const sqlContent = parts.slice(2).join(':');
        
        sqlNameRef.value = name || '未命名SQL';
        sqlContentRef.value = sqlContent;
        varNameRef.value = name || ''; // 使用名称作为变量名
        
        // 如果有数据库配置，默认选第一个
        if (dbConfigs.value.length > 0) {
          selectedDbConfigRef.value = String(dbConfigs.value[0].id);
        }
        
        return;
      }
    }
    
    // 默认处理：尝试使用extractFromPythonCode提取数据
    console.log('尝试通用方法提取SQL数据');
    const { sql, dbKey, varName } = extractFromPythonCode(props.value);
    
    if (sql) {
      sqlContentRef.value = sql;
      varNameRef.value = varName;
      sqlNameRef.value = varName 
        ? `${varName} = SQL查询` 
        : `SQL查询_${dbKey || 'default'}`;
      
      // 查找匹配的数据库配置
      const matchedConfig = dbConfigs.value.find(config => {
        return config.database === dbKey || 
               config.name.toLowerCase().includes(dbKey.toLowerCase());
      });
      
      if (matchedConfig) {
        selectedDbConfigRef.value = String(matchedConfig.id);
      } else if (dbConfigs.value.length > 0) {
        selectedDbConfigRef.value = String(dbConfigs.value[0].id);
      }
      
      return;
    }
  }
  
  // 无法处理的情况，使用默认值
  console.warn('无法处理的SQL钩子格式，使用默认值');
  sqlNameRef.value = `${hookTypeText.value}SQL`;
  sqlContentRef.value = '';
  varNameRef.value = '';
  
  if (dbConfigs.value.length > 0) {
    selectedDbConfigRef.value = String(dbConfigs.value[0].id);
  }
};

// 监听对话框显示状态
watch(() => props.visible, (newVal) => {
  if (newVal) {
    initForm();
  }
});

// 监听值变化
watch(() => props.value, () => {
  if (props.visible) {
    initForm();
  }
});

// 获取所选数据库的db_key
const getSelectedDbKey = () => {
  const selectedId = Number(selectedDbConfigRef.value);
  const selectedConfig = dbConfigs.value.find(config => config.id === selectedId);
  
  if (selectedConfig) {
    // 使用实际的数据库名称作为key
    return selectedConfig.database || 'default';
  }
  
  return 'default';
};

// 处理提交按钮
const handleSubmit = () => {
  // 验证表单
  if (!sqlContentRef.value) {
    Message.warning('SQL语句不能为空');
    return;
  }
  
  if (!selectedDbConfigRef.value) {
    Message.warning('请选择数据库配置');
    return;
  }
  
  // 检查是否有可用的数据库配置
  if (dbConfigs.value.length === 0) {
    Message.warning('未找到可用的数据库配置，请先在环境管理中添加');
    return;
  }
  
  // 包装数据为SQL钩子对象
  const sqlHookObj = {
    type: 'sql',
    db_id: Number(selectedDbConfigRef.value),
    sql: sqlContentRef.value,
    var_name: varNameRef.value || undefined
  };
  
  // 生成JSON字符串作为最终输出
  const jsonValue = JSON.stringify(sqlHookObj);
  
  console.log('提交SQL钩子:', jsonValue);
  
  // 发送值给父组件
  emits('update:value', jsonValue);
  emits('confirm', jsonValue);
  
  // 关闭对话框
  emits('update:visible', false);
};

// 处理取消按钮
const handleCancel = () => {
  console.log('取消编辑SQL钩子');
  emits('update:visible', false);
  emits('cancel');
};

// 组件加载时获取数据库配置
onMounted(() => {
  loadDbConfigs();
});
</script>

<template>
  <a-modal
    :visible="props.visible"
    modal-class="sql-hook-editor-modal"
    @cancel="handleCancel"
    :unmount-on-close="false"
    :footer="false"
    :title="`编辑${hookTypeText}SQL`"
    :mask-closable="false"
    width="800px"
  >
    <div class="flex flex-col gap-4 p-2">
      <!-- SQL名称 -->
      <div>
        <div class="sql-field-label text-sm mb-1">SQL名称</div>
        <a-input
          v-model="sqlNameRef"
          placeholder="输入SQL名称"
          allow-clear
        />
      </div>
      
      <!-- 数据库配置选择 -->
      <div>
        <div class="sql-field-label text-sm mb-1">数据库配置</div>
        <a-select
          v-model="selectedDbConfigRef"
          placeholder="选择数据库配置"
          allow-clear
        >
          <a-option
            v-for="config in dbConfigs"
            :key="config.id"
            :value="String(config.id)"
          >
            {{ config.name }} ({{ config.database }} - {{ config.type }})
          </a-option>
        </a-select>
        <div class="sql-helper-text text-xs mt-1">
          SQL将在选定的数据库上执行
        </div>
      </div>
      
      <!-- 变量名 -->
      <div>
        <div class="sql-field-label text-sm mb-1">变量名（可选）</div>
        <a-input
          v-model="varNameRef"
          placeholder="输入变量名，用于保存结果"
          allow-clear
        />
        <div class="sql-helper-text text-xs mt-1">
          如果需要SQL查询结果，请指定变量名，后续步骤可引用该变量
        </div>
      </div>
      
      <!-- SQL内容 -->
      <div class="flex-1">
        <div class="sql-field-label text-sm mb-1">SQL语句</div>
        <a-textarea
          v-model="sqlContentRef"
          placeholder="输入SQL语句，如 SELECT * FROM users WHERE id = 1"
          allow-clear
          :auto-size="{ minRows: 8, maxRows: 15 }"
        />
        <div class="sql-helper-text text-xs mt-1">
          只需输入SQL语句，系统会自动生成完整的钩子函数代码
        </div>
      </div>
      
      <!-- 按钮组 -->
      <div class="flex justify-end gap-2 mt-2">
        <a-button @click="handleCancel">取消</a-button>
        <a-button type="primary" @click="handleSubmit">确定</a-button>
      </div>
    </div>
  </a-modal>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";

.sql-field-label {
  color: var(--color-text-2);
}

.sql-helper-text {
  color: var(--color-text-3);
}

:global(.sql-hook-editor-modal .arco-modal) {
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

:global(.sql-hook-editor-modal .arco-modal-header) {
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

:global(.sql-hook-editor-modal .arco-modal-title) {
  color: var(--color-text-1);
}

:global(.sql-hook-editor-modal .arco-modal-close-btn) {
  color: var(--color-text-3);
}

:global(.sql-hook-editor-modal .arco-modal-close-btn:hover) {
  color: var(--color-text-1);
}

:global(body.api-testing-theme) .sql-field-label {
  color: rgb(156, 163, 175);
}

:global(body.api-testing-theme) .sql-helper-text {
  color: rgb(107, 114, 128);
}

:global(body.api-testing-theme .sql-hook-editor-modal .arco-modal) {
  background: rgb(31, 41, 55);
  border: 1px solid rgb(55, 65, 81);
}

:global(body.api-testing-theme .sql-hook-editor-modal .arco-modal-header) {
  border-bottom-color: rgb(55, 65, 81);
}

:global(body.api-testing-theme .sql-hook-editor-modal .arco-modal-title) {
  color: rgb(229, 231, 235);
}

:global(body.api-testing-theme .sql-hook-editor-modal .arco-modal-close-btn) {
  color: rgb(156, 163, 175);
}

:global(body.api-testing-theme .sql-hook-editor-modal .arco-modal-close-btn:hover) {
  color: rgb(229, 231, 235);
}

:deep(.arco-input-wrapper) {
  @apply bg-white border-[color:var(--color-border-2)];
  
  .arco-input {
    @apply text-[color:var(--color-text-1)] bg-transparent;
    &::placeholder {
      @apply text-[color:var(--color-text-3)];
    }
  }
}

:deep(.arco-textarea-wrapper) {
  @apply bg-white border-[color:var(--color-border-2)];
  
  .arco-textarea {
    @apply text-[color:var(--color-text-1)] bg-transparent;
    &::placeholder {
      @apply text-[color:var(--color-text-3)];
    }
  }
}

:deep(.arco-select-view) {
  @apply bg-white border-[color:var(--color-border-2)];
  
  .arco-select-view-value {
    @apply text-[color:var(--color-text-1)];
  }
}

:deep(.arco-btn) {
  @apply text-[color:var(--color-text-2)];
  
  &:hover {
    @apply border-blue-500 text-blue-500;
  }
  
  &.arco-btn-primary {
    @apply bg-blue-500 border-blue-500 text-white;
    
    &:hover {
      @apply bg-blue-600 border-blue-600;
    }
  }
}

:global(body.api-testing-theme) :deep(.arco-input-wrapper) {
  @apply bg-gray-900/60 border-gray-700;

  .arco-input {
    @apply text-gray-200 bg-transparent;
    &::placeholder {
      @apply text-gray-500;
    }
  }
}

:global(body.api-testing-theme) :deep(.arco-textarea-wrapper) {
  @apply bg-gray-900/60 border-gray-700;

  .arco-textarea {
    @apply text-gray-200 bg-transparent;
    &::placeholder {
      @apply text-gray-500;
    }
  }
}

:global(body.api-testing-theme) :deep(.arco-select-view) {
  @apply bg-gray-900/60 border-gray-700;

  .arco-select-view-value {
    @apply text-gray-200;
  }
}

pre {
  @apply font-mono bg-gray-950 p-2 rounded border border-gray-800;
}
</style> 
