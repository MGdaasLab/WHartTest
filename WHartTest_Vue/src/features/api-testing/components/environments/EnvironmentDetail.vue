<script setup lang="ts">
import { computed } from 'vue'
import type { Environment } from '../../services/environmentService'
import {
  IconStorage,
  IconEdit,
  IconCopy,
  IconDelete,
  IconSettings,
  IconApps,
} from '@arco-design/web-vue/es/icon'
import { useThemeStore } from '@/store/themeStore'

interface Props {
  environment: Environment
}

interface Emits {
  (e: 'edit'): void
  (e: 'clone'): void
  (e: 'delete'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()
const themeStore = useThemeStore()
const isDarkTheme = computed(() => themeStore.isBlack)
</script>

<template>
  <div
    class="environment-detail h-full overflow-hidden"
    :class="isDarkTheme ? 'environment-detail--dark' : 'environment-detail--light'"
  >
    <div class="h-full overflow-y-auto overflow-x-hidden custom-scrollbar p-6 space-y-4">
      <a-card class="detail-card detail-card--hero !rounded-lg">
        <div class="flex items-center justify-between flex-wrap gap-y-2">
          <div class="flex items-center gap-3 mr-2">
            <div class="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
              <icon-storage class="text-blue-500" />
            </div>
            <h2 class="detail-hero-title text-lg font-medium">
              {{ environment.name }}
            </h2>
            <a-tag
              :color="environment.is_active ? 'green' : 'red'"
              size="small"
            >{{ environment.is_active ? '启用' : '禁用' }}</a-tag>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <a-button type="outline" size="small" @click="emit('edit')">
              <template #icon><icon-edit /></template>
              编辑
            </a-button>
            <a-button type="outline" size="small" @click="emit('clone')">
              <template #icon><icon-copy /></template>
              克隆
            </a-button>
            <a-popconfirm
              content="确定要删除这个环境吗？"
              type="warning"
              position="left"
              @ok="emit('delete')"
            >
              <a-button type="outline" status="danger" size="small">
                <template #icon><icon-delete /></template>
                删除
              </a-button>
            </a-popconfirm>
          </div>
        </div>
      </a-card>

      <a-card class="detail-card detail-card--panel !rounded-lg">
        <template #title>
          <div class="flex items-center gap-2">
            <icon-settings class="detail-section-icon" />
            <span class="detail-section-title">基本信息</span>
          </div>
        </template>
        <div class="space-y-6 overflow-hidden">
          <div class="space-y-2">
            <div class="detail-label text-sm">所属项目</div>
            <div class="detail-value-shell p-3 rounded-lg break-all">
              {{ environment.project_info?.name || environment.project_name }}
            </div>
          </div>
          <div class="space-y-2" v-if="environment.parent_info">
            <div class="detail-label text-sm">父环境</div>
            <div class="detail-value-shell p-3 rounded-lg break-all">
              {{ environment.parent_info.name }}
            </div>
          </div>
          <div class="space-y-2" v-if="environment.database_config_info">
            <div class="detail-label text-sm">数据库配置</div>
            <div class="detail-value-shell p-3 rounded-lg space-y-2">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="detail-inline-label">名称：</span>
                <span class="detail-value-text break-all">{{ environment.database_config_info.name }}</span>
              </div>
              <div class="flex items-center gap-2 flex-wrap">
                <span class="detail-inline-label">类型：</span>
                <span class="detail-value-text">{{ environment.database_config_info.db_type }}</span>
              </div>
              <div class="flex items-center gap-2 flex-wrap">
                <span class="detail-inline-label">主机：</span>
                <span class="detail-value-text">{{ environment.database_config_info.host }}</span>
              </div>
            </div>
          </div>
          <div class="space-y-2">
            <div class="detail-label text-sm">基础 URL</div>
            <div class="detail-value-shell p-3 rounded-lg break-all">
              {{ environment.base_url }}
            </div>
          </div>
          <div class="space-y-2" v-if="environment.description">
            <div class="detail-label text-sm">描述</div>
            <div class="detail-value-shell p-3 rounded-lg whitespace-pre-wrap">
              {{ environment.description }}
            </div>
          </div>
          <div class="space-y-2">
            <div class="detail-label text-sm">创建信息</div>
            <div class="detail-value-shell p-3 rounded-lg space-y-2">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="detail-inline-label">创建人：</span>
                <span class="detail-value-text break-all">{{ environment.created_by_name }}</span>
              </div>
              <div class="flex items-center gap-2 flex-wrap">
                <span class="detail-inline-label">创建时间：</span>
                <span class="detail-value-text">{{ new Date(environment.created_at).toLocaleString('zh-CN') }}</span>
              </div>
              <div class="flex items-center gap-2 flex-wrap">
                <span class="detail-inline-label">更新时间：</span>
                <span class="detail-value-text">{{ new Date(environment.updated_at).toLocaleString('zh-CN') }}</span>
              </div>
            </div>
          </div>
        </div>
      </a-card>

      <a-card class="detail-card detail-card--hero !rounded-lg">
        <template #title>
          <div class="flex items-center gap-2">
            <icon-apps class="detail-section-icon" />
            <span class="detail-section-title">环境变量</span>
          </div>
        </template>
        <div class="space-y-4 overflow-hidden">
          <div
            v-for="(variable, index) in environment.variables"
            :key="index"
            class="variable-card flex items-start gap-3 p-3 rounded-lg"
          >
            <div class="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center flex-shrink-0">
              <icon-apps class="text-purple-400" />
            </div>
            <div class="flex-1 min-w-0 overflow-hidden">
              <div class="flex items-center gap-2 mb-2 flex-wrap">
                <span class="detail-value-text text-sm font-medium">变量 #{{ index + 1 }}</span>
                <span class="detail-meta-dot text-xs">·</span>
                <span class="detail-label text-xs truncate">{{ variable.description || '暂无描述' }}</span>
              </div>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div class="space-y-1 overflow-hidden">
                  <div class="detail-label text-xs">变量名</div>
                  <div class="detail-value-text text-sm break-all">{{ variable.name }}</div>
                </div>
                <div class="space-y-1 overflow-hidden">
                  <div class="detail-label text-xs">变量值</div>
                  <div class="detail-value-text text-sm break-all">{{ variable.value }}</div>
                </div>
              </div>
            </div>
          </div>

          <div
            v-if="!environment.variables?.length"
            class="detail-label text-center py-8"
          >
            暂无环境变量
          </div>
        </div>
      </a-card>
    </div>
  </div>
</template>

<style lang="postcss" scoped>
.environment-detail {
  --env-card-bg: rgba(255, 255, 255, 0.92);
  --env-card-hero-bg: linear-gradient(135deg, rgba(248, 250, 252, 0.98), rgba(241, 245, 249, 0.94));
  --env-card-border: rgba(148, 163, 184, 0.2);
  --env-value-bg: rgba(248, 250, 252, 0.92);
  --env-value-border: rgba(148, 163, 184, 0.16);
  --env-value-hover: rgba(241, 245, 249, 0.98);
  --env-text: var(--color-text-1);
  --env-subtle: var(--color-text-3);
  --env-muted: var(--color-text-2);
  --env-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}

.environment-detail--dark {
  --env-card-bg: rgba(17, 24, 39, 0.62);
  --env-card-hero-bg: linear-gradient(135deg, rgba(29, 36, 51, 0.96), rgba(17, 24, 39, 0.9));
  --env-card-border: rgba(55, 65, 81, 0.92);
  --env-value-bg: rgba(31, 41, 55, 0.58);
  --env-value-border: rgba(75, 85, 99, 0.38);
  --env-value-hover: rgba(31, 41, 55, 0.82);
  --env-text: rgb(229, 231, 235);
  --env-subtle: rgb(156, 163, 175);
  --env-muted: rgb(209, 213, 219);
  --env-shadow: 0 10px 26px rgba(0, 0, 0, 0.18);
}

.custom-scrollbar {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
  
  &::-webkit-scrollbar {
    display: none; /* Chrome, Safari, Opera*/
  }
}

.detail-card {
  background: var(--env-card-bg);
  border: 1px solid var(--env-card-border);
  box-shadow: var(--env-shadow);
}

.detail-card--hero {
  background: var(--env-card-hero-bg);
}

.detail-hero-title,
.detail-section-title,
.detail-value-text {
  color: var(--env-text);
}

.detail-section-icon,
.detail-label,
.detail-inline-label,
.detail-meta-dot {
  color: var(--env-subtle);
}

.detail-value-shell,
.variable-card {
  background: var(--env-value-bg);
  border: 1px solid var(--env-value-border);
  color: var(--env-muted);
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.detail-value-shell:hover,
.variable-card:hover {
  background: var(--env-value-hover);
}

.environment-detail :deep(.arco-card-header) {
  background: transparent;
  border-bottom-color: var(--env-card-border);
}

.environment-detail :deep(.arco-card-body) {
  background: transparent;
}
</style> 