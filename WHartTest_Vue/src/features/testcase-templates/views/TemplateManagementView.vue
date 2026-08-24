<template>
  <div class="template-management-view">
    <a-page-header title="用例导入导出模版管理" :show-back="true" @back="$router.back()">
      <template #extra>
        <a-button type="primary" @click="handleCreate">
          <template #icon><icon-plus /></template>
          新建模版
        </a-button>
      </template>
    </a-page-header>

    <a-card class="template-list-card">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <a-space>
          <a-select
            v-model="filters.template_type"
            placeholder="模版类型"
            allow-clear
            style="width: 120px"
            @change="loadTemplates"
          >
            <a-option value="import">导入</a-option>
            <a-option value="export">导出</a-option>
            <a-option value="both">导入/导出</a-option>
          </a-select>
          <a-select
            v-model="filters.is_active"
            placeholder="状态"
            allow-clear
            style="width: 100px"
            @change="loadTemplates"
          >
            <a-option :value="true">启用</a-option>
            <a-option :value="false">禁用</a-option>
          </a-select>
        </a-space>
      </div>

      <!-- 模版列表 -->
      <a-table
        :columns="columns"
        :data="templates"
        :loading="loading"
        :pagination="false"
        row-key="id"
        :scroll="{ x: 900 }"
      >
        <template #empty>
          <div class="empty-state">
            <icon-file-image style="font-size: 48px; color: var(--color-text-4);" />
            <p class="empty-text">暂无模版</p>
            <p class="empty-desc">点击上方"新建模版"创建您的第一个导入导出模版</p>
          </div>
        </template>
        <template #template_type="{ record }">
          <a-tag :color="getTypeColor(record.template_type)">
            {{ record.template_type_display }}
          </a-tag>
        </template>

        <template #is_active="{ record }">
          <a-switch
            :model-value="record.is_active"
            @change="(val: string | number | boolean) => handleToggleActive(record, Boolean(val))"
          />
        </template>

        <template #created_at="{ record }">
          {{ formatDate(record.created_at) }}
        </template>

        <template #actions="{ record }">
          <a-space>
            <a-button size="small" @click="handleEdit(record)">编辑</a-button>
            <a-button size="small" @click="handleDuplicate(record)">复制</a-button>
            <a-popconfirm
              content="确定要删除此模版吗？"
              @ok="handleDelete(record)"
            >
              <a-button size="small" status="danger">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </a-card>

    <!-- 创建/编辑模版弹窗 -->
    <TemplateFormModal
      ref="formModalRef"
      @success="loadTemplates"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconPlus, IconFileImage } from '@arco-design/web-vue/es/icon';
import {
  getTemplateList,
  deleteTemplate,
  updateTemplate,
  duplicateTemplate,
  type ImportExportTemplateListItem,
  type TemplateType,
} from '../services/templateService';
import TemplateFormModal from '../components/TemplateFormModal.vue';

const loading = ref(false);
const templates = ref<ImportExportTemplateListItem[]>([]);
const formModalRef = ref<InstanceType<typeof TemplateFormModal> | null>(null);

const filters = reactive({
  template_type: undefined as TemplateType | undefined,
  is_active: undefined as boolean | undefined,
});

const columns = [
  { title: '模版名称', dataIndex: 'name', width: 200 },
  { title: '类型', dataIndex: 'template_type', slotName: 'template_type', width: 100 },
  { title: '描述', dataIndex: 'description', ellipsis: true },
  { title: '状态', dataIndex: 'is_active', slotName: 'is_active', width: 80 },
  { title: '创建人', dataIndex: 'creator_name', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', slotName: 'created_at', width: 160 },
  { title: '操作', slotName: 'actions', width: 180, fixed: 'right' },
];

const getTypeColor = (type: TemplateType) => {
  const colors: Record<TemplateType, string> = {
    import: 'green',
    export: 'blue',
    both: 'purple',
  };
  return colors[type] || 'gray';
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const loadTemplates = async () => {
  loading.value = true;
  try {
    const result = await getTemplateList({
      template_type: filters.template_type,
      is_active: filters.is_active,
    });
    if (result.success && result.data) {
      templates.value = result.data;
    } else {
      Message.error(result.error || '加载模版列表失败');
    }
  } finally {
    loading.value = false;
  }
};

const handleCreate = () => {
  formModalRef.value?.open();
};

const handleEdit = (record: ImportExportTemplateListItem) => {
  formModalRef.value?.open(record.id);
};

const handleToggleActive = async (record: ImportExportTemplateListItem, isActive: boolean) => {
  const result = await updateTemplate(record.id, { is_active: isActive });
  if (result.success) {
    Message.success(isActive ? '已启用' : '已禁用');
    loadTemplates();
  } else {
    Message.error(result.error || '操作失败');
  }
};

const handleDuplicate = async (record: ImportExportTemplateListItem) => {
  const result = await duplicateTemplate(record.id);
  if (result.success) {
    Message.success('复制成功');
    loadTemplates();
  } else {
    Message.error(result.error || '复制失败');
  }
};

const handleDelete = async (record: ImportExportTemplateListItem) => {
  const result = await deleteTemplate(record.id);
  if (result.success) {
    Message.success('删除成功');
    loadTemplates();
  } else {
    Message.error(result.error || '删除失败');
  }
};

onMounted(() => {
  loadTemplates();
});
</script>

<style scoped>
.template-management-view {
  padding: 20px 24px;
  min-height: 100%;
  background: var(--color-bg-1);
}

.template-list-card {
  margin-top: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.filter-bar {
  margin-bottom: 20px;
  padding: 16px 20px;
  background: var(--color-fill-1);
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .template-management-view {
    padding: 12px 16px;
  }

  .filter-bar {
    padding: 12px;
  }

  .template-list-card :deep(.arco-table-th),
  .template-list-card :deep(.arco-table-td) {
    padding: 10px 8px;
    font-size: 13px;
  }
}

@media (max-width: 576px) {
  .template-management-view {
    padding: 8px 12px;
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-bar :deep(.arco-select) {
    width: 100% !important;
  }
}

/* 表格优化 */
.template-list-card :deep(.arco-table) {
  border-radius: 6px;
  overflow: hidden;
}

.template-list-card :deep(.arco-table-th) {
  background: var(--color-fill-2);
  font-weight: 600;
}

.template-list-card :deep(.arco-table-tr:hover .arco-table-td) {
  background: var(--color-fill-1);
}

/* 操作按钮组优化 */
.template-list-card :deep(.arco-btn-size-small) {
  padding: 0 10px;
  height: 28px;
  font-size: 13px;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
}

.empty-text {
  margin: 16px 0 8px;
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-2);
}

.empty-desc {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-3);
}
</style>
