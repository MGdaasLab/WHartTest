<template>
  <div class="remote-mcp-management">
    <div class="page-header">
      <h2>{{ pageText.pageTitle }}</h2>
      <a-button type="primary" @click="showAddForm">{{ pageText.addRemoteMcp }}</a-button>
    </div>

    <!-- 远程MCP配置列表 -->
    <a-card class="content-card">
      <a-table
        :data="mcpConfigs"
        :columns="columns"
        :loading="loading"
        :pagination="pagination"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
        row-key="id"
      >
        <template #is_active="{ record }">
          <a-tag :color="record.is_active ? 'green' : 'red'">
            {{ record.is_active ? pageText.enabled : pageText.disabled }}
          </a-tag>
        </template>

        <template #is_global="{ record }">
          <a-tag :color="record.is_global ? 'green' : 'gray'">
            {{ record.is_global ? pageText.globalShared : pageText.private }}
          </a-tag>
        </template>

        <template #auth_status="{ record }">
          <template v-if="record.auth_type === 'oauth'">
            <a-tag :color="record.oauth_authorized ? 'green' : 'orange'">
              {{ record.oauth_authorized ? pageText.oauthAuthorized : pageText.oauthNotAuthorized }}
            </a-tag>
            <div v-if="record.is_global && !record.is_owner && record.oauth_authorized" style="margin-top:2px; font-size:12px; color:#888;">
              {{ pageText.sharedOauthTip }}
            </div>
          </template>
          <span v-else>{{ pageText.noAuth }}</span>
        </template>

        <template #created_at="{ record }">
          {{ formatDate(record.created_at) }}
        </template>

        <template #operations="{ record }">
          <a-space>
            <a-button type="text" size="small" @click="showEditForm(record)">
              <template #icon><icon-edit /></template>
              {{ pageText.edit }}
            </a-button>
            <a-button type="text" status="danger" size="small" @click="showDeleteConfirm(record)">
              <template #icon><icon-delete /></template>
              {{ pageText.delete }}
            </a-button>
            <a-button
              type="text"
              :status="record.is_active ? 'warning' : 'success'"
              size="small"
              @click="toggleStatus(record)"
            >
              <template #icon>
                <icon-eye-invisible v-if="record.is_active" />
                <icon-eye v-else />
              </template>
              {{ record.is_active ? pageText.disable : pageText.enable }}
            </a-button>
            <a-button
              type="text"
              status="success"
              size="small"
              @click="pingConfig(record)"
              :loading="record.pinging"
            >
              <template #icon><icon-link /></template>
              {{ pageText.checkConnectivity }}
            </a-button>
            <a-button
              v-if="record.auth_type === 'oauth' && record.can_authorize"
              type="text"
              size="small"
              :status="record.oauth_authorized ? 'danger' : 'normal'"
              @click="record.oauth_authorized ? handleDisconnectOAuth(record) : handleAuthorizeOAuth(record)"
            >
              <template #icon><icon-safe /></template>
              {{ record.oauth_authorized ? pageText.oauthDisconnect : pageText.oauthAuthorize }}
            </a-button>
            <a-button
              v-else-if="record.auth_type === 'oauth' && !record.can_authorize && record.is_global && record.oauth_authorized"
              type="text"
              size="small"
              disabled
            >
              {{ pageText.sharedOauthAvailable }}
            </a-button>
          </a-space>
        </template>
      </a-table>

      <!-- 调试信息 -->
      <div v-if="mcpConfigs.length === 0 && !loading" class="empty-data">
        <p>{{ pageText.noData }}</p>
      </div>
      <div v-if="mcpConfigs.length > 0" class="debug-info" style="margin-top: 10px; font-size: 12px; color: var(--theme-text-tertiary);">
        <p>{{ pageText.currentDataCount(mcpConfigs.length) }}</p>
      </div>
    </a-card>

    <!-- 添加/编辑远程MCP配置的弹窗 -->
    <a-modal
      v-model:visible="modalVisible"
      :title="isEditing ? pageText.editRemoteMcpTitle : pageText.addRemoteMcpTitle"
      :ok-text="pageText.confirm"
      :cancel-text="pageText.cancel"
      @cancel="closeModal"
      @before-ok="handleSubmit"
    >
      <a-form ref="formRef" :model="formData" :rules="formRules" label-align="left">
        <a-form-item field="name" :label="pageText.name" required>
          <a-input v-model="formData.name" :placeholder="pageText.namePlaceholder" />
        </a-form-item>
        <a-form-item field="url" :label="pageText.url" required>
          <a-input v-model="formData.url" :placeholder="pageText.urlPlaceholder" />
        </a-form-item>
        <a-form-item field="transport" :label="pageText.transport" required>
          <a-select v-model="formData.transport" :placeholder="pageText.transportPlaceholder">
            <a-option value="stdio">stdio</a-option>
            <a-option value="streamable_http">streamable_http</a-option>
            <a-option value="sse">sse</a-option>
          </a-select>
        </a-form-item>
        <a-form-item field="headers" :label="pageText.headers">
          <a-textarea
            v-model="formData.headersStr"
            :placeholder="pageText.headersPlaceholder"
            :auto-size="{ minRows: 3, maxRows: 5 }"
          />
        </a-form-item>
        <a-form-item field="auth_type" :label="pageText.authType">
          <a-radio-group v-model="formData.auth_type" type="button">
            <a-radio value="none">{{ pageText.authNone }}</a-radio>
            <a-radio value="oauth">{{ pageText.authOAuth }}</a-radio>
          </a-radio-group>
          <template #extra>
            <span class="form-tip">{{ pageText.authTypeTip }}</span>
          </template>
        </a-form-item>

        <template v-if="formData.auth_type === 'oauth'">
          <a-form-item field="oauth_client_id" :label="pageText.oauthClientId">
            <a-input v-model="formData.oauth_client_id" :placeholder="pageText.oauthClientIdPlaceholder" />
          </a-form-item>
          <a-form-item field="oauth_client_secret" :label="pageText.oauthClientSecret">
            <a-input-password v-model="formData.oauth_client_secret" :placeholder="pageText.oauthClientSecretPlaceholder" />
          </a-form-item>
          <a-form-item field="oauth_scope" :label="pageText.oauthScope">
            <a-input v-model="formData.oauth_scope" :placeholder="pageText.oauthScopePlaceholder" />
          </a-form-item>
          <a-form-item field="oauth_client_metadata_url" :label="pageText.oauthMetadataUrl">
            <a-input v-model="formData.oauth_client_metadata_url" :placeholder="pageText.oauthMetadataUrlPlaceholder" />
          </a-form-item>
          <a-alert type="info" style="margin-bottom: 16px;">
            <template #title>
              {{ isEditing && formData.id ? pageText.oauthEditTip : pageText.oauthCreateTip }}
            </template>
          </a-alert>
        </template>

        <a-form-item field="is_active" :label="pageText.status">
          <a-switch v-model="formData.is_active" />
        </a-form-item>
        <a-form-item field="is_global" :label="pageText.visibility">
          <a-switch v-model="formData.is_global" />
          <template #extra>
            <span class="form-tip">{{ pageText.visibilityTip }}</span>
          </template>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 删除确认弹窗 -->
    <a-modal
      v-model:visible="deleteModalVisible"
      :title="pageText.deleteConfirmTitle"
      :ok-text="pageText.confirm"
      :cancel-text="pageText.cancel"
      @ok="handleDelete"
      @cancel="deleteModalVisible = false"
      simple
    >
      <p>{{ pageText.deleteConfirmContent(currentConfig?.name || '') }}</p>
    </a-modal>

    <!-- OAuth 授权弹窗（支持自动/手动模式） -->
    <a-modal
      v-model:visible="oauthModalVisible"
      :title="pageText.oauthModalTitle"
      :footer="false"
      :width="640"
      @cancel="closeOAuthModal"
    >
      <a-spin :loading="oauthLoading">
        <template v-if="oauthAuthUrl">
          <a-alert :type="oauthRecord?.is_global ? 'warning' : 'info'" style="margin-bottom: 16px;">
            <template #title>
              {{ oauthRecord?.is_global ? pageText.sharedOauthAuthorizeStarted : pageText.privateOauthAuthorizeStarted }}
            </template>
          </a-alert>

          <!-- 自动授权等待状态卡片 -->
          <div style="background: var(--color-fill-2); border-radius: 8px; padding: 20px 16px; margin-bottom: 16px; text-align: center;">
            <div style="display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 16px; font-weight: 500; color: rgb(var(--primary-6)); font-size: 14px;">
              <a-spin :size="16" />
              <span>{{ pageText.oauthWaitingTip }}</span>
            </div>
            <a-space size="medium">
              <a-button type="primary" size="medium" @click="openOAuthUrl">
                <template #icon><icon-launch /></template>
                {{ pageText.openAuthUrl }}
              </a-button>
              <a-button size="medium" @click="copyOAuthUrl">
                <template #icon><icon-link /></template>
                {{ pageText.copy }}
              </a-button>
            </a-space>
          </div>

          <!-- 折叠手动备用输入区域 -->
          <a-collapse :bordered="false">
            <a-collapse-item :header="pageText.oauthManualCollapse" key="manual">
              <a-form layout="vertical">
                <a-form-item :label="pageText.oauthStep1">
                  <div style="display:flex; gap:8px; align-items:center;">
                    <a-input :model-value="oauthAuthUrl" readonly />
                    <a-button @click="copyOAuthUrl">{{ pageText.copy }}</a-button>
                  </div>
                </a-form-item>

                <a-form-item :label="pageText.oauthStep3">
                  <a-textarea
                    v-model="oauthCallbackUrl"
                    :placeholder="pageText.oauthCallbackPlaceholder"
                    :auto-size="{ minRows: 2, maxRows: 4 }"
                  />
                </a-form-item>

                <a-button
                  type="primary"
                  long
                  @click="handleCompleteOAuth"
                  :loading="oauthCompleting"
                  :disabled="!oauthCallbackUrl.trim()"
                >
                  {{ pageText.completeOAuth }}
                </a-button>
              </a-form>
            </a-collapse-item>
          </a-collapse>
        </template>
        <template v-else-if="!oauthLoading">
          <a-empty :description="pageText.oauthNoUrl" />
        </template>
      </a-spin>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue';
import { Message } from '@arco-design/web-vue';
import {
  IconEdit,
  IconDelete,
  IconEye,
  IconEyeInvisible,
  IconLink,
  IconSafe,
  IconLaunch
} from '@arco-design/web-vue/es/icon';
import {
  fetchRemoteMcpConfigs,
  createRemoteMcpConfig,
  updateRemoteMcpConfig,
  deleteRemoteMcpConfig,
  pingRemoteMcpConfig,
  authorizeRemoteMcpConfig,
  completeRemoteMcpConfigOAuth,
  disconnectRemoteMcpConfig,
  type RemoteMcpConfig
} from '@/services/remoteMcpConfigService';
import { useAppI18n } from '@/composables/useAppI18n';

const { isEnglish } = useAppI18n();
const pageText = computed(() => (
  isEnglish.value
    ? {
        pageTitle: 'MCP Configuration Management',
        addRemoteMcp: 'Add Remote MCP',
        enabled: 'Enabled',
        disabled: 'Disabled',
        edit: 'Edit',
        delete: 'Delete',
        enable: 'Enable',
        disable: 'Disable',
        checkConnectivity: 'Check connectivity',
        noData: 'No data',
        currentDataCount: (count: number) => `Current records: ${count}`,
        editRemoteMcpTitle: 'Edit Remote MCP Config',
        addRemoteMcpTitle: 'Add Remote MCP Config',
        confirm: 'Confirm',
        cancel: 'Cancel',
        name: 'Name',
        namePlaceholder: 'Enter config name',
        url: 'URL',
        urlPlaceholder: 'Enter MCP server URL',
        transport: 'Transport',
        transportPlaceholder: 'Select transport',
        headers: 'Headers',
        headersPlaceholder: 'Enter headers in JSON format, e.g. {"Authorization": "Bearer token"}',
        status: 'Status',
        visibility: 'Visibility',
        visibilityTip: 'Global sharing makes this config visible and usable by all users; private is visible only to you.',
        globalShared: 'Shared',
        private: 'Private',
        authType: 'Auth type',
        authNone: 'None',
        authOAuth: 'OAuth 2.0',
        authTypeTip: 'OAuth uses authorization code flow. Only the creator can authorize; shared MCPs are usable by all users after authorization.',
        oauthClientId: 'OAuth Client ID',
        oauthClientIdPlaceholder: 'Optional, leave empty for dynamic client registration',
        oauthClientSecret: 'OAuth Client Secret',
        oauthClientSecretPlaceholder: 'Optional, required for client_secret mode',
        oauthScope: 'OAuth Scope',
        oauthScopePlaceholder: 'Optional, space separated',
        oauthMetadataUrl: 'Client Metadata URL',
        oauthMetadataUrlPlaceholder: 'Optional, for URL-based client (CIMD)',
        oauthEditTip: 'After saving, use the OAuth authorize button in the list to complete authorization.',
        oauthCreateTip: 'You can configure OAuth fields now and authorize after saving.',
        oauthAuthorized: 'Authorized',
        oauthNotAuthorized: 'Not authorized',
        noAuth: 'None',
        oauthAuthorize: 'Authorize',
        oauthDisconnect: 'Disconnect',
        oauthDisconnectConfirm: 'Disconnect OAuth authorization? The saved token will be removed.',
        oauthDisconnectSuccess: 'OAuth authorization removed',
        oauthDisconnectFailed: 'Failed to remove OAuth authorization',
        oauthAuthorizeFailed: 'Failed to start OAuth authorization',
        oauthModalTitle: 'OAuth Authorization',
        oauthWaitingTip: 'Waiting for authorization... This modal will close automatically once authorization is completed in the new window.',
        oauthManualCollapse: "Didn't redirect automatically? Expand to enter callback URL manually",
        oauthStep1: '1. Copy the authorization URL',
        oauthStep2: '2. Open it in a browser and complete login',
        oauthStep3: '3. After authorized, copy the browser address bar URL back here',
        copy: 'Copy',
        copySuccess: 'Copied',
        openAuthUrl: 'Open authorization URL',
        oauthManualTip: 'For server deployment: open the URL manually, then paste the redirect URL back.',
        oauthCallbackPlaceholder: 'Paste the full callback URL from the browser address bar here (e.g. http://host/mcp_tools/oauth/callback/?code=...&state=...)',
        completeOAuth: 'Complete authorization',
        oauthNoUrl: 'No authorization URL yet. Please try again.',
        sharedOauthTip: 'Shared MCP: authorization is provided by the creator for all users.',
        sharedOauthAvailable: 'Shared & ready',
        sharedOauthAuthorizeStarted: 'This shared MCP will be available to all users after the creator authorizes it.',
        privateOauthAuthorizeStarted: 'This private MCP is only visible and callable by you.',
        sharedOauthAuthorizeSuccess: 'Authorization successful! This shared MCP is now available to all users.',
        privateOauthAuthorizeSuccess: 'Authorization successful! This private MCP is now ready for your use.',
        nameColumn: 'Name',
        statusColumn: 'Status',
        visibilityColumn: 'Visibility',
        authStatusColumn: 'Auth',
        createdAtColumn: 'Created at',
        actionsColumn: 'Actions',
        nameRequired: 'Enter config name',
        urlRequired: 'Enter MCP server URL',
        urlInvalid: 'URL must start with http:// or https://',
        headersInvalid: 'Headers must be valid JSON',
        fetchListFailed: 'Failed to fetch remote MCP configs',
        headersFormatIncorrect: 'Invalid headers format',
        updateSuccess: 'Remote MCP config updated successfully',
        createSuccess: 'Remote MCP config added successfully',
        updateFailed: 'Failed to update remote MCP config',
        createFailed: 'Failed to add remote MCP config',
        deleteConfirmTitle: 'Confirm deletion',
        deleteConfirmContent: (name: string) => `Delete remote MCP config "${name}"? This action cannot be undone.`,
        deleteSuccess: 'Remote MCP config deleted successfully',
        deleteFailed: 'Failed to delete remote MCP config',
        disableSuccess: 'Remote MCP config disabled successfully',
        enableSuccess: 'Remote MCP config enabled successfully',
        disableFailed: 'Failed to disable remote MCP config',
        enableFailed: 'Failed to enable remote MCP config',
        responseTime: (time: number) => `Response time: ${time}ms`,
        connectionFailed: (message: string) => `Connection failed: ${message}`,
        connectivityCheckFailed: 'Connectivity check failed, please try again later',
      }
    : {
        pageTitle: 'MCP配置管理',
        addRemoteMcp: '添加远程MCP',
        enabled: '启用',
        disabled: '禁用',
        edit: '编辑',
        delete: '删除',
        enable: '启用',
        disable: '禁用',
        checkConnectivity: '检查连通性',
        noData: '暂无数据',
        currentDataCount: (count: number) => `当前数据条数: ${count}`,
        editRemoteMcpTitle: '编辑远程MCP配置',
        addRemoteMcpTitle: '添加远程MCP配置',
        confirm: '确认',
        cancel: '取消',
        name: '名称',
        namePlaceholder: '请输入配置名称',
        url: 'URL',
        urlPlaceholder: '请输入MCP服务器URL',
        transport: '通信方式',
        transportPlaceholder: '请选择通信方式',
        headers: '请求头',
        headersPlaceholder: '请输入请求头 (JSON格式, 例如: {"Authorization": "Bearer token"})',
        status: '状态',
        visibility: '可见范围',
        visibilityTip: '全局共享后所有用户可见可用；私有则仅自己可见。',
        globalShared: '全局共享',
        private: '私有',
        authType: '认证类型',
        authNone: '无认证',
        authOAuth: 'OAuth 2.0',
        authTypeTip: 'OAuth 使用授权码登录流程。仅创建人可授权；共享 MCP 授权后所有用户均可调用。',
        oauthClientId: 'OAuth 客户端 ID',
        oauthClientIdPlaceholder: '可选，留空则使用动态客户端注册',
        oauthClientSecret: 'OAuth 客户端密钥',
        oauthClientSecretPlaceholder: '可选，client_secret 模式需要',
        oauthScope: 'OAuth Scope',
        oauthScopePlaceholder: '可选，多个 scope 用空格分隔',
        oauthMetadataUrl: '客户端元数据 URL',
        oauthMetadataUrlPlaceholder: '可选，URL-based 客户端（CIMD）使用',
        oauthEditTip: '保存后请在列表中使用「授权登录」按钮完成授权。',
        oauthCreateTip: '可先配置 OAuth 字段，保存后再进行授权。',
        oauthAuthorized: '已授权',
        oauthNotAuthorized: '未授权',
        noAuth: '无',
        oauthAuthorize: '授权登录',
        oauthDisconnect: '解除授权',
        oauthDisconnectConfirm: '确定解除 OAuth 授权吗？已保存的 token 将被清除。',
        oauthDisconnectSuccess: '已解除 OAuth 授权',
        oauthDisconnectFailed: '解除 OAuth 授权失败',
        oauthAuthorizeFailed: '发起 OAuth 授权失败',
        oauthModalTitle: 'OAuth 授权',
        oauthWaitingTip: '正在等待授权完成... 在新窗口授权成功后，此弹窗将自动识别并关闭。',
        oauthManualCollapse: '未能自动跳转？展开手动输入回调地址',
        oauthStep1: '1. 复制授权链接',
        oauthStep2: '2. 在浏览器中打开并登录授权',
        oauthStep3: '3. 授权完成后，把浏览器地址栏的完整回调地址粘贴到下面',
        copy: '复制',
        copySuccess: '已复制',
        openAuthUrl: '打开授权链接',
        oauthManualTip: '服务器部署场景：请手动打开授权链接，授权后把回调地址粘贴回来。',
        oauthCallbackPlaceholder: '在此粘贴浏览器地址栏中的完整回调地址（例如 http://主机/mcp_tools/oauth/callback/?code=...&state=...）',
        completeOAuth: '完成授权',
        oauthNoUrl: '暂未获取到授权链接，请重试。',
        sharedOauthTip: '共享 MCP：由创建人统一授权，所有用户可共用。',
        sharedOauthAvailable: '共享已就绪',
        sharedOauthAuthorizeStarted: '该 MCP 是全局共享的，授权后所有用户均可调用。',
        privateOauthAuthorizeStarted: '该 MCP 是私有的，授权后仅你自己可见和调用。',
        sharedOauthAuthorizeSuccess: '授权成功！该共享 MCP 已对所有用户开放。',
        privateOauthAuthorizeSuccess: '授权成功！该私有 MCP 已可供你使用。',
        nameColumn: '名称',
        statusColumn: '状态',
        visibilityColumn: '可见范围',
        authStatusColumn: '认证',
        createdAtColumn: '创建时间',
        actionsColumn: '操作',
        nameRequired: '请输入配置名称',
        urlRequired: '请输入MCP服务器URL',
        urlInvalid: 'URL必须以http://或https://开头',
        headersInvalid: '请求头必须是有效的JSON格式',
        fetchListFailed: '获取远程MCP配置列表失败',
        headersFormatIncorrect: '请求头格式不正确',
        updateSuccess: '更新远程MCP配置成功',
        createSuccess: '添加远程MCP配置成功',
        updateFailed: '更新远程MCP配置失败',
        createFailed: '添加远程MCP配置失败',
        deleteConfirmTitle: '确认删除',
        deleteConfirmContent: (name: string) => `确定要删除远程MCP配置 "${name}" 吗？此操作不可撤销。`,
        deleteSuccess: '删除远程MCP配置成功',
        deleteFailed: '删除远程MCP配置失败',
        disableSuccess: '禁用远程MCP配置成功',
        enableSuccess: '启用远程MCP配置成功',
        disableFailed: '禁用远程MCP配置失败',
        enableFailed: '启用远程MCP配置失败',
        responseTime: (time: number) => `响应时间: ${time}ms`,
        connectionFailed: (message: string) => `连接失败: ${message}`,
        connectivityCheckFailed: '检查连通性失败，请稍后重试',
      }
));

// 表格数据和加载状态
const mcpConfigs = ref<RemoteMcpConfig[]>([]);
const loading = ref(false);
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
});

// OAuth 授权弹窗状态
const oauthModalVisible = ref(false);
const oauthLoading = ref(false);
const oauthCompleting = ref(false);
const oauthRecord = ref<RemoteMcpConfig | null>(null);
const oauthAuthUrl = ref('');
const oauthCallbackUrl = ref('');

// 表格列定义
const columns = computed(() => [
  {
    title: pageText.value.nameColumn,
    dataIndex: 'name',
  },
  {
    title: 'URL',
    dataIndex: 'url',
  },
  {
    title: pageText.value.statusColumn,
    dataIndex: 'is_active',
    slotName: 'is_active',
  },
  {
    title: pageText.value.visibilityColumn,
    dataIndex: 'is_global',
    slotName: 'is_global',
  },
  {
    title: pageText.value.authStatusColumn,
    dataIndex: 'auth_status',
    slotName: 'auth_status',
  },
  {
    title: pageText.value.createdAtColumn,
    dataIndex: 'created_at',
    slotName: 'created_at',
  },
  {
    title: pageText.value.actionsColumn,
    slotName: 'operations',
    align: 'center',
  },
]);

// 表单数据和验证规则
const formRef = ref();
const formData = reactive({
  id: undefined as number | undefined,
  name: '',
  url: '',
  transport: 'streamable_http',
  headersStr: '',
  auth_type: 'none' as 'none' | 'oauth',
  oauth_client_id: '',
  oauth_client_secret: '',
  oauth_scope: '',
  oauth_client_metadata_url: '',
  is_active: true,
  is_global: false,
});

const formRules = computed(() => ({
  name: [{ required: true, message: pageText.value.nameRequired }],
  url: [
    { required: true, message: pageText.value.urlRequired },
    {
      match: /^https?:\/\/.+/,
      message: pageText.value.urlInvalid
    }
  ],
  headersStr: [
    {
      validator: (value: string) => {
        if (!value) return true;
        try {
          JSON.parse(value);
          return true;
        } catch (e) {
          return false;
        }
      },
      message: pageText.value.headersInvalid
    }
  ]
}));

// 弹窗状态
const modalVisible = ref(false);
const deleteModalVisible = ref(false);
const isEditing = ref(false);
const currentConfig = ref<RemoteMcpConfig | null>(null);

// 加载远程MCP配置列表
const loadMcpConfigs = async () => {
  loading.value = true;
  try {
    console.log('开始加载MCP配置数据...');
    const data = await fetchRemoteMcpConfigs();
    console.log('API返回的原始数据:', data);
    mcpConfigs.value = Array.isArray(data) ? data : [];
    pagination.total = mcpConfigs.value.length;
    console.log('处理后的MCP配置数据:', mcpConfigs.value);
  } catch (error) {
    console.error('获取远程MCP配置列表失败:', error);
    Message.error(pageText.value.fetchListFailed);
    mcpConfigs.value = [];
    pagination.total = 0;
  } finally {
    loading.value = false;
  }
};

// 分页相关方法
const onPageChange = (page: number) => {
  pagination.current = page;
};

const onPageSizeChange = (pageSize: number) => {
  pagination.pageSize = pageSize;
};

// 格式化日期
const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString(isEnglish.value ? 'en-US' : 'zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
};

// 显示添加表单
const showAddForm = () => {
  isEditing.value = false;
  formData.id = undefined;
  formData.name = '';
  formData.url = '';
  formData.transport = 'streamable_http';
  formData.headersStr = '';
  formData.auth_type = 'none';
  formData.oauth_client_id = '';
  formData.oauth_client_secret = '';
  formData.oauth_scope = '';
  formData.oauth_client_metadata_url = '';
  formData.is_active = true;
  formData.is_global = false;
  modalVisible.value = true;
};

// 显示编辑表单
const showEditForm = (record: RemoteMcpConfig) => {
  isEditing.value = true;
  formData.id = record.id;
  formData.name = record.name;
  formData.url = record.url;
  formData.transport = record.transport;
  formData.headersStr = record.headers ? JSON.stringify(record.headers) : '';
  formData.auth_type = record.auth_type || 'none';
  formData.oauth_client_id = record.oauth_client_id || '';
  formData.oauth_client_secret = record.oauth_client_secret || '';
  formData.oauth_scope = record.oauth_scope || '';
  formData.oauth_client_metadata_url = record.oauth_client_metadata_url || '';
  formData.is_active = record.is_active;
  formData.is_global = record.is_global;
  modalVisible.value = true;
};

// 关闭表单弹窗
const closeModal = () => {
  formRef.value?.resetFields();
  modalVisible.value = false;
};

// 提交表单
const handleSubmit = async (done: (closed: boolean) => void) => {
  const result = await formRef.value?.validate();
  if (result) {
    done(false);
    return;
  }

  try {
    let headers = {};
    if (formData.headersStr) {
      try {
        headers = JSON.parse(formData.headersStr);
      } catch (e) {
        Message.error(pageText.value.headersFormatIncorrect);
        done(false);
        return;
      }
    }

    const configData: RemoteMcpConfig = {
      name: formData.name,
      url: formData.url,
      transport: formData.transport as RemoteMcpConfig['transport'],
      headers,
      is_active: formData.is_active,
      is_global: formData.is_global,
      auth_type: formData.auth_type,
      oauth_client_id: formData.oauth_client_id,
      oauth_client_secret: formData.oauth_client_secret,
      oauth_scope: formData.oauth_scope,
      oauth_client_metadata_url: formData.oauth_client_metadata_url
    };

    if (isEditing.value && formData.id) {
      // 更新配置
      await updateRemoteMcpConfig(formData.id, configData);
      Message.success(pageText.value.updateSuccess);
    } else {
      // 创建新配置
      await createRemoteMcpConfig(configData);
      Message.success(pageText.value.createSuccess);
    }

    await loadMcpConfigs(); // 重新加载列表
    done(true); // 关闭弹窗
  } catch (error) {
    Message.error(isEditing.value ? pageText.value.updateFailed : pageText.value.createFailed);
    done(false); // 不关闭弹窗
  }
};

// 显示删除确认弹窗
const showDeleteConfirm = (record: RemoteMcpConfig) => {
  currentConfig.value = record;
  deleteModalVisible.value = true;
};

// 处理删除操作
const handleDelete = async () => {
  if (!currentConfig.value?.id) return;

  try {
    await deleteRemoteMcpConfig(currentConfig.value.id);
    Message.success(pageText.value.deleteSuccess);
    await loadMcpConfigs(); // 重新加载列表
  } catch (error) {
    Message.error(pageText.value.deleteFailed);
  } finally {
    deleteModalVisible.value = false;
  }
};

// 切换配置状态
const toggleStatus = async (record: RemoteMcpConfig) => {
  if (!record.id) return;

  try {
    await updateRemoteMcpConfig(record.id, {
      is_active: !record.is_active
    });
    Message.success(record.is_active ? pageText.value.disableSuccess : pageText.value.enableSuccess);
    await loadMcpConfigs(); // 重新加载列表
  } catch (error) {
    Message.error(record.is_active ? pageText.value.disableFailed : pageText.value.enableFailed);
  }
};

// OAuth 轮询定时器
let oauthPollTimer: any = null;

const startOAuthPolling = (configId: number) => {
  stopOAuthPolling();
  oauthPollTimer = setInterval(async () => {
    try {
      const data = await fetchRemoteMcpConfigs();
      if (Array.isArray(data)) {
        mcpConfigs.value = data;
        const target = data.find(c => c.id === configId);
        if (target && target.oauth_authorized) {
          const isGlobal = target.is_global;
          Message.success(isGlobal
            ? pageText.value.sharedOauthAuthorizeSuccess
            : pageText.value.privateOauthAuthorizeSuccess);
          closeOAuthModal();
        }
      }
    } catch (e) {
      // 静默处理轮询异常
    }
  }, 1500);
};

const stopOAuthPolling = () => {
  if (oauthPollTimer) {
    clearInterval(oauthPollTimer);
    oauthPollTimer = null;
  }
};

// 发起 OAuth 授权（打开授权弹窗，支持自动/手动）
const handleAuthorizeOAuth = async (record: RemoteMcpConfig) => {
  if (!record.id) return;
  oauthLoading.value = true;
  oauthModalVisible.value = true;
  oauthRecord.value = record;
  oauthAuthUrl.value = '';
  oauthCallbackUrl.value = '';
  try {
    const result = await authorizeRemoteMcpConfig(record.id);
    oauthAuthUrl.value = result.authorization_url;
    // 启动状态轮询（一旦授权成功自动关闭弹窗）
    startOAuthPolling(record.id);
    // 自动打开新窗口（保留 opener 供跨窗口通知）
    window.open(result.authorization_url, '_blank');
  } catch (error: any) {
    Message.error(error.message || pageText.value.oauthAuthorizeFailed);
    oauthModalVisible.value = false;
    stopOAuthPolling();
  } finally {
    oauthLoading.value = false;
  }
};

// 手动打开授权 URL
const openOAuthUrl = () => {
  if (oauthAuthUrl.value) {
    if (oauthRecord.value?.id) {
      startOAuthPolling(oauthRecord.value.id);
    }
    window.open(oauthAuthUrl.value, '_blank');
  }
};

// 复制授权 URL
const copyOAuthUrl = async () => {
  try {
    await navigator.clipboard.writeText(oauthAuthUrl.value);
    Message.success(pageText.value.copySuccess);
  } catch (e) {
    // 兼容非 https 环境
    const textarea = document.createElement('textarea');
    textarea.value = oauthAuthUrl.value;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    Message.success(pageText.value.copySuccess);
  }
};

// 手动粘贴回调地址完成授权
const handleCompleteOAuth = async () => {
  const record = oauthRecord.value;
  if (!record?.id) return;
  const callbackUrl = oauthCallbackUrl.value.trim();
  if (!callbackUrl) return;

  oauthCompleting.value = true;
  try {
    const result = await completeRemoteMcpConfigOAuth(record.id, callbackUrl);
    Message.success(result?.message || (record.is_global
      ? pageText.value.sharedOauthAuthorizeSuccess
      : pageText.value.privateOauthAuthorizeSuccess));
    closeOAuthModal();
    await loadMcpConfigs();
  } catch (error: any) {
    Message.error(error.message || pageText.value.oauthAuthorizeFailed);
  } finally {
    oauthCompleting.value = false;
  }
};

// 关闭 OAuth 弹窗
const closeOAuthModal = () => {
  stopOAuthPolling();
  oauthModalVisible.value = false;
  oauthRecord.value = null;
  oauthAuthUrl.value = '';
  oauthCallbackUrl.value = '';
};

// 解除 OAuth 授权
const handleDisconnectOAuth = async (record: RemoteMcpConfig) => {
  if (!record.id) return;
  try {
    await disconnectRemoteMcpConfig(record.id);
    Message.success(pageText.value.oauthDisconnectSuccess);
    await loadMcpConfigs();
  } catch (error: any) {
    Message.error(error.message || pageText.value.oauthDisconnectFailed);
  }
};

// 添加ping功能
const pingConfig = async (record: RemoteMcpConfig) => {
  if (!record.id) return;

  // 设置当前记录的pinging状态为true
  mcpConfigs.value = mcpConfigs.value.map(config =>
    config.id === record.id ? { ...config, pinging: true } : config
  );

  try {
    const result = await pingRemoteMcpConfig(record.id);

    if (result.success) {
      let successMessage = result.message;
      if (result.response_time !== undefined) {
        successMessage += ` (${pageText.value.responseTime(result.response_time)})`;
      }
      Message.success(successMessage);
    } else {
      Message.error(pageText.value.connectionFailed(result.message));
    }
  } catch (error) {
    Message.error(pageText.value.connectivityCheckFailed);
  } finally {
    // 重置pinging状态
    mcpConfigs.value = mcpConfigs.value.map(config =>
      config.id === record.id ? { ...config, pinging: false } : config
    );
  }
};

// 监听 OAuth 回调页面的 postMessage 通知
const handleOAuthMessage = async (event: MessageEvent) => {
  if (event.data?.type === 'mcp_oauth_result') {
    if (event.data.success) {
      const isGlobal = oauthRecord.value?.is_global;
      Message.success(isGlobal
        ? pageText.value.sharedOauthAuthorizeSuccess
        : pageText.value.privateOauthAuthorizeSuccess);
      closeOAuthModal();
      await loadMcpConfigs();
    }
  }
};

// 组件挂载时加载数据并注册 message 监听
onMounted(() => {
  window.addEventListener('message', handleOAuthMessage);
  loadMcpConfigs();
});

// 组件卸载时移除监听与定时器
onUnmounted(() => {
  stopOAuthPolling();
  window.removeEventListener('message', handleOAuthMessage);
});
</script>

<style scoped>
.remote-mcp-management {
  padding: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.content-card {
  margin-bottom: 16px;
}
</style>
