<template>
  <a-modal
    v-model:visible="modalVisible"
    :title="isEditing ? '编辑模块' : '添加模块'"
    @ok="handleSubmit"
    @cancel="handleCancel"
    :mask-closable="false"
    :confirm-loading="formLoading"
  >
    <a-form ref="moduleFormRef" :model="formState" :rules="moduleFormRules" layout="vertical">
      <a-form-item field="name" label="模块名称">
        <a-input v-model="formState.name" placeholder="请输入模块名称" allow-clear />
      </a-form-item>
      <a-form-item field="parent" label="父模块 (可选)">
        <a-tree-select
          v-model="formState.parent"
          :data="moduleTree"
          placeholder="请选择父模块 (不选则为根模块)"
          allow-clear
          allow-search
          :field-names="{ key: 'id', title: 'name' }"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch, toRefs } from 'vue';
import { Message } from '@arco-design/web-vue';
import type { FormInstance, TreeNodeData } from '@arco-design/web-vue';
import {
  createTestCaseModule,
  updateTestCaseModule,
  type CreateTestCaseModuleRequest,
  type UpdateTestCaseModuleRequest,
} from '@/services/testcaseModuleService';

const props = defineProps<{
  visible: boolean;
  isEditing: boolean;
  initialData?: CreateTestCaseModuleRequest & { id?: number };
  moduleTree: TreeNodeData[];
  projectId: number | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'submit', success: boolean): void;
}>();

const { visible, isEditing, initialData, moduleTree, projectId } = toRefs(props);

const modalVisible = ref(visible.value);
const formLoading = ref(false);
const moduleFormRef = ref<FormInstance>();

const formState = reactive<CreateTestCaseModuleRequest & { id?: number }>({
  id: undefined,
  name: '',
  parent: undefined,
});

const moduleFormRules = {
  name: [
    { required: true, message: '请输入模块名称' },
    { maxLength: 50, message: '模块名称长度不能超过50个字符' },
  ],
};

watch(visible, (newVal) => {
  modalVisible.value = newVal;
  if (newVal) {
    // 重置表单状态
    formLoading.value = false;
    moduleFormRef.value?.resetFields();
    if (initialData?.value) {
      formState.id = initialData.value.id;
      formState.name = initialData.value.name;
      formState.parent = initialData.value.parent;
    } else {
      formState.id = undefined;
      formState.name = '';
      formState.parent = undefined;
    }
  }
});

watch(initialData, (newData) => {
  if (newData) {
    formState.id = newData.id;
    formState.name = newData.name;
    formState.parent = newData.parent;
  } else {
    formState.id = undefined;
    formState.name = '';
    formState.parent = undefined;
  }
}, { deep: true });


const handleSubmit = async () => {
  if (!projectId.value) {
    Message.error('项目ID不存在，无法提交');
    return;
  }
  try {
    const validation = await moduleFormRef.value?.validate();
    if (validation) {
      return; // 验证失败
    }

    formLoading.value = true;
    let response;
    const payload: CreateTestCaseModuleRequest | UpdateTestCaseModuleRequest = {
      name: formState.name,
      parent: formState.parent || undefined,
    };

    if (isEditing.value && formState.id) {
      response = await updateTestCaseModule(projectId.value, formState.id, payload);
    } else {
      response = await createTestCaseModule(projectId.value, payload as CreateTestCaseModuleRequest);
    }

    if (response.success) {
      Message.success(isEditing.value ? '模块更新成功' : '模块添加成功');
      emit('submit', true);
    } else {
      Message.error(response.error || (isEditing.value ? '更新模块失败' : '添加模块失败'));
      emit('submit', false);
    }
  } catch (error) {
    console.error('模块操作失败:', error);
    Message.error('模块操作时发生错误');
    emit('submit', false);
  } finally {
    formLoading.value = false;
  }
};

const handleCancel = () => {
  emit('close');
};

</script>