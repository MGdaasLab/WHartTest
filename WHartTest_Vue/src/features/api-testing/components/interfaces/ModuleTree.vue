<script setup lang="ts">
import { computed, ref, watch, inject } from 'vue'
import type { Ref } from 'vue'
import type { ApiModule, ApiInterface } from '../../services/interfaceService'
import { getInterfaces, getInterfaceById } from '../../services/interfaceService'
import { toArray } from '../../services/responseHelpers'
import {
  IconPlus,
  IconDelete,
  IconRight,
  IconDown,
  IconSend,
  IconEdit,
  IconCopy
} from '@arco-design/web-vue/es/icon'
import { Message } from '@arco-design/web-vue'

interface Props {
  module: ApiModule
  level?: number
  expandedIds: number[]
  selectedId?: number
  selectedInterfaceId?: number
  formLoading?: boolean
  displayMode?: 'list' | 'detail'
  interfaceSelectMode?: 'detail' | 'direct'
}

const props = withDefaults(defineProps<Props>(), {
  level: 0,
  formLoading: false,
  displayMode: 'detail',
  interfaceSelectMode: 'detail'
})

const emit = defineEmits<{
  (e: 'select', module: ApiModule): void
  (e: 'toggle-expand', id: number): void
  (e: 'edit', module: ApiModule): void
  (e: 'add-child', parentId: number): void
  (e: 'delete', module: ApiModule): void
  (e: 'edit-interface', api: ApiInterface): void
  (e: 'delete-interface', api: ApiInterface): void
  (e: 'copy-interface', api: ApiInterface): void
  (e: 'run-interface', api: ApiInterface): void
  (e: 'select-interface', api: ApiInterface): void
}>()

// 接口列表相关状态
const interfaces = ref<ApiInterface[]>([])
const interfaceLoading = ref(false)

const toInterfaceList = (results: unknown): ApiInterface[] => {
  return toArray<ApiInterface>(results)
}

// 获取接口列表
const fetchInterfaces = async (moduleId: number) => {
  try {
    interfaceLoading.value = true
    const response = await getInterfaces({
      module_id: moduleId,
      project_id: props.module.project,
      page_size: 1000
    })
    interfaces.value = toInterfaceList(response.data?.results ?? response.data)
    console.log(`模块${props.module.name}获取到${interfaces.value.length}个接口`)
  } catch (error: any) {
    console.error('获取接口列表失败:', error)
  } finally {
    interfaceLoading.value = false
  }
}

// 导出刷新接口列表方法供父组件调用
defineExpose({
  refreshInterfaces: () => {
    if (props.module.id) {
      fetchInterfaces(props.module.id)
    }
  }
})

const paddingLeft = computed(() => {
  return props.level * 4 + 6
})

const isExpanded = computed(() => {
  return props.expandedIds.includes(props.module.id)
})

const isSelected = computed(() => {
  return props.selectedId === props.module.id
})

// 监听展开状态变化（仅在详情模式下加载接口）
watch(() => isExpanded.value, (newVal) => {
  if (newVal && props.module.id && props.displayMode === 'detail') {
    fetchInterfaces(props.module.id)
  }
})

// 记录已加载详情的接口ID
const loadedInterfaceIds = ref<Set<number>>(new Set())

// 获取接口详情
const fetchInterfaceDetail = async (api: ApiInterface) => {
  try {
    const response = await getInterfaceById(api.id!)
    const data = response.data
    // 更新接口数据
    const index = interfaces.value.findIndex(item => item.id === api.id)
    if (index !== -1) {
      interfaces.value[index] = data
    }
    // 标记为已加载
    if (api.id) {
      loadedInterfaceIds.value.add(api.id)
    }
    // 发送选择事件
    emit('select-interface', data)
  } catch (error: any) {
    console.error('获取接口详情失败:', error)
    Message.error('获取接口详情失败')
  }
}

// 处理接口选择
const handleInterfaceSelect = async (api: ApiInterface) => {
  console.log('接口被点击:', api)

  if (props.interfaceSelectMode === 'direct') {
    emit('select-interface', api)
    return
  }
  
  // 如果已经加载过详情，直接使用
  if (api.id && loadedInterfaceIds.value.has(api.id)) {
    console.log('接口已加载过详情，直接使用')
    emit('select-interface', api)
    return
  }
  
  console.log('接口未加载过详情，开始获取')
  // 否则请求详情
  await fetchInterfaceDetail(api)
}

const handleModuleSelect = () => {
  if (props.module.id && props.displayMode === 'detail') {
    fetchInterfaces(props.module.id)
  }
  emit('select', props.module)
}

// 拖拽排序逻辑注入与处理
const draggingModule = inject<Ref<ApiModule | null>>('draggingModule')
const dragOverModule = inject<Ref<ApiModule | null>>('dragOverModule')
const dragOverPosition = inject<Ref<number | null>>('dragOverPosition')
const handleModuleDrop = inject<(dragged: ApiModule, target: ApiModule, position: number) => Promise<void>>('handleModuleDrop')

const isDragging = computed(() => draggingModule?.value?.id === props.module.id)
const isDragOver = computed(() => dragOverModule?.value?.id === props.module.id)
const currentDragOverPos = computed(() => isDragOver.value ? dragOverPosition?.value : null)

const handleDragStart = (e: DragEvent) => {
  if (draggingModule) {
    draggingModule.value = props.module
  }
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(props.module.id))
  }
}

const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
  if (!draggingModule?.value || draggingModule.value.id === props.module.id) return

  // 防止将父模块拖拽到其子孙模块下
  const descendantIds = getAllDescendantIds(draggingModule.value)
  if (descendantIds.includes(props.module.id)) {
    return
  }

  if (dragOverModule) {
    dragOverModule.value = props.module
  }

  // 根据鼠标在目标元素上的垂直坐标，判断位置（-1 之前，0 之中/作为子模块，1 之后）
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const relativeY = e.clientY - rect.top
  const height = rect.height

  let position = 0
  if (relativeY < height * 0.25) {
    position = -1
  } else if (relativeY > height * 0.75) {
    position = 1
  } else {
    position = 0
  }

  if (dragOverPosition) {
    dragOverPosition.value = position
  }
}

const getAllDescendantIds = (module: ApiModule): number[] => {
  let ids = [module.id]
  if (module.children) {
    module.children.forEach(child => {
      ids = ids.concat(getAllDescendantIds(child))
    })
  }
  return ids
}

const handleDragLeave = () => {
  if (dragOverModule?.value?.id === props.module.id) {
    dragOverModule.value = null
    if (dragOverPosition) {
      dragOverPosition.value = null
    }
  }
}

const handleDragEnd = () => {
  if (draggingModule) {
    draggingModule.value = null
  }
  if (dragOverModule) {
    dragOverModule.value = null
  }
  if (dragOverPosition) {
    dragOverPosition.value = null
  }
}

const handleDrop = async (e: DragEvent) => {
  e.preventDefault()
  if (!draggingModule?.value || draggingModule.value.id === props.module.id) return
  if (!handleModuleDrop || dragOverPosition?.value === null) return

  const position = dragOverPosition.value
  const dragged = draggingModule.value

  await handleModuleDrop(dragged, props.module, position)
}
</script>

<template>
  <div class="module-tree space-y-1">
    <!-- 当前模块 -->
    <div
      class="module-tree__item px-6 py-2 cursor-pointer transition-colors rounded-lg"
      :class="{ 
        'module-tree__item--selected': isSelected,
        'module-tree__item--dragging': isDragging,
        'module-tree__item--drag-over-before': currentDragOverPos === -1,
        'module-tree__item--drag-over-inside': currentDragOverPos === 0,
        'module-tree__item--drag-over-after': currentDragOverPos === 1
      }"
      :style="{ paddingLeft: `${paddingLeft}px` }"
      draggable="true"
      @dragstart="handleDragStart"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @dragend="handleDragEnd"
      @drop="handleDrop"
      @click.stop="handleModuleSelect"
    >
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="w-4 flex items-center justify-center">
            <a-button
              v-if="(displayMode === 'detail' && (module.children?.length || interfaces.length)) || (displayMode === 'list' && module.children?.length)"
              type="text"
              size="mini"
              class="module-tree__toggle-btn !w-4 !h-4 !p-0 !min-w-0"
              @click.stop="emit('toggle-expand', module.id)"
            >
              <template #icon>
                <icon-right v-if="!isExpanded" class="!w-3 !h-3" />
                <icon-down v-else class="!w-3 !h-3" />
              </template>
            </a-button>
            <div v-else class="w-4"></div>
          </div>
          <a-spin :loading="interfaceLoading" dot>
            <span class="module-tree__name">{{ module.name }}</span>
          </a-spin>
        </div>
        <div class="flex items-center -mr-4">
          <a-button
            v-if="level < 2"
            type="text"
            size="mini"
            class="module-tree__action-btn !p-0"
            @click.stop="emit('add-child', module.id)"
          >
            <template #icon><icon-plus /></template>
          </a-button>
          <a-button
            type="text"
            size="mini"
            class="module-tree__action-btn !p-0"
            @click.stop="emit('edit', module)"
          >
            <template #icon><icon-edit /></template>
          </a-button>
          <a-button
            type="text"
            size="mini"
            class="module-tree__action-btn !p-0"
            @click.stop="emit('delete', module)"
          >
            <template #icon><icon-delete /></template>
          </a-button>
        </div>
      </div>
    </div>

    <div v-if="isExpanded" class="space-y-1">
      <!-- 接口列表（仅在详情模式下显示） -->
      <template v-if="displayMode === 'detail' && interfaces.length">
        <div class="space-y-1">
          <div
            v-for="api in interfaces"
            :key="api.id"
            class="module-tree__interface-item px-6 py-2 text-sm rounded min-w-0 cursor-pointer"
            :class="{ 'module-tree__interface-item--selected': selectedInterfaceId === api.id }"
            :style="{ paddingLeft: `${paddingLeft + 4}px` }"
            @click="handleInterfaceSelect(api)"
          >
            <div class="module-tree__interface-main">
              <div class="module-tree__interface-info">
                <a-tag
                  :color="api.method === 'GET' ? 'blue' : api.method === 'POST' ? 'green' : api.method === 'PUT' ? 'orange' : 'red'"
                  class="!w-16 !flex !justify-center !flex-shrink-0"
                >
                  {{ api.method }}
                </a-tag>
                <span class="module-tree__interface-name truncate" :title="api.name">{{ api.name }}</span>
              </div>
              <div class="module-tree__interface-actions -mr-4 ml-4">
                <a-button
                  type="text"
                  size="mini"
                  class="module-tree__action-btn !p-0"
                  @click.stop="emit('run-interface', api)"
                  title="调试接口"
                >
                  <template #icon><icon-send /></template>
                </a-button>
                <a-button
                  type="text"
                  size="mini"
                  class="module-tree__action-btn !p-0"
                  @click.stop="emit('edit-interface', api)"
                  title="编辑接口"
                >
                  <template #icon><icon-edit /></template>
                </a-button>
                <a-button
                  type="text"
                  size="mini"
                  class="module-tree__action-btn !p-0"
                  @click.stop="emit('copy-interface', api)"
                  title="复制接口"
                >
                  <template #icon><icon-copy /></template>
                </a-button>
                <a-button
                  type="text"
                  size="mini"
                  class="module-tree__action-btn !p-0"
                  @click.stop="emit('delete-interface', api)"
                  title="删除接口"
                >
                  <template #icon><icon-delete /></template>
                </a-button>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- 子模块递归渲染 -->
      <div v-if="module.children?.length" class="space-y-1">
        <ModuleTree
          v-for="child in module.children"
          :key="child.id"
          :module="child"
          :level="level + 1"
          :expanded-ids="expandedIds"
          :selected-id="selectedId"
          :selected-interface-id="selectedInterfaceId"
          :form-loading="formLoading"
          :display-mode="displayMode"
          :interface-select-mode="interfaceSelectMode"
          @select="emit('select', $event)"
          @toggle-expand="emit('toggle-expand', $event)"
          @edit="emit('edit', $event)"
          @add-child="emit('add-child', $event)"
          @delete="emit('delete', $event)"
          @edit-interface="emit('edit-interface', $event)"
          @delete-interface="emit('delete-interface', $event)"
          @copy-interface="emit('copy-interface', $event)"
          @run-interface="emit('run-interface', $event)"
          @select-interface="emit('select-interface', $event)"
        />
      </div>
    </div>
  </div>
</template>

<style lang="postcss" scoped>
.module-tree {
  --module-action-text: rgb(100, 116, 139);
  --module-action-hover: rgb(71, 85, 105);
  --module-interface-bg: rgba(148, 163, 184, 0.16);
  --module-interface-hover-bg: rgba(148, 163, 184, 0.26);
  --module-interface-text: var(--color-text-2);
}

.module-tree__toggle-btn,
.module-tree__action-btn {
  color: var(--module-action-text) !important;
}

.module-tree__toggle-btn:hover,
.module-tree__action-btn:hover {
  color: var(--module-action-hover) !important;
}

.module-tree__interface-item {
  background: var(--module-interface-bg);
  color: var(--module-interface-text);
  overflow: hidden;
}

.module-tree__interface-item:hover {
  background: var(--module-interface-hover-bg);
}

.module-tree__interface-item--selected {
  background: var(--interface-module-active, rgba(24, 144, 255, 0.16));
  box-shadow: inset 0 0 0 1px var(--interface-module-active-border, rgba(24, 144, 255, 0.2));
}

.module-tree__interface-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.75rem;
  min-width: 0;
  width: 100%;
}

.module-tree__interface-info {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  column-gap: 0.5rem;
  min-width: 0;
  overflow: hidden;
}

.module-tree__interface-name {
  display: block;
  flex: 1 1 auto;
  min-width: 0;
}

.module-tree__interface-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

:global(body.api-testing-theme) .module-tree {
  --module-action-text: #6b7785;
  --module-action-hover: #86909c;
  --module-interface-bg: rgba(70, 84, 102, 0.2);
  --module-interface-hover-bg: rgba(70, 84, 102, 0.4);
  --module-interface-text: rgb(156, 163, 175);
}

.module-tree__item {
  background-color: var(--interface-module-surface, rgba(15, 23, 42, 0.05));
}

.module-tree__item:hover {
  background-color: var(--interface-module-hover, rgba(24, 144, 255, 0.1));
}

.module-tree__item--selected {
  background-color: var(--interface-module-active, rgba(24, 144, 255, 0.16));
  box-shadow: inset 0 0 0 1px var(--interface-module-active-border, rgba(24, 144, 255, 0.2));
}

.module-tree__item--dragging {
  opacity: 0.4;
  border: 1px dashed var(--color-text-3, #86909c);
}

.module-tree__item--drag-over-before {
  position: relative;
}
.module-tree__item--drag-over-before::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background-color: var(--color-primary, #165dff);
  z-index: 10;
}

.module-tree__item--drag-over-inside {
  background-color: var(--interface-module-hover, rgba(24, 144, 255, 0.15)) !important;
  outline: 2px solid var(--color-primary, #165dff);
}

.module-tree__item--drag-over-after {
  position: relative;
}
.module-tree__item--drag-over-after::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background-color: var(--color-primary, #165dff);
  z-index: 10;
}

.module-tree__name {
  color: var(--interface-text-primary, var(--color-text-1, #1d2129));
  font-weight: 500;
}

/* 隐藏滚动条但保留滚动功能 */
.scrollbar-hide {
  -ms-overflow-style: none;  /* IE and Edge */
  scrollbar-width: none;  /* Firefox */
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;  /* Chrome, Safari and Opera */
}
</style>
