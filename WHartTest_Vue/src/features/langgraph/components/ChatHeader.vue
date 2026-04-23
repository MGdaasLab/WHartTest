<template>
  <div class="chat-header-container">
    <div class="chat-header">
      <div class="chat-actions">
        <div class="kb-toggle">
          <span class="kb-icon">📚</span>
          <span class="toggle-label">知识库</span>
          <a-switch
            :model-value="useKnowledgeBase"
            @update:model-value="handleKnowledgeBaseToggle"
            size="small"
          />
        </div>

        <div class="prompt-selector">
          <span class="prompt-label">提示词：</span>
          <a-select
            v-model="selectedPromptId"
            :placeholder="defaultPrompt ? defaultPrompt.name : '选择提示词'"
            style="width: 160px"
            allow-clear
            @change="handlePromptChange"
            :loading="promptsLoading"
            :fallback-option="false"
          >
            <a-option
              v-for="prompt in userPrompts"
              :key="prompt.id"
              :value="prompt.id"
              :label="prompt.name"
            >
              <span>{{ prompt.name }}</span>
              <a-tag v-if="prompt.is_default" color="blue" size="small" style="margin-left: 8px;">默认</a-tag>
            </a-option>
          </a-select>
        </div>

        <a-button type="text" @click="$emit('show-system-prompt')">
          <template #icon>
            <icon-file />
          </template>
          管理提示词
        </a-button>

        <a-button type="text" @click="goToLlmConfigs">
          <template #icon>
            <icon-settings />
          </template>
          LLM配置
        </a-button>

        <a-button type="text" @click="$emit('show-tool-approval-settings')">
          <template #icon>
            <icon-thunderbolt />
          </template>
          工具审批
        </a-button>

        <a-button type="text" @click="$emit('show-weixin-connect')">
          <template #icon>
            <icon-message />
          </template>
          微信接入
        </a-button>

        <a-button v-if="hasMessages" type="text" status="danger" @click="$emit('clear-chat')">
          <template #icon>
            <icon-delete style="color: #f53f3f;" />
          </template>
          清除对话
        </a-button>
      </div>
    </div>

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
import { ref, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { Button as AButton, Tag as ATag, Switch as ASwitch, Select as ASelect, Option as AOption } from '@arco-design/web-vue';
import { IconDelete, IconSettings, IconThunderbolt, IconFile, IconMessage } from '@arco-design/web-vue/es/icon';
import KnowledgeBaseSelector from './KnowledgeBaseSelector.vue';
import { getUserPrompts, getDefaultPrompt } from '@/features/prompts/services/promptService';
import type { UserPrompt } from '@/features/prompts/types/prompt';

const router = useRouter();

interface Props {
  sessionId: string;
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
  (e: 'clear-chat'): void;
  (e: 'show-system-prompt'): void;
  (e: 'show-tool-approval-settings'): void;
  (e: 'show-weixin-connect'): void;
  (e: 'update:use-knowledge-base', value: boolean): void;
  (e: 'update:selected-knowledge-base-id', value: string | null): void;
  (e: 'update:similarity-threshold', value: number): void;
  (e: 'update:top-k', value: number): void;
  (e: 'update:selected-prompt-id', value: number | null): void;
}>();

// 跳转到LLM配置页面
const goToLlmConfigs = () => {
  router.push('/llm-configs');
};

// 提示词相关数据
const selectedPromptId = ref<number | null>(props.selectedPromptId);
const userPrompts = ref<UserPrompt[]>([]);
const defaultPrompt = ref<UserPrompt | null>(null);
const promptsLoading = ref(false);

// 加载用户提示词
const loadUserPrompts = async () => {
  console.log('🔄 ChatHeader开始加载提示词数据...');
  promptsLoading.value = true;
  try {
    const [promptsResponse, defaultResponse] = await Promise.all([
      getUserPrompts({
        is_active: true,
        ordering: 'name', // 先按名称排序
        page_size: 100
      }),
      getDefaultPrompt()
    ]);

    if (promptsResponse.status === 'success' && promptsResponse.data) {
      let allPrompts: UserPrompt[] = [];
      if (Array.isArray(promptsResponse.data)) {
        allPrompts = promptsResponse.data;
      } else if (promptsResponse.data.results) {
        allPrompts = promptsResponse.data.results;
      }

      // 过滤：只显示 general 类型的提示词
      allPrompts = allPrompts.filter(prompt =>
        (prompt.prompt_type || 'general') === 'general'
      );

      // 排序：默认提示词在前，然后按名称排序
      userPrompts.value = allPrompts.sort((a, b) => {
        // 第一级：按 is_default 排序，默认的在前
        if (a.is_default && !b.is_default) return -1;
        if (!a.is_default && b.is_default) return 1;

        // 第二级：按名称排序
        return a.name.localeCompare(b.name);
      });
      console.log('📋 ChatHeader加载到的提示词列表:', userPrompts.value.map(p => ({ id: p.id, name: p.name, isDefault: p.is_default, type: p.prompt_type })));

      // 🆕 检查当前选中的提示词是否在允许的列表中
      if (selectedPromptId.value !== null) {
        const selectedExists = userPrompts.value.some(p => p.id === selectedPromptId.value);
        if (!selectedExists) {
          console.log(`⚠️ 当前选中的提示词(ID:${selectedPromptId.value})不在允许列表中，重置选择`);
          selectedPromptId.value = null;
          emit('update:selected-prompt-id', null);
        }
      }
    }

    if (defaultResponse.status === 'success' && defaultResponse.data) {
      defaultPrompt.value = defaultResponse.data;
      console.log('🌟 ChatHeader加载到的默认提示词:', defaultPrompt.value.name);

      // 如果当前没有选择提示词且有默认提示词，则自动选中默认提示词
      if (selectedPromptId.value === null && !props.selectedPromptId) {
        selectedPromptId.value = defaultPrompt.value.id;
        emit('update:selected-prompt-id', defaultPrompt.value.id);
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

// 处理知识库开关变化
const handleKnowledgeBaseToggle = (value: string | number | boolean) => {
  emit('update:use-knowledge-base', Boolean(value));
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
  justify-content: flex-end;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.chat-title {
  font-size: 18px;
  font-weight: 600;
  color: #1d2129;
  margin: 0;
  flex-shrink: 0;
}

.chat-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  min-width: 0;
}

@media (max-width: 900px) {
  .chat-header {
    padding: 12px 16px;
  }

  .chat-actions {
    gap: 6px;
  }

  .prompt-selector :deep(.arco-select) {
    width: 150px !important;
  }
}

@media (max-width: 1200px) {
  .prompt-label {
    display: none;
  }
}

@media (max-width: 600px) {
  .chat-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .chat-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .prompt-selector {
    width: 100%;
  }

  .prompt-selector :deep(.arco-select) {
    width: 100% !important;
    flex: 1;
  }
}

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
