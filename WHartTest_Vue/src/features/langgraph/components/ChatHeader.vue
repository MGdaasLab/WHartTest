<template>
  <div class="chat-header-container">
    <div class="chat-header">
      <h1 class="chat-title">LLM对话</h1>
      <div class="chat-actions">
        <div class="stream-toggle">
          <span class="toggle-label">流式输出</span>
          <a-switch
            :model-value="isStreamMode"
            @update:model-value="(value: string | number | boolean) => $emit('update:is-stream-mode', Boolean(value))"
            size="small"
          />
        </div>

        <!-- 知识库开关 -->
        <div class="kb-toggle">
          <span class="kb-icon">📚</span>
          <span class="toggle-label">知识库</span>
          <a-switch
            :model-value="useKnowledgeBase"
            @update:model-value="$emit('update:use-knowledge-base', $event)"
            size="small"
          />
        </div>

        <!-- 提示词选择器 -->
        <div class="prompt-selector">
          <span class="prompt-label">提示词：</span>
          <a-select
            v-model="selectedPromptId"
            :placeholder="selectedPromptId === null && defaultPrompt ? defaultPrompt.name : '选择提示词'"
            style="width: 200px"
            allow-clear
            @change="handlePromptChange"
            :loading="promptsLoading"
          >
            <a-option
              :value="null"
              :label="defaultPrompt ? defaultPrompt.name : '使用默认'"
            >
              <span>{{ defaultPrompt ? defaultPrompt.name : '使用默认' }}</span>
              <a-tag v-if="defaultPrompt" color="blue" size="small" style="margin-left: 8px;">默认</a-tag>
            </a-option>
            <a-option
              v-for="prompt in nonDefaultUserPrompts"
              :key="prompt.id"
              :value="prompt.id"
              :label="prompt.name"
            >
              <span>{{ prompt.name }}</span>
            </a-option>
          </a-select>
        </div>

        <a-button type="text" @click="$emit('show-system-prompt')">
          <template #icon>
            <i class="icon-settings"></i>
          </template>
          管理提示词
        </a-button>
        <a-tag v-if="sessionId" color="green">会话ID: {{ sessionIdShort }}</a-tag>
        <a-button v-if="hasMessages" type="text" status="danger" @click="$emit('clear-chat')">
          <template #icon>
            <icon-delete style="color: #f53f3f;" />
          </template>
          清除对话
        </a-button>
      </div>
    </div>

    <!-- 知识库选择和设置面板 -->
    <div v-if="useKnowledgeBase" class="kb-settings-panel">
      <KnowledgeBaseSelector
        :project-id="projectId"
        :use-knowledge-base="useKnowledgeBase"
        :selected-knowledge-base-id="selectedKnowledgeBaseId"
        :similarity-threshold="similarityThreshold"
        :top-k="topK"
        @update:use-knowledge-base="$emit('update:use-knowledge-base', $event)"
        @update:selected-knowledge-base-id="$emit('update:selected-knowledge-base-id', $event)"
        @update:similarity-threshold="$emit('update:similarity-threshold', $event)"
        @update:top-k="$emit('update:top-k', $event)"
      />
    </div>


  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue';
import { Button as AButton, Tag as ATag, Switch as ASwitch, Select as ASelect, Option as AOption } from '@arco-design/web-vue';
import { IconDelete } from '@arco-design/web-vue/es/icon';
import KnowledgeBaseSelector from './KnowledgeBaseSelector.vue';
import { getUserPrompts, getDefaultPrompt } from '@/features/prompts/services/promptService';
import type { UserPrompt } from '@/features/prompts/types/prompt';

interface Props {
  sessionId: string;
  isStreamMode: boolean;
  hasMessages: boolean;
  projectId: number | null;
  useKnowledgeBase: boolean;
  selectedKnowledgeBaseId: string | null;
  similarityThreshold: number;
  topK: number;
  selectedPromptId: number | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  'update:is-stream-mode': [value: boolean];
  'clear-chat': [];
  'show-system-prompt': []; // 🆕 新增提示词管理事件
  'update:use-knowledge-base': [value: boolean];
  'update:selected-knowledge-base-id': [value: string | null];
  'update:similarity-threshold': [value: number];
  'update:top-k': [value: number];
  'update:selected-prompt-id': [value: number | null];
}>();

// 截断会话ID以便展示
const sessionIdShort = computed(() => {
  if (!props.sessionId) return '';
  return props.sessionId.length > 8 ? `${props.sessionId.substring(0, 8)}...` : props.sessionId;
});

// 提示词相关数据
const selectedPromptId = ref<number | null>(props.selectedPromptId);
const userPrompts = ref<UserPrompt[]>([]);
const defaultPrompt = ref<UserPrompt | null>(null);
const promptsLoading = ref(false);

// 过滤掉默认提示词的用户提示词列表（避免重复显示）
const nonDefaultUserPrompts = computed(() => {
  return userPrompts.value.filter(prompt => !prompt.is_default);
});

// 加载用户提示词
const loadUserPrompts = async () => {
  console.log('🔄 ChatHeader开始加载提示词数据...');
  promptsLoading.value = true;
  try {
    const [promptsResponse, defaultResponse] = await Promise.all([
      getUserPrompts({
        prompt_type: 'general',
        is_active: true,
        ordering: 'name', // 先按名称排序
        page_size: 100
      }),
      getDefaultPrompt()
    ]);

    if (promptsResponse.status === 'success') {
      let allPrompts: UserPrompt[] = [];
      if (Array.isArray(promptsResponse.data)) {
        allPrompts = promptsResponse.data;
      } else if (promptsResponse.data.results) {
        allPrompts = promptsResponse.data.results;
      }
      
      // 🆕 在前端手动排序：默认提示词在前，然后按类型和名称排序
      userPrompts.value = allPrompts.sort((a, b) => {
        // 第一级：按 is_default 排序，默认的在前
        if (a.is_default && !b.is_default) return -1;
        if (!a.is_default && b.is_default) return 1;
        
        // 第二级：按提示词类型排序，通用对话类型在前
        const getTypeSort = (type: string) => {
          if (type === 'general') return 1; // 通用对话类型
          return 2; // 其他程序调用类型
        };
        
        const aTypeSort = getTypeSort(a.prompt_type || 'general');
        const bTypeSort = getTypeSort(b.prompt_type || 'general');
        if (aTypeSort !== bTypeSort) return aTypeSort - bTypeSort;
        
        // 第三级：按名称排序
        return a.name.localeCompare(b.name);
      });
      console.log('📋 ChatHeader加载到的提示词列表:', userPrompts.value.map(p => ({ id: p.id, name: p.name, isDefault: p.is_default, type: p.prompt_type })));
    }

    if (defaultResponse.status === 'success' && defaultResponse.data) {
      defaultPrompt.value = defaultResponse.data;
      console.log('🌟 ChatHeader加载到的默认提示词:', defaultPrompt.value.name);

      // 如果当前没有选择提示词且有默认提示词，则初始化为使用默认提示词
      if (selectedPromptId.value === null && !props.selectedPromptId) {
        // 不需要设置selectedPromptId，保持null表示使用默认
        emit('update:selected-prompt-id', null);
      }
    } else {
      console.log('❌ ChatHeader未找到默认提示词');
    }
  } catch (error) {
    console.error('加载用户提示词失败:', error);
    userPrompts.value = [];
    defaultPrompt.value = null;
  } finally {
    promptsLoading.value = false;
    console.log('✅ ChatHeader提示词数据加载完成');
  }
};

// 处理提示词变化
const handlePromptChange = (promptId: number | null) => {
  selectedPromptId.value = promptId;
  emit('update:selected-prompt-id', promptId);
};

// 监听props变化
watch(
  () => props.selectedPromptId,
  (newValue) => {
    selectedPromptId.value = newValue;
  }
);

// 组件挂载时加载数据
onMounted(() => {
  loadUserPrompts();
});

// 暴露刷新方法给父组件
defineExpose({
  refreshPrompts: loadUserPrompts
});
</script>

<style scoped>
.chat-header-container {
  background-color: #ffffff;
  border-bottom: 1px solid #e5e6eb;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  z-index: 1;
}

.chat-header {
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chat-title {
  font-size: 18px;
  font-weight: 600;
  color: #1d2129;
  margin: 0;
}

.chat-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.stream-toggle,
.kb-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background-color: rgba(0, 0, 0, 0.04);
  border-radius: 16px;
  font-size: 12px;
}

.kb-icon {
  font-size: 14px;
}

.toggle-label {
  color: #4e5969;
  font-weight: 500;
}

.icon-settings::before {
  content: '⚙️';
  margin-right: 4px;
}

.kb-settings-panel {
  border-top: 1px solid #e5e6eb;
  background-color: #f7f8fa;
}

.prompt-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.prompt-label {
  font-size: 13px;
  color: #4e5969;
  white-space: nowrap;
}


</style>
