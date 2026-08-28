<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { FormInstance } from '@arco-design/web-vue'
import type { ApiModule } from '../../services/interfaceService'
import { IconClose } from '@arco-design/web-vue/es/icon'
import { useThemeStore } from '@/store/themeStore'

interface Props {
  visible: boolean
  type: 'create' | 'edit'
  loading: boolean
  apis?: ApiModule[]
  currentModule?: ApiModule
  parentId?: number
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const emit = defineEmits<{
  (e: 'update:visible', visible: boolean): void
  (e: 'submit', formData: any): void
}>()

const themeStore = useThemeStore()
const formRef = ref<FormInstance>()
const isDarkTheme = computed(() => themeStore.isBlack)

// 表单数据
const formData = ref({
  name: '',
  description: '',
  parent: undefined as number | undefined
})

// 表单验证规则
const rules = {
  name: [
    { required: true, message: '请输入模块名称' }
  ]
}

// 关闭弹窗
const handleClose = () => {
  emit('update:visible', false)
  resetForm()
}

// 重置表单
const resetForm = () => {
  formData.value = {
    name: '',
    description: '',
    parent: undefined
  }
}

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
    emit('submit', {
      ...formData.value,
      parent: formData.value.parent || props.parentId || undefined
    })
  } catch (error) {
    // 表单验证失败
    console.error('表单验证失败:', error)
  }
}

// 监听visible变化,初始化表单数据
watch(() => props.visible, (newVal) => {
  if (newVal && props.type === 'edit' && props.currentModule) {
    formData.value = {
      name: props.currentModule.name,
      description: props.currentModule.description || '',
      parent: props.currentModule.parent === null ? undefined : props.currentModule.parent
    }
  } else {
    resetForm()
  }
})
</script>

<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center">
    <div
      class="fixed inset-0 backdrop-blur-sm"
      :class="isDarkTheme ? 'bg-black/60' : 'bg-black/30'"
      @click="handleClose"
    ></div>
    <a-card 
      :bordered="false"
      class="w-[500px] z-10"
      :class="isDarkTheme ? '!bg-gray-800 !border-gray-700' : '!bg-white !border-gray-200 shadow-lg'"
    >
      <template #title>
        <div class="flex justify-between items-center">
          <span :class="isDarkTheme ? 'text-gray-100' : 'text-gray-800'">{{ type === 'create' ? '新建模块' : '编辑模块' }}</span>
          <a-button type="text" @click="handleClose">
            <template #icon>
              <icon-close />
            </template>
          </a-button>
        </div>
      </template>
      <a-form
        ref="formRef"
        :model="formData"
        :rules="rules"
        layout="vertical"
        autocomplete="off"
      >
        <a-form-item field="name" label="模块名称" validate-trigger="blur">
          <a-input
            v-model="formData.name"
            placeholder="请输入模块名称"
            allow-clear
            :disabled="loading"
            aria-label="模块名称输入框"
            autocomplete="off"
          />
        </a-form-item>
        <a-form-item v-if="type === 'create'" field="parent" label="父级模块" validate-trigger="blur">
          <a-select
            v-model="formData.parent"
            placeholder="请选择父级模块（可选）"
            allow-clear
            :disabled="loading || !!parentId"
          >
            <a-option
              v-for="api in apis"
              :key="api.id"
              :value="api.id"
            >
              {{ api.name }}
            </a-option>
          </a-select>
        </a-form-item>
        <a-form-item field="description" label="模块描述" validate-trigger="blur">
          <a-textarea
            v-model="formData.description"
            placeholder="请输入模块描述"
            allow-clear
            :disabled="loading"
          />
        </a-form-item>
        <div class="flex justify-end gap-2 mt-6">
          <a-button @click="handleClose" class="w-24" :disabled="loading" aria-label="取消">取消</a-button>
          <a-button type="primary" :loading="loading" @click="handleSubmit" class="w-24" aria-label="确定">
            确定
          </a-button>
        </div>
      </a-form>
    </a-card>
  </div>
</template>