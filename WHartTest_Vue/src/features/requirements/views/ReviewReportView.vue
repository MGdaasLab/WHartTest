<template>
  <div class="review-report">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <a-button type="text" @click="goBack" class="back-button">
          <template #icon><icon-arrow-left /></template>
          返回列表
        </a-button>
        <h1 class="page-title">{{ report?.document_title || '评审报告' }}</h1>
        <a-tag :color="getRatingColor(report?.overall_rating)" class="status-tag">
          {{ report?.overall_rating_display }}
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
        <a-button type="primary" @click="shareReport">
          <template #icon><icon-share-alt /></template>
          分享报告
        </a-button>
      </div>
    </div>

    <!-- 评审概览 -->
    <div class="overview-section" :class="{ 'content-loading': loading }">
      <a-row :gutter="24">
        <a-col :span="6">
          <a-card class="metric-card">
            <div class="metric-content">
              <div class="metric-value">{{ report?.completion_score || 0 }}</div>
              <div class="metric-label">完整度评分</div>
              <div class="metric-unit">/100</div>
            </div>
            <div class="metric-icon score-icon">
              <icon-trophy />
            </div>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card class="metric-card">
            <div class="metric-content">
              <div class="metric-value">{{ report?.total_issues || 0 }}</div>
              <div class="metric-label">发现问题</div>
              <div class="metric-unit">个</div>
            </div>
            <div class="metric-icon issues-icon">
              <icon-exclamation-circle />
            </div>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card class="metric-card">
            <div class="metric-content">
              <div class="metric-value">{{ report?.high_priority_issues || 0 }}</div>
              <div class="metric-label">高优先级</div>
              <div class="metric-unit">个</div>
            </div>
            <div class="metric-icon high-priority-icon">
              <icon-fire />
            </div>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card class="metric-card">
            <div class="metric-content">
              <div class="metric-value">{{ formatDate(report?.review_date) }}</div>
              <div class="metric-label">评审时间</div>
            </div>
            <div class="metric-icon date-icon">
              <icon-calendar />
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 评审总结 -->
    <div class="summary-section" :class="{ 'content-loading': loading }">
      <a-card title="评审总结" class="summary-card">
        <div class="summary-content">
          <div class="summary-text">
            {{ report?.summary }}
          </div>
          <div v-if="report?.recommendations" class="recommendations">
            <h4>改进建议</h4>
            <div class="recommendations-text">
              {{ report.recommendations }}
            </div>
          </div>
        </div>
      </a-card>
    </div>

    <!-- 问题分布 -->
    <div class="issues-distribution">
      <a-card title="问题分布" class="distribution-card">
        <div class="distribution-content">
          <div class="priority-stats">
            <div class="priority-item high">
              <div class="priority-count">{{ report?.high_priority_issues || 0 }}</div>
              <div class="priority-label">高优先级</div>
            </div>
            <div class="priority-item medium">
              <div class="priority-count">{{ report?.medium_priority_issues || 0 }}</div>
              <div class="priority-label">中优先级</div>
            </div>
            <div class="priority-item low">
              <div class="priority-count">{{ report?.low_priority_issues || 0 }}</div>
              <div class="priority-label">低优先级</div>
            </div>
          </div>
        </div>
      </a-card>
    </div>

    <!-- 模块评审结果 -->
    <div class="modules-section">
      <a-card title="模块评审结果" class="modules-card">
        <div class="modules-list">
          <div 
            v-for="moduleResult in report?.module_results" 
            :key="moduleResult.id"
            class="module-result-item"
          >
            <div class="module-header">
              <div class="module-info">
                <h3 class="module-name">{{ moduleResult.module_name }}</h3>
                <a-tag :color="getRatingColor(moduleResult.module_rating)">
                  {{ moduleResult.module_rating_display }}
                </a-tag>
                <span class="issues-count">{{ moduleResult.issues_count }} 个问题</span>
              </div>
              <div class="severity-score">
                严重度: {{ moduleResult.severity_score }}
              </div>
            </div>
            
            <div class="module-details">
              <div class="strengths" v-if="moduleResult.strengths">
                <h4><icon-check-circle /> 优点</h4>
                <p>{{ moduleResult.strengths }}</p>
              </div>
              
              <div class="weaknesses" v-if="moduleResult.weaknesses">
                <h4><icon-close-circle /> 不足</h4>
                <p>{{ moduleResult.weaknesses }}</p>
              </div>
              
              <div class="module-recommendations" v-if="moduleResult.recommendations">
                <h4><icon-bulb /> 建议</h4>
                <p>{{ moduleResult.recommendations }}</p>
              </div>
            </div>
          </div>
        </div>
      </a-card>
    </div>

    <!-- 详细问题列表 -->
    <div class="issues-section">
      <a-card class="issues-card">
        <template #title>
          <div class="issues-header">
            <span>详细问题列表 ({{ report?.issues?.length || 0 }}个)</span>
            <div class="filter-controls">
              <a-select
                v-model="issueTypeFilter"
                placeholder="问题类型"
                style="width: 120px"
                @change="filterIssues"
                allow-clear
              >
                <a-option value="">全部类型</a-option>
                <a-option value="specification">规范性</a-option>
                <a-option value="clarity">清晰度</a-option>
                <a-option value="completeness">完整性</a-option>
                <a-option value="consistency">一致性</a-option>
                <a-option value="feasibility">可行性</a-option>
              </a-select>
              <a-select
                v-model="priorityFilter"
                placeholder="优先级"
                style="width: 100px; margin-left: 8px"
                @change="filterIssues"
                allow-clear
              >
                <a-option value="">全部</a-option>
                <a-option value="high">高</a-option>
                <a-option value="medium">中</a-option>
                <a-option value="low">低</a-option>
              </a-select>
            </div>
          </div>
        </template>

        <div class="issues-list">
          <div 
            v-for="issue in filteredIssues" 
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
              <div class="issue-actions">
                <a-button 
                  v-if="!issue.is_resolved"
                  type="text" 
                  size="small"
                  @click="resolveIssue(issue)"
                >
                  标记已解决
                </a-button>
                <a-tag v-else color="green" size="small">已解决</a-tag>
              </div>
            </div>
            
            <div class="issue-content">
              <h4 class="issue-title">{{ issue.title }}</h4>
              <p class="issue-description">{{ issue.description }}</p>
              <div class="issue-suggestion">
                <strong>建议：</strong>{{ issue.suggestion }}
              </div>
              <div v-if="issue.resolution_note" class="resolution-note">
                <strong>解决说明：</strong>{{ issue.resolution_note }}
              </div>
            </div>
          </div>
        </div>

        <a-empty v-if="filteredIssues.length === 0" description="暂无问题数据" />
      </a-card>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <a-spin size="large" />
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
  IconTrophy,
  IconExclamationCircle,
  IconFire,
  IconCalendar,
  IconCheckCircle,
  IconCloseCircle,
  IconBulb
} from '@arco-design/web-vue/es/icon';
import { RequirementDocumentService, ReviewIssueService } from '../services/requirementService';
import type { ReviewReport, ReviewIssue, Rating, IssuePriority, IssueType, DocumentDetail } from '../types';
import ReportVersionSelector from '../components/ReportVersionSelector.vue';

// 路由
const route = useRoute();
const router = useRouter();

// 响应式数据
const loading = ref(false);
const report = ref<ReviewReport | null>(null);
const documentDetail = ref<DocumentDetail | null>(null);
const selectedReportId = ref<string>('');
const issueTypeFilter = ref<IssueType | ''>('');
const priorityFilter = ref<IssuePriority | ''>('');

// 计算属性
const filteredIssues = computed(() => {
  if (!report.value?.issues) return [];

  return report.value.issues.filter(issue => {
    const typeMatch = !issueTypeFilter.value || issue.issue_type === issueTypeFilter.value;
    const priorityMatch = !priorityFilter.value || issue.priority === priorityFilter.value;
    return typeMatch && priorityMatch;
  });
});

// 获取所有报告版本（按时间倒序）
const reportVersions = computed(() => {
  if (!documentDetail.value?.review_reports) return [];

  return [...documentDetail.value.review_reports].sort((a, b) =>
    new Date(b.review_date).getTime() - new Date(a.review_date).getTime()
  );
});

// 判断当前是否为最新版本
const isLatestVersion = computed(() => {
  if (!reportVersions.value.length || !selectedReportId.value) return false;
  return reportVersions.value[0]?.id === selectedReportId.value;
});

// 方法
const getRatingColor = (rating?: Rating) => {
  if (!rating) return 'gray';
  const colorMap = {
    excellent: 'green',
    good: 'blue',
    fair: 'orange',
    poor: 'red'
  };
  return colorMap[rating] || 'gray';
};

const getPriorityColor = (priority: IssuePriority) => {
  const colorMap = {
    high: 'red',
    medium: 'orange',
    low: 'blue'
  };
  return colorMap[priority] || 'gray';
};

const formatDate = (dateTime?: string) => {
  if (!dateTime) return '';
  return new Date(dateTime).toLocaleDateString();
};

// 加载文档详情和报告列表
const loadDocumentDetail = async () => {
  const documentId = route.params.id as string;
  if (!documentId) {
    Message.error('文档ID不存在');
    return;
  }

  loading.value = true;
  try {
    const response = await RequirementDocumentService.getDocumentDetail(documentId);

    if (response.status === 'success') {
      documentDetail.value = response.data;

      // 如果有历史报告，默认选择最新的
      if (documentDetail.value.review_reports && documentDetail.value.review_reports.length > 0) {
        const sortedReports = [...documentDetail.value.review_reports].sort((a, b) =>
          new Date(b.review_date).getTime() - new Date(a.review_date).getTime()
        );

        // 如果没有指定版本，选择最新版本
        if (!selectedReportId.value) {
          selectedReportId.value = sortedReports[0].id;
        }

        // 加载选中的报告
        loadSelectedReport();
      } else {
        Message.warning('该文档暂无评审报告');
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

// 加载选中的报告
const loadSelectedReport = () => {
  if (!documentDetail.value?.review_reports || !selectedReportId.value) {
    return;
  }

  // 添加短暂的加载状态，提供视觉反馈
  loading.value = true;

  setTimeout(() => {
    const selectedReport = documentDetail.value?.review_reports?.find(
      report => report.id === selectedReportId.value
    );

    if (selectedReport) {
      report.value = selectedReport;
      // 重置筛选条件
      issueTypeFilter.value = '';
      priorityFilter.value = '';
    } else {
      Message.error('找不到指定的报告版本');
    }

    loading.value = false;
  }, 200); // 短暂延迟，提供切换动画效果
};

// 版本切换处理
const handleVersionChange = (reportId: string) => {
  if (reportId === selectedReportId.value) return;

  selectedReportId.value = reportId;
  loadSelectedReport();

  // 显示切换成功提示
  const selectedReport = documentDetail.value?.review_reports?.find(r => r.id === reportId);
  if (selectedReport) {
    const isLatest = reportVersions.value[0]?.id === reportId;
    const versionLabel = isLatest ? '最新版本' : `历史版本`;
    Message.success(`已切换到${versionLabel}（${formatDate(selectedReport.review_date)}）`);
  }
};

// 返回列表
const goBack = () => {
  router.push('/requirements');
};

// 筛选问题
const filterIssues = () => {
  // 筛选逻辑已在计算属性中实现
};

// 解决问题
const resolveIssue = async (issue: ReviewIssue) => {
  try {
    const response = await ReviewIssueService.resolveIssue(issue.id, '已在新版本中修复');
    
    if (response.status === 'success') {
      Message.success('问题已标记为解决');
      // 更新本地状态
      issue.is_resolved = true;
      issue.resolution_note = '已在新版本中修复';
    } else {
      Message.error(response.message || '标记失败');
    }
  } catch (error) {
    console.error('标记问题失败:', error);
    Message.error('标记问题失败');
  }
};

// 导出报告
const exportReport = () => {
  Message.info('导出功能开发中...');
};

// 分享报告
const shareReport = () => {
  Message.info('分享功能开发中...');
};

// 监听路由参数变化
watch(
  () => route.params.id,
  (newId) => {
    if (newId) {
      selectedReportId.value = ''; // 重置选中的报告ID
      loadDocumentDetail();
    }
  },
  { immediate: true }
);

// 生命周期
onMounted(() => {
  loadDocumentDetail();
});
</script>

<style scoped>
.review-report {
  padding: 24px;
  background: transparent; /* 使用主布局的背景 */
  min-height: 100%; /* 适应父容器 */
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center; /* 改为居中对齐 */
  margin-bottom: 24px;
  padding: 24px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header-left {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 16px; /* 元素之间的间距 */
}

.version-selector {
  margin-left: auto; /* 将版本选择器推到右侧 */
  margin-right: 16px;
}

.back-button {
  flex-shrink: 0; /* 防止按钮被压缩 */
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1d2129;
  flex: 1; /* 标题占据剩余空间 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis; /* 长标题显示省略号 */
}

.status-tag {
  flex-shrink: 0; /* 防止标签被压缩 */
}

.version-indicator {
  flex-shrink: 0;
  font-size: 12px;
}

.header-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0; /* 防止操作按钮被压缩 */
}

.overview-section {
  margin-bottom: 24px;
}

.metric-card {
  position: relative;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.metric-content {
  position: relative;
  z-index: 2;
}

.metric-value {
  font-size: 32px;
  font-weight: 700;
  color: #1d2129;
  line-height: 1;
}

.metric-label {
  font-size: 14px;
  color: #86909c;
  margin-top: 4px;
}

.metric-unit {
  font-size: 14px;
  color: #86909c;
}

.metric-icon {
  position: absolute;
  top: 16px;
  right: 16px;
  font-size: 32px;
  opacity: 0.1;
}

.score-icon { color: #3370ff; }
.issues-icon { color: #ff7d00; }
.high-priority-icon { color: #f53f3f; }
.date-icon { color: #00b42a; }

.summary-section,
.issues-distribution,
.modules-section,
.issues-section {
  margin-bottom: 24px;
}

.summary-card,
.distribution-card,
.modules-card,
.issues-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.summary-content {
  line-height: 1.6;
}

.summary-text {
  font-size: 16px;
  color: #4e5969;
  margin-bottom: 16px;
}

.recommendations h4 {
  margin: 0 0 8px 0;
  color: #1d2129;
}

.recommendations-text {
  color: #4e5969;
  white-space: pre-line;
}

.distribution-content {
  padding: 16px 0;
}

.priority-stats {
  display: flex;
  justify-content: space-around;
  align-items: center;
}

.priority-item {
  text-align: center;
  padding: 16px;
  border-radius: 8px;
  min-width: 120px;
}

.priority-item.high { background: rgba(245, 63, 63, 0.1); }
.priority-item.medium { background: rgba(255, 125, 0, 0.1); }
.priority-item.low { background: rgba(51, 112, 255, 0.1); }

.priority-count {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 4px;
}

.priority-item.high .priority-count { color: #f53f3f; }
.priority-item.medium .priority-count { color: #ff7d00; }
.priority-item.low .priority-count { color: #3370ff; }

.priority-label {
  font-size: 14px;
  color: #86909c;
}

.modules-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.module-result-item {
  border: 1px solid #f2f3f5;
  border-radius: 8px;
  padding: 16px;
  background: #fafafa;
}

.module-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.module-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.module-name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
}

.issues-count {
  font-size: 12px;
  color: #86909c;
}

.severity-score {
  font-size: 14px;
  color: #4e5969;
}

.module-details {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}

.module-details h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.module-details p {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  color: #4e5969;
}

.issues-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.filter-controls {
  display: flex;
  gap: 8px;
}

.issues-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.issue-item {
  border: 1px solid #f2f3f5;
  border-radius: 8px;
  padding: 16px;
  background: white;
  transition: all 0.3s;
}

.issue-item:hover {
  border-color: #3370ff;
  box-shadow: 0 2px 8px rgba(51, 112, 255, 0.1);
}

.issue-item.resolved {
  opacity: 0.6;
  background: #f8f9fa;
}

.issue-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.issue-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.issue-location {
  font-size: 12px;
  color: #86909c;
}

.issue-content {
  line-height: 1.6;
}

.issue-title {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
}

.issue-description {
  margin: 0 0 12px 0;
  color: #4e5969;
}

.issue-suggestion {
  margin-bottom: 8px;
  padding: 8px 12px;
  background: #f0f8ff;
  border-radius: 4px;
  font-size: 14px;
}

.resolution-note {
  padding: 8px 12px;
  background: #f0f9f0;
  border-radius: 4px;
  font-size: 14px;
  color: #00b42a;
}

.loading-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 内容切换动画 */
.content-loading {
  opacity: 0.6;
  transition: opacity 0.3s ease;
  pointer-events: none;
}

/* 版本切换动画 */
.overview-section,
.summary-section,
.issues-distribution,
.modules-section,
.issues-section {
  transition: all 0.3s ease;
}

/* 版本选择器动画 */
.version-selector {
  transition: all 0.2s ease;
}

.version-selector:hover {
  transform: translateY(-1px);
}
</style>
