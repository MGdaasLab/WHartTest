<template>
  <a-drawer
    v-model:visible="internalVisible"
    :title="tl('AI 失败根因诊断与自愈分析')"
    :width="640"
    :footer="false"
  >
    <div v-if="loading" class="diagnosis-loading">
      <a-spin :size="32" />
      <div class="loading-text">{{ tl('AI 测试工程师正在深度分析失败现场...') }}</div>
      <div class="loading-sub">{{ tl('正在比对页面 DOM 结构、错误堆栈与多模态视觉上下文') }}</div>
    </div>

    <div v-else-if="diagnosis" class="diagnosis-container">
      <!-- 诊断概要头图卡片 -->
      <a-card class="summary-card" :bordered="false">
        <div class="summary-header">
          <div class="root-cause-tag-group">
            <a-tag :color="getRootCauseColor(diagnosis.root_cause_type)" size="large">
              <template #icon>
                <icon-bug v-if="diagnosis.root_cause_type === 'BUG'" />
                <icon-tool v-else-if="diagnosis.root_cause_type === 'SCRIPT_DEFECT'" />
                <icon-wifi v-else />
              </template>
              {{ diagnosis.root_cause_label || diagnosis.root_cause_type }}
            </a-tag>
            <a-tag v-if="diagnosis.confidence" color="arcoblue" size="small">
              {{ tl('置信度') }}: {{ Math.round((diagnosis.confidence || 0) * 100) }}%
            </a-tag>
            <a-tag v-if="diagnosis.model_name" color="gray" size="small">
              {{ diagnosis.model_name }}
            </a-tag>
          </div>
          <div class="diagnose-time">{{ formatTime(diagnosis.diagnosed_at) }}</div>
        </div>

        <div class="summary-title">{{ diagnosis.summary }}</div>
        <div class="summary-desc">{{ diagnosis.detailed_analysis }}</div>
      </a-card>

      <!-- 失败现场详情 -->
      <a-card v-if="diagnosis.failure_step_info" class="section-card" :title="tl('受阻步骤现场')">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item :label="tl('失败步骤')">
            第 {{ diagnosis.failure_step_info.step_sort }} 步
          </a-descriptions-item>
          <a-descriptions-item v-if="diagnosis.failure_step_info.page_name" :label="tl('所属页面')">
            {{ diagnosis.failure_step_info.page_name }}
          </a-descriptions-item>
          <a-descriptions-item v-if="diagnosis.failure_step_info.element_name" :label="tl('目标元素')">
            <a-tag color="blue">{{ diagnosis.failure_step_info.element_name }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item v-if="diagnosis.failure_step_info.operation_type" :label="tl('操作方式')">
            <code>{{ diagnosis.failure_step_info.operation_type }}</code>
          </a-descriptions-item>
          <a-descriptions-item v-if="diagnosis.failure_step_info.error_message" :label="tl('报错堆栈')">
            <div class="error-code-block">{{ diagnosis.failure_step_info.error_message }}</div>
          </a-descriptions-item>
        </a-descriptions>
      </a-card>

      <!-- 自愈建议卡片（高亮） -->
      <a-card
        v-if="diagnosis.healing_suggestion && diagnosis.healing_suggestion.can_self_heal"
        class="section-card healing-card"
        :title="tl('AI 元素定位自愈方案')"
      >
        <div class="healing-body">
          <div class="healing-desc">
            {{ diagnosis.healing_suggestion.explanation }}
          </div>

          <div class="locator-comparison">
            <div class="locator-row old">
              <span class="loc-label">{{ tl('当前定位') }}:</span>
              <span class="loc-type">[{{ diagnosis.healing_suggestion.current_locator_type || 'xpath' }}]</span>
              <code class="loc-val">{{ diagnosis.healing_suggestion.current_locator_value || '-' }}</code>
            </div>
            <div class="locator-row new">
              <span class="loc-label">{{ tl('推荐定位') }}:</span>
              <span class="loc-type">[{{ diagnosis.healing_suggestion.suggested_locator_type }}]</span>
              <code class="loc-val">{{ diagnosis.healing_suggestion.suggested_locator_value }}</code>
            </div>
          </div>

          <div class="healing-actions">
            <a-button
              type="primary"
              status="success"
              :loading="applyingHealing"
              @click="handleApplyHealing"
            >
              <template #icon><icon-check /></template>
              {{ tl('一键应用自愈（更新 UI 元素定位）') }}
            </a-button>
          </div>
        </div>
      </a-card>

      <!-- 缺陷报告草稿 -->
      <a-card
        v-if="diagnosis.defect_report && diagnosis.defect_report.is_real_bug"
        class="section-card bug-card"
        :title="tl('疑似业务缺陷报告建议')"
      >
        <div class="bug-content">
          <div class="bug-title">
            <a-tag color="red" size="small">{{ diagnosis.defect_report.severity || 'Medium' }}</a-tag>
            <span class="title-text">{{ diagnosis.defect_report.title }}</span>
          </div>
          <div class="bug-row">
            <span class="row-label">{{ tl('复现摘要') }}:</span>
            <span class="row-text">{{ diagnosis.defect_report.reproduction_summary }}</span>
          </div>
          <div class="bug-row">
            <span class="row-label">{{ tl('预期 vs 实际') }}:</span>
            <span class="row-text">{{ diagnosis.defect_report.expected_vs_actual }}</span>
          </div>
        </div>
      </a-card>
    </div>

    <div v-else class="empty-diagnosis">
      <a-empty :description="tl('暂无 AI 诊断记录')" />
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { Message } from '@arco-design/web-vue';
import {
  IconBug,
  IconTool,
  IconWifi,
  IconCheck,
} from '@arco-design/web-vue/es/icon';
import { useAppI18n } from '@/composables/useAppI18n';
import type { TestCase, AiDiagnosisResult } from '@/services/testcaseService';
import { applyHealingSuggestion } from '@/services/testcaseService';

interface Props {
  visible: boolean;
  testCase: TestCase | null;
  diagnosis: AiDiagnosisResult | null;
  loading?: boolean;
}

interface Emits {
  (e: 'update:visible', value: boolean): void;
  (e: 'healing-applied'): void;
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
});
const emit = defineEmits<Emits>();
const { tl } = useAppI18n();

const internalVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
});

const applyingHealing = ref(false);

const getRootCauseColor = (type?: string) => {
  switch (type) {
    case 'BUG':
      return 'red';
    case 'SCRIPT_DEFECT':
      return 'orange';
    case 'ENV_ISSUE':
      return 'cyan';
    default:
      return 'blue';
  }
};

const formatTime = (timeStr?: string) => {
  if (!timeStr) return '';
  try {
    return new Date(timeStr).toLocaleString();
  } catch {
    return timeStr;
  }
};

const handleApplyHealing = async () => {
  if (!props.testCase || !props.diagnosis?.healing_suggestion) return;
  const suggestion = props.diagnosis.healing_suggestion;

  applyingHealing.value = true;
  try {
    const res = await applyHealingSuggestion(props.testCase.project, props.testCase.id, {
      element_id: suggestion.element_id,
      element_name: suggestion.element_name,
      suggested_locator_type: suggestion.suggested_locator_type,
      suggested_locator_value: suggestion.suggested_locator_value,
    });

    if (res.success) {
      Message.success(tl('自愈更新成功！UI 元素定位已自动同步回写'));
      emit('healing-applied');
    } else {
      Message.error(res.error || tl('应用自愈建议失败'));
    }
  } catch (err: any) {
    Message.error(err.message || tl('应用自愈建议出错'));
  } finally {
    applyingHealing.value = false;
  }
};
</script>

<style scoped lang="less">
.diagnosis-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;

  .loading-text {
    font-size: 16px;
    font-weight: 500;
    margin-top: 16px;
    color: var(--color-text-1);
  }

  .loading-sub {
    font-size: 13px;
    color: var(--color-text-3);
    margin-top: 6px;
  }
}

.diagnosis-container {
  display: flex;
  flex-direction: column;
  gap: 16px;

  .summary-card {
    background: var(--color-fill-2);
    border-radius: 8px;

    .summary-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;

      .root-cause-tag-group {
        display: flex;
        gap: 8px;
        align-items: center;
      }

      .diagnose-time {
        font-size: 12px;
        color: var(--color-text-3);
      }
    }

    .summary-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--color-text-1);
      margin-bottom: 8px;
    }

    .summary-desc {
      font-size: 13px;
      line-height: 1.6;
      color: var(--color-text-2);
      white-space: pre-wrap;
    }
  }

  .section-card {
    border-radius: 8px;
    border: 1px solid var(--color-border-2);

    :deep(.arco-card-header) {
      font-weight: 600;
    }

    .error-code-block {
      max-height: 140px;
      overflow-y: auto;
      background: var(--color-fill-3);
      padding: 8px 12px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 12px;
      color: rgb(var(--danger-6));
      white-space: pre-wrap;
    }
  }

  .healing-card {
    border-color: rgb(var(--success-3));
    background: rgba(var(--success-1), 0.3);

    .healing-body {
      display: flex;
      flex-direction: column;
      gap: 12px;

      .healing-desc {
        font-size: 13px;
        color: var(--color-text-2);
        line-height: 1.5;
      }

      .locator-comparison {
        display: flex;
        flex-direction: column;
        gap: 8px;
        background: var(--color-bg-2);
        padding: 12px;
        border-radius: 6px;
        border: 1px dashed var(--color-border-3);

        .locator-row {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 13px;

          .loc-label {
            font-weight: 500;
            width: 70px;
          }

          .loc-type {
            font-weight: 600;
            color: var(--color-text-3);
          }

          .loc-val {
            background: var(--color-fill-2);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
            word-break: break-all;
          }

          &.old .loc-val {
            color: var(--color-text-3);
            text-decoration: line-through;
          }

          &.new .loc-val {
            color: rgb(var(--success-6));
            font-weight: bold;
            background: rgba(var(--success-1), 0.5);
          }
        }
      }

      .healing-actions {
        display: flex;
        justify-content: flex-end;
        margin-top: 4px;
      }
    }
  }

  .bug-card {
    border-color: rgb(var(--danger-3));
    background: rgba(var(--danger-1), 0.2);

    .bug-content {
      display: flex;
      flex-direction: column;
      gap: 8px;

      .bug-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 600;
        font-size: 14px;
        color: rgb(var(--danger-6));
      }

      .bug-row {
        display: flex;
        gap: 8px;
        font-size: 13px;

        .row-label {
          font-weight: 500;
          color: var(--color-text-3);
          width: 80px;
          flex-shrink: 0;
        }

        .row-text {
          color: var(--color-text-2);
          line-height: 1.5;
        }
      }
    }
  }
}

.empty-diagnosis {
  padding: 40px 0;
}
</style>
