<template>
  <div class="document-detail">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <a-button type="text" @click="goBack" class="back-button">
          <template #icon><icon-arrow-left /></template>
          返回列表
        </a-button>
        <h1 class="page-title">{{ document?.title || '文档详情' }}</h1>
        <a-tag :color="getStatusColor(document?.status)" class="status-tag">
          {{ getStatusText(document?.status) }}
        </a-tag>
      </div>
      <div class="header-actions">
        <!-- 上传状态优先拆分 -->
        <a-button
          v-if="document?.status === 'uploaded'"
          type="primary"
          @click="handleShowSplitOptionsWithDefault('h2')"
          :loading="splitLoading"
        >
          <template #icon><icon-robot /></template>
          AI智能拆分
        </a-button>

        <!-- 用户调整状态：显示确认按钮 -->
        <a-button
          v-if="document?.status === 'user_reviewing'"
          type="primary"
          @click="confirmModules"
          :loading="splitLoading"
        >
          <template #icon><icon-check-circle /></template>
          确认模块拆分
        </a-button>

        <!-- 待评审状态：显示开始评审按钮 -->
        <a-button
          v-if="document?.status === 'ready_for_review'"
          type="primary"
          @click="startReview"
          :loading="reviewLoading"
        >
          <template #icon><icon-check-circle /></template>
          开始评审
        </a-button>

        <!-- 评审完成状态：显示查看报告和重新评审按钮 -->
        <a-space v-if="document?.status === 'review_completed'">
          <a-button
            type="primary"
            @click="viewReport"
          >
            <template #icon><icon-file /></template>
            查看详细报告
          </a-button>
          <a-button
            type="outline"
            @click="restartReview"
            :loading="reviewLoading"
          >
            <template #icon><icon-refresh /></template>
            重新评审
          </a-button>
        </a-space>

        <!-- 处理失败状态：显示重新评审按钮 -->
        <a-button
          v-if="document?.status === 'failed'"
          type="primary"
          @click="retryReview"
          :loading="reviewLoading"
        >
          <template #icon><icon-refresh /></template>
          重新评审
        </a-button>
      </div>
    </div>

    <!-- 文档信息卡片 -->
    <div class="info-section">
      <a-card title="文档信息" class="info-card">
        <div class="info-grid">
          <div class="info-item">
            <span class="label">文档类型：</span>
            <a-tag color="blue">{{ getTypeText(document?.document_type) }}</a-tag>
          </div>
          <div class="info-item">
            <span class="label">字数：</span>
            <span>{{ document?.word_count || 0 }} 字</span>
          </div>
          <div class="info-item">
            <span class="label">页数：</span>
            <span>{{ document?.page_count || 0 }} 页</span>
          </div>
          <div class="info-item">
            <span class="label">模块数：</span>
            <span>{{ document?.modules_count || 0 }} 个</span>
          </div>
          <div class="info-item">
            <span class="label">上传者：</span>
            <span>{{ document?.uploader_name }}</span>
          </div>
          <div class="info-item">
            <span class="label">上传时间：</span>
            <span>{{ formatDateTime(document?.uploaded_at) }}</span>
          </div>
          <div class="info-item">
            <span class="label">更新时间：</span>
            <span>{{ formatDateTime(document?.updated_at) }}</span>
          </div>
        </div>
        <div v-if="document?.description" class="description">
          <span class="label">描述：</span>
          <a-tooltip :content="document.description" position="top">
            <p class="description-text">{{ document.description }}</p>
          </a-tooltip>
        </div>

        <!-- 上传状态提示 -->
        <div v-if="document?.status === 'uploaded'" class="upload-hint">
          <a-alert
            type="warning"
            message="请先进行拆分"
            description="上传完成后请使用 AI 拆分生成模块，用例生成和后续评审依赖这些模块。"
            show-icon
          />
        </div>
      </a-card>
    </div>

    <!-- 工作流程指示器 -->
    <div v-if="document" class="workflow-indicator">
      <a-card title="📋 评审工作流程" class="workflow-card">
        <a-steps :current="getCurrentStep(document.status)" size="small">
          <a-step title="文档上传" description="上传需求文档">
            <template #icon>
              <icon-file />
            </template>
          </a-step>
          <a-step title="AI智能拆分" description="使用 AI 拆分文档生成模块">
            <template #icon>
              <icon-scissor />
            </template>
          </a-step>
          <a-step title="用户调整" description="确认模块拆分结果（如需要）">
            <template #icon>
              <icon-edit />
            </template>
          </a-step>
          <a-step title="需求评审" description="AI分析需求质量">
            <template #icon>
              <icon-check-circle />
            </template>
          </a-step>
          <a-step title="评审完成" description="查看评审报告">
            <template #icon>
              <icon-file />
            </template>
          </a-step>
        </a-steps>
      </a-card>
    </div>

    <!-- 评审报告区域 -->
    <div v-if="document?.status === 'review_completed' && document?.latest_review" class="review-report-section">
      <a-card title="📊 评审报告" class="review-report-card">
        <div class="report-overview">
          <div class="report-header">
            <div class="report-meta">
              <h2>{{ document.latest_review.document_title }}</h2>
              <div class="report-info">
                <a-tag :color="getRatingColor(document.latest_review.overall_rating)">
                  {{ document.latest_review.overall_rating_display }}
                </a-tag>
                <span class="report-date">{{ formatDateTime(document.latest_review.review_date) }}</span>
              </div>
            </div>
            <div class="report-score">
              <div class="score-circle">
                <span class="score-number">{{ document.latest_review.completion_score }}</span>
                <span class="score-label">分</span>
              </div>
            </div>
          </div>

          <!-- 问题统计 -->
          <div class="issues-stats">
            <div
              class="stat-item high"
              :class="{ active: selectedPriority === 'high' }"
              @click="handlePrioritySelect('high')"
            >
              <span class="stat-number">{{ document.latest_review.high_priority_issues }}</span>
              <span class="stat-label">高优先级</span>
            </div>
            <div
              class="stat-item medium"
              :class="{ active: selectedPriority === 'medium' }"
              @click="handlePrioritySelect('medium')"
            >
              <span class="stat-number">{{ document.latest_review.medium_priority_issues }}</span>
              <span class="stat-label">中优先级</span>
            </div>
            <div
              class="stat-item low"
              :class="{ active: selectedPriority === 'low' }"
              @click="handlePrioritySelect('low')"
            >
              <span class="stat-number">{{ document.latest_review.low_priority_issues }}</span>
              <span class="stat-label">低优先级</span>
            </div>
            <div
              class="stat-item total"
              :class="{ active: selectedPriority === 'all' }"
              @click="handlePrioritySelect('all')"
            >
              <span class="stat-number">{{ document.latest_review.total_issues }}</span>
              <span class="stat-label">总问题</span>
            </div>
          </div>

          <!-- 动态内容区域 -->
          <div v-if="selectedPriority === 'all'" class="report-overview">
            <!-- 评审摘要 -->
            <div class="report-summary">
              <h4>📝 评审摘要</h4>
              <p>{{ document.latest_review.summary }}</p>
            </div>

            <!-- 改进建议 -->
            <div class="report-recommendations">
              <h4>💡 改进建议</h4>
              <div class="recommendations-content">
                {{ document.latest_review.recommendations }}
              </div>
            </div>
          </div>

          <!-- 筛选后的问题列表 -->
          <div v-else class="filtered-issues">
            <h4>
              {{ selectedPriority === 'high' ? '🔴 高优先级问题' :
                 selectedPriority === 'medium' ? '🟡 中优先级问题' :
                 '🟢 低优先级问题' }}
              ({{ filteredIssues.length }}个)
            </h4>

            <div v-if="filteredIssues.length === 0" class="no-issues">
              <a-empty description="暂无此优先级的问题" />
            </div>

            <div v-else class="issues-list">
              <div
                v-for="issue in filteredIssues"
                :key="issue.id"
                class="issue-item"
              >
                <div class="issue-header">
                  <a-tag
                    :color="issue.priority === 'high' ? 'red' :
                           issue.priority === 'medium' ? 'orange' : 'green'"
                    size="small"
                  >
                    {{ issue.priority_display }}
                  </a-tag>
                  <a-tag color="blue" size="small">
                    {{ issue.issue_type_display }}
                  </a-tag>
                </div>
                <div class="issue-content">
                  <h5>{{ issue.title }}</h5>
                  <p>{{ issue.description }}</p>
                  <div v-if="issue.suggestion" class="issue-suggestion">
                    <strong>建议：</strong>{{ issue.suggestion }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </a-card>
    </div>

    <!-- 模块管理区域 -->
    <div v-if="document?.modules && document.modules.length > 0" class="modules-section">
      <a-card class="modules-card">
        <template #title>
          <div class="modules-header">
            <span>{{ document.status === 'review_completed' ? '模块详情' : '模块管理' }} ({{ document.modules.length }}个)</span>
            <div class="modules-actions">
              <a-button 
                v-if="document.status === 'user_reviewing'"
                type="primary" 
                size="small"
                @click="confirmModules"
              >
                确认模块划分
              </a-button>
              <a-button 
                v-if="document.status === 'user_reviewing'"
                type="outline" 
                size="small"
                @click="addModule"
              >
                <template #icon><icon-plus /></template>
                添加模块
              </a-button>
            </div>
          </div>
        </template>

        <!-- 统一的文档内容展示区域 -->
        <div class="document-content-container">
          <!-- 模块导航栏 -->
          <div v-if="document.status === 'user_reviewing'" class="modules-toolbar">
            <div class="toolbar-left">
              <span class="modules-count">共 {{ sortedModules.length }} 个模块</span>
            </div>
            <div class="toolbar-right">
              <a-button size="small" @click="addModule">
                <template #icon><icon-plus /></template>
                添加模块
              </a-button>
              <a-button size="small" @click="mergeSelectedModules" :disabled="selectedModules.length < 2">
                <template #icon><icon-link /></template>
                合并选中
              </a-button>
            </div>
          </div>

          <!-- 文档内容区域 -->
          <div class="unified-content" :class="{ 'editing-mode': document.status === 'user_reviewing' }">
            <!-- 模块内容片段 -->
            <div
              v-for="(module, index) in sortedModules"
              :key="module.id"
              class="content-segment"
              :class="{
                'selected': selectedModules.includes(module.id),
                'highlighted': hoveredModuleId === module.id,
                'editing': editingContentId === module.id
              }"
              @mouseenter="hoveredModuleId = module.id"
              @mouseleave="hoveredModuleId = null"
              @click="toggleModuleSelection(module.id)"
            >
              <!-- 模块标签 -->
              <div
                class="module-label"
                :style="{ backgroundColor: getModuleColor(index) }"
              >
                <div class="label-content">
                  <span class="module-number">{{ module.order }}</span>
                  <span
                    class="module-title-inline"
                    @dblclick.stop="startEditTitle(module)"
                  >
                    {{ module.title }}
                  </span>
                  <div v-if="document.status === 'user_reviewing'" class="label-actions">
                    <a-button type="text" size="mini" @click.stop="editModuleContent(module)">
                      <template #icon><icon-edit /></template>
                    </a-button>
                    <a-button type="text" size="mini" @click.stop="splitAtCursor(module)">
                      <template #icon><icon-scissor /></template>
                    </a-button>
                  </div>
                </div>
              </div>

              <!-- 内容编辑区域 -->
              <div v-if="editingContentId === module.id" class="inline-content-edit">
                <a-textarea
                  v-model="editingContent"
                  :auto-size="{ minRows: 3 }"
                  placeholder="请输入模块内容..."
                  @blur="saveContent(module)"
                  @keyup.ctrl.enter="saveContent(module)"
                  @keyup.esc="cancelContentEdit"
                  ref="contentTextarea"
                />
                <div class="edit-hint">Ctrl+Enter 保存，Esc 取消</div>
              </div>

              <!-- 内容显示区域 -->
              <div
                v-else
                class="segment-content"
                @dblclick="editModuleContent(module)"
                :style="{
                  borderLeft: `4px solid ${getModuleColor(index)}`,
                  backgroundColor: selectedModules.includes(module.id) ? getModuleColor(index, 0.1) : 'white'
                }"
              >
                {{ module.content }}
              </div>
            </div>
          </div>

          <!-- 标题编辑模态框 -->
          <a-modal
            v-model:visible="titleEditVisible"
            title="编辑模块标题"
            width="400px"
            @ok="saveTitleModal"
            @cancel="cancelTitleEdit"
          >
            <a-input
              v-model="editingTitle"
              placeholder="请输入模块标题"
              @keyup.enter="saveTitleModal"
            />
          </a-modal>
        </div>

        <!-- 选中模块信息栏 -->
        <div v-if="selectedModules.length > 0 && document.status === 'user_reviewing'" class="selection-info">
          <div class="selection-details">
            已选择 {{ selectedModules.length }} 个模块
            <span class="selected-titles">
              {{ getSelectedModuleTitles() }}
            </span>
          </div>
          <div class="selection-actions">
            <a-button size="small" @click="mergeSelectedModules">
              <template #icon><icon-link /></template>
              合并模块
            </a-button>
            <a-button size="small" status="danger" @click="deleteSelectedModules">
              <template #icon><icon-delete /></template>
              删除选中
            </a-button>
            <a-button size="small" @click="clearSelection">清除选择</a-button>
          </div>
        </div>
      </a-card>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="empty-state">
      <a-empty description="暂无模块数据">
        <template #image>
          <icon-file />
        </template>
        <!-- 上传状态：显示检测按钮 -->
        <a-button
          v-if="document?.status === 'uploaded'"
          type="primary"
          @click="handleShowSplitOptionsWithDefault('h2')"
          :loading="splitLoading"
        >
          <template #icon><icon-robot /></template>
          AI智能拆分
        </a-button>

      </a-empty>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <a-spin size="large" />
    </div>

    <!-- 模块编辑模态框 -->
    <a-modal
      v-model:visible="editModalVisible"
      title="编辑模块"
      width="800px"
      @ok="saveModule"
      @cancel="cancelModalEdit"
    >
      <a-form
        ref="editFormRef"
        :model="editForm"
        layout="vertical"
      >
        <a-form-item label="模块标题" field="title">
          <a-input v-model="editForm.title" placeholder="请输入模块标题" />
        </a-form-item>
        <a-form-item label="模块内容" field="content">
          <a-textarea
            v-model="editForm.content"
            placeholder="请输入模块内容"
            :auto-size="{ minRows: 5 }"
          />
        </a-form-item>
        <a-form-item label="排序" field="order">
          <a-input-number v-model="editForm.order" :min="1" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 模块拆分配置模态框 -->
    <SplitOptionsModal
      :visible="showSplitModal"
      :default-level="splitDefaultLevel"
      @confirm="handleSplitConfirm"
      @cancel="showSplitModal = false"
      @update:visible="showSplitModal = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Message, Modal } from '@arco-design/web-vue';
import {
  IconArrowLeft,
  IconCheckCircle,
  IconPlus,
  IconEdit,
  IconDelete,
  IconFile,
  IconScissor,
  IconRobot,
  IconRefresh
} from '@arco-design/web-vue/es/icon';
import { RequirementDocumentService } from '../services/requirementService';
import type {
  DocumentDetail,
  DocumentModule,
  DocumentStatus,
  DocumentType,
  SplitModulesRequest
} from '../types';
import { DocumentStatusDisplay, DocumentTypeDisplay } from '../types';
import SplitOptionsModal from '../components/SplitOptionsModal.vue';

// 路由
const route = useRoute();
const router = useRouter();

// 响应式数据
const loading = ref(false);
const splitLoading = ref(false);
const reviewLoading = ref(false);
const document = ref<DocumentDetail | null>(null);
const expandedModules = ref<string[]>([]);

// 拆分配置状态
const showSplitModal = ref(false);
const splitDefaultLevel = ref<string>('auto');

// 编辑相关
const editModalVisible = ref(false);
const editFormRef = ref();
const editForm = ref<Partial<DocumentModule>>({});
const currentEditingModule = ref<DocumentModule | null>(null);

// 新增的交互式编辑变量
const editingModuleId = ref<string | null>(null);
const editingContentId = ref<string | null>(null);
const editingTitle = ref('');
const editingContent = ref('');
const selectedModules = ref<string[]>([]);
const titleInput = ref();
const contentTextarea = ref();

// 新的统一展示相关变量
const hoveredModuleId = ref<string | null>(null);
const titleEditVisible = ref(false);
const currentEditingTitleModule = ref<DocumentModule | null>(null);

// 优先级筛选相关
const selectedPriority = ref<'all' | 'high' | 'medium' | 'low'>('all');

// 计算属性
const sortedModules = computed(() => {
  if (!document.value?.modules) return [];
  return [...document.value.modules].sort((a, b) => a.order - b.order);
});

// 筛选后的问题列表
const filteredIssues = computed(() => {
  if (!document.value?.latest_review?.issues) return [];

  if (selectedPriority.value === 'all') {
    return document.value.latest_review.issues;
  }

  return document.value.latest_review.issues.filter(issue =>
    issue.priority === selectedPriority.value
  );
});

// 方法
const getStatusColor = (status?: DocumentStatus) => {
  if (!status) return 'gray';
  const colorMap = {
    uploaded: 'blue',
    processing: 'orange',
    module_split: 'orange',
    user_reviewing: 'purple',
    ready_for_review: 'cyan',
    reviewing: 'orange',
    review_completed: 'green',
    failed: 'red'
  };
  return colorMap[status] || 'gray';
};

const getStatusText = (status?: DocumentStatus) => {
  if (!status) return '';
  return DocumentStatusDisplay[status] || status;
};

const getTypeText = (type?: DocumentType) => {
  if (!type) return '';
  return DocumentTypeDisplay[type] || type;
};

const formatDateTime = (dateTime?: string) => {
  if (!dateTime) return '';
  return new Date(dateTime).toLocaleString();
};

// 优先级选择处理
const handlePrioritySelect = (priority: 'all' | 'high' | 'medium' | 'low') => {
  selectedPriority.value = priority;
};

// 获取当前工作流程步骤
const getCurrentStep = (status: DocumentStatus) => {
  // 上传状态下引导执行拆分
  if (status === 'uploaded') {
    return 2;
  }

  const stepMap: Partial<Record<DocumentStatus, number>> = {
    'processing': 2,
    'module_split': 3,
    'user_reviewing': 3,
    'ready_for_review': 4,
    'reviewing': 4,
    'review_completed': 5,
    'failed': 0
  };

  return stepMap[status] || 0;
};
// 获取评级颜色
const getRatingColor = (rating: string) => {
  const colorMap: Record<string, string> = {
    'excellent': 'green',
    'good': 'blue',
    'fair': 'orange',
    'poor': 'red'
  };

  return colorMap[rating] || 'gray';
};

// 获取优先级颜色
const getPriorityColor = (priority: string) => {
  const colorMap: Record<string, string> = {
    'high': 'red',
    'medium': 'orange',
    'low': 'blue'
  };
  return colorMap[priority] || 'gray';
};

// 加载文档详情
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

// 返回列表
const goBack = () => {
  router.push('/requirements');
};

// 查看详细报告
const viewReport = () => {
  if (document.value?.id) {
    router.push(`/requirements/${document.value.id}/report`);
  }
};

// 重新评审
const restartReview = async () => {
  if (!document.value) return;

  try {
    // 确认重新评审
    const confirmed = await new Promise((resolve) => {
      Modal.confirm({
        title: '确认重新评审',
        content: '重新评审将创建新的评审报告，原有报告将保留。是否继续？',
        okText: '确认',
        cancelText: '取消',
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });

    if (!confirmed) return;

    reviewLoading.value = true;

    const response = await RequirementDocumentService.restartReview(document.value.id, {
      analysis_type: 'comprehensive',
      parallel_processing: true
    });

    if (response.status === 'success') {
      Message.success('重新评审已开始');
      await loadDocument(); // 重新加载文档
    } else {
      Message.error(response.message || '重新评审启动失败');
    }
  } catch (error) {
    console.error('重新评审启动失败:', error);
    Message.error('重新评审启动失败');
  } finally {
    reviewLoading.value = false;
  }
};

// 失败后重试评审
const retryReview = async () => {
  if (!document.value) return;

  try {
    // 确认重试
    const confirmed = await new Promise((resolve) => {
      Modal.confirm({
        title: '确认重试评审',
        content: '系统将重新尝试对文档进行评审处理。是否继续？',
        okText: '确认',
        cancelText: '取消',
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });

    if (!confirmed) return;

    reviewLoading.value = true;

    // 文档还没有拆分模块时提示用户先拆分
    if (!document.value.modules || document.value.modules.length === 0) {
      Message.warning('请先完成文档拆分生成模块');
      handleShowSplitOptionsWithDefault('h2');
      return;
    }

    // 如果已有模块，直接开始评审
    const response = await RequirementDocumentService.startReview(document.value.id, {
      analysis_type: 'comprehensive',
      parallel_processing: true
    });

    if (response.status === 'success') {
      Message.success('重试评审已开始');
      await loadDocument(); // 重新加载文档
    } else {
      Message.error(response.message || '重试评审启动失败');
    }
  } catch (error) {
    console.error('重试评审启动失败:', error);
    Message.error('重试评审启动失败');
  } finally {
    reviewLoading.value = false;
  }
};


// 显示拆分选项并预选指定级别
const handleShowSplitOptionsWithDefault = (defaultLevel: string) => {
  splitDefaultLevel.value = defaultLevel;
  showSplitModal.value = true;
};

// 确认拆分配置
const handleSplitConfirm = async (config: SplitModulesRequest) => {
  if (!document.value) return;

  splitLoading.value = true;
  try {
    const response = await RequirementDocumentService.splitModules(document.value.id, config);

    if (response.status === 'success') {
      Message.success(`按${config.split_level.toUpperCase()}级别拆分完成`);
      await loadDocument(); // 重新加载文档
    } else {
      Message.error(response.message || 'AI模块拆分失败');
    }
  } catch (error) {
    console.error('AI模块拆分失败:', error);
    Message.error('AI模块拆分失败');
  } finally {
    splitLoading.value = false;
  }
};

// 确认模块拆分（将状态从user_reviewing改为ready_for_review）
const confirmModules = async () => {
  if (!document.value) return;

  try {
    const response = await RequirementDocumentService.confirmModules(document.value.id);

    if (response.status === 'success') {
      Message.success('模块拆分已确认，可以开始评审');
      await loadDocument(); // 重新加载文档以更新状态
    } else {
      Message.error(response.message || '确认模块拆分失败');
    }
  } catch (error) {
    console.error('确认模块拆分失败:', error);
    Message.error('确认模块拆分失败');
  }
};



// 开始评审
const startReview = async () => {
  if (!document.value) return;

  reviewLoading.value = true;
  try {
    const response = await RequirementDocumentService.startReview(document.value.id, {
      analysis_type: 'comprehensive',
      parallel_processing: true
    });

    if (response.status === 'success') {
      Message.success('需求评审已开始');
      await loadDocument(); // 重新加载文档
    } else {
      Message.error(response.message || '需求评审启动失败');
    }
  } catch (error) {
    console.error('需求评审启动失败:', error);
    Message.error('需求评审启动失败');
  } finally {
    reviewLoading.value = false;
  }
};

// 模块展开/收起
const toggleModuleExpand = (moduleId: string) => {
  const index = expandedModules.value.indexOf(moduleId);
  if (index > -1) {
    expandedModules.value.splice(index, 1);
  } else {
    expandedModules.value.push(moduleId);
  }
};

// 编辑模块
const editModule = (module: DocumentModule) => {
  currentEditingModule.value = module;
  editForm.value = { ...module };
  editModalVisible.value = true;
};

// 保存模块
const saveModule = async () => {
  // TODO: 实现模块保存逻辑
  Message.success('模块保存成功');
  editModalVisible.value = false;
  await loadDocument();
};

// 取消模态框编辑
const cancelModalEdit = () => {
  editModalVisible.value = false;
  editForm.value = {};
  currentEditingModule.value = null;
};

// 移动模块
const moveModule = async (index: number, direction: 'up' | 'down') => {
  // TODO: 实现模块移动逻辑
  Message.success(`模块${direction === 'up' ? '上移' : '下移'}成功`);
  await loadDocument();
};

// 删除模块
const deleteModule = async (module: DocumentModule) => {
  // TODO: 实现模块删除逻辑
  Message.success('模块删除成功');
  await loadDocument();
};

// 添加模块
const addModule = () => {
  editForm.value = {
    title: '',
    content: '',
    order: (document.value?.modules?.length || 0) + 1,
    is_auto_generated: false
  };
  currentEditingModule.value = null;
  editModalVisible.value = true;
};

// 确认模块划分方法已在上面定义

// 新的统一展示方法
const toggleModuleSelection = (moduleId: string) => {
  if (document.value?.status !== 'user_reviewing') return;

  const index = selectedModules.value.indexOf(moduleId);
  if (index > -1) {
    selectedModules.value.splice(index, 1);
  } else {
    selectedModules.value.push(moduleId);
  }
};

const getModuleColor = (index: number, alpha: number = 1) => {
  const colors = [
    `rgba(0, 160, 233, ${alpha})`,   // 蓝色
    `rgba(0, 180, 42, ${alpha})`,     // 绿色
    `rgba(255, 125, 0, ${alpha})`,    // 橙色
    `rgba(245, 63, 63, ${alpha})`,    // 红色
    `rgba(114, 46, 209, ${alpha})`,   // 紫色
    `rgba(255, 193, 7, ${alpha})`,    // 黄色
  ];
  return colors[index % colors.length];
};

const getSelectedModuleTitles = () => {
  const titles = selectedModules.value
    .map(id => sortedModules.value.find(m => m.id === id)?.title)
    .filter(Boolean)
    .slice(0, 3);

  if (selectedModules.value.length > 3) {
    titles.push('...');
  }

  return titles.join('、');
};

// 标题编辑方法
const startEditTitle = (module: DocumentModule) => {
  currentEditingTitleModule.value = module;
  editingTitle.value = module.title;
  titleEditVisible.value = true;
};

const saveTitleModal = async () => {
  if (editingTitle.value.trim() && currentEditingTitleModule.value) {
    // TODO: 调用API保存标题
    currentEditingTitleModule.value.title = editingTitle.value.trim();
    Message.success('标题已更新');
  }
  cancelTitleEdit();
};

const cancelTitleEdit = () => {
  titleEditVisible.value = false;
  editingTitle.value = '';
  currentEditingTitleModule.value = null;
};

const editModuleContent = (module: DocumentModule) => {
  editingContentId.value = module.id;
  editingContent.value = module.content;
  nextTick(() => {
    contentTextarea.value?.focus();
  });
};

const saveContent = async (module: DocumentModule) => {
  if (editingContent.value.trim()) {
    // TODO: 调用API保存内容
    module.content = editingContent.value.trim();
    Message.success('内容已更新');
  }
  cancelContentEdit();
};

const cancelContentEdit = () => {
  editingContentId.value = null;
  editingContent.value = '';
};

const splitAtCursor = (module: DocumentModule) => {
  // TODO: 实现在光标位置拆分模块
  Message.info('模块拆分功能开发中...');
};

const splitModule = (module: DocumentModule) => {
  // TODO: 实现模块拆分逻辑
  Message.info('模块拆分功能开发中...');
};

const mergeSelectedModules = async () => {
  if (selectedModules.value.length < 2) {
    Message.warning('请至少选择两个模块进行合并');
    return;
  }
  // TODO: 实现模块合并逻辑
  Message.success(`已合并 ${selectedModules.value.length} 个模块`);
  clearSelection();
  await loadDocument();
};

const deleteSelectedModules = async () => {
  if (selectedModules.value.length === 0) {
    Message.warning('请选择要删除的模块');
    return;
  }
  // TODO: 实现批量删除逻辑
  Message.success(`已删除 ${selectedModules.value.length} 个模块`);
  clearSelection();
  await loadDocument();
};

const clearSelection = () => {
  selectedModules.value = [];
};

// 生命周期
onMounted(() => {
  loadDocument();
});
</script>

<style scoped>
.document-detail {
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
  gap: 24px; /* 增加左侧和右侧区域之间的间距 */
}

.header-left {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 16px; /* 元素之间的间距 */
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
  margin-right: 8px; /* 增加状态标签右侧额外间距 */
}

.header-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0; /* 防止操作按钮被压缩 */
}

.info-section {
  margin-bottom: 24px;
}

.info-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.info-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  margin-bottom: 16px;
  align-items: center;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.label {
  font-weight: 500;
  color: #86909c;
  font-size: 14px;
  white-space: nowrap;
}

.info-item span:not(.label) {
  font-size: 14px;
  color: #1d2129;
}

.description {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  border-top: 1px solid #f2f3f5;
  padding-top: 16px;
  max-width: 100%;
  overflow: hidden; /* 确保容器不溢出 */
}

.description p,
.description .description-text {
  margin: 0;
  line-height: 1.6;
  /* 添加文本省略处理 */
  max-height: 4.8em; /* 限制最多显示3行文本 (1.6 * 3) */
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-inline-box;
  -webkit-line-clamp: 3;
  line-clamp: 3; /* 标准属性 */
  -webkit-box-orient: vertical;
  word-break: break-word;
  word-wrap: break-word;
  cursor: pointer; /* 添加鼠标指针提示 */
}

/* 确保tooltip内容正确换行 */
:deep(.arco-tooltip-content-inner) {
  max-width: 400px;
  white-space: normal;
  word-break: break-word;
}

.modules-section {
  margin-bottom: 24px;
}

.modules-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.modules-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.modules-actions {
  display: flex;
  gap: 8px;
}

.modules-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.module-item {
  border: 1px solid #f2f3f5;
  border-radius: 8px;
  padding: 16px;
  background: #fafafa;
  transition: all 0.3s;
  margin-bottom: 16px;
}

.module-item:hover {
  border-color: #00a0e9;
  box-shadow: 0 2px 8px rgba(0, 160, 233, 0.1);
}



.module-item.editing {
  border-color: #00a0e9;
  background: #f0f8ff;
}

.module-item.selected {
  border-color: #00a0e9;
  background: #e6f4ff;
}

.module-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.module-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.module-checkbox {
  flex-shrink: 0;
}

.module-order-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: #00a0e9;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.module-info {
  flex: 1;
  min-width: 0;
}

.module-title {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.module-title:hover .edit-hint {
  opacity: 1;
}

.edit-hint {
  opacity: 0;
  transition: opacity 0.2s;
  font-size: 12px;
  color: #86909c;
}

.title-edit {
  margin-bottom: 8px;
}

.module-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.page-range {
  font-size: 12px;
  color: #86909c;
}

.module-actions {
  display: flex;
  gap: 4px;
}

.module-content {
  position: relative;
}

.content-preview {
  max-height: 100px;
  overflow: hidden;
  line-height: 1.6;
  color: #4e5969;
  white-space: pre-wrap;
  transition: max-height 0.3s;
}

.content-preview.expanded {
  max-height: none;
}

.expand-btn {
  margin-top: 8px;
}

/* 新增的交互式编辑样式 */
.content-edit {
  margin-top: 16px;
}

.content-textarea {
  width: 100%;
  margin-bottom: 12px;
}

.edit-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.content-display {
  margin-top: 16px;
  padding: 12px;
  background: white;
  border-radius: 6px;
  border: 1px solid #f2f3f5;
  cursor: pointer;
  transition: all 0.2s;
}

.content-display:hover {
  border-color: #00a0e9;
  background: #f8faff;
}

.content-text {
  line-height: 1.6;
  color: #4e5969;
  white-space: pre-wrap;
  margin-bottom: 8px;
}

.content-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #86909c;
  opacity: 0;
  transition: opacity 0.2s;
}

.content-display:hover .content-hint {
  opacity: 1;
}

/* 批量操作工具栏 */
.batch-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #e6f4ff;
  border: 1px solid #91caff;
  border-radius: 6px;
  margin-top: 16px;
}

.batch-info {
  font-size: 14px;
  color: #1677ff;
  font-weight: 500;
}

.batch-buttons {
  display: flex;
  gap: 8px;
}

.empty-state,
.loading-state {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 新的统一展示样式 */
.document-content-container {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.modules-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.modules-count {
  font-size: 14px;
  color: #6c757d;
  font-weight: 500;
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

.unified-content {
  padding: 24px;
  line-height: 1.8;
  font-size: 14px;
  color: #333;
  max-height: 600px;
  overflow-y: auto;
}

.unified-content.editing-mode {
  background: #fafbfc;
}

.content-segment {
  position: relative;
  margin-bottom: 20px;
  transition: all 0.2s ease;
  cursor: pointer;
  border-radius: 8px;
  padding: 16px;
  border: 2px solid #e9ecef;
  background: #fafbfc;
  min-height: 60px;
}

.content-segment:hover {
  border-color: rgba(0, 160, 233, 0.4);
  background: rgba(0, 160, 233, 0.05);
  box-shadow: 0 2px 8px rgba(0, 160, 233, 0.1);
}

.content-segment.selected {
  background: rgba(0, 160, 233, 0.1);
  border: 2px solid rgba(0, 160, 233, 0.5);
  box-shadow: 0 4px 12px rgba(0, 160, 233, 0.2);
}

.content-segment.highlighted {
  background: rgba(0, 160, 233, 0.08);
  border-color: rgba(0, 160, 233, 0.3);
}

.content-segment.editing {
  background: #fff;
  border: 2px solid #00a0e9;
  box-shadow: 0 4px 16px rgba(0, 160, 233, 0.25);
}

.module-label {
  position: absolute;
  top: -12px;
  left: 12px;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  color: white;
  font-weight: 600;
  z-index: 10;
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.15);
  border: 2px solid rgba(255, 255, 255, 0.2);
}

.label-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.module-number {
  background: rgba(255, 255, 255, 0.2);
  padding: 2px 6px;
  border-radius: 2px;
  font-weight: 600;
}

.module-title-inline {
  cursor: pointer;
}

.module-title-inline:hover {
  text-decoration: underline;
}

.label-actions {
  display: flex;
  gap: 4px;
}

.segment-content {
  white-space: pre-wrap;
  padding: 12px;
  border-radius: 6px;
  transition: all 0.2s;
  background: white;
  margin-top: 8px;
  line-height: 1.6;
  font-size: 14px;
  color: #333;
  min-height: 40px;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.inline-content-edit {
  margin: 8px 0;
}

.edit-hint {
  font-size: 12px;
  color: #86909c;
  margin-top: 4px;
  text-align: right;
}

.selection-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: #e6f4ff;
  border-top: 1px solid #91caff;
  margin-top: 16px;
}

.selection-details {
  font-size: 14px;
  color: #1677ff;
  font-weight: 500;
}

.selected-titles {
  font-weight: normal;
  color: #666;
  margin-left: 8px;
}

.selection-actions {
  display: flex;
  gap: 8px;
}


/* 工作流程指示器样式 */
.workflow-indicator {
  margin-bottom: 24px;
}

.workflow-card {
  border: 1px solid #e5e6eb;
}

.workflow-card :deep(.arco-card-header) {
  background: #f7f8fa;
  border-bottom: 1px solid #e5e6eb;
}

.workflow-card :deep(.arco-steps-item-title) {
  font-size: 13px;
}

.workflow-card :deep(.arco-steps-item-description) {
  font-size: 12px;
  color: #86909c;
}

/* 上传提示样式 */
.upload-hint {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e6eb;
}

/* 评审报告区域样式 */
.review-report-section {
  margin-bottom: 24px;
}

.review-report-card {
  border: 1px solid #e5e6eb;
}

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
  font-size: 20px;
}

.report-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.report-date {
  color: #86909c;
  font-size: 14px;
}

.score-circle {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #165dff, #722ed1);
  color: white;
}

.score-number {
  font-size: 24px;
  font-weight: bold;
  line-height: 1;
}

.score-label {
  font-size: 12px;
  margin-top: 2px;
}

.issues-stats {
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  border-radius: 8px;
  min-width: 80px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.stat-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-item.active {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
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
  font-size: 20px;
  font-weight: bold;
  line-height: 1;
}

.stat-label {
  font-size: 12px;
  color: #86909c;
  margin-top: 4px;
}

.report-summary,
.report-recommendations {
  margin-bottom: 20px;
}

.report-summary h4,
.report-recommendations h4 {
  margin: 0 0 8px 0;
  color: #1d2129;
  font-size: 14px;
}

.report-summary p {
  margin: 0;
  color: #4e5969;
  line-height: 1.6;
}

.recommendations-content {
  color: #4e5969;
  line-height: 1.6;
  white-space: pre-wrap;
}

/* 筛选后的问题列表样式 */
.filtered-issues {
  margin-top: 20px;
}

.filtered-issues h4 {
  margin-bottom: 16px;
  color: #1d2129;
  font-size: 16px;
  font-weight: 600;
}

.no-issues {
  text-align: center;
  padding: 40px 0;
}

.filtered-issues .issues-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 0;
}

.issue-item {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 16px;
  transition: all 0.2s ease;
}

.issue-item:hover {
  border-color: #165dff;
  box-shadow: 0 2px 8px rgba(22, 93, 255, 0.1);
}

.issue-header {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.issue-content h5 {
  margin: 0 0 8px 0;
  color: #1d2129;
  font-size: 14px;
  font-weight: 600;
}

.issue-content p {
  margin: 0 0 8px 0;
  color: #4e5969;
  line-height: 1.5;
}

.issue-suggestion {
  margin-top: 8px;
  padding: 8px 12px;
  background: #f7f8fa;
  border-radius: 4px;
  font-size: 13px;
  color: #4e5969;
}

.issue-suggestion strong {
  color: #1d2129;
}

.module-results,
.issues-list {
  margin-top: 24px;
}

.module-results h4,
.issues-list h4 {
  margin: 0 0 16px 0;
  color: #1d2129;
  font-size: 16px;
  font-weight: 600;
}

.module-results-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.module-result-item {
  padding: 16px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  background: #f7f8fa;
}

.module-result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.module-result-header h5 {
  margin: 0;
  color: #1d2129;
  font-size: 14px;
  font-weight: 600;
}

.issues-count {
  color: #86909c;
  font-size: 12px;
}

.module-analysis {
  color: #4e5969;
  font-size: 13px;
  line-height: 1.5;
}

.issues-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.issue-item {
  padding: 16px;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
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
  font-size: 12px;
}

.issue-title {
  margin: 0 0 8px 0;
  color: #1d2129;
  font-size: 14px;
  font-weight: 600;
}

.issue-description {
  margin: 0 0 8px 0;
  color: #4e5969;
  font-size: 13px;
  line-height: 1.5;
}

.issue-suggestion {
  color: #4e5969;
  font-size: 13px;
  line-height: 1.5;
  background: #f7f8fa;
  padding: 8px;
  border-radius: 4px;
}
</style>
