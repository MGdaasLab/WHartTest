<template>
  <a-modal
    v-model:visible="modalVisible"
    title="测试执行报告"
    :width="1200"
    :footer="false"
    :mask-closable="false"
    unmount-on-close
    @cancel="handleClose"
  >
    <div v-if="loading" class="loading-state">
      <a-spin size="large" tip="正在加载报告..." />
    </div>
    <div v-else-if="error" class="error-state">
      <a-result status="error" :title="error" />
    </div>
    <div v-else-if="report" class="report-container">
      <!-- 报告头部 -->
      <div class="report-header">
        <h2>{{ report.suite.name }}</h2>
        <div class="header-meta">
          <a-tag :color="getStatusColor(report.status)">{{ getStatusText(report.status) }}</a-tag>
          <span class="meta-item">
            <icon-calendar /> {{ formatDateTime(report.started_at) }}
          </span>
          <span class="meta-item">
            <icon-clock-circle /> {{ formatDuration(report.duration) }}
          </span>
        </div>
      </div>

      <!-- 统计概览 -->
      <div class="statistics-grid">
        <a-card :bordered="false" class="stat-card total">
          <div class="stat-title-wrapper">
            <span class="stat-main-title">总任务数</span>
            <div class="stat-subtitle">
              <a-tag size="small" color="blue">{{ report.results?.length || 0 }} 用例</a-tag>
            </div>
          </div>
        </a-card>
        <a-card :bordered="false" class="stat-card passed">
          <a-statistic title="通过" :value="report.statistics.passed" />
        </a-card>
        <a-card :bordered="false" class="stat-card failed">
          <a-statistic title="失败" :value="report.statistics.failed" />
        </a-card>
        <a-card :bordered="false" class="stat-card error">
          <a-statistic title="错误" :value="report.statistics.error" />
        </a-card>
        <a-card :bordered="false" class="stat-card pass-rate">
          <a-statistic title="通过率" :value="report.statistics.pass_rate" :precision="1" suffix="%" />
        </a-card>
      </div>

      <!-- 结果列表 -->
      <div class="results-section">
          <a-table
            v-if="report.results && report.results.length > 0"
            :data="report.results"
            :columns="resultColumns"
            row-key="testcase_id"
            :pagination="false"
            stripe
            class="results-table"
          >
            <template #status="{ record }">
              <a-tag :color="getStatusColor(record.status)">
                {{ getStatusText(record.status) }}
              </a-tag>
            </template>
            <template #duration="{ record }">
              <span>{{ formatDuration(record.execution_time) }}</span>
            </template>
            <template #actions="{ record }">
              <a-button type="text" size="small" @click="viewResultDetail(record)">
                查看详情
              </a-button>
            </template>
          </a-table>
          <a-empty v-else description="暂无用例执行结果" />
      </div>
    </div>
  </a-modal>

  <!-- 用例结果详情抽屉 -->
  <a-drawer
    :width="900"
    :visible="detailDrawerVisible"
    @ok="detailDrawerVisible = false"
    @cancel="detailDrawerVisible = false"
    unmount-on-close
  >
    <template #title>
      用例执行详情
    </template>
    <div v-if="selectedResult">
      <h4>{{ selectedResult.testcase_name }}</h4>
      <a-descriptions :column="1" bordered>
        <a-descriptions-item label="状态">
          <a-tag :color="getStatusColor(selectedResult.status)">
            {{ getStatusText(selectedResult.status) }}
          </a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="执行时长">
          {{ formatDuration(selectedResult.execution_time) }}
        </a-descriptions-item>
        <a-descriptions-item v-if="selectedResult.error_message" label="错误信息">
          <pre class="error-message">{{ selectedResult.error_message }}</pre>
        </a-descriptions-item>
      </a-descriptions>

      <a-divider>执行日志</a-divider>
      <div class="execution-log-container" v-html="formatExecutionLog(getExecutionLog(selectedResult.testcase_id))"></div>

      <a-divider>执行截图</a-divider>
      <div v-if="selectedResult.screenshots && selectedResult.screenshots.length > 0">
        <div class="screenshot-count">
          共 {{ selectedResult.screenshots.length }} 张截图
        </div>
        <div class="screenshot-viewer-wrapper">
          <!-- 截图信息面板暂时移除，因为顶层screenshots数组不包含title等详细信息 -->
          <!-- 如果需要显示，后端需要在顶层screenshots中提供对象数组 -->
          <div class="screenshot-viewer">
            <div class="screenshot-container">
              <div class="screenshot-index">
                {{ currentSlideIndex + 1 }} / {{ selectedResult.screenshots.length }}
              </div>
              <img
                :src="selectedResult.screenshots[currentSlideIndex]"
                :key="currentSlideIndex"
                class="screenshot-image"
              />
            </div>
            <button
              v-if="selectedResult.screenshots.length > 1"
              class="custom-arrow custom-arrow-left"
              @click="handlePrev"
            >
              <icon-left />
            </button>
            <button
              v-if="selectedResult.screenshots.length > 1"
              class="custom-arrow custom-arrow-right"
              @click="handleNext"
            >
              <icon-right />
            </button>
          </div>
        </div>
      </div>
      <a-empty v-else description="暂无截图" />
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { IconCalendar, IconClockCircle, IconLeft, IconRight } from '@arco-design/web-vue/es/icon';
import {
  getTestExecutionReport,
  getTestExecutionResults,
  type TestReportResponse,
  type TestCaseResult,
} from '@/services/testExecutionService';
import { formatDateTime, formatDuration } from '@/utils/formatters';

// 类型定义
type ReportData = NonNullable<TestReportResponse['data']>;
type ReportResult = ReportData['results'][0];

// 组件属性
interface Props {
  visible: boolean;
  currentProjectId: number | null;
  executionId: number | null;
}
const props = defineProps<Props>();

// 组件事件
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

// 状态数据
const loading = ref(false);
const error = ref('');
const report = ref<ReportData | null>(null);
const fullResults = ref<TestCaseResult[]>([]);
const detailDrawerVisible = ref(false);
const selectedResult = ref<ReportResult | null>(null);

const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
});

// 表格列配置
const resultColumns = [
  { title: '用例名称', dataIndex: 'testcase_name' },
  { title: '状态', slotName: 'status', width: 100 },
  { title: '执行时长', slotName: 'duration', width: 120 },
  { title: '操作', slotName: 'actions', width: 100 },
];

// 业务方法
const fetchReport = async () => {
  if (!props.currentProjectId || !props.executionId) return;

  loading.value = true;
  error.value = '';
  try {
    const [reportRes, resultsRes] = await Promise.all([
      getTestExecutionReport(props.currentProjectId, props.executionId),
      getTestExecutionResults(props.currentProjectId, props.executionId),
    ]);

    if (reportRes.success && reportRes.data) {
      report.value = reportRes.data;
    } else {
      error.value = reportRes.error || '加载报告失败';
    }

    if (resultsRes.success && resultsRes.data) {
      fullResults.value = resultsRes.data;
    }

  } catch (e: any) {
    error.value = e.message || '加载报告时发生未知错误';
  } finally {
    loading.value = false;
  }
};

const viewResultDetail = (result: ReportResult) => {
  // 从 fullResults 中找到完整的结果数据，包含 testcase_detail.screenshots
  const fullResult = fullResults.value.find(r => r.testcase === result.testcase_id);
  selectedResult.value = {
    ...result,
    testcase_detail: fullResult?.testcase_detail
  };
  currentSlideIndex.value = 0;
  detailDrawerVisible.value = true;
};

const getExecutionLog = (testcaseId: number) => {
  const result = fullResults.value.find(r => r.testcase === testcaseId);
  return result?.execution_log || '无执行日志';
};

const handleClose = () => {
  modalVisible.value = false;
};

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: 'gray', running: 'blue', completed: 'green',
    pass: 'green', fail: 'red',
    cancelled: 'orange', error: 'orangered', skip: 'cyan'
  };
  return colors[status] || 'gray';
};

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '等待中', running: '执行中', completed: '已完成',
    pass: '通过', fail: '失败',
    cancelled: '已取消', error: '错误', skip: '跳过'
  };
  return texts[status] || status;
};

const formatExecutionLog = (log: string): string => {
  if (!log || log === '无执行日志') {
    return '<div class="log-empty">无执行日志</div>';
  }

  const lines = log.split('\n');
  let html = '<div class="log-content">';
  let inResultSection = false;
  let resultSectionHtml = '';
  let inAiSection = false;
  let aiSectionHtml = '';
  let aiStepCount = 0;

  const closeAiSection = () => {
    if (inAiSection && aiSectionHtml) {
      html += `<details class="log-ai-section">
        <summary class="log-ai-header">🤖 AI 执行过程（共 ${aiStepCount} 个步骤）</summary>
        <div class="log-ai-content">${aiSectionHtml}</div>
      </details>`;
      aiSectionHtml = '';
      aiStepCount = 0;
      inAiSection = false;
    }
  };

  for (const line of lines) {
    const trimmedLine = line.trim();

    // 检测测试结果分隔线开始 - 结束AI区块
    if (trimmedLine.startsWith('==') && trimmedLine.endsWith('==')) {
      closeAiSection();
      if (!inResultSection) {
        inResultSection = true;
        resultSectionHtml = '<div class="log-result-section">';
      } else {
        inResultSection = false;
        resultSectionHtml += '</div>';
        html += resultSectionHtml;
        resultSectionHtml = '';
      }
      continue;
    }

    // 测试结果部分的特殊处理
    if (inResultSection) {
      if (trimmedLine.startsWith('测试结果:')) {
        const status = trimmedLine.replace('测试结果:', '').trim();
        const isPass = status.toUpperCase() === 'PASS';
        resultSectionHtml += `<div class="log-result-status ${isPass ? 'pass' : 'fail'}">
          <span class="status-icon">${isPass ? '✓' : '✗'}</span>
          <span class="status-text">测试结果: ${status}</span>
        </div>`;
      } else if (trimmedLine.startsWith('总结:')) {
        resultSectionHtml += `<div class="log-result-summary">${escapeHtml(trimmedLine)}</div>`;
      } else if (trimmedLine.startsWith('测试完成')) {
        const isPass = trimmedLine.includes('通过');
        resultSectionHtml += `<div class="log-result-status ${isPass ? 'pass' : 'fail'}">
          <span class="status-icon">${isPass ? '✓' : '✗'}</span>
          <span class="status-text">${escapeHtml(trimmedLine)}</span>
        </div>`;
      } else if (trimmedLine) {
        resultSectionHtml += `<div class="log-result-line">${escapeHtml(trimmedLine)}</div>`;
      }
      continue;
    }

    // AI执行步骤开始
    if (trimmedLine.startsWith('🔄')) {
      if (!inAiSection) {
        inAiSection = true;
      }
      aiStepCount++;
      aiSectionHtml += `<div class="log-line step">${escapeHtml(trimmedLine)}</div>`;
      continue;
    }

    // AI区块内的子内容
    if (inAiSection) {
      if (trimmedLine.startsWith('🔧')) {
        aiSectionHtml += `<div class="log-line tool">${escapeHtml(trimmedLine)}</div>`;
      } else if (trimmedLine.startsWith('💬')) {
        aiSectionHtml += `<div class="log-line message">${escapeHtml(trimmedLine)}</div>`;
      } else if (trimmedLine.startsWith('❌')) {
        aiSectionHtml += `<div class="log-line error">${escapeHtml(trimmedLine)}</div>`;
      } else if (trimmedLine) {
        aiSectionHtml += `<div class="log-line">${escapeHtml(trimmedLine)}</div>`;
      }
      continue;
    }

    // 普通日志行处理
    if (!trimmedLine) {
      html += '<div class="log-line empty"></div>';
    } else if (trimmedLine.startsWith('✓')) {
      html += `<div class="log-line success">${escapeHtml(trimmedLine)}</div>`;
    } else if (trimmedLine.startsWith('✗') || trimmedLine.startsWith('❌')) {
      html += `<div class="log-line error">${escapeHtml(trimmedLine)}</div>`;
    } else if (trimmedLine.startsWith('⚠')) {
      html += `<div class="log-line warning">${escapeHtml(trimmedLine)}</div>`;
    } else if (trimmedLine.startsWith('[步骤')) {
      const isPass = trimmedLine.includes('✓');
      html += `<div class="log-line step-result ${isPass ? 'pass' : 'fail'}">${escapeHtml(trimmedLine)}</div>`;
    } else if (trimmedLine.startsWith('  错误:')) {
      html += `<div class="log-line step-error">${escapeHtml(trimmedLine)}</div>`;
    } else {
      html += `<div class="log-line">${escapeHtml(trimmedLine)}</div>`;
    }
  }

  closeAiSection();
  html += '</div>';
  return html;
};

const escapeHtml = (text: string): string => {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
};

const currentSlideIndex = ref(0);

// 获取当前截图列表（支持用例和脚本两种类型）
const getCurrentScreenshots = () => {
  return selectedResult.value?.screenshots || [];
};

const handlePrev = () => {
  const screenshots = getCurrentScreenshots();
  const total = screenshots.length;
  if (!total || total <= 1) return;
  
  // 计算新的索引
  currentSlideIndex.value = (currentSlideIndex.value - 1 + total) % total;
};

const handleNext = () => {
  const screenshots = getCurrentScreenshots();
  const total = screenshots.length;
  if (!total || total <= 1) return;
  
  // 计算新的索引
  currentSlideIndex.value = (currentSlideIndex.value + 1) % total;
};

watch(
  () => selectedResult.value?.screenshots,
  (screens) => {
    if (!screens || screens.length === 0) return;
    currentSlideIndex.value = 0;
  }
);

// 侦听器
watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      fetchReport();
    } else {
      report.value = null;
      fullResults.value = [];
    }
  }
);
</script>

<style scoped>
.report-container { padding: 8px; }
.loading-state, .error-state { display: flex; justify-content: center; align-items: center; height: 400px; }
.report-header { margin-bottom: 24px; }
.report-header h2 { margin: 0; font-size: 24px; }
.header-meta { display: flex; align-items: center; gap: 16px; margin-top: 8px; color: var(--color-text-3); }
.meta-item { display: flex; align-items: center; gap: 4px; }
.statistics-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card { text-align: center; }
.stat-card.total { display: flex; align-items: center; justify-content: center; }
.stat-title-wrapper { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 12px 0; }
.stat-main-title { font-size: 14px; color: var(--color-text-2); }
.stat-subtitle { display: flex; gap: 4px; }
.results-table { margin-top: 16px; }
.error-message { white-space: pre-wrap; background-color: var(--color-fill-2); padding: 8px; border-radius: 4px; font-family: monospace; }

/* 执行日志样式 */
.execution-log-container {
  background-color: var(--color-fill-1);
  border-radius: 8px;
  padding: 16px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  max-height: 400px;
  overflow-y: auto;
}

.execution-log-container :deep(.log-empty) {
  color: var(--color-text-3);
  text-align: center;
  padding: 20px;
}

.execution-log-container :deep(.log-content) {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* AI执行过程整体折叠区块 */
.execution-log-container :deep(.log-ai-section) {
  margin: 8px 0;
  border: 1px solid rgba(22, 93, 255, 0.2);
  border-radius: 6px;
  background-color: rgba(22, 93, 255, 0.02);
}

.execution-log-container :deep(.log-ai-header) {
  padding: 10px 12px;
  cursor: pointer;
  color: #165dff;
  font-weight: 600;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

.execution-log-container :deep(.log-ai-header:hover) {
  background-color: rgba(22, 93, 255, 0.08);
}

.execution-log-container :deep(.log-ai-header::marker) {
  color: #165dff;
}

.execution-log-container :deep(.log-ai-content) {
  padding: 8px 12px 12px 16px;
  border-top: 1px solid rgba(22, 93, 255, 0.1);
}

.execution-log-container :deep(.log-line.step) {
  color: #165dff;
  font-weight: 600;
  margin-top: 8px;
  padding: 6px 8px;
  background-color: rgba(22, 93, 255, 0.06);
  border-radius: 4px;
}

.execution-log-container :deep(.log-line) {
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.execution-log-container :deep(.log-line:hover) {
  background-color: var(--color-fill-2);
}

.execution-log-container :deep(.log-line.empty) {
  height: 8px;
}

.execution-log-container :deep(.log-line.success) {
  color: #00b42a;
}

.execution-log-container :deep(.log-line.error) {
  color: #f53f3f;
}

.execution-log-container :deep(.log-line.warning) {
  color: #ff7d00;
}

.execution-log-container :deep(.log-line.tool) {
  color: #722ed1;
  padding-left: 8px;
}

.execution-log-container :deep(.log-line.message) {
  color: var(--color-text-2);
  padding-left: 8px;
  font-style: italic;
}

.execution-log-container :deep(.log-line.step-result) {
  padding: 6px 12px;
  margin: 4px 0;
  border-radius: 6px;
  font-weight: 500;
}

.execution-log-container :deep(.log-line.step-result.pass) {
  background-color: rgba(0, 180, 42, 0.1);
  color: #00b42a;
  border-left: 3px solid #00b42a;
}

.execution-log-container :deep(.log-line.step-result.fail) {
  background-color: rgba(245, 63, 63, 0.1);
  color: #f53f3f;
  border-left: 3px solid #f53f3f;
}

.execution-log-container :deep(.log-line.step-error) {
  color: #f53f3f;
  padding-left: 32px;
  font-size: 12px;
}

/* 测试结果区块样式 */
.execution-log-container :deep(.log-result-section) {
  margin: 16px 0;
  padding: 16px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--color-fill-2) 0%, var(--color-fill-3) 100%);
  border: 1px solid var(--color-border);
}

.execution-log-container :deep(.log-result-status) {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.execution-log-container :deep(.log-result-status.pass) {
  background: linear-gradient(135deg, rgba(0, 180, 42, 0.15) 0%, rgba(0, 180, 42, 0.08) 100%);
  color: #00b42a;
  border: 1px solid rgba(0, 180, 42, 0.3);
}

.execution-log-container :deep(.log-result-status.fail) {
  background: linear-gradient(135deg, rgba(245, 63, 63, 0.15) 0%, rgba(245, 63, 63, 0.08) 100%);
  color: #f53f3f;
  border: 1px solid rgba(245, 63, 63, 0.3);
}

.execution-log-container :deep(.log-result-status .status-icon) {
  font-size: 20px;
}

.execution-log-container :deep(.log-result-summary) {
  color: var(--color-text-2);
  padding: 8px 0;
  line-height: 1.6;
}

.execution-log-container :deep(.log-result-line) {
  color: var(--color-text-2);
  padding: 4px 0;
}
.screenshot-count {
  margin-bottom: 12px;
  color: var(--color-text-2);
  font-size: 14px;
  text-align: center;
}

.screenshot-container {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 20px 80px 20px 80px;
  box-sizing: border-box;
}

.screenshot-image {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  display: block;
  transition: opacity 0.3s ease;
  border: 1px solid #e5e6eb;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.screenshot-index {
  position: absolute;
  top: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  z-index: 1;
}

.screenshot-info-panel {
  background: #f7f8fa;
  padding: 16px;
  margin-bottom: 12px;
  border-radius: 4px;
  border: 1px solid #e5e6eb;
}

.screenshot-title {
  font-weight: bold;
  margin-bottom: 8px;
  color: #1d2129;
  font-size: 15px;
}

.screenshot-description {
  font-size: 14px;
  margin-bottom: 8px;
  color: #4e5969;
  line-height: 1.5;
}

.screenshot-meta {
  font-size: 12px;
  color: #86909c;
  display: flex;
  gap: 16px;
}

.screenshot-meta span {
  display: inline-flex;
  align-items: center;
}

/* 截图查看器容器 */
.screenshot-viewer-wrapper {
  position: relative;
}

.screenshot-viewer {
  position: relative;
  width: 100%;
  height: 600px;
}

/* 自定义箭头样式 */
.custom-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 56px;
  height: 56px;
  background: rgba(0, 0, 0, 0.7);
  border: 2px solid rgba(255, 255, 255, 0.9);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  z-index: 100;
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.4),
    0 4px 16px rgba(0, 0, 0, 0.3);
}

.custom-arrow-left {
  left: 20px;
}

.custom-arrow-right {
  right: 20px;
}

.custom-arrow:hover {
  background: rgba(0, 0, 0, 0.85);
  border-color: rgba(255, 255, 255, 1);
  transform: translateY(-50%) scale(1.15);
  box-shadow:
    0 4px 12px rgba(0, 0, 0, 0.5),
    0 6px 20px rgba(0, 0, 0, 0.4);
}

.custom-arrow:active {
  transform: translateY(-50%) scale(1.05);
}

.custom-arrow :deep(.arco-icon) {
  font-size: 28px;
  color: white;
  font-weight: bold;
}

/* 结果标签页样式 */
.results-tabs {
  margin-top: 16px;
}
</style>
