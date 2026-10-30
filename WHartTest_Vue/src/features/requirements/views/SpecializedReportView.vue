<template>
  <div class="specialized-report-view">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <a-button type="text" @click="goBack" class="back-button">
          <template #icon><icon-arrow-left /></template>
          返回列表
        </a-button>
        <h1 class="page-title">{{ document?.title || '评审报告' }}</h1>
        <a-tag v-if="selectedReport?.status === 'failed'" color="red" class="status-tag">
          {{ pageText.reportFailed }}
        </a-tag>
        <a-tag v-else-if="selectedReport" :color="getRatingColor(selectedReport.overall_rating)" class="status-tag">
          {{ getRatingText(selectedReport.overall_rating) }}
        </a-tag>
        <!-- 版本指示器 -->
        <a-tag
          v-if="reportVersions.length > 1 && selectedReportId"
          :color="isLatestVersion ? 'green' : 'blue'"
          class="version-indicator"
        >
          {{ isLatestVersion ? '最新版本' : '历史版本' }}
        </a-tag>
        <!-- 版本选择器 -->
        <ReportVersionSelector
          v-if="reportVersions.length > 1"
          :report-versions="reportVersions"
          :selected-report-id="selectedReportId"
          :loading="loading"
          @version-change="handleVersionChange"
          class="version-selector"
        />
      </div>
      <div class="header-actions">
        <a-button type="outline" @click="exportReport">
          <template #icon><icon-download /></template>
          导出报告
        </a-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
    </div>

    <!-- 主要内容区域 -->
    <div v-else-if="document && selectedReport" class="report-content">
      <!-- 评审失败提示：如实展示失败原因，不渲染伪造的评分报告 -->
      <a-alert
        v-if="selectedReport.status === 'failed'"
        type="error"
        class="report-failed-alert"
      >
        {{ pageText.reportFailedReason(selectedReport.error_message || '') }}
      </a-alert>
      <!-- 左侧：专项分析选择器 -->
      <div class="left-panel">
        <a-card :title="`📊 ${pageText.analysisDimensions}`" class="analysis-selector-panel">
          <!-- 总体评分卡片 -->
          <div class="overall-score-card">
            <div class="score-display">
              <div class="score-circle">
                <span class="score-number">{{ selectedReport.completion_score ?? selectedReport.overall_score ?? '—' }}</span>
                <span class="score-label">总分</span>
              </div>
              <div class="score-details">
                <h3>总体评价</h3>
                <a-tag :color="getRatingColor(selectedReport.overall_rating)" size="large">
                  {{ getRatingText(selectedReport.overall_rating) }}
                </a-tag>
                <div class="issues-summary">
                  <span class="issue-stat high">🔴 {{ selectedReport.high_priority_issues || 0 }} 高</span>
                  <span class="issue-stat medium">🟡 {{ selectedReport.medium_priority_issues || 0 }} 中</span>
                  <span class="issue-stat low">🟢 {{ selectedReport.low_priority_issues || 0 }} 低</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 专项分析列表 -->
          <div class="analysis-list">
            <div
              v-for="analysis in analysisTypes"
              :key="analysis.key"
              class="analysis-item"
              :class="{ active: selectedAnalysisType === analysis.key }"
              @click="selectAnalysis(analysis.key)"
            >
              <div class="analysis-header">
                <span class="analysis-icon">{{ analysis.icon }}</span>
                <h4 class="analysis-title">{{ analysis.title }}</h4>
              </div>
              <div class="analysis-meta">
                <div class="analysis-score">
                  <a-tag v-if="isAnalysisFailed(analysis.key)" color="red" size="small">
                    {{ pageText.analysisFailed }}
                  </a-tag>
                  <template v-else>
                    <span class="score-value">{{ getAnalysisScore(analysis.key) ?? '—' }}</span>
                    <span v-if="getAnalysisScore(analysis.key) !== null" class="score-max">/100</span>
                  </template>
                </div>
                <span class="analysis-issues">{{ getAnalysisIssuesCount(analysis.key) }} 问题</span>
              </div>
            </div>
          </div>
        </a-card>
      </div>

      <!-- 右侧：选中专项的详细信息 -->
      <div class="right-panel">
        <a-card :title="`${getCurrentAnalysis?.icon} ${getCurrentAnalysis?.title}`" class="analysis-detail-panel">
          <template v-if="currentAnalysisData">
            <!-- 该专项分析失败：如实展示失败原因，不显示伪造评分 -->
            <div v-if="isCurrentAnalysisFailed" class="analysis-failed">
              <a-alert type="error">
                {{ pageText.analysisFailedReason(currentAnalysisData.error_message || '') }}
              </a-alert>
              <div class="retry-actions">
                <a-button
                  type="primary"
                  size="small"
                  :loading="retryingDimension === selectedAnalysisType || isDocumentReviewing"
                  :disabled="retryingDimension !== null || isDocumentReviewing"
                  @click="retryCurrentDimension"
                >
                  <template #icon><icon-refresh /></template>
                  {{ pageText.retryDimension }}
                </a-button>
                <span v-if="retryingDimension === selectedAnalysisType" class="retry-hint">
                  {{ pageText.retryRunningHint }}
                </span>
                <span v-else-if="isDocumentReviewing" class="retry-hint">
                  {{ pageText.retryOccupiedHint }}
                </span>
              </div>
            </div>

            <!-- 评分和总结 -->
            <div v-else class="analysis-summary">
              <div class="summary-header">
                <div class="summary-score">
                  <div class="score-circle-large">
                    <span class="score-number">{{ currentAnalysisData.overall_score ?? '—' }}</span>
                    <span class="score-label">分</span>
                  </div>
                </div>
                <div class="summary-text">
                  <h3>分析总结</h3>
                  <p>{{ currentAnalysisData.summary }}</p>
                </div>
              </div>
            </div>

            <!-- 优势 -->
            <div v-if="currentAnalysisData.strengths && currentAnalysisData.strengths.length > 0" class="strengths-section">
              <h4>✅ {{ pageText.strengths }}</h4>
              <ul class="list-items">
                <li v-for="(strength, index) in currentAnalysisData.strengths" :key="index">{{ strength }}</li>
              </ul>
            </div>

            <!-- 改进建议 -->
            <div v-if="currentAnalysisData.recommendations && currentAnalysisData.recommendations.length > 0" class="recommendations-section">
              <h4>💡 {{ pageText.improvementSuggestions }}</h4>
              <ul class="list-items">
                <li v-for="(rec, index) in currentAnalysisData.recommendations" :key="index">{{ rec }}</li>
              </ul>
            </div>

            <!-- 问题列表 -->
            <div class="issues-section">
              <div class="issues-header">
                <h4>⚠️ {{ pageText.issuesFound(currentAnalysisIssues.length) }}</h4>
                <a-select v-model="priorityFilter" placeholder="按优先级筛选" style="width: 140px" allow-clear>
                  <a-option value="high">高优先级</a-option>
                  <a-option value="medium">中优先级</a-option>
                  <a-option value="low">低优先级</a-option>
                </a-select>
              </div>

              <div v-if="filteredIssues.length > 0" class="issues-list">
                <div
                  v-for="issue in filteredIssues"
                  :key="issue.id || issue.description"
                  class="issue-item"
                >
                  <div class="issue-header-row">
                    <a-tag :color="getPriorityColor(issue.severity || issue.priority)" size="small">
                      {{ issue.severity || issue.priority || '中' }}
                    </a-tag>
                    <span v-if="issue.category" class="issue-category">{{ issue.category }}</span>
                    <span v-if="issue.location" class="issue-location">📍 {{ issue.location }}</span>
                  </div>
                  <h5 class="issue-title">{{ issue.title || issue.description }}</h5>
                  <p v-if="issue.description && issue.title" class="issue-description">{{ issue.description }}</p>
                  <div v-if="issue.suggestion" class="issue-suggestion">
                    <strong>💡 建议：</strong>{{ issue.suggestion }}
                  </div>
                </div>
              </div>

              <div v-else class="no-issues">
                <a-empty description="该维度暂无发现问题" />
              </div>
            </div>
          </template>

          <div v-else class="no-data">
            <a-empty description="暂无分析数据" />
          </div>
        </a-card>
      </div>
    </div>

    <!-- 无数据状态 -->
    <div v-else class="empty-state">
      <a-empty description="暂无评审报告数据" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Message } from '@arco-design/web-vue';
import {
  IconArrowLeft,
  IconDownload,
  IconRefresh
} from '@arco-design/web-vue/es/icon';
import { useAppI18n } from '@/composables/useAppI18n';
import { RequirementDocumentService } from '../services/requirementService';
import ReportVersionSelector from '../components/ReportVersionSelector.vue';

// 路由
const route = useRoute();
const router = useRouter();
const { isEnglish } = useAppI18n();

const pageText = computed(() => (
  isEnglish.value
    ? {
        analysisDimensions: 'Specialized analysis dimensions',
        reportFailed: 'Review failed',
        reportFailedReason: (reason: string) => `Review failed: ${reason || 'unknown reason'}`,
        analysisFailed: 'Analysis failed',
        analysisFailedReason: (reason: string) => `This analysis failed: ${reason || 'unknown reason'}`,
        retryDimension: 'Retry this dimension',
        retryRunningHint: 'Retrying in background, this page will refresh automatically...',
        retryStarted: 'Dimension retry started',
        retryCompleted: 'Dimension retry completed, report updated',
        retryFailed: 'Dimension retry failed. Please try again later',
        retryTimeout: 'The retry is taking longer than expected. Refresh later to check the result.',
        retryOccupiedHint: 'A retry or review is already running on this document. Please wait for it to finish.',
        issuesFound: (count: number) => `Issues found (${count})`,
        strengths: 'Strengths',
        improvementSuggestions: 'Improvement suggestions',
        completeness: 'completeness analysis',
        consistency: 'consistency analysis',
        testability: 'testability analysis',
        feasibility: 'feasibility analysis',
        clarity: 'clarity analysis',
        logic: 'logic analysis',
      }
    : {
        analysisDimensions: '专项分析维度',
        reportFailed: '评审失败',
        reportFailedReason: (reason: string) => `评审失败：${reason || '未知原因'}`,
        analysisFailed: '分析失败',
        analysisFailedReason: (reason: string) => `该专项分析失败：${reason || '未知原因'}`,
        retryDimension: '重试此维度',
        retryRunningHint: '正在后台重试，完成后自动刷新...',
        retryStarted: '维度重试已启动',
        retryCompleted: '维度重试完成，报告已更新',
        retryFailed: '维度重试失败，请稍后重试',
        retryTimeout: '重试耗时较长，本页已停止自动刷新，请稍后手动刷新查看结果。',
        retryOccupiedHint: '该文档已有重试/评审正在进行，请等待完成后再操作。',
        issuesFound: (count: number) => `发现的问题 (${count}个)`,
        strengths: '优势',
        improvementSuggestions: '改进建议',
        completeness: '完整性分析',
        consistency: '一致性分析',
        testability: '可测性分析',
        feasibility: '可行性分析',
        clarity: '清晰度分析',
        logic: '逻辑分析',
      }
));

// 响应式数据
const loading = ref(false);
const document = ref<any>(null);
const selectedAnalysisType = ref<string>('completeness');
const priorityFilter = ref<string>('');
const selectedReportId = ref<string>(''); // 当前选中的报告ID

// 专项分析类型定义
const analysisTypes = computed(() => [
  { key: 'completeness', title: pageText.value.completeness, icon: '📋' },
  { key: 'consistency', title: pageText.value.consistency, icon: '🔗' },
  { key: 'testability', title: pageText.value.testability, icon: '🧪' },
  { key: 'feasibility', title: pageText.value.feasibility, icon: '⚙️' },
  { key: 'clarity', title: pageText.value.clarity, icon: '💡' },
  { key: 'logic', title: pageText.value.logic, icon: '🧠' }
]);

// 计算属性
// 所有报告版本列表(按时间倒序)
const reportVersions = computed(() => {
  if (!document.value?.review_reports) return [];
  return [...document.value.review_reports].sort((a, b) =>
    new Date(b.review_date).getTime() - new Date(a.review_date).getTime()
  );
});

// 判断当前是否为最新版本
const isLatestVersion = computed(() => {
  if (!reportVersions.value.length || !selectedReportId.value) return false;
  return reportVersions.value[0]?.id === selectedReportId.value;
});

// 当前选中的报告
const selectedReport = computed(() => {
  if (!document.value?.review_reports || !selectedReportId.value) {
    return document.value?.latest_review || null;
  }
  return document.value.review_reports.find((r: any) => r.id === selectedReportId.value) || null;
});

const getCurrentAnalysis = computed(() => {
  return analysisTypes.value.find(a => a.key === selectedAnalysisType.value);
});

const currentAnalysisData = computed(() => {
  if (!selectedReport.value?.specialized_analyses) return null;
  return selectedReport.value.specialized_analyses[`${selectedAnalysisType.value}_analysis`] || null;
});

const currentAnalysisIssues = computed(() => {
  // 直接从专项分析中获取问题列表
  if (!currentAnalysisData.value?.issues) return [];
  return currentAnalysisData.value.issues;
});

const filteredIssues = computed(() => {
  if (!priorityFilter.value) return currentAnalysisIssues.value;
  return currentAnalysisIssues.value.filter(
    (issue: any) => (issue.severity || issue.priority) === priorityFilter.value
  );
});

// 方法
const loadDocument = async () => {
  const documentId = route.params.id as string;
  if (!documentId) {
    Message.error('文档ID不存在');
    return;
  }

  loading.value = true;
  try {
    const response = await RequirementDocumentService.getDocumentDetail(documentId);

    if (response.status === 'success') {
      document.value = response.data;
      
      // 如果有历史报告，默认选择最新的
      if (document.value.review_reports && document.value.review_reports.length > 0) {
        const sortedReports = [...document.value.review_reports].sort((a: any, b: any) =>
          new Date(b.review_date).getTime() - new Date(a.review_date).getTime()
        );
        // 如果没有指定版本，选择最新版本
        if (!selectedReportId.value) {
          selectedReportId.value = sortedReports[0].id;
        }
      }
      
      console.log('Document loaded:', document.value);  // 调试日志
      console.log('Selected report:', selectedReport.value);  // 调试日志
    } else {
      Message.error(response.message || '加载文档详情失败');
    }
  } catch (error) {
    console.error('加载文档详情失败:', error);
    Message.error('加载文档详情失败');
  } finally {
    loading.value = false;
  }
};

const selectAnalysis = (type: string) => {
  selectedAnalysisType.value = type;
  priorityFilter.value = ''; // 重置筛选
};

// 返回该维度的真实评分；未产出有效评分为 null（展示为未评估），不再用 0 兜底
// 单维度重试：派发后轮询文档状态，评审完成后自动刷新报告
const retryingDimension = ref<string | null>(null);
// 文档级占位状态：后台已有重试/评审在跑时，禁用重试按钮并提示
const isDocumentReviewing = computed(() => document.value?.status === 'reviewing');
let retryPollTimer: ReturnType<typeof setTimeout> | null = null;

const clearRetryPoll = () => {
  if (retryPollTimer !== null) {
    clearTimeout(retryPollTimer);
    retryPollTimer = null;
  }
};

const pollRetryStatus = (documentId: string, attempts: number) => {
  if (attempts > 200) {
    // 200 次 x 3 秒 = 10 分钟安全上限
    retryingDimension.value = null;
    clearRetryPoll();
    Message.warning(pageText.value.retryTimeout);
    return;
  }
  retryPollTimer = setTimeout(async () => {
    try {
      const response = await RequirementDocumentService.getDocumentDetail(documentId);
      if (response.status === 'success') {
        const doc = response.data;
        if (doc.status === 'review_completed' || doc.status === 'failed') {
          retryingDimension.value = null;
          clearRetryPoll();
          document.value = doc;
          if (doc.status === 'review_completed') {
            Message.success(pageText.value.retryCompleted);
          } else {
            Message.error(pageText.value.retryFailed);
          }
          return;
        }
      }
    } catch (error) {
      console.error('轮询维度重试状态失败:', error);
    }
    pollRetryStatus(documentId, attempts + 1);
  }, 3000);
};

const retryCurrentDimension = async () => {
  if (!document.value || !selectedAnalysisType.value) return;
  const documentId = String(document.value.id);
  try {
    const response = await RequirementDocumentService.retryAnalysis(
      documentId,
      selectedAnalysisType.value
    );
    if (response.status === 'success') {
      retryingDimension.value = selectedAnalysisType.value;
      Message.info(pageText.value.retryStarted);
      pollRetryStatus(documentId, 0);
    } else {
      Message.error(response.message || pageText.value.retryFailed);
    }
  } catch (error) {
    console.error('维度重试启动失败:', error);
    Message.error(pageText.value.retryFailed);
  }
};

onBeforeUnmount(() => {
  clearRetryPoll();
});

const getAnalysisScore = (analysisKey: string): number | null => {
  const value = selectedReport.value?.scores?.[analysisKey];
  return typeof value === 'number' ? value : null;
};

const getAnalysisData = (analysisKey: string): any => {
  return selectedReport.value?.specialized_analyses?.[`${analysisKey}_analysis`] || null;
};

const isAnalysisFailed = (analysisKey: string): boolean => {
  const analysis = getAnalysisData(analysisKey);
  return analysis?.status === 'failed';
};

const isCurrentAnalysisFailed = computed(() => {
  return currentAnalysisData.value?.status === 'failed';
});

const getAnalysisIssuesCount = (analysisKey: string) => {
  if (!selectedReport.value?.specialized_analyses) return 0;
  const analysis = selectedReport.value.specialized_analyses[`${analysisKey}_analysis`];
  return analysis?.issues?.length || 0;
};

const getRatingColor = (rating: string) => {
  const colorMap: Record<string, string> = {
    'excellent': 'green',
    'good': 'blue',
    'average': 'orange',
    'needs_improvement': 'red',
    'poor': 'red'
  };
  return colorMap[rating] || 'gray';
};

const getRatingText = (rating: string) => {
  const textMap: Record<string, string> = {
    'excellent': '优秀',
    'good': '良好',
    'average': '中等',
    'needs_improvement': '需改进',
    'poor': '较差'
  };
  return textMap[rating] || '未知';
};

const getPriorityColor = (priority: string) => {
  const colorMap: Record<string, string> = {
    'high': 'red',
    'medium': 'orange',
    'low': 'blue'
  };
  return colorMap[priority] || 'gray';
};

const goBack = () => {
  router.push('/requirements');
};

// 处理版本切换
const handleVersionChange = (reportId: string) => {
  selectedReportId.value = reportId;
  // 切换版本后重置分析类型选择
  selectedAnalysisType.value = 'completeness';
  priorityFilter.value = '';
};

const exportReport = () => {
  Message.info('导出功能开发中...');
};

// 生命周期
onMounted(() => {
  loadDocument();
});
</script>

<style scoped>
.specialized-report-view {
  padding: 24px;
  background: transparent;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
}

/* 页面头部 */
.page-header {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 24px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  gap: 24px;
}

.header-left {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
  overflow: hidden;
}

.back-button {
  flex-shrink: 0;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1d2129;
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-tag {
  flex-shrink: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}

/* 加载状态 */
.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
}

/* 主要内容区域 */
.report-content {
  display: flex;
  gap: 24px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* 左侧面板 */
.left-panel {
  flex: 0 0 420px;
  height: 100%;
  overflow: hidden;
}

.analysis-selector-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.analysis-selector-panel :deep(.arco-card-body) {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

/* 总体评分卡片 */
.overall-score-card {
  margin-bottom: 20px;
  padding: 20px;
  background: linear-gradient(135deg, #00a0e9 0%, #0090d1 100%);
  border-radius: 12px;
  color: white;
}

.score-display {
  display: flex;
  align-items: center;
  gap: 20px;
}

.score-circle {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
}

.score-number {
  font-size: 28px;
  font-weight: bold;
  line-height: 1;
}

.score-label {
  font-size: 12px;
  margin-top: 4px;
  opacity: 0.9;
}

.score-details h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
}

.issues-summary {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.issue-stat {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.2);
}

/* 专项分析列表 */
.analysis-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.analysis-item {
  padding: 16px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: white;
}

.analysis-item:hover {
  background: #f7f8fa;
  border-color: #00a0e9;
}

.analysis-item.active {
  background: #e8f4ff;
  border-color: #00a0e9;
  box-shadow: 0 2px 8px rgba(0, 160, 233, 0.15);
}

.analysis-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.analysis-icon {
  font-size: 20px;
}

.analysis-title {
  margin: 0;
  color: #1d2129;
  font-size: 14px;
  font-weight: 600;
}

.analysis-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-failed-alert {
  margin-bottom: 16px;
}

.analysis-failed {
  margin-bottom: 16px;
}

.retry-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}

.retry-hint {
  font-size: 12px;
  color: #86909c;
}

.analysis-score {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.score-value {
  font-size: 20px;
  font-weight: bold;
  color: #00a0e9;
}

.score-max {
  font-size: 12px;
  color: #86909c;
}

.analysis-issues {
  color: #86909c;
  font-size: 12px;
}

/* 右侧面板 */
.right-panel {
  flex: 1;
  height: 100%;
  overflow: hidden;
}

.analysis-detail-panel {
  height: 100%;
}

.analysis-detail-panel :deep(.arco-card-body) {
  height: calc(100% - 60px);
  overflow-y: auto;
}

/* 分析总结 */
.analysis-summary {
  margin-bottom: 24px;
  padding: 20px;
  background: #f7f8fa;
  border-radius: 8px;
}

.summary-header {
  display: flex;
  gap: 24px;
  align-items: center;
}

.summary-score .score-circle-large {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: linear-gradient(135deg, #00a0e9, #0090d1);
  color: white;
}

.summary-score .score-number {
  font-size: 32px;
  font-weight: bold;
}

.summary-score .score-label {
  font-size: 12px;
  margin-top: 4px;
}

.summary-text {
  flex: 1;
}

.summary-text h3 {
  margin: 0 0 12px 0;
  color: #1d2129;
  font-size: 16px;
  font-weight: 600;
}

.summary-text p {
  margin: 0;
  color: #4e5969;
  line-height: 1.6;
}

/* 优势和建议部分 */
.strengths-section,
.recommendations-section {
  margin-bottom: 24px;
  padding: 16px;
  border-radius: 8px;
}

.strengths-section {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.recommendations-section {
  background: #e6f7ff;
  border: 1px solid #91d5ff;
}

.strengths-section h4,
.recommendations-section h4 {
  margin: 0 0 12px 0;
  color: #1d2129;
  font-size: 14px;
  font-weight: 600;
}

.list-items {
  margin: 0;
  padding-left: 20px;
  color: #4e5969;
  line-height: 1.8;
}

.list-items li {
  margin-bottom: 8px;
}

/* 问题部分 */
.issues-section {
  margin-top: 24px;
  margin-bottom: 12px;
}

.issues-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.issues-header h4 {
  margin: 0;
  color: #1d2129;
  font-size: 16px;
  font-weight: 600;
}

.issues-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.issue-item {
  padding: 16px;
  background: white;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  transition: all 0.2s;
}

.issue-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.issue-header-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.issue-category {
  padding: 2px 8px;
  background: #f2f3f5;
  border-radius: 4px;
  font-size: 12px;
  color: #4e5969;
}

.issue-location {
  color: #86909c;
  font-size: 12px;
}

.issue-title {
  margin: 0 0 8px 0;
  color: #1d2129;
  font-size: 14px;
  font-weight: 600;
}

.issue-description {
  margin: 0 0 12px 0;
  color: #4e5969;
  line-height: 1.6;
  font-size: 13px;
}

.issue-suggestion {
  padding: 12px;
  background: #e8f4ff;
  border-left: 3px solid #00a0e9;
  border-radius: 4px;
  font-size: 13px;
  color: #4e5969;
  line-height: 1.6;
}

.issue-suggestion strong {
  color: #00a0e9;
}

.no-issues,
.no-data {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 300px;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
}
</style>
