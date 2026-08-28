<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import {
  IconClose,
  IconEdit,
  IconCode,
  IconDelete,
  IconSettings,
  IconCopy,
} from '@arco-design/web-vue/es/icon'
import MonacoEditor from '@guolao/vue-monaco-editor'
import type { Function } from '../../services/functionService'
import { useThemeStore } from '@/store/themeStore'

interface Props {
  loading?: boolean
  functionData: Function
}

interface Emits {
  (e: 'close'): void
  (e: 'edit', func: Function): void
  (e: 'delete', func: Function): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const emit = defineEmits<Emits>()
const themeStore = useThemeStore()

// 只读代码内容（用于 v-model:value 绑定）
const codeContent = ref(props.functionData.code)
const editorTheme = computed(() => (themeStore.isBlack ? 'vs-dark' : 'vs'))

const editorOptions = {
  minimap: { enabled: true },
  readOnly: true,
  scrollBeyondLastLine: false,
  fontSize: 14,
  tabSize: 4,
  renderLineHighlight: 'all',
  roundedSelection: false,
  occurrencesHighlight: 'off',
  padding: { top: 10, bottom: 10 }
}

// 监听函数数据变化
watch(
  () => props.functionData,
  (newData) => {
    codeContent.value = newData.code
  },
  { deep: true }
)

// 处理编辑按钮点击
const handleEdit = () => {
  emit('edit', props.functionData)
}

// 处理删除按钮点击
const handleDelete = () => {
  emit('delete', props.functionData)
}

// 复制函数名称到剪贴板
const handleCopyName = () => {
  navigator.clipboard.writeText(props.functionData.name)
}
</script>

<template>
  <div class="function-detail-panel h-full overflow-hidden">
    <a-spin :loading="loading" dot class="!block h-full">
      <div class="h-full overflow-y-auto overflow-x-hidden custom-scrollbar p-6 space-y-4">
        <!-- 顶部信息栏 -->
        <a-card class="detail-top-card !rounded-lg">
          <div class="flex items-center justify-between flex-wrap gap-y-2">
            <div class="flex items-center gap-3 mr-2">
              <div class="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                <icon-code class="text-blue-500" />
              </div>
              <h2 class="text-lg font-medium detail-title">
                {{ functionData.name }}
              </h2>
              <a-tag
                :color="functionData.is_active ? 'green' : 'red'"
                size="small"
              >{{ functionData.is_active ? '启用' : '禁用' }}</a-tag>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <a-button type="outline" size="small" @click="handleEdit">
                <template #icon><icon-edit /></template>
                编辑
              </a-button>
              <a-button type="outline" size="small" @click="handleCopyName">
                <template #icon><icon-copy /></template>
                复制名称
              </a-button>
              <a-popconfirm
                content="确定要删除这个函数吗？"
                type="warning"
                position="left"
                @ok="handleDelete"
              >
                <a-button type="outline" status="danger" size="small">
                  <template #icon><icon-delete /></template>
                  删除
                </a-button>
              </a-popconfirm>
              <a-button type="text" size="small" @click="emit('close')">
                <template #icon><icon-close /></template>
              </a-button>
            </div>
          </div>
        </a-card>

        <!-- 基本信息卡片 -->
        <a-card class="detail-info-card !rounded-lg">
          <template #title>
            <div class="flex items-center gap-2">
              <icon-settings class="detail-subtle" />
              <span class="detail-text">基本信息</span>
            </div>
          </template>
          <div class="space-y-6 overflow-hidden">
            <!-- 函数名称 -->
            <div class="space-y-2">
              <div class="text-sm detail-subtle">函数名称</div>
              <div class="detail-block p-3 rounded-lg break-all">
                {{ functionData.name }}
              </div>
            </div>
            <!-- 函数描述 -->
            <div class="space-y-2">
              <div class="text-sm detail-subtle">函数描述</div>
              <div class="detail-block p-3 rounded-lg whitespace-pre-wrap">
                {{ functionData.description || '暂无描述' }}
              </div>
            </div>
            <!-- 创建信息 -->
            <div class="space-y-2">
              <div class="text-sm detail-subtle">创建信息</div>
              <div class="detail-block p-3 rounded-lg space-y-2">
                <div class="flex items-center gap-2 flex-wrap" v-if="functionData.created_by">
                  <span class="detail-subtle">创建人：</span>
                  <span class="break-all">{{ functionData.created_by_name || '-' }}</span>
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="detail-subtle">创建时间：</span>
                  <span>{{ functionData.created_at ? new Date(functionData.created_at).toLocaleString('zh-CN') : '-' }}</span>
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="detail-subtle">更新时间：</span>
                  <span>{{ functionData.updated_at ? new Date(functionData.updated_at).toLocaleString('zh-CN') : '-' }}</span>
                </div>
              </div>
            </div>
          </div>
        </a-card>

        <!-- 函数代码卡片 -->
        <a-card class="detail-top-card !rounded-lg">
          <template #title>
            <div class="flex items-center gap-2">
              <icon-code class="detail-subtle" />
              <span class="detail-text">函数代码</span>
            </div>
          </template>
          <div class="editor-shell">
            <MonacoEditor
              v-model:value="codeContent"
              language="python"
              :theme="editorTheme"
              :options="editorOptions"
              style="height: 500px; width: 100%;"
            />
          </div>
        </a-card>
      </div>
    </a-spin>
  </div>
</template>

<style lang="postcss" scoped>
@reference "tailwindcss";

.detail-top-card,
.detail-info-card {
  background: var(--func-shell-bg) !important;
  border: 1px solid var(--func-shell-border) !important;
  box-shadow: var(--func-shell-shadow);
}

.detail-title,
.detail-text {
  color: var(--func-text);
}

.detail-subtle {
  color: var(--func-text-subtle);
}

.detail-block {
  background: color-mix(in srgb, var(--func-card-bg) 86%, var(--theme-page-bg) 14%);
  border: 1px solid var(--func-card-border);
  color: var(--func-text-muted);
}

.editor-shell {
  border: 1px solid var(--func-editor-border);
  border-radius: 0.5rem;
  overflow: hidden;
  background: var(--func-editor-bg);
}

.custom-scrollbar {
  scrollbar-width: none;
  -ms-overflow-style: none;

  &::-webkit-scrollbar {
    display: none;
  }
}

:deep(.arco-btn-text) {
  color: var(--func-text-subtle);

  &:hover {
    color: var(--func-text) !important;
    background: rgba(var(--theme-accent-rgb), 0.08) !important;
  }
}

:deep(.arco-card-header) {
  border-bottom: 1px solid var(--func-shell-border);
}

:deep(.arco-card-header-title) {
  color: var(--func-text);
}

:deep(.arco-card-body) {
  text-align: left;
}
</style>
