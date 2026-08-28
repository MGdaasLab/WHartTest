<template>
  <div class="knowledge-base-selector">
    <div class="kb-select-container">
      <a-select
        :model-value="selectedKnowledgeBaseId"
        @update:model-value="handleSelectKnowledgeBase"
        :placeholder="text.selectKnowledgeBase"
        :loading="loading"
        :disabled="!knowledgeBases.length"
        size="small"
        style="width: 200px;"
      >
        <a-option
          v-for="kb in knowledgeBases"
          :key="kb.id"
          :value="kb.id"
          :label="kb.name"
        >
          <div class="kb-option">
            <span class="kb-name">{{ kb.name }}</span>
            <span class="kb-stats">{{ text.kbStats(kb.document_count, kb.chunk_count) }}</span>
          </div>
        </a-option>
      </a-select>

      <a-tooltip :content="text.advancedSettings">
        <a-button
          type="text"
          size="small"
          @click="showAdvancedSettings = !showAdvancedSettings"
          :class="{ 'active': showAdvancedSettings }"
        >
          <template #icon>
            <i class="icon-settings"></i>
          </template>
        </a-button>
      </a-tooltip>
    </div>

    <!-- 高级设置面板 -->
    <div v-if="showAdvancedSettings" class="advanced-settings">
      <div class="setting-item">
        <label>{{ text.similarityThreshold }}</label>
        <a-slider
          :model-value="similarityThreshold"
          @update:model-value="handleSimilarityChange"
          :min="0.1"
          :max="1.0"
          :step="0.1"
          :show-tooltip="true"
          style="width: 120px;"
        />
        <span class="value-display">{{ similarityThreshold }}</span>
      </div>

      <div class="setting-item">
        <label>{{ text.retrievalCount }}</label>
        <a-input-number
          :model-value="topK"
          @update:model-value="handleTopKChange"
          :min="1"
          :max="20"
          :step="1"
          size="small"
          style="width: 80px;"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue';
import {
  Message,
  Select as ASelect,
  Option as AOption,
  Button as AButton,
  Tooltip as ATooltip,
  Slider as ASlider,
  InputNumber as AInputNumber
} from '@arco-design/web-vue';
import { KnowledgeService } from '@/features/knowledge/services/knowledgeService';
import type { KnowledgeBase } from '@/features/knowledge/types/knowledge';
import { useAppI18n } from '@/composables/useAppI18n';
import { toArray } from '@/features/api-testing/services/responseHelpers';

interface Props {
  projectId: number | null;
  useKnowledgeBase: boolean;
  selectedKnowledgeBaseId: string | null;
  similarityThreshold: number;
  topK: number;
}

const props = defineProps<Props>();
const { isEnglish } = useAppI18n();

const text = computed(() => (
  isEnglish.value
    ? {
        selectKnowledgeBase: 'Select knowledge base',
        kbStats: (documentCount: number, chunkCount: number) => `${documentCount} docs ${chunkCount} chunks`,
        advancedSettings: 'Advanced settings',
        similarityThreshold: 'Similarity threshold:',
        retrievalCount: 'Top K:',
        fetchKnowledgeBasesFailed: 'Failed to load knowledge bases',
      }
    : {
        selectKnowledgeBase: '选择知识库',
        kbStats: (documentCount: number, chunkCount: number) => `${documentCount}文档 ${chunkCount}分块`,
        advancedSettings: '高级设置',
        similarityThreshold: '相似度阈值:',
        retrievalCount: '检索数量:',
        fetchKnowledgeBasesFailed: '获取知识库列表失败',
      }
));

const emit = defineEmits<{
  'update:use-knowledge-base': [value: boolean];
  'update:selected-knowledge-base-id': [value: string | null];
  'update:similarity-threshold': [value: number];
  'update:top-k': [value: number];
}>();

// 响应式数据
const loading = ref(false);
const knowledgeBases = ref<KnowledgeBase[]>([]);
const showAdvancedSettings = ref(false);

// 方法
const fetchKnowledgeBases = async () => {
  if (!props.projectId) return;

  loading.value = true;
  try {
    const response = await KnowledgeService.getKnowledgeBases({
      project: props.projectId,
      is_active: true,
    });

    const kbList = toArray<KnowledgeBase>((response as any)?.results ?? response);

    knowledgeBases.value = kbList;

    // 如果当前选中的知识库不在列表中，默认选择第一个
    if (!props.selectedKnowledgeBaseId || !kbList.find(kb => kb.id === props.selectedKnowledgeBaseId)) {
      if (kbList.length > 0) {
        emit('update:selected-knowledge-base-id', kbList[0].id);
      } else {
        emit('update:selected-knowledge-base-id', null);
      }
    }
  } catch (error) {
    console.error('获取知识库列表失败:', error);
    Message.error(text.value.fetchKnowledgeBasesFailed);
    knowledgeBases.value = [];
  } finally {
    loading.value = false;
  }
};

const handleSelectKnowledgeBase = (value: string) => {
  emit('update:selected-knowledge-base-id', value);
};

const handleSimilarityChange = (value: number) => {
  emit('update:similarity-threshold', value);
};

const handleTopKChange = (value: number | undefined) => {
  if (value !== undefined) {
    emit('update:top-k', value);
  }
};

// 监听项目变化
watch(
  () => props.projectId,
  (newProjectId) => {
    if (newProjectId) {
      fetchKnowledgeBases();
    } else {
      knowledgeBases.value = [];
      emit('update:selected-knowledge-base-id', null);
    }
  }
);

// 组件挂载时加载知识库列表
onMounted(() => {
  if (props.projectId) {
    fetchKnowledgeBases();
  }
});
</script>

<style scoped>
.knowledge-base-selector {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 16px;
}

.kb-select-container {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kb-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kb-name {
  font-size: 13px;
  font-weight: 500;
}

.kb-stats {
  font-size: 11px;
  color: #86909c;
}

.advanced-settings {
  padding: 8px 12px;
  background-color: white;
  border-radius: 6px;
  border: 1px solid #e5e6eb;
  display: flex;
  gap: 16px;
  align-items: center;
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.setting-item label {
  font-size: 12px;
  color: #4e5969;
  white-space: nowrap;
}

.value-display {
  font-size: 12px;
  color: #86909c;
  min-width: 30px;
}

.icon-settings::before {
  content: '⚙️';
}

.active {
  background-color: #e8f4ff;
  color: #00a0e9;
}
</style>
