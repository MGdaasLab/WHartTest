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
          <a-statistic title="总用例数" :value="report.statistics.total" />
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
      <a-table
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
    </div>
  </a-modal>

  <!-- 结果详情抽屉 -->
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
      <pre class="execution-log">{{ getExecutionLog(selectedResult.testcase_id) }}</pre>

      <a-divider>执行截图</a-divider>
      <div v-if="selectedResult.testcase_detail?.screenshots && selectedResult.testcase_detail.screenshots.length > 0">
        <div class="screenshot-count">
          共 {{ selectedResult.testcase_detail.screenshots.length }} 张截图
        </div>
        <div class="screenshot-viewer-wrapper">
          <div v-if="selectedResult.testcase_detail.screenshots[currentSlideIndex]" class="screenshot-info-panel">
            <div class="screenshot-title">{{ selectedResult.testcase_detail.screenshots[currentSlideIndex].title }}</div>
            <div class="screenshot-description">{{ selectedResult.testcase_detail.screenshots[currentSlideIndex].description }}</div>
            <div class="screenshot-meta">
              <span v-if="selectedResult.testcase_detail.screenshots[currentSlideIndex].step_number">
                步骤 {{ selectedResult.testcase_detail.screenshots[currentSlideIndex].step_number }}
              </span>
              <span v-if="selectedResult.testcase_detail.screenshots[currentSlideIndex].page_url">
                {{ selectedResult.testcase_detail.screenshots[currentSlideIndex].page_url }}
              </span>
            </div>
          </div>
          <div class="screenshot-viewer">
            <div class="screenshot-container">
              <div class="screenshot-index">
                {{ currentSlideIndex + 1 }} / {{ selectedResult.testcase_detail.screenshots.length }}
              </div>
              <img
                :src="selectedResult.testcase_detail.screenshots[currentSlideIndex].screenshot_url"
                :key="currentSlideIndex"
                class="screenshot-image"
              />
            </div>
            <button
              v-if="selectedResult.testcase_detail.screenshots.length > 1"
              class="custom-arrow custom-arrow-left"
              @click="handlePrev"
            >
              <icon-left />
            </button>
            <button
              v-if="selectedResult.testcase_detail.screenshots.length > 1"
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
import { ref, computed, watch, nextTick } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconCalendar, IconClockCircle, IconLeft, IconRight } from '@arco-design/web-vue/es/icon';
import {
  getTestExecutionReport,
  getTestExecutionResults,
  type TestReportResponse,
  type TestCaseResult,
} from '@/services/testExecutionService';
import { formatDateTime, formatDuration } from '@/utils/formatters';
import { API_BASE_URL } from '@/config/api';

// Types
type ReportData = NonNullable<TestReportResponse['data']>;
type ReportResult = ReportData['results'][0];

// Props
interface Props {
  visible: boolean;
  currentProjectId: number | null;
  executionId: number | null;
}
const props = defineProps<Props>();

// Emits
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

// Data
const loading = ref(false);
const error = ref('');
const report = ref<ReportData | null>(null);
const fullResults = ref<TestCaseResult[]>([]);
const detailDrawerVisible = ref(false);
const selectedResult = ref<ReportResult | null>(null);
const carouselRef = ref<any>(null);

const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
});

// Columns
const resultColumns = [
  { title: '用例名称', dataIndex: 'testcase_name' },
  { title: '状态', slotName: 'status', width: 100 },
  { title: '执行时长', slotName: 'duration', width: 120 },
  { title: '操作', slotName: 'actions', width: 100 },
];

// Methods
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
  currentSlideIndex.value = 0; // 重置轮播索引
  detailDrawerVisible.value = true;
};

const getExecutionLog = (testcaseId: number) => {
  const result = fullResults.value.find(r => r.testcase === testcaseId);
  return result?.execution_log || '无执行日志';
};

const getFullScreenshotUrl = (relativePath: string) => {
  if (!relativePath) return '';
  // 假设API_BASE_URL是http://localhost:8000/api, 我们需要http://localhost:8000
  const baseUrl = API_BASE_URL.replace('/api', '');
  return `${baseUrl}/media/${relativePath}`;
};

const handleClose = () => {
  modalVisible.value = false;
};

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    pending: 'gray', running: 'blue', completed: 'green',
    pass: 'green', failed: 'red', fail: 'red',
    cancelled: 'orange', error: 'orangered', skip: 'cyan'
  };
  return colors[status] || 'gray';
};

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '等待中', running: '执行中', completed: '已完成',
    pass: '通过', failed: '失败', fail: '失败',
    cancelled: '已取消', error: '错误', skip: '跳过'
  };
  return texts[status] || status;
};

const currentSlideIndex = ref(0);

const handlePrev = () => {
  if (!selectedResult.value?.testcase_detail?.screenshots) return;
  const total = selectedResult.value.testcase_detail.screenshots.length;
  if (!total || total <= 1) return;
  
  // 计算新的索引
  currentSlideIndex.value = (currentSlideIndex.value - 1 + total) % total;
};

const handleNext = () => {
  if (!selectedResult.value?.testcase_detail?.screenshots) return;
  const total = selectedResult.value.testcase_detail.screenshots.length;
  if (!total || total <= 1) return;
  
  // 计算新的索引
  currentSlideIndex.value = (currentSlideIndex.value + 1) % total;
};

watch(
  () => selectedResult.value?.testcase_detail?.screenshots,
  (screens) => {
    if (!screens || screens.length === 0) return;
    currentSlideIndex.value = 0;
  }
);

// Watchers
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
.results-table { margin-top: 16px; }
.error-message, .execution-log { white-space: pre-wrap; background-color: var(--color-fill-2); padding: 8px; border-radius: 4px; font-family: monospace; }
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
</style>
