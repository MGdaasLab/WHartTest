<template>
  <div class="report-detail">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <a-button type="text" @click="goBack" class="back-button">
          <template #icon><icon-arrow-left /></template>
          返回列表
        </a-button>
        <h1 class="page-title">{{ document?.title || '评审报告' }}</h1>
        <a-tag v-if="selectedReport" :color="getRatingColor(selectedReport.overall_rating)" class="status-tag">
          {{ selectedReport.overall_rating_display }}
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
        <a-button type="text" @click="viewFullReport">
          <template #icon><icon-file /></template>
          完整报告
        </a-button>
        <a-button type="outline" @click="exportReport">
          <template #icon><icon-download /></template>
          导出报告
        </a-button>
        <a-button type="primary" @click="shareReport">
          <template #icon><icon-share-alt /></template>
          分享报告
        </a-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <a-spin size="large" />
    </div>

    <!-- 主要内容区域 -->
    <div v-else-if="document && selectedReport" class="report-content">
      <!-- 左侧：模块详情 -->
      <div class="left-panel">
        <a-card title="📄 模块内容" class="modules-panel">
          <div class="modules-list">
            <div 
              v-for="(module, index) in document.modules" 
              :key="module.id"
              class="module-item"
              :class="{ active: selectedModuleId === module.id }"
              @click="selectModule(module.id)"
            >
              <div class="module-header">
                <span class="module-index">{{ index + 1 }}</span>
                <h4 class="module-title">{{ module.title }}</h4>
                <div class="module-meta">
                  <span class="module-issues">{{ getModuleIssuesCount(module.id) }} 问题</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 选中模块的详细内容 -->
          <div v-if="selectedModule" class="module-detail">
            <div class="module-detail-header">
              <h3>{{ selectedModule.title }}</h3>
              <a-tag v-if="selectedModuleResult" :color="getRatingColor(selectedModuleResult.module_rating)">
                {{ selectedModuleResult.module_rating_display }}
              </a-tag>
            </div>
            <div class="module-content">
              <h5>📝 模块内容</h5>
              <div class="content-text">{{ selectedModule.content }}</div>
            </div>
          </div>
        </a-card>
      </div>

      <!-- 右侧：模块问题 -->
      <div class="right-panel">
        <a-card :title="selectedModule ? `⚠️ ${selectedModule.title} - 相关问题` : '⚠️ 模块问题'" class="issues-panel">
          <!-- 选中模块的评审结果 -->
          <div v-if="selectedModuleResult" class="module-review-result">
            <div class="module-rating">
              <h4>📊 模块评级</h4>
              <div class="rating-display">
                <a-tag :color="getRatingColor(selectedModuleResult.module_rating)" size="large">
                  {{ selectedModuleResult.module_rating_display }}
                </a-tag>
                <span class="issues-count">{{ selectedModuleIssues.length }} 个问题</span>
              </div>
            </div>

            <!-- 移除原始分析结果，下面已有美化显示 -->

            <!-- 优势和不足 -->
            <div class="strengths-weaknesses">
              <div v-if="selectedModuleResult.strengths" class="strengths">
                <h5>✅ 优势</h5>
                <p>{{ selectedModuleResult.strengths }}</p>
              </div>
              <div v-if="selectedModuleResult.weaknesses" class="weaknesses">
                <h5>⚠️ 不足</h5>
                <p>{{ selectedModuleResult.weaknesses }}</p>
              </div>
              <div v-if="selectedModuleResult.recommendations" class="module-recommendations">
                <h5>💡 改进建议</h5>
                <p>{{ selectedModuleResult.recommendations }}</p>
              </div>
            </div>
          </div>

          <!-- 模块相关问题 -->
          <div class="module-issues-section">
            <div class="issues-header">
              <h4>⚠️ 相关问题 ({{ selectedModuleIssues.length }}个)</h4>
              <div class="issues-filters">
                <a-select v-model="priorityFilter" placeholder="优先级" style="width: 120px" allow-clear>
                  <a-option value="high">高优先级</a-option>
                  <a-option value="medium">中优先级</a-option>
                  <a-option value="low">低优先级</a-option>
                </a-select>
                <a-select v-model="typeFilter" placeholder="问题类型" style="width: 120px" allow-clear>
                  <a-option value="specification">规范性</a-option>
                  <a-option value="clarity">清晰度</a-option>
                  <a-option value="completeness">完整性</a-option>
                  <a-option value="consistency">一致性</a-option>
                  <a-option value="feasibility">可行性</a-option>
                </a-select>
              </div>
            </div>

            <!-- 问题列表 -->
            <div v-if="filteredModuleIssues.length > 0" class="issues-list">
              <div
                v-for="issue in filteredModuleIssues"
                :key="issue.id"
                class="issue-item"
                :class="{ resolved: issue.is_resolved }"
              >
                <div class="issue-header">
                  <div class="issue-meta">
                    <a-tag :color="getPriorityColor(issue.priority)" size="small">
                      {{ issue.priority_display }}
                    </a-tag>
                    <a-tag color="blue" size="small">
                      {{ issue.issue_type_display }}
                    </a-tag>
                    <span class="issue-location">{{ issue.location }}</span>
                  </div>
                  <a-tag v-if="issue.is_resolved" color="green" size="small">已解决</a-tag>
                </div>
                <h6 class="issue-title">{{ issue.title }}</h6>
                <p class="issue-description">{{ issue.description }}</p>
                <div v-if="issue.suggestion" class="issue-suggestion">
                  <strong>建议：</strong>{{ issue.suggestion }}
                </div>
              </div>
            </div>

            <!-- 无问题状态 -->
            <div v-else class="no-issues">
              <a-empty description="该模块暂无发现问题" />
            </div>
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
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Message } from '@arco-design/web-vue';
import {
  IconArrowLeft,
  IconDownload,
  IconShareAlt,
  IconFile
} from '@arco-design/web-vue/es/icon';
import { RequirementDocumentService } from '../services/requirementService';
import type { DocumentDetail, DocumentModule, ModuleReviewResult, ReviewIssue, ReviewReport } from '../types';
import ReportVersionSelector from '../components/ReportVersionSelector.vue';

// 路由
const route = useRoute();
const router = useRouter();

// 响应式数据
const loading = ref(false);
const document = ref<DocumentDetail | null>(null);
const selectedReportId = ref<string>('');
const selectedModuleId = ref<string | null>(null);
const priorityFilter = ref<string>('');
const typeFilter = ref<string>('');

// 计算属性
// 获取所有报告版本（按时间倒序）
const reportVersions = computed(() => {
  if (!document.value?.review_reports) return [];

  return [...document.value.review_reports].sort((a, b) =>
    new Date(b.review_date).getTime() - new Date(a.review_date).getTime()
  );
});

// 当前选中的报告
const selectedReport = computed(() => {
  if (!selectedReportId.value || !document.value?.review_reports) return null;
  return document.value.review_reports.find(r => r.id === selectedReportId.value) || null;
});

// 判断当前是否为最新版本
const isLatestVersion = computed(() => {
  if (!reportVersions.value.length || !selectedReportId.value) return false;
  return reportVersions.value[0]?.id === selectedReportId.value;
});

const selectedModule = computed(() => {
  if (!selectedModuleId.value || !document.value?.modules) return null;
  return document.value.modules.find(m => m.id === selectedModuleId.value) || null;
});

const selectedModuleResult = computed(() => {
  if (!selectedModuleId.value || !selectedReport.value?.module_results) return null;
  return selectedReport.value.module_results.find(r => r.module === selectedModuleId.value) || null;
});

// 选中模块的问题列表
const selectedModuleIssues = computed(() => {
  if (!selectedModuleId.value || !selectedReport.value?.issues) return [];
  return selectedReport.value.issues.filter(issue => issue.module === selectedModuleId.value);
});

// 筛选后的模块问题
const filteredModuleIssues = computed(() => {
  return selectedModuleIssues.value.filter(issue => {
    const priorityMatch = !priorityFilter.value || issue.priority === priorityFilter.value;
    const typeMatch = !typeFilter.value || issue.issue_type === typeFilter.value;
    return priorityMatch && typeMatch;
  });
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
        const sortedReports = [...document.value.review_reports].sort((a, b) =>
          new Date(b.review_date).getTime() - new Date(a.review_date).getTime()
        );

        // 如果没有指定版本，选择最新版本
        if (!selectedReportId.value) {
          selectedReportId.value = sortedReports[0].id;
        }
      }

      // 默认选择第一个模块
      if (document.value.modules && document.value.modules.length > 0) {
        selectedModuleId.value = document.value.modules[0].id;
      }
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

const selectModule = (moduleId: string) => {
  selectedModuleId.value = moduleId;
};

// 版本切换处理
const handleVersionChange = (reportId: string) => {
  if (reportId === selectedReportId.value) return;

  selectedReportId.value = reportId;

  // 显示切换成功提示
  const selectedReportData = document.value?.review_reports?.find(r => r.id === reportId);
  if (selectedReportData) {
    const isLatest = reportVersions.value[0]?.id === reportId;
    const versionLabel = isLatest ? '最新版本' : `历史版本`;
    Message.success(`已切换到${versionLabel}（${formatDateTime(selectedReportData.review_date)}）`);
  }
};

const getModuleIssuesCount = (moduleId: string) => {
  if (!selectedReport.value?.issues) return 0;
  return selectedReport.value.issues.filter(issue => issue.module === moduleId).length;
};

const getRatingColor = (rating: string) => {
  const colorMap: Record<string, string> = {
    'excellent': 'green',
    'good': 'blue',
    'fair': 'orange',
    'poor': 'red'
  };
  return colorMap[rating] || 'gray';
};

const getPriorityColor = (priority: string) => {
  const colorMap: Record<string, string> = {
    'high': 'red',
    'medium': 'orange',
    'low': 'blue'
  };
  return colorMap[priority] || 'gray';
};

const formatDateTime = (dateTime?: string) => {
  if (!dateTime) return '';
  return new Date(dateTime).toLocaleString('zh-CN');
};

const goBack = () => {
  router.push('/requirements');
};

const viewFullReport = () => {
  if (document.value?.id) {
    router.push(`/requirements/${document.value.id}`);
  }
};

const exportReport = () => {
  Message.info('导出功能开发中...');
};

const shareReport = () => {
  Message.info('分享功能开发中...');
};

// 监听路由参数变化
watch(
  () => route.params.id,
  (newId) => {
    if (newId) {
      selectedReportId.value = ''; // 重置选中的报告ID
      loadDocument();
    }
  },
  { immediate: true }
);

// 生命周期
onMounted(() => {
  loadDocument();
});
</script>

<style scoped>
.report-detail {
  padding: 24px;
  background: transparent;
  height: calc(100vh - 100px);
  overflow: hidden;
  box-sizing: border-box;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e6eb;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.version-selector {
  margin-left: auto; /* 将版本选择器推到右侧 */
  margin-right: 20px;
  flex-shrink: 0; /* 防止被压缩 */
}

.version-indicator {
  flex-shrink: 0;
  font-size: 12px;
}

.back-button {
  color: #86909c;
}

.page-title {
  margin: 0;
  color: #1d2129;
  font-size: 24px;
  font-weight: 600;
}

.status-tag {
  font-size: 12px;
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
  height: calc(100% - 60px);
  overflow: hidden;
}

/* 左侧面板 */
.left-panel {
  flex: 0 0 45%;
  min-width: 400px;
  max-width: 600px;
  height: 100%;
  overflow: hidden;
}

.modules-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.modules-panel :deep(.arco-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.modules-panel :deep(.arco-card-body) {
  flex: 1;
  overflow-y: auto;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.modules-panel :deep(.arco-card-body)::-webkit-scrollbar {
  display: none; /* Chrome, Safari and Opera */
}

.modules-list {
  margin-bottom: 16px;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
}

.module-item {
  padding: 12px 16px;
  border-bottom: 1px solid #e5e6eb;
  cursor: pointer;
  transition: all 0.2s;
}

.module-item:last-child {
  border-bottom: none;
}

.module-item:hover {
  background: #f7f8fa;
}

.module-item.active {
  background: #e8f4ff;
  border-color: #165dff;
}

.module-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.module-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: #165dff;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: bold;
}

.module-title {
  flex: 1;
  margin: 0;
  color: #1d2129;
  font-size: 14px;
  font-weight: 500;
}

.module-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.module-issues {
  color: #86909c;
  font-size: 12px;
}

/* 模块详情 */
.module-detail {
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  padding: 16px;
  background: #fafbfc;
}

.module-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e6eb;
}

.module-detail-header h3 {
  margin: 0;
  color: #1d2129;
  font-size: 16px;
  font-weight: 600;
}

.module-content {
  margin-bottom: 20px;
}

.module-content h5 {
  margin: 0 0 8px 0;
  color: #1d2129;
  font-size: 14px;
  font-weight: 600;
}

.content-text {
  color: #4e5969;
  line-height: 1.6;
  white-space: pre-wrap;
  background: white;
  padding: 12px;
  border-radius: 4px;
  border: 1px solid #e5e6eb;
}

/* 右侧面板 */
.right-panel {
  flex: 1;
  min-width: 500px;
  height: 100%;
  overflow: hidden;
}

.issues-panel {
  height: 100%;
}

.issues-panel :deep(.arco-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.issues-panel :deep(.arco-card-body) {
  height: calc(100% - 60px);
  overflow-y: auto;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.issues-panel :deep(.arco-card-body)::-webkit-scrollbar {
  display: none; /* Chrome, Safari and Opera */
}

/* 模块评审结果 */
.module-review-result {
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid #e5e6eb;
}

.module-rating {
  margin-bottom: 16px;
}

.module-rating h4 {
  margin: 0 0 8px 0;
  color: #1d2129;
  font-size: 14px;
  font-weight: 600;
}

.rating-display {
  display: flex;
  align-items: center;
  gap: 12px;
}

.issues-count {
  color: #86909c;
  font-size: 13px;
}

/* 移除了 module-analysis-summary 样式，因为不再显示原始分析结果 */

.strengths-weaknesses {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.strengths,
.weaknesses,
.module-recommendations {
  padding: 12px;
  border-radius: 6px;
}

.strengths {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.weaknesses {
  background: #fff2e8;
  border: 1px solid #ffbb96;
}

.module-recommendations {
  background: #e6f7ff;
  border: 1px solid #91d5ff;
}

.strengths h5,
.weaknesses h5,
.module-recommendations h5 {
  margin: 0 0 6px 0;
  color: #1d2129;
  font-size: 13px;
  font-weight: 600;
}

.strengths p,
.weaknesses p,
.module-recommendations p {
  margin: 0;
  color: #4e5969;
  line-height: 1.5;
  font-size: 12px;
}

/* 模块问题部分 */
.module-issues-section {
  margin-top: 20px;
}

.no-issues {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
  color: #86909c;
}

/* 报告概览 */
.report-overview {
  margin-bottom: 24px;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e6eb;
}

.report-meta h2 {
  margin: 0 0 8px 0;
  color: #1d2129;
  font-size: 18px;
  font-weight: 600;
}

.report-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.report-date,
.reviewer {
  color: #86909c;
  font-size: 13px;
}

.score-circle {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 70px;
  height: 70px;
  border-radius: 50%;
  background: linear-gradient(135deg, #165dff, #722ed1);
  color: white;
}

.score-number {
  font-size: 20px;
  font-weight: bold;
  line-height: 1;
}

.score-label {
  font-size: 11px;
  margin-top: 2px;
}

/* 问题统计 */
.issues-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px;
  border-radius: 6px;
  min-width: 70px;
}

.stat-item.high {
  background: #ffece8;
  border: 1px solid #f53f3f;
}

.stat-item.medium {
  background: #fff7e8;
  border: 1px solid #ff7d00;
}

.stat-item.low {
  background: #e8f7ff;
  border: 1px solid #165dff;
}

.stat-item.total {
  background: #f2f3f5;
  border: 1px solid #86909c;
}

.stat-number {
  font-size: 18px;
  font-weight: bold;
  line-height: 1;
}

.stat-label {
  font-size: 11px;
  color: #86909c;
  margin-top: 4px;
}

/* 评审摘要和建议 */
.report-summary,
.report-recommendations {
  margin-bottom: 20px;
}

.report-summary h4,
.report-recommendations h4 {
  margin: 0 0 8px 0;
  color: #1d2129;
  font-size: 14px;
  font-weight: 600;
}

.report-summary p {
  margin: 0;
  color: #4e5969;
  line-height: 1.6;
  font-size: 13px;
}

.recommendations-content {
  color: #4e5969;
  line-height: 1.6;
  white-space: pre-wrap;
  font-size: 13px;
}

/* 问题部分 */
.issues-section {
  margin-top: 24px;
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
  font-size: 14px;
  font-weight: 600;
}

.issues-filters {
  display: flex;
  gap: 8px;
}

.issues-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.issue-item {
  padding: 12px;
  margin-bottom: 8px;
  border: 1px solid #e5e6eb;
  border-radius: 6px;
  background: white;
}

.issue-item.resolved {
  background: #f6ffed;
  border-color: #b7eb8f;
}

.issue-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.issue-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.issue-location {
  color: #86909c;
  font-size: 11px;
}

.issue-title {
  margin: 0 0 6px 0;
  color: #1d2129;
  font-size: 13px;
  font-weight: 600;
}

.issue-description {
  margin: 0 0 6px 0;
  color: #4e5969;
  font-size: 12px;
  line-height: 1.4;
}

.issue-suggestion {
  color: #4e5969;
  font-size: 12px;
  line-height: 1.4;
  background: #f7f8fa;
  padding: 6px;
  border-radius: 4px;
}

/* 空状态 */
.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .report-content {
    flex-direction: column;
    height: auto;
  }

  .left-panel,
  .right-panel {
    flex: none;
    min-width: auto;
    max-width: none;
  }

  .left-panel {
    height: 500px;
  }

  .modules-panel,
  .issues-panel {
    height: 500px;
  }
}

@media (max-width: 768px) {
  .report-detail {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .report-content {
    gap: 16px;
  }

  .left-panel {
    height: 400px;
  }

  .modules-panel,
  .issues-panel {
    height: 400px;
  }
}
</style>
