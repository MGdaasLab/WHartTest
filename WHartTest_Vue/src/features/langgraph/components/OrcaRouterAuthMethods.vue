<template>
  <div class="orca-auth-methods" data-testid="orca-auth-methods">
    <!-- Both entries are always visible and independently usable: a user with
         an existing key never has to start a login, and a user without one
         never has to hunt for a key field. -->

    <!-- Entry 1: paste an existing key. -->
    <section class="orca-entry" data-testid="orca-api-key-panel">
      <header class="orca-entry-header">
        <span class="orca-entry-title">{{ text.apiOption }}</span>
        <a-link
          :href="keyDashboardUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="orca-entry-link"
        >
          {{ text.keyDashboard }}
        </a-link>
      </header>
      <a-form-item field="api_key" :label="text.apiKeyLabel">
        <a-input-password
          v-model="apiKeyInput"
          :placeholder="hasStoredKey ? text.apiKeyConfigured : text.apiKeyPlaceholder"
          data-testid="orca-api-key-input"
          allow-clear
          @input="handleApiKeyInput"
        />
      </a-form-item>
      <p class="orca-hint">{{ text.apiKeyHint }}</p>
    </section>

    <!-- Entry 2: OAuth 2.0 + PKCE login (out-of-band code). -->
    <section class="orca-entry" data-testid="orca-pkce-panel">
      <header class="orca-entry-header">
        <span class="orca-entry-title">{{ text.oauthOption }}</span>
      </header>

      <div v-if="!authorizeUrl" class="orca-connect-row">
        <a-button
          type="primary"
          :loading="busy"
          data-testid="orca-connect-button"
          @click="emit('connect')"
        >
          {{ text.connectButton }}
        </a-button>
        <span class="orca-hint">{{ text.connectHint }}</span>
      </div>

      <template v-else>
        <p class="orca-hint">{{ text.authorizeInstruction }}</p>
        <div class="orca-authorize-row">
          <a-link
            :href="authorizeUrl"
            target="_blank"
            rel="noopener noreferrer"
            data-testid="orca-authorize-url"
          >
            {{ text.openAuthorizePage }}
          </a-link>
        </div>
        <a-form-item field="orca_code" :label="text.codeLabel">
          <a-input-password
            v-model="codeInput"
            :placeholder="text.codePlaceholder"
            data-testid="orca-code-input"
          />
        </a-form-item>
        <div class="orca-authorize-row">
          <a-button
            type="primary"
            :loading="busy"
            data-testid="orca-complete-button"
            @click="submitCode"
          >
            {{ text.submitCode }}
          </a-button>
          <a-button
            type="text"
            :disabled="busy"
            data-testid="orca-cancel-button"
            @click="cancel"
          >
            {{ text.cancelLogin }}
          </a-button>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import {
  FormItem as AFormItem,
  InputPassword as AInputPassword,
  Button as AButton,
  Link as ALink,
} from '@arco-design/web-vue';
import { useAppI18n } from '@/composables/useAppI18n';

interface Props {
  /** Whether a key is already stored for this config (masked in the UI). */
  hasStoredKey?: boolean;
  /** Non-empty while a PKCE login is in flight. */
  authorizeUrl?: string;
  busy?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  hasStoredKey: false,
  authorizeUrl: '',
  busy: false,
});

const emit = defineEmits<{
  (e: 'update:api-key', value: string): void;
  (e: 'connect'): void;
  (e: 'complete', code: string): void;
  (e: 'cancel'): void;
}>();

const { isEnglish } = useAppI18n();
const keyDashboardUrl = 'https://www.orcarouter.ai/console/authorized-apps';

const text = computed(() => (
  isEnglish.value
    ? {
        apiOption: 'OrcaRouter - API',
        oauthOption: 'OrcaRouter - Auth',
        apiKeyLabel: 'API Key',
        apiKeyPlaceholder: 'Paste an sk-orca-… key',
        apiKeyConfigured: 'Key configured (leave blank to keep it)',
        apiKeyHint: 'Keys are issued and revocable in the OrcaRouter console and are stored server-side.',
        keyDashboard: 'Manage keys',
        connectButton: 'Connect with OrcaRouter',
        connectHint: 'Authorize in your browser — no key copying needed.',
        authorizeInstruction:
          'Open the link below in your browser, approve access, then paste the authorization code it shows.',
        openAuthorizePage: 'Open authorization page',
        codeLabel: 'Authorization code',
        codePlaceholder: 'Paste the authorization code',
        submitCode: 'Complete connection',
        cancelLogin: 'Cancel login',
      }
    : {
        apiOption: 'OrcaRouter - API',
        oauthOption: 'OrcaRouter - 账号授权',
        apiKeyLabel: 'API Key',
        apiKeyPlaceholder: '粘贴 sk-orca-… 开头的密钥',
        apiKeyConfigured: '已配置密钥（留空则不修改）',
        apiKeyHint: '密钥在 OrcaRouter 控制台签发与撤销，仅保存在服务端。',
        keyDashboard: '管理密钥',
        connectButton: '连接 OrcaRouter',
        connectHint: '在浏览器中授权，无需手动复制密钥。',
        authorizeInstruction: '在浏览器中打开以下链接并同意授权，然后把页面显示的授权码粘贴到下方。',
        openAuthorizePage: '打开授权页面',
        codeLabel: '授权码',
        codePlaceholder: '粘贴授权码',
        submitCode: '完成连接',
        cancelLogin: '取消登录',
      }
));

const apiKeyInput = ref('');
const codeInput = ref('');

const handleApiKeyInput = () => {
  emit('update:api-key', apiKeyInput.value);
};

// Never keep a pasted code in the component once the login is over.
watch(
  () => props.authorizeUrl,
  (next) => {
    if (!next) {
      codeInput.value = '';
    }
  }
);

const submitCode = () => {
  emit('complete', codeInput.value);
};

const cancel = () => {
  codeInput.value = '';
  emit('cancel');
};

defineExpose({
  reset() {
    apiKeyInput.value = '';
    codeInput.value = '';
  },
});
</script>

<style scoped>
.orca-auth-methods {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}
.orca-entry {
  padding: 12px;
  border: 1px solid var(--color-border-2);
  border-radius: 6px;
  background: var(--color-fill-1);
}
.orca-entry-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.orca-entry-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-1);
}
.orca-entry-link {
  font-size: 12px;
}
.orca-connect-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.orca-authorize-row {
  margin-bottom: 8px;
}
.orca-hint {
  margin: 0;
  color: var(--color-text-3);
  font-size: 12px;
  line-height: 1.6;
  word-break: break-word;
}
</style>
