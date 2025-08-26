<template>
  <div class="report-version-selector">
    <a-select
      :model-value="selectedReportId"
      @update:model-value="handleVersionChange"
      placeholder="选择报告版本"
      :loading="loading"
      :disabled="!reportVersions.length"
      size="medium"
      style="min-width: 280px;"
    >
      <a-option
        v-for="(report, index) in reportVersions"
        :key="report.id"
        :value="report.id"
        :label="getVersionLabel(report, index)"
      >
        <div class="version-option">
          <div class="version-header">
            <span class="version-label">{{ getVersionLabel(report, index) }}</span>
            <a-tag 
              v-if="index === 0" 
              color="green" 
              size="small"
              class="latest-tag"
            >
              最新
            </a-tag>
          </div>
          <div class="version-meta">
            <span class="version-date">{{ formatDateTime(report.review_date) }}</span>
            <span class="version-score">{{ report.completion_score }}分</span>
            <a-tag
              :color="getRatingColor(report.overall_rating)"
              size="small"
            >
              {{ report.overall_rating_display }}
            </a-tag>
          </div>
          <div class="version-stats">
            <span class="issues-count">{{ report.total_issues }}个问题</span>
            <span v-if="report.high_priority_issues > 0" class="high-priority">
              高优先级{{ report.high_priority_issues }}个
            </span>
          </div>
        </div>
      </a-option>
    </a-select>
  </div>
</template>

<script setup lang="ts">

import type { ReviewReport, Rating } from '../types';

// Props
interface Props {
  reportVersions: ReviewReport[];
  selectedReportId?: string;
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  reportVersions: () => [],
  selectedReportId: '',
  loading: false
});

// Emits
const emit = defineEmits<{
  'version-change': [reportId: string];
}>();

// 方法
const handleVersionChange = (reportId: string) => {
  emit('version-change', reportId);
};

const getVersionLabel = (report: ReviewReport, index: number) => {
  if (index === 0) {
    return '最新版本';
  }
  return `版本 ${props.reportVersions.length - index}`;
};

const formatDateTime = (dateTime: string) => {
  const date = new Date(dateTime);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
};

const getRatingColor = (rating: Rating) => {
  const colorMap = {
    excellent: 'green',
    good: 'blue',
    fair: 'orange',
    poor: 'red'
  };
  return colorMap[rating] || 'gray';
};
</script>

<style scoped>
.report-version-selector {
  display: flex;
  align-items: center;
}

.version-option {
  padding: 8px 12px;
  width: 100%;
  max-width: 280px;
  box-sizing: border-box;
  overflow: hidden;
}

.version-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  flex-wrap: nowrap;
}

.version-label {
  font-weight: 600;
  color: #1d2129;
  font-size: 14px;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.latest-tag {
  margin-left: 8px;
}

.version-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  font-size: 12px;
  flex-wrap: nowrap;
  overflow: hidden;
}

.version-date {
  color: #86909c;
  white-space: nowrap;
  flex-shrink: 0;
}

.version-score {
  color: #3370ff;
  font-weight: 600;
  flex-shrink: 0;
}

.version-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  flex-wrap: wrap;
}

.issues-count {
  color: #86909c;
}

.high-priority {
  color: #f53f3f;
  font-weight: 500;
}

/* 下拉框样式优化 */
:deep(.arco-select-dropdown) {
  max-height: 500px;
  width: 280px !important; /* 强制与选择框宽度一致 */
}

:deep(.arco-select-option) {
  padding: 8px 12px;
  width: 100% !important;
  box-sizing: border-box;
}

:deep(.arco-select-option:hover) {
  background-color: #f2f3f5;
}

:deep(.arco-select-option-content) {
  width: 100% !important;
  overflow: hidden;
}
</style>
