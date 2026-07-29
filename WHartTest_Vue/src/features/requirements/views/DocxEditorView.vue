<template>
  <div class="docx-editor-page">
    <div v-if="loading" class="loading-state">
      <a-spin size="large" />
    </div>

    <template v-else>
      <div v-if="serviceUnavailable" class="service-unavailable">
        <a-empty
          description=""
        >
          <template #image>
            <icon-exclamation-circle style="font-size: 64px; color: var(--color-text-3);" />
          </template>
          <div style="text-align: center;">
            <div style="font-size: 16px; color: var(--color-text-1); margin-bottom: 8px;">在线编辑服务暂不可用</div>
            <div style="color: var(--color-text-3); margin-bottom: 16px;">{{ pageError }}</div>
            <a-button type="primary" @click="goBack">返回文档详情</a-button>
          </div>
        </a-empty>
      </div>

      <a-alert
        v-else-if="pageError"
        type="error"
        :show-icon="true"
        :closable="false"
        :content="pageError"
        class="page-alert"
      />

      <a-alert
        v-else-if="!supportsDocxEditor"
        type="warning"
        :show-icon="true"
        :closable="false"
        content="仅 Word 文档支持在线编辑。"
        class="page-alert"
      />

      <section v-else class="editor-shell">
        <div v-if="iframeUrl" class="frame-shell">
          <iframe
            :src="iframeUrl"
            class="editor-frame"
            title="DOCX Editor"
          />
        </div>
        <a-empty
          v-else
          description="编辑器还没有加载成功，请刷新页面后重试。"
        />
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router';
import { Message } from '@arco-design/web-vue';
import { RequirementDocumentService } from '../services/requirementService';
import type { DocumentDetail } from '../types';

const route = useRoute();
const router = useRouter();

const loading = ref(false);
const sessionLoading = ref(false);
const document = ref<DocumentDetail | null>(null);
const iframeUrl = ref('');
const pageError = ref('');
const syncStatus = ref<'idle' | 'syncing' | 'synced' | 'failed'>('idle');
const knownUpdatedAt = ref('');
const editedInSession = ref(false);
const waitingToLeave = ref(false);

let syncTimer: number | null = null;

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const supportsDocxEditor = computed(() => {
  if (!document.value?.file) return false;
  return document.value.document_type === 'doc' || document.value.document_type === 'docx';
});

const serviceUnavailable = computed(() => {
  if (!pageError.value) return false;
  return pageError.value.includes('未配置') || pageError.value.includes('不可用');
});

const goBack = () => {
  const documentId = route.params.id as string;
  if (documentId) {
    router.push(`/requirements/${documentId}`);
  } else {
    router.push('/requirements');
  }
};

const clearSyncTimer = () => {
  if (syncTimer !== null) {
    window.clearInterval(syncTimer);
    syncTimer = null;
  }
};

const handleEmbedMessage = (event: MessageEvent) => {
  const payload = event.data;
  if (!payload || payload.source !== 'docx-editor-embed') {
    return;
  }

  if (payload.type === 'document-state-change' && payload.dirty) {
    editedInSession.value = true;
  }
};

const loadDocument = async (silent = false) => {
  const documentId = route.params.id as string;
  if (!documentId) {
    pageError.value = '文档ID不存在';
    return;
  }

  if (!silent) {
    loading.value = true;
  }

  try {
    const response = await RequirementDocumentService.getDocumentDetail(documentId);
    if (response.status === 'success') {
      document.value = response.data;
      if (!supportsDocxEditor.value) {
        pageError.value = '';
        clearSyncTimer();
        iframeUrl.value = '';
        syncStatus.value = 'idle';
      }
      return;
    }

    pageError.value = response.message || '加载文档详情失败';
  } catch (error) {
    console.error('加载在线编辑页面失败:', error);
    pageError.value = '加载文档详情失败';
  } finally {
    if (!silent) {
      loading.value = false;
    }
  }
};

const startSyncPolling = () => {
  clearSyncTimer();

  if (!iframeUrl.value) {
    syncStatus.value = 'idle';
    return;
  }

  knownUpdatedAt.value = document.value?.updated_at || '';
  syncStatus.value = 'syncing';

  syncTimer = window.setInterval(async () => {
    const previousUpdatedAt = knownUpdatedAt.value;
    await loadDocument(true);
    const currentUpdatedAt = document.value?.updated_at || '';

    if (previousUpdatedAt && currentUpdatedAt && currentUpdatedAt !== previousUpdatedAt) {
      knownUpdatedAt.value = currentUpdatedAt;
      syncStatus.value = 'synced';
      editedInSession.value = false;
      Message.success('检测到在线编辑内容已同步到主项目');
      return;
    }

    knownUpdatedAt.value = currentUpdatedAt;
  }, 5000);
};

const waitForDocumentSync = async (timeoutMs = 45000, intervalMs = 1000) => {
  const baselineUpdatedAt = knownUpdatedAt.value || document.value?.updated_at || '';
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    await loadDocument(true);
    const currentUpdatedAt = document.value?.updated_at || '';
    if (baselineUpdatedAt && currentUpdatedAt && currentUpdatedAt !== baselineUpdatedAt) {
      knownUpdatedAt.value = currentUpdatedAt;
      syncStatus.value = 'synced';
      editedInSession.value = false;
      return true;
    }
    await sleep(intervalMs);
  }

  return false;
};

const createSession = async () => {
  if (!document.value) {
    await loadDocument();
  }

  if (!document.value) {
    return;
  }

  if (!supportsDocxEditor.value) {
    pageError.value = '仅 Word 文档支持在线编辑';
    return;
  }

  sessionLoading.value = true;
  pageError.value = '';
  syncStatus.value = 'idle';
  editedInSession.value = false;

  try {
    const response = await RequirementDocumentService.createDocxEditorSession(document.value.id);
    if (response.status === 'success' && response.data?.iframe_url) {
      iframeUrl.value = response.data.iframe_url;
      knownUpdatedAt.value = document.value.updated_at || '';
      startSyncPolling();
      return;
    }

    pageError.value = response.message || '创建在线编辑会话失败';
    syncStatus.value = 'failed';
  } catch (error) {
    console.error('创建在线编辑会话失败:', error);
    pageError.value = '创建在线编辑会话失败';
    syncStatus.value = 'failed';
  } finally {
    sessionLoading.value = false;
  }
};

const initializePage = async () => {
  iframeUrl.value = '';
  pageError.value = '';
  syncStatus.value = 'idle';
  clearSyncTimer();
  await loadDocument();

  if (supportsDocxEditor.value) {
    await createSession();
  }
};

watch(
  () => route.params.id,
  async (newId, oldId) => {
    if (newId && newId !== oldId) {
      await initializePage();
    }
  }
);

onMounted(async () => {
  window.addEventListener('message', handleEmbedMessage);
  await initializePage();
});

onBeforeUnmount(() => {
  window.removeEventListener('message', handleEmbedMessage);
  clearSyncTimer();
});

onBeforeRouteLeave(async () => {
  if (!iframeUrl.value || !editedInSession.value || waitingToLeave.value) {
    return true;
  }

  const confirmed = window.confirm('检测到本次在线编辑有修改记录，离开前将等待回传完成。确定返回吗？');
  if (!confirmed) {
    return false;
  }

  waitingToLeave.value = true;
  Message.info('正在等待在线编辑内容回传...');
  try {
    const synced = await waitForDocumentSync();
    if (synced) {
      Message.success('在线编辑内容已同步');
    } else {
      Message.warning('45 秒内未检测到回传，已先返回。请稍后刷新详情页确认。');
    }
    return true;
  } finally {
    waitingToLeave.value = false;
  }
});
</script>

<style scoped>
.docx-editor-page {
  min-height: 100%;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.page-alert {
  margin: 24px;
  margin-bottom: 0;
}

.editor-shell {
  flex: 1;
  min-height: 0;
}

.frame-shell {
  width: 100%;
  height: 100%;
}

.editor-frame {
  width: 100%;
  height: 100%;
  border: 0;
}

.loading-state {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 96px 0;
}

.service-unavailable {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 96px 24px;
}

@media (max-width: 960px) {
  .frame-shell,
  .editor-frame {
    height: 100%;
  }
}
</style>
