<template>
  <div class="permission-table">
    <!-- 权限树形展示 -->
    <PermissionTreeSelector
      :type="type"
      :id="id"
      @refresh="handleRefresh"
    />
  </div>
</template>

<script setup lang="ts">
import PermissionTreeSelector from './PermissionTreeSelector.vue';

const props = defineProps<{
  type: 'user' | 'group';
  id: number;
}>();

const emit = defineEmits<{
  (e: 'refresh'): void;
}>();

// 处理刷新事件
const handleRefresh = () => {
  emit('refresh');
};
</script>

<style scoped>
.permission-table {
  margin-top: 20px;
  height: 100%;
}
</style>
