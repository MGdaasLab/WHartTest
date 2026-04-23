<template>
  <a-modal
    :visible="visible"
    title="微信接入"
    :footer="false"
    :width="920"
    modal-class="weixin-connect-dialog"
    :mask-closable="false"
    @cancel="handleClose"
  >
    <div class="weixin-connect-modal">
      <section class="hero-panel">
        <div class="hero-copy">
          <span class="hero-eyebrow">WeChat Bridge</span>
          <h2 class="hero-title">把当前项目接到微信对话里</h2>
          <p class="hero-description">
            扫码后，用户可以直接在微信里与当前项目对应的 WHartTest 会话沟通，消息仍然走你现有的对话链路。
          </p>
        </div>

        <div class="hero-side">
          <div class="hero-stats">
            <div class="hero-stat-card">
              <span>已绑定</span>
              <strong>{{ accounts.length }}</strong>
            </div>
            <div class="hero-stat-card">
              <span>运行中</span>
              <strong>{{ runningAccountCount }}</strong>
            </div>
            <div class="hero-stat-card">
              <span>异常</span>
              <strong>{{ errorAccountCount }}</strong>
            </div>
          </div>

          <a-button
            type="primary"
            size="large"
            long
            :loading="starting"
            :disabled="!projectId"
            @click="handleStartLogin"
          >
            生成二维码
          </a-button>
        </div>
      </section>

      <div class="workflow-strip">
        <div
          v-for="(step, index) in workflowSteps"
          :key="step.key"
          class="workflow-step"
          :class="{
            active: index <= workflowStepIndex,
            current: index === workflowStepIndex,
          }"
        >
          <div class="workflow-index">{{ index + 1 }}</div>
          <div class="workflow-copy">
            <div class="workflow-title">{{ step.title }}</div>
            <div class="workflow-text">{{ step.text }}</div>
          </div>
        </div>
      </div>

      <div class="weixin-main">
        <section class="qr-panel panel-shell">
          <div class="panel-header">
            <div>
              <span class="panel-eyebrow">扫码区</span>
              <div class="panel-title-row">
                <h3 class="panel-title">连接微信账号</h3>
                <a-tag :color="statusColor" bordered>{{ statusText }}</a-tag>
              </div>
            </div>
          </div>

          <div class="qr-stage" :class="{ ready: !!loginSession?.qr_data_url }">
            <template v-if="loginSession?.qr_data_url">
              <a-spin :loading="resolvingQrImage" class="qr-spin">
                <img v-if="displayedQrSrc" :src="displayedQrSrc" alt="微信二维码" class="qr-image" />
                <a-empty v-else description="二维码加载失败，请重新生成" />
              </a-spin>
            </template>
            <template v-else>
              <div class="qr-placeholder">
                <div class="qr-placeholder-grid">
                  <span v-for="cell in 16" :key="cell" class="qr-placeholder-cell" />
                </div>
                <p>点击上方按钮生成二维码</p>
              </div>
            </template>
          </div>

          <div class="qr-status-card">
            <p class="qr-message">{{ statusMessage }}</p>
            <div class="qr-session-meta">
              <span>会话状态：{{ statusText }}</span>
              <span v-if="loginSession?.updated_at">更新时间：{{ formatDateTime(loginSession.updated_at) }}</span>
            </div>
          </div>
        </section>

        <section class="account-panel panel-shell">
          <div class="panel-header">
            <div>
              <span class="panel-eyebrow">账号区</span>
              <div class="panel-title-row">
                <h3 class="panel-title">已绑定账号</h3>
                <span class="panel-subtitle">可直接启停监听，不需要重新创建绑定</span>
              </div>
            </div>
          </div>

          <a-spin :loading="loadingAccounts">
            <div v-if="!accounts.length" class="account-empty">
              <a-empty description="当前项目还没有绑定微信账号" />
            </div>
            <div v-else class="account-list">
              <div v-for="account in accounts" :key="account.id" class="account-card">
                <div class="account-card-top">
                  <div class="account-main">
                    <div class="account-name-row">
                      <div class="account-name">{{ account.raw_account_id }}</div>
                      <span class="account-status-pill" :class="accountStatusClass(account)">
                        {{ accountStatusText(account) }}
                      </span>
                    </div>
                    <div class="account-sub">
                      扫码微信用户：{{ account.scanned_user_id || '未知' }}
                    </div>
                  </div>
                  <a-switch
                    :model-value="account.is_active"
                    :loading="togglingAccountId === account.id"
                    @change="(value) => handleToggleAccount(account.id, Boolean(value))"
                  />
                </div>
                <div class="account-facts">
                  <div class="account-fact">
                    <span class="account-fact-label">最近收消息</span>
                    <strong>{{ formatAccountTime(account.last_inbound_at) }}</strong>
                  </div>
                  <div class="account-fact">
                    <span class="account-fact-label">最近发消息</span>
                    <strong>{{ formatAccountTime(account.last_outbound_at) }}</strong>
                  </div>
                </div>
                <div v-if="account.last_error" class="account-error">
                  {{ account.last_error }}
                </div>
              </div>
            </div>
          </a-spin>
        </section>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import QRCode from 'qrcode';
import {
  getWeixinAccounts,
  getWeixinLoginStatus,
  startWeixinLogin,
  toggleWeixinAccount,
  type WeixinBotAccount,
  type WeixinLoginSession,
} from '@/features/langgraph/services/weixinService';

interface Props {
  visible: boolean;
  projectId: number | null;
  selectedPromptId: number | null;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void;
}>();

const starting = ref(false);
const loadingAccounts = ref(false);
const togglingAccountId = ref<number | null>(null);
const loginSession = ref<WeixinLoginSession | null>(null);
const accounts = ref<WeixinBotAccount[]>([]);
const renderedQrSrc = ref('');
const resolvingQrImage = ref(false);
const pollingLoginStatus = ref(false);
const LOGIN_POLL_INTERVAL_MS = 2000;
const LOGIN_POLL_RETRY_INTERVAL_MS = 4000;
let pollTimer: number | null = null;

const workflowSteps = [
  { key: 'wait', title: '生成二维码', text: '为当前项目生成绑定入口' },
  { key: 'scaned', title: '微信扫码', text: '在手机端确认登录授权' },
  { key: 'confirmed', title: '开始对话', text: '账号接入后直接收发消息' },
];

const runningAccountCount = computed(() => accounts.value.filter((item) => item.worker_running).length);
const errorAccountCount = computed(() => accounts.value.filter((item) => Boolean(item.last_error)).length);

const statusText = computed(() => {
  const status = loginSession.value?.status;
  if (status === 'wait') return '等待扫码';
  if (status === 'scaned') return '已扫码';
  if (status === 'confirmed') return '已确认';
  if (status === 'expired') return '已过期';
  if (status === 'failed') return '失败';
  return '未开始';
});

const statusColor = computed(() => {
  const status = loginSession.value?.status;
  if (status === 'confirmed') return 'green';
  if (status === 'scaned') return 'arcoblue';
  if (status === 'expired' || status === 'failed') return 'red';
  return 'gold';
});

const statusMessage = computed(() => {
  if (!loginSession.value) return '生成二维码后会在这里显示扫码状态。';
  if (loginSession.value.error_message) return loginSession.value.error_message;
  if (loginSession.value.status === 'confirmed') {
    return `绑定成功：${loginSession.value.raw_account_id}`;
  }
  return '请使用微信扫描二维码，并在手机上确认授权。';
});

const displayedQrSrc = computed(() => renderedQrSrc.value || loginSession.value?.qr_data_url || '');
const workflowStepIndex = computed(() => {
  const status = loginSession.value?.status;
  if (status === 'confirmed') return 2;
  if (status === 'scaned') return 1;
  return 0;
});

const clearPollTimer = () => {
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
};

const shouldKeepPolling = (status?: WeixinLoginSession['status']) =>
  status === 'wait' || status === 'scaned';

const canLoadAsImage = (src: string) =>
  new Promise<boolean>((resolve) => {
    const image = new Image();
    image.onload = () => resolve(true);
    image.onerror = () => resolve(false);
    image.src = src;
  });

const resolveQrImageSrc = async (rawValue?: string | null) => {
  const value = (rawValue || '').trim();
  renderedQrSrc.value = '';
  if (!value) {
    return;
  }

  resolvingQrImage.value = true;
  try {
    if (value.startsWith('data:image/')) {
      renderedQrSrc.value = value;
      return;
    }

    const imageLoaded = await canLoadAsImage(value);
    if (imageLoaded) {
      renderedQrSrc.value = value;
      return;
    }

    renderedQrSrc.value = await QRCode.toDataURL(value, {
      width: 220,
      margin: 1,
      errorCorrectionLevel: 'M',
    });
  } catch (error) {
    console.error('Failed to resolve Weixin QR image', error);
    renderedQrSrc.value = '';
  } finally {
    resolvingQrImage.value = false;
  }
};

const schedulePollLoginStatus = (delay = LOGIN_POLL_INTERVAL_MS) => {
  if (!props.visible || !loginSession.value?.session_key || pollTimer !== null) {
    return;
  }
  pollTimer = window.setTimeout(() => {
    pollTimer = null;
    void pollLoginStatus();
  }, delay);
};

const formatDateTime = (value?: string | null) => {
  if (!value) return '暂无';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const formatAccountTime = (value?: string | null) => {
  if (!value) return '暂无记录';
  return formatDateTime(value);
};

const accountStatusText = (account: WeixinBotAccount) => {
  if (!account.is_active) return '已停用';
  if (account.last_error) return '异常';
  if (account.worker_running) return '运行中';
  return '已连接';
};

const accountStatusClass = (account: WeixinBotAccount) => {
  if (!account.is_active) return 'is-muted';
  if (account.last_error) return 'is-danger';
  if (account.worker_running) return 'is-running';
  return 'is-ready';
};

const loadAccounts = async () => {
  if (!props.projectId) {
    accounts.value = [];
    return;
  }
  loadingAccounts.value = true;
  try {
    const response = await getWeixinAccounts(props.projectId);
    accounts.value = response.success && response.data ? response.data : [];
  } finally {
    loadingAccounts.value = false;
  }
};

const pollLoginStatus = async () => {
  if (!loginSession.value?.session_key || pollingLoginStatus.value) return;

  pollingLoginStatus.value = true;
  let nextDelay: number | null = null;

  try {
    const response = await getWeixinLoginStatus(loginSession.value.session_key);
    if (!(response.success && response.data)) {
      if (loginSession.value) {
        loginSession.value = {
          ...loginSession.value,
          error_message: response.error || '微信登录状态查询失败，请稍后重试。',
        };
      }
      nextDelay = LOGIN_POLL_RETRY_INTERVAL_MS;
      return;
    }

    loginSession.value = response.data;

    if (response.data.status === 'confirmed') {
      await loadAccounts();
      Message.success('微信绑定成功，后台已开始监听微信消息');
      return;
    }

    if (shouldKeepPolling(response.data.status)) {
      nextDelay = response.data.error_message
        ? LOGIN_POLL_RETRY_INTERVAL_MS
        : LOGIN_POLL_INTERVAL_MS;
    }
  } finally {
    pollingLoginStatus.value = false;
    if (nextDelay !== null) {
      schedulePollLoginStatus(nextDelay);
    }
  }
};

const handleStartLogin = async () => {
  if (!props.projectId) {
    Message.error('请先选择项目');
    return;
  }
  starting.value = true;
  clearPollTimer();
  try {
    const response = await startWeixinLogin({
      project_id: props.projectId,
      prompt_id: props.selectedPromptId,
    });
    if (!(response.success && response.data)) {
      Message.error(response.error || '生成二维码失败');
      return;
    }
    loginSession.value = response.data;
    schedulePollLoginStatus();
  } finally {
    starting.value = false;
  }
};

const handleToggleAccount = async (accountId: number, isActive: boolean) => {
  togglingAccountId.value = accountId;
  try {
    const response = await toggleWeixinAccount(accountId, isActive);
    if (!response.success) {
      Message.error(response.error || '更新微信账号状态失败');
      return;
    }
    await loadAccounts();
  } finally {
    togglingAccountId.value = null;
  }
};

const handleClose = () => {
  clearPollTimer();
  emit('update:visible', false);
};

watch(
  () => loginSession.value?.qr_data_url,
  (value) => {
    void resolveQrImageSrc(value);
  },
  { immediate: true }
);

watch(
  () => props.visible,
  async (visible) => {
    if (!visible) {
      clearPollTimer();
      return;
    }
    await loadAccounts();
    if (loginSession.value && shouldKeepPolling(loginSession.value.status)) {
      schedulePollLoginStatus();
    }
  }
);

onBeforeUnmount(() => {
  clearPollTimer();
});
</script>

<style scoped>
:deep(.weixin-connect-dialog .arco-modal) {
  width: min(94vw, 920px) !important;
}

:deep(.weixin-connect-dialog .arco-modal-header) {
  padding: 18px 20px 12px;
}

:deep(.weixin-connect-dialog .arco-modal-body) {
  padding: 8px 20px 20px;
  background:
    radial-gradient(circle at top left, rgba(7, 193, 96, 0.08), transparent 32%),
    linear-gradient(180deg, #f9fcfb 0%, #f4f7f7 100%);
}

.weixin-connect-modal {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.hero-panel {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) 250px;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 18px;
  background:
    linear-gradient(140deg, rgba(7, 193, 96, 0.14), rgba(250, 252, 251, 0.96) 42%, rgba(18, 24, 31, 0.04)),
    #ffffff;
  border: 1px solid rgba(7, 193, 96, 0.16);
  box-shadow: 0 18px 40px rgba(18, 24, 31, 0.08);
}

.hero-eyebrow,
.panel-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #159957;
}

.hero-title {
  margin: 8px 0 6px;
  font-size: 22px;
  line-height: 1.18;
  color: #0f1720;
}

.hero-description {
  margin: 0;
  max-width: 520px;
  font-size: 13px;
  line-height: 1.6;
  color: #4a5968;
}

.hero-stat-card {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(15, 23, 32, 0.06);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.hero-stat-card span {
  font-size: 12px;
  color: #5b6b79;
}

.hero-stat-card strong {
  font-size: 15px;
  color: #0f1720;
  word-break: break-word;
}

.hero-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  justify-content: flex-start;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.workflow-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.workflow-step {
  display: flex;
  gap: 10px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(15, 23, 32, 0.08);
  background: rgba(255, 255, 255, 0.78);
  transition: all 0.2s ease;
}

.workflow-step.active {
  border-color: rgba(7, 193, 96, 0.3);
  background: rgba(242, 251, 246, 0.95);
}

.workflow-step.current {
  box-shadow: 0 8px 20px rgba(7, 193, 96, 0.12);
}

.workflow-index {
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #6a7784;
  background: rgba(15, 23, 32, 0.06);
}

.workflow-step.active .workflow-index {
  color: #ffffff;
  background: linear-gradient(135deg, #07c160, #14a44d);
}

.workflow-copy {
  min-width: 0;
}

.workflow-title {
  font-size: 13px;
  font-weight: 700;
  color: #1f2a37;
}

.workflow-text {
  margin-top: 2px;
  font-size: 11px;
  line-height: 1.45;
  color: #5f6c79;
}

.weixin-main {
  display: grid;
  grid-template-columns: 272px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.panel-shell {
  min-height: 0;
  min-width: 0;
  padding: 16px;
  box-sizing: border-box;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(15, 23, 32, 0.08);
  box-shadow: 0 14px 32px rgba(18, 24, 31, 0.06);
}

.account-panel {
  align-self: start;
  min-width: 0;
}

.account-panel :deep(.arco-spin),
.account-panel :deep(.arco-spin-children) {
  display: block;
  width: 100%;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 6px;
}

.qr-spin {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
}

.qr-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 216px;
  padding: 12px;
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(243, 247, 245, 0.92), rgba(255, 255, 255, 0.98)),
    #ffffff;
  border: 1px dashed rgba(7, 193, 96, 0.25);
}

.qr-stage.ready {
  border-style: solid;
}

.qr-image {
  width: 184px;
  height: 184px;
  object-fit: contain;
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 32, 0.08);
  background: #fff;
  box-shadow: 0 12px 28px rgba(15, 23, 32, 0.08);
}

.qr-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #6b7885;
}

.qr-placeholder-grid {
  display: grid;
  grid-template-columns: repeat(4, 16px);
  gap: 7px;
  padding: 16px;
  border-radius: 16px;
  background: rgba(7, 193, 96, 0.08);
}

.qr-placeholder-cell {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  background: linear-gradient(135deg, rgba(7, 193, 96, 0.68), rgba(7, 193, 96, 0.18));
}

.qr-status-card {
  margin-top: 12px;
  padding: 12px;
  border-radius: 16px;
  background: #f7faf8;
  border: 1px solid rgba(15, 23, 32, 0.06);
}

.qr-message {
  margin: 0;
  font-size: 12px;
  color: #41505f;
  line-height: 1.45;
}

.qr-session-meta {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 11px;
  color: #6b7885;
}

.panel-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #101a22;
}

.panel-subtitle {
  display: inline-flex;
  font-size: 12px;
  color: #657381;
}

.account-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 220px;
}

.account-list {
  display: flex;
  flex-direction: column;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  gap: 10px;
}

.account-card {
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid rgba(15, 23, 32, 0.08);
  border-radius: 16px;
  padding: 14px;
  background:
    linear-gradient(180deg, rgba(251, 253, 252, 0.98), rgba(246, 249, 248, 0.94)),
    #ffffff;
  box-shadow: 0 10px 20px rgba(15, 23, 32, 0.04);
}

.account-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.account-main {
  min-width: 0;
}

.account-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.account-name {
  font-size: 14px;
  font-weight: 700;
  color: #16202a;
  word-break: break-all;
}

.account-status-pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  background: rgba(15, 23, 32, 0.06);
  color: #62707d;
}

.account-status-pill.is-running {
  background: rgba(7, 193, 96, 0.12);
  color: #11864b;
}

.account-status-pill.is-ready {
  background: rgba(22, 93, 255, 0.1);
  color: #165dff;
}

.account-status-pill.is-danger {
  background: rgba(245, 63, 63, 0.12);
  color: #d93030;
}

.account-status-pill.is-muted {
  background: rgba(134, 144, 156, 0.14);
  color: #66707a;
}

.account-sub {
  margin-top: 4px;
  font-size: 11px;
  color: #75818d;
}

.account-facts {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  min-width: 0;
  gap: 8px;
}

.account-fact {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  box-sizing: border-box;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(15, 23, 32, 0.06);
}

.account-fact-label {
  font-size: 11px;
  color: #6b7885;
}

.account-fact strong {
  font-size: 12px;
  color: #1b2630;
  word-break: break-word;
}

.account-error {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(245, 63, 63, 0.08);
  border: 1px solid rgba(245, 63, 63, 0.16);
  color: #d93030;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
}

@media (max-width: 920px) {
  .hero-panel,
  .weixin-main {
    grid-template-columns: 1fr;
  }

  .hero-stats,
  .workflow-strip {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .hero-panel,
  .panel-shell,
  .workflow-step {
    padding: 14px;
  }

  :deep(.weixin-connect-dialog .arco-modal-header) {
    padding: 16px 16px 10px;
  }

  :deep(.weixin-connect-dialog .arco-modal-body) {
    padding: 8px 16px 16px;
  }

  .account-facts {
    grid-template-columns: 1fr;
  }

  .account-list {
    grid-template-columns: 1fr;
  }

  .hero-title {
    font-size: 22px;
  }
}
</style>
