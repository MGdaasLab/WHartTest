<template>
  <a-modal
    :visible="visible"
    :title="text.title"
    :width="520"
    :ok-text="text.confirmInstall"
    :cancel-text="text.cancel"
    :ok-loading="submitting"
    :ok-button-props="{ disabled: !canConfirm }"
    unmount-on-close
    @ok="handleConfirm"
    @cancel="emit('update:visible', false)"
    @update:visible="(v: boolean) => emit('update:visible', v)"
  >
    <div class="api-key-confirm">
      <a-alert type="info" show-icon style="margin-bottom: 16px">
        {{ text.hint }}
      </a-alert>

      <div v-if="skillNames.length" class="skill-names">
        <span class="label">{{ text.targetSkills }}</span>
        <a-space wrap>
          <a-tag v-for="n in skillNames" :key="n" color="arcoblue">{{ n }}</a-tag>
        </a-space>
      </div>

      <a-spin :loading="loadingKeys">
        <div v-if="!loadingKeys && keys.length === 0" class="empty-keys">
          <p>{{ text.noKeys }}</p>
          <a-button type="primary" size="small" @click="showCreate = true">
            {{ text.createNow }}
          </a-button>
        </div>

        <div v-else class="key-list">
          <div class="label">{{ text.selectKey }}</div>
          <a-radio-group v-model="selectedKeyId" direction="vertical">
            <a-radio
              v-for="item in keys"
              :key="item.id"
              :value="item.id"
              :disabled="!item.is_active"
            >
              <span class="key-item">
                <strong>{{ item.name }}</strong>
                <code class="key-value">{{ maskKey(item.key) }}</code>
                <a-tag v-if="!item.is_active" size="small" color="red">{{ text.inactive }}</a-tag>
              </span>
            </a-radio>
          </a-radio-group>
          <div class="create-row">
            <a-button type="outline" size="mini" @click="showCreate = true">
              {{ text.createAnother }}
            </a-button>
          </div>
        </div>
      </a-spin>

      <a-modal
        v-model:visible="showCreate"
        :title="text.createTitle"
        :ok-text="text.create"
        :cancel-text="text.cancel"
        :ok-loading="creating"
        unmount-on-close
        @ok="handleCreate"
      >
        <a-form :model="createForm" layout="vertical">
          <a-form-item :label="text.keyName" required>
            <a-input v-model="createForm.name" :placeholder="text.keyNamePlaceholder" />
          </a-form-item>
        </a-form>
        <a-alert v-if="createdKeyPreview" type="success" style="margin-top: 12px">
          {{ text.createdOnce }}
          <code>{{ createdKeyPreview }}</code>
        </a-alert>
      </a-modal>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { createApiKey, getApiKeyList, type ApiKey } from '@/services/apiKeyService'
import { useAppI18n } from '@/composables/useAppI18n'

const props = defineProps<{
  visible: boolean
  skillNames?: string[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'confirmed', payload: { apiKey: string; keyId: number; keyName: string }): void
}>()

const { isEnglish } = useAppI18n()
const text = computed(() =>
  isEnglish.value
    ? {
        title: 'Confirm API Key for internal Skills',
        hint: 'These platform Skills call backend APIs with an API Key. Confirm which Key to bake into the Skill before install.',
        targetSkills: 'Skills to install',
        noKeys: 'You have no API Key yet. Create one to continue.',
        createNow: 'Create API Key',
        selectKey: 'Select an API Key (required even if only one)',
        createAnother: 'Create new Key',
        inactive: 'Inactive',
        confirmInstall: 'Confirm & install',
        cancel: 'Cancel',
        createTitle: 'Create API Key',
        create: 'Create',
        keyName: 'Key name',
        keyNamePlaceholder: 'e.g. Skill install key',
        createdOnce: 'Created. Full key (shown once):',
        loadFailed: 'Failed to load API Keys',
        createFailed: 'Failed to create API Key',
        nameRequired: 'Please enter a key name',
        selectRequired: 'Please select an API Key',
      }
    : {
        title: '确认内部 Skill 使用的 API Key',
        hint: '平台内部 Skill 会使用 API Key 调用后端接口。安装前请确认要写入 Skill 的 Key。',
        targetSkills: '即将安装的 Skill',
        noKeys: '当前还没有 API Key，请先创建后再安装。',
        createNow: '立即创建 API Key',
        selectKey: '选择一个 API Key（仅有一个时也需确认）',
        createAnother: '新建 Key',
        inactive: '已停用',
        confirmInstall: '确认并安装',
        cancel: '取消',
        createTitle: '创建 API Key',
        create: '创建',
        keyName: 'Key 名称',
        keyNamePlaceholder: '例如：Skill 安装专用',
        createdOnce: '创建成功，完整 Key（仅显示一次）：',
        loadFailed: '加载 API Key 失败',
        createFailed: '创建 API Key 失败',
        nameRequired: '请输入 Key 名称',
        selectRequired: '请选择一个 API Key',
      }
)

const loadingKeys = ref(false)
const submitting = ref(false)
const keys = ref<ApiKey[]>([])
const selectedKeyId = ref<number | null>(null)
const showCreate = ref(false)
const creating = ref(false)
const createdKeyPreview = ref('')
const createForm = reactive({ name: 'Skill install key' })

const skillNames = computed(() => props.skillNames || [])
const canConfirm = computed(() => {
  if (selectedKeyId.value == null) return false
  const item = keys.value.find((k) => k.id === selectedKeyId.value)
  return !!item?.is_active && !!item.key
})

function maskKey(key: string): string {
  if (!key) return ''
  if (key.length <= 8) {
    return `${key.slice(0, 2)}…${key.slice(-2)}`
  }
  return `${key.slice(0, 8)}…${key.slice(-4)}`
}

async function loadKeys() {
  loadingKeys.value = true
  try {
    const res = await getApiKeyList({ pageSize: 100 })
    if (!res.success) {
      throw new Error(res.error || text.value.loadFailed)
    }
    const raw = res.data as any
    const list: ApiKey[] = Array.isArray(raw)
      ? raw
      : Array.isArray(raw?.results)
        ? raw.results
        : Array.isArray(raw?.data)
          ? raw.data
          : []
    keys.value = list.filter((k) => k && k.id != null)
    const active = keys.value.filter((k) => k.is_active)
    if (active.length >= 1) {
      selectedKeyId.value = active[0].id
    }
  } catch (e: any) {
    Message.error(e?.message || text.value.loadFailed)
    keys.value = []
  } finally {
    loadingKeys.value = false
  }
}

async function handleCreate() {
  if (!createForm.name.trim()) {
    Message.warning(text.value.nameRequired)
    return Promise.reject()
  }
  creating.value = true
  try {
    const res = await createApiKey({ name: createForm.name.trim(), is_active: true })
    if (!res.success) {
      throw new Error(res.error || text.value.createFailed)
    }
    const created = res.data as ApiKey
    if (!created?.id || !created.key) {
      throw new Error(text.value.createFailed)
    }
    createdKeyPreview.value = created.key
    await loadKeys()
    selectedKeyId.value = created.id
    Message.success(isEnglish.value ? 'API Key created' : 'API Key 已创建')
    showCreate.value = false
  } catch (e: any) {
    Message.error(e?.message || text.value.createFailed)
    return Promise.reject(e)
  } finally {
    creating.value = false
  }
}

async function handleConfirm() {
  if (!canConfirm.value) {
    Message.warning(text.value.selectRequired)
    throw new Error(text.value.selectRequired)
  }
  const item = keys.value.find((k) => k.id === selectedKeyId.value)!
  submitting.value = true
  try {
    emit('confirmed', {
      apiKey: item.key,
      keyId: item.id,
      keyName: item.name,
    })
    emit('update:visible', false)
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      selectedKeyId.value = null
      createdKeyPreview.value = ''
      createForm.name = isEnglish.value ? 'Skill install key' : 'Skill 安装专用'
      loadKeys()
    }
  }
)
</script>

<style scoped>
.api-key-confirm .label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: var(--color-text-2);
}
.skill-names {
  margin-bottom: 16px;
}
.key-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.key-value {
  font-size: 12px;
  color: var(--color-text-3);
}
.create-row {
  margin-top: 12px;
}
.empty-keys {
  text-align: center;
  padding: 16px 0;
}
</style>
