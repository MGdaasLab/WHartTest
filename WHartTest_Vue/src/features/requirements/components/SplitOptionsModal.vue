<template>
  <a-modal
    :visible="visible"
    title="模块拆分配置"
    :width="600"
    @ok="handleConfirm"
    @cancel="handleCancel"
  >
    <div class="split-options">
      <!-- 拆分级别选择 -->
      <div class="option-group">
        <h4>拆分级别</h4>
        <a-radio-group v-model="splitConfig.split_level" direction="vertical">
          <a-radio value="h1">
            <div class="radio-content">
              <strong>H1级别拆分</strong>
              <div class="radio-desc">按一级标题（# 标题）拆分 - 适合大章节拆分</div>
            </div>
          </a-radio>
          <a-radio value="h2">
            <div class="radio-content">
              <strong>H2级别拆分 ⭐推荐</strong>
              <div class="radio-desc">按二级标题（## 标题）拆分 - 适合功能模块拆分</div>
            </div>
          </a-radio>
          <a-radio value="h3">
            <div class="radio-content">
              <strong>H3级别拆分</strong>
              <div class="radio-desc">按三级标题（### 标题）拆分 - 适合子功能拆分</div>
            </div>
          </a-radio>
          <a-radio value="auto">
            <div class="radio-content">
              <strong>智能拆分</strong>
              <div class="radio-desc">智能按字数拆分 - 适合没有明确标题结构的文档</div>
            </div>
          </a-radio>
        </a-radio-group>
      </div>

      <!-- 其他配置选项 -->
      <div class="option-group">
        <h4>拆分配置</h4>
        <a-checkbox v-model="splitConfig.include_context">
          包含上下文（包含上级标题作为上下文）
        </a-checkbox>
      </div>

      <!-- 智能拆分的分块大小 -->
      <div v-if="splitConfig.split_level === 'auto'" class="option-group">
        <h4>分块大小</h4>
        <a-input-number
          v-model="splitConfig.chunk_size"
          :min="500"
          :max="5000"
          :step="100"
          style="width: 200px"
        />
        <div class="input-desc">字符数，建议1500-3000之间</div>
      </div>

      <!-- 文档结构分析结果 -->
      <div v-if="structureAnalysis" class="option-group">
        <h4>文档结构分析</h4>
        <div class="structure-info">
          <div class="structure-item">
            <span class="structure-label">H1标题：</span>
            <span class="structure-count">{{ structureAnalysis.structure_analysis.h1_titles.length }}个</span>
          </div>
          <div class="structure-item">
            <span class="structure-label">H2标题：</span>
            <span class="structure-count">{{ structureAnalysis.structure_analysis.h2_titles.length }}个</span>
          </div>
          <div class="structure-item">
            <span class="structure-label">H3标题：</span>
            <span class="structure-count">{{ structureAnalysis.structure_analysis.h3_titles.length }}个</span>
          </div>
        </div>

        <!-- 拆分建议 -->
        <div v-if="structureAnalysis.split_recommendations?.length" class="recommendations">
          <h5>💡 拆分建议：</h5>
          <div
            v-for="rec in structureAnalysis.split_recommendations"
            :key="rec.level"
            class="recommendation-item"
            :class="{ recommended: rec.recommended }"
          >
            <div class="rec-header">
              <strong>{{ rec.level.toUpperCase() }}级别</strong>
              <span v-if="rec.recommended" class="rec-badge">推荐</span>
              <span class="rec-count">{{ rec.modules_count }}个模块</span>
            </div>
            <div class="rec-desc">{{ rec.description }} - {{ rec.suitable_for }}</div>
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue';
import type { SplitModulesRequest, DocumentStructureResponse } from '../types';

interface Props {
  visible: boolean;
  structureAnalysis?: DocumentStructureResponse | null;
  defaultLevel?: string;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'confirm', config: SplitModulesRequest): void;
  (e: 'cancel'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const splitConfig = reactive<SplitModulesRequest>({
  split_level: 'h2',
  include_context: true,
  chunk_size: 2000
});

// 监听默认级别变化
watch(() => props.defaultLevel, (newLevel) => {
  if (newLevel) {
    splitConfig.split_level = newLevel as any;
  }
}, { immediate: true });

const handleConfirm = () => {
  emit('confirm', { ...splitConfig });
  emit('update:visible', false);
};

const handleCancel = () => {
  emit('cancel');
  emit('update:visible', false);
};
</script>

<style scoped>
.split-options {
  padding: 8px 0;
}

.option-group {
  margin-bottom: 24px;
}

.option-group h4 {
  margin: 0 0 12px 0;
  color: #1d2129;
  font-size: 14px;
  font-weight: 600;
}

.option-group h5 {
  margin: 12px 0 8px 0;
  color: #4e5969;
  font-size: 13px;
  font-weight: 500;
}

.radio-content {
  margin-left: 8px;
}

.radio-desc {
  color: #86909c;
  font-size: 12px;
  margin-top: 2px;
}

.input-desc {
  color: #86909c;
  font-size: 12px;
  margin-top: 4px;
}

.structure-info {
  background: #f7f8fa;
  border-radius: 4px;
  padding: 12px;
  margin-bottom: 12px;
}

.structure-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.structure-label {
  color: #4e5969;
  font-size: 13px;
}

.structure-count {
  color: #1d2129;
  font-weight: 500;
  font-size: 13px;
}

.recommendations {
  border: 1px solid #e5e6eb;
  border-radius: 4px;
  padding: 12px;
}

.recommendation-item {
  padding: 8px;
  border-radius: 4px;
  margin-bottom: 8px;
  border: 1px solid #e5e6eb;
}

.recommendation-item.recommended {
  border-color: #165dff;
  background: #f2f7ff;
}

.rec-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.rec-badge {
  background: #165dff;
  color: white;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
}

.rec-count {
  color: #86909c;
  font-size: 12px;
}

.rec-desc {
  color: #4e5969;
  font-size: 12px;
}
</style>
