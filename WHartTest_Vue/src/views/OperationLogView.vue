<template>
  <div class="operation-log-page">
    <!-- 无访问权限展示 -->
    <div v-if="!hasPermission" class="access-denied">
      <div class="denied-card">
        <div class="denied-icon">
          <icon-exclamation-polygon-fill />
        </div>
        <h2>{{ tl('无访问权限') }}</h2>
        <p>{{ tl('操作审计日志仅系统管理员或被授权的审计人员可访问。') }}</p>
        <a-button type="primary" @click="$router.push('/')">{{ tl('返回首页') }}</a-button>
      </div>
    </div>

    <!-- 主体内容 -->
    <template v-else>
      <div class="page-header">
        <div class="filter-box">
          <a-space wrap :size="10">
            <a-input 
              v-model="filterForm.search" 
              :placeholder="tl('搜索用户名、模块、路径')" 
              style="width: 240px"
              allow-clear
              @keyup.enter="handleSearch"
            >
              <template #prefix><icon-search /></template>
            </a-input>

            <a-input 
              v-model="filterForm.module" 
              :placeholder="tl('操作模块')" 
              style="width: 140px"
              allow-clear
              @keyup.enter="handleSearch"
            />

            <a-select v-model="filterForm.method" :placeholder="tl('请求方法')" style="width: 140px" allow-clear>
              <a-option value="POST">POST</a-option>
              <a-option value="PUT">PUT</a-option>
              <a-option value="PATCH">PATCH</a-option>
              <a-option value="DELETE">DELETE</a-option>
              <a-option value="GET">GET</a-option>
            </a-select>

            <a-select v-model="filterForm.response_code" :placeholder="tl('状态码')" style="width: 130px" allow-clear>
              <a-option :value="200">200</a-option>
              <a-option :value="201">201</a-option>
              <a-option :value="204">204</a-option>
              <a-option :value="400">400</a-option>
              <a-option :value="401">401</a-option>
              <a-option :value="403">403</a-option>
              <a-option :value="404">404</a-option>
              <a-option :value="500">500</a-option>
            </a-select>

            <a-range-picker
              v-model="filterForm.dateRange"
              show-time
              format="YYYY-MM-DD HH:mm:ss"
              style="width: 320px"
            />

            <a-button type="primary" @click="handleSearch">
              <template #icon><icon-search /></template>
              {{ tl('查询') }}
            </a-button>
            <a-button @click="handleReset">
              <template #icon><icon-refresh /></template>
              {{ tl('重置') }}
            </a-button>
          </a-space>
        </div>

        <div v-if="canViewCleanupSettings" class="header-actions">
            <a-button
              v-if="canEditCleanupSettings"
              status="danger"
              :loading="cleanupNowLoading"
              @click="handleCleanupNow"
            >
              <template #icon><icon-delete /></template>
              {{ tl('立即清理') }}
            </a-button>

          <a-button @click="cleanupSettingsVisible = true">
            <template #icon><icon-settings /></template>
            {{ tl('清理设置') }}
          </a-button>
        </div>
      </div>

      <a-table
        :columns="columns"
        :data="logs"
        :loading="loading"
        :pagination="pagination"
        :bordered="false"
        :scroll="{ y: 'calc(100vh - 240px)' }"
        @page-change="handlePageChange"
        @page-size-change="handlePageSizeChange"
      >
        <template #module="{ record }">
          <span>{{ translateOperationLogModule(record.module) }}</span>
        </template>

        <template #action="{ record }">
          <span>{{ translateOperationLogAction(record.action, record.module) }}</span>
        </template>

        <!-- 请求方法渲染 -->
        <template #method="{ record }">
          <a-tag :color="getMethodTagColor(record.method)">
            {{ record.method }}
          </a-tag>
        </template>

        <!-- 响应状态渲染 -->
        <template #response_code="{ record }">
          <a-tag :color="getStatusTagColor(record.response_code)">
            {{ record.response_code }}
          </a-tag>
        </template>

        <!-- 执行耗时渲染 -->
        <template #duration="{ record }">
          <span :class="['duration-text', { 'slow-request': record.duration > 1000 }]">
            {{ record.duration }} ms
          </span>
        </template>

        <!-- 路径样式渲染 -->
        <template #path="{ record }">
          <span class="mono-text code-bubble" :title="record.path">
            {{ record.path }}
          </span>
        </template>

        <!-- 操作按钮渲染 -->
        <template #optional="{ record }">
          <a-button type="primary" size="mini" @click="showLogDetail(record)">
            <template #icon><icon-eye /></template>
            {{ tl('明细') }}
          </a-button>
        </template>
      </a-table>
    </template>

    <!-- 详情抽屉 (Drawer) -->
    <a-drawer
      :visible="drawerVisible"
      @cancel="closeDrawer"
      :width="640"
      :footer="false"
      unmount-on-close
    >
      <template #title>
        <div class="drawer-header-title">
          <icon-info-circle class="drawer-header-icon" />
          <span>{{ tl('操作日志详细明细') }}</span>
        </div>
      </template>

      <div v-if="currentLog" class="drawer-content">
        <a-descriptions :column="1" bordered>
          <a-descriptions-item :label="tl('操作人')">{{ currentLog.username }}</a-descriptions-item>
          <a-descriptions-item :label="tl('操作模块')">{{ translateOperationLogModule(currentLog.module) }}</a-descriptions-item>
          <a-descriptions-item :label="tl('操作描述')">{{ translateOperationLogAction(currentLog.action, currentLog.module) }}</a-descriptions-item>
          <a-descriptions-item :label="tl('请求方法')">
            <a-tag :color="getMethodTagColor(currentLog.method)">{{ currentLog.method }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="tl('请求路径')">
            <span class="mono-text">{{ currentLog.path }}</span>
          </a-descriptions-item>
          <a-descriptions-item :label="tl('IP地址')">{{ currentLog.ip_address || 'N/A' }}</a-descriptions-item>
          <a-descriptions-item :label="tl('状态码')">
            <a-tag :color="getStatusTagColor(currentLog.response_code)">{{ currentLog.response_code }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="tl('执行耗时')">
            <span :class="{ 'slow-request': currentLog.duration > 1000 }">{{ currentLog.duration }} ms</span>
          </a-descriptions-item>
          <a-descriptions-item :label="tl('操作时间')">{{ currentLog.created_at }}</a-descriptions-item>
          <a-descriptions-item :label="tl('User-Agent')">
            <span class="ua-text">{{ currentLog.user_agent }}</span>
          </a-descriptions-item>
        </a-descriptions>

        <!-- 请求数据展示 -->
        <div class="audit-section">
          <div class="section-title-wrapper">
            <h3 class="section-title"><icon-code /> {{ tl('请求数据 (Request Data)') }}</h3>
            <a-button type="text" size="mini" class="copy-btn" @click="copyToClipboard(currentLog.request_data)">
              <template #icon><icon-copy /></template>
              {{ tl('复制') }}
            </a-button>
          </div>
          <pre class="json-code"><code>{{ formatJson(currentLog.request_data) }}</code></pre>
        </div>

        <!-- 响应数据展示 -->
        <div class="audit-section">
          <div class="section-title-wrapper">
            <h3 class="section-title"><icon-code /> {{ tl('响应数据 (Response Data)') }}</h3>
            <a-button type="text" size="mini" class="copy-btn" @click="copyToClipboard(currentLog.response_data)">
              <template #icon><icon-copy /></template>
              {{ tl('复制') }}
            </a-button>
          </div>
          <pre class="json-code"><code>{{ formatJson(currentLog.response_data) }}</code></pre>
        </div>
      </div>
    </a-drawer>

    <operation-log-cleanup-settings-modal
      v-model:visible="cleanupSettingsVisible"
      :can-edit="canEditCleanupSettings"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue';
import { useAuthStore } from '@/store/authStore';
import { useAppI18n } from '@/composables/useAppI18n';
import { Message, Modal } from '@arco-design/web-vue';
import { 
  cleanupOperationLogsNow,
  getOperationLogList, 
  type OperationLog 
} from '@/services/operationLogService';
import OperationLogCleanupSettingsModal from '@/components/operation-log/OperationLogCleanupSettingsModal.vue';
import {
  IconSearch,
  IconRefresh,
  IconEye,
  IconDelete,
  IconSettings,
  IconCopy,
  IconCode,
  IconInfoCircle,
  IconExclamationPolygonFill
} from '@arco-design/web-vue/es/icon';

// 国际化
const { tl, isEnglish } = useAppI18n();

// 鉴权
const authStore = useAuthStore();
const hasPermission = computed(() => {
  return authStore.user?.is_staff || 
         authStore.hasPermission('accounts.view_operationlog') || 
         authStore.hasPermission('operation_logs.view_operationlog');
});
const canViewCleanupSettings = computed(() => canEditCleanupSettings.value);
const canEditCleanupSettings = computed(() => {
  return authStore.user?.is_staff || authStore.hasPermission('operation_logs.delete_operationlog');
});

// 数据变量
const logs = ref<OperationLog[]>([]);
const totalLogs = ref(0);
const loading = ref(false);
const cleanupNowLoading = ref(false);
const cleanupSettingsVisible = ref(false);

// 筛选表单
const filterForm = reactive({
  search: '',
  module: '',
  method: '',
  response_code: undefined as number | undefined,
  dateRange: [] as string[]
});

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50, 100]
});

// Table 列配置
const columns = computed(() => [
  {
    title: tl('操作时间'),
    dataIndex: 'created_at',
    width: 170,
  },
  {
    title: tl('操作人'),
    dataIndex: 'username',
    width: 120,
  },
  {
    title: tl('操作模块'),
    dataIndex: 'module',
    slotName: 'module',
    width: 130,
  },
  {
    title: tl('操作描述'),
    dataIndex: 'action',
    slotName: 'action',
    width: 180,
  },
  {
    title: tl('请求方法'),
    dataIndex: 'method',
    slotName: 'method',
    width: 120,
    align: 'center' as const,
  },
  {
    title: tl('请求路径'),
    dataIndex: 'path',
    slotName: 'path',
  },
  {
    title: tl('状态码'),
    dataIndex: 'response_code',
    slotName: 'response_code',
    width: 110,
    align: 'center' as const,
  },
  {
    title: tl('耗时'),
    dataIndex: 'duration',
    slotName: 'duration',
    width: 100,
    align: 'right' as const,
  },
  {
    title: tl('操作'),
    slotName: 'optional',
    width: 100,
    align: 'center' as const,
  },
]);

// 详情 Drawer
const drawerVisible = ref(false);
const currentLog = ref<OperationLog | null>(null);

// 初始化加载
onMounted(() => {
  if (hasPermission.value) {
    loadLogs();
  }
});

// 获取日志数据
const loadLogs = async () => {
  loading.value = true;
  try {
    const params: any = {
      page: pagination.current,
      pageSize: pagination.pageSize,
      search: filterForm.search || undefined,
      module: filterForm.module || undefined,
      method: filterForm.method || undefined,
      response_code: filterForm.response_code || undefined,
    };

    if (filterForm.dateRange && filterForm.dateRange.length === 2) {
      params.start_time = filterForm.dateRange[0];
      params.end_time = filterForm.dateRange[1];
    }

    const res = await getOperationLogList(params);
    if (res.success && res.data) {
      logs.value = res.data;
      totalLogs.value = res.total || 0;
      pagination.total = res.total || 0;
    } else {
      Message.error(res.error || tl('加载日志失败'));
    }
  } catch (error: any) {
    Message.error(error.message || tl('加载日志时发生网络异常'));
  } finally {
    loading.value = false;
  }
};

const handleCleanupNow = () => {
  Modal.confirm({
    title: tl('立即清理操作日志'),
    content: tl('系统将立刻删除超过当前保留天数的操作日志，是否继续？'),
    okButtonProps: {
      status: 'danger',
    },
    onOk: async () => {
      cleanupNowLoading.value = true;
      try {
        const res = await cleanupOperationLogsNow();
        if (res.success && res.data) {
          Message.success(
            `${tl('立即清理完成，已删除')} ${res.data.deleted_count} ${tl('条过期日志，当前保留')} ${res.data.retention_days} ${tl('天')}`,
          );
          await loadLogs();
          return;
        }

        Message.error(res.error || tl('立即清理失败'));
      } catch (error: any) {
        Message.error(error.message || tl('立即清理失败'));
      } finally {
        cleanupNowLoading.value = false;
      }
    },
  });
};

// 搜索
const handleSearch = () => {
  pagination.current = 1;
  loadLogs();
};

// 重置
const handleReset = () => {
  filterForm.search = '';
  filterForm.module = '';
  filterForm.method = '';
  filterForm.response_code = undefined;
  filterForm.dateRange = [];
  pagination.current = 1;
  loadLogs();
};

// 分页变化
const handlePageChange = (page: number) => {
  pagination.current = page;
  loadLogs();
};

// 页数大小变化
const handlePageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
  pagination.current = 1;
  loadLogs();
};

// 显示日志详情 Drawer
const showLogDetail = (record: OperationLog) => {
  currentLog.value = record;
  drawerVisible.value = true;
};

// 关闭 Drawer
const closeDrawer = () => {
  drawerVisible.value = false;
};

const OPERATION_LOG_ACRONYMS = new Set(['AI', 'API', 'DRF', 'HTTP', 'IP', 'JWT', 'LLM', 'MCP', 'UI']);
const ASCII_LOG_TEXT_PATTERN = /^[A-Za-z0-9][A-Za-z0-9\s/_-]*$/;

const toEnglishTitleCase = (value: string) => value
  .split(/[\s/_-]+/)
  .filter(Boolean)
  .map((segment) => {
    const upperSegment = segment.toUpperCase();
    if (OPERATION_LOG_ACRONYMS.has(upperSegment)) {
      return upperSegment;
    }

    return segment.charAt(0).toUpperCase() + segment.slice(1).toLowerCase();
  })
  .join(' ');

const translateOperationLogFragment = (value: string) => {
  const text = value?.trim() || '';
  if (!text) {
    return '';
  }

  const translated = tl(text);
  if (translated !== text) {
    return translated;
  }

  if (isEnglish.value && ASCII_LOG_TEXT_PATTERN.test(text)) {
    return toEnglishTitleCase(text);
  }

  return text;
};

const translateOperationLogModule = (module: string) => translateOperationLogFragment(module);

const translateOperationLogAction = (action: string, module: string) => {
  const actionText = action?.trim() || '';
  const moduleText = module?.trim() || '';
  if (!actionText) {
    return '';
  }

  const translatedAction = tl(actionText);
  if (translatedAction !== actionText) {
    return translatedAction;
  }

  if (moduleText && actionText.toLowerCase().endsWith(moduleText.toLowerCase())) {
    const actionPrefix = actionText.slice(0, actionText.length - moduleText.length).trim();
    return [
      actionPrefix ? translateOperationLogFragment(actionPrefix) : '',
      translateOperationLogFragment(moduleText),
    ].filter(Boolean).join(' ');
  }

  return translateOperationLogFragment(actionText);
};

// JSON 载荷高亮格式化
const formatJson = (jsonStr: string) => {
  if (!jsonStr) return tl('无载荷内容 / Empty Body');
  try {
    const parsed = JSON.parse(jsonStr);
    return JSON.stringify(parsed, null, 2);
  } catch (e) {
    return jsonStr;
  }
};

// 复制到剪切板（兼容 HTTP / 非安全上下文部署）
const copyToClipboard = async (text: string) => {
  if (!text) {
    Message.warning(tl('无内容可复制'));
    return;
  }

  const targetText = formatJson(text);

  try {
    // Clipboard API 仅在 HTTPS、localhost 等安全上下文可用。
    // 服务器如果通过 HTTP 访问，navigator.clipboard 可能为 undefined。
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(targetText);
      Message.success(tl('复制成功！已写入系统剪切板'));
      return;
    }

    // 回退方案：兼容 HTTP 部署环境
    const textArea = document.createElement('textarea');
    textArea.value = targetText;
    textArea.setAttribute('readonly', 'readonly');
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    textArea.style.top = '-9999px';
    textArea.style.opacity = '0';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    const successful = document.execCommand('copy');
    document.body.removeChild(textArea);

    if (successful) {
      Message.success(tl('复制成功！已写入系统剪切板'));
    } else {
      Message.error(tl('复制失败，请手动选择复制'));
    }
  } catch (error) {
    console.error('复制失败:', error);
    Message.error(tl('复制失败，请手动选择复制'));
  }
};

// 各种标签色彩辅助器
const getMethodTagColor = (method: string) => {
  const colors: Record<string, string> = {
    'POST': 'green',
    'PUT': 'arcoblue',
    'PATCH': 'orange',
    'DELETE': 'red',
    'GET': 'gray'
  };
  return colors[method] || 'gray';
};

const getStatusTagColor = (code: number | null) => {
  if (!code) return 'gray';
  if (code >= 200 && code < 300) return 'green';
  if (code >= 300 && code < 400) return 'arcoblue';
  if (code >= 400 && code < 500) return 'warning';
  return 'danger';
};
</script>

<style scoped>
.operation-log-page {
  background-color: var(--theme-card-bg, #fff);
  color: var(--theme-page-text, var(--color-text-1));
  border: 1px solid var(--theme-card-border, transparent);
  border-radius: 8px;
  padding: 20px;
  box-shadow: var(--theme-card-shadow, 0 0 10px rgba(0, 0, 0, 0.15));
  height: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.filter-box {
  display: flex;
  align-items: center;
  flex: 1;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.duration-text {
  font-family: 'Consolas', monospace;
  font-weight: 500;
}

.slow-request {
  color: var(--color-danger-light-4) !important;
  font-weight: bold;
}

.mono-text {
  font-family: 'Consolas', 'Courier New', Courier, monospace;
  font-size: 13px;
}

.code-bubble {
  background-color: var(--color-neutral-2);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--color-text-2);
  max-width: 320px;
  display: inline-block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
}

/* 详情抽屉样式 */
.drawer-header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 18px;
}

.drawer-header-icon {
  color: var(--color-primary-light-4);
  font-size: 20px;
}

.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 10px 0;
}

.audit-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-2);
  margin: 0;
}

.section-title-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.copy-btn {
  color: var(--color-primary-light-4);
  padding: 0 4px;
}

.copy-btn:hover {
  background-color: var(--color-primary-light-1);
}

.ua-text {
  font-size: 12px;
  color: var(--color-text-3);
  line-height: 1.4;
  word-break: break-all;
  display: block;
}

/* VS Code风格格式化代码块 */
.json-code {
  background: #1e1e1e;
  color: #a9b7c6;
  padding: 16px;
  border-radius: 8px;
  max-height: 280px;
  overflow: auto;
  font-family: 'Consolas', 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.5;
  border: 1px solid #2d2d2d;
  margin: 0;
  box-shadow: inset 0 2px 8px rgba(0,0,0,0.3);
}

.json-code::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.json-code::-webkit-scrollbar-thumb {
  background: #3c3f41;
  border-radius: 3px;
}

.json-code::-webkit-scrollbar-track {
  background: #1e1e1e;
}

/* 权限拦截卡片 */
.access-denied {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  min-height: calc(100vh - 280px);
}

.denied-card {
  text-align: center;
  background: var(--color-bg-2);
  padding: 40px;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.05);
  max-width: 420px;
  border: 1px solid var(--color-neutral-3);
}

.denied-icon {
  font-size: 54px;
  color: var(--color-warning-light-4);
  margin-bottom: 20px;
}

.denied-card h2 {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 10px 0;
  color: var(--color-text-1);
}

.denied-card p {
  color: var(--color-text-3);
  margin-bottom: 24px;
  font-size: 14px;
  line-height: 1.6;
}
</style>
