<template>
  <div class="knowledge-management">
    <div v-if="!selectedKB" class="page-header">
      <h1 class="page-title">知识库管理</h1>
      <div class="header-actions">
        <a-button type="primary" @click="showCreateModal">
          <template #icon><icon-plus /></template>
          新建知识库
        </a-button>
      </div>
    </div>

    <div class="content-container">
      <!-- 知识库列表 -->
      <div v-if="!selectedKB" class="knowledge-base-list">
        <div class="list-header">
          <div class="search-bar">
            <a-input-search
              v-model="searchKeyword"
              placeholder="搜索知识库..."
              style="width: 300px"
              @search="handleSearch"
              @clear="handleSearch"
            />
          </div>
          <div class="filter-bar">
            <a-select
              v-model="statusFilter"
              placeholder="状态筛选"
              style="width: 120px"
              @change="handleSearch"
            >
              <a-option value="">全部</a-option>
              <a-option value="true">启用</a-option>
              <a-option value="false">禁用</a-option>
            </a-select>
          </div>
        </div>

        <a-table
          :columns="columns"
          :data="knowledgeBases"
          :loading="loading"
          :pagination="pagination"
          @page-change="handlePageChange"
          @page-size-change="handlePageSizeChange"
        >
          <template #name="{ record }">
            <a-link @click="selectKnowledgeBase(record)">{{ record.name }}</a-link>
          </template>

          <template #project="{ record }">
            {{ getProjectName(record.project) }}
          </template>

          <template #status="{ record }">
            <a-tag :color="record.is_active ? 'green' : 'red'">
              {{ record.is_active ? '启用' : '禁用' }}
            </a-tag>
          </template>

          <template #stats="{ record }">
            <div class="stats-cell">
              <div>文档: {{ record.document_count }}</div>
              <div>分块: {{ record.chunk_count }}</div>
            </div>
          </template>

          <template #actions="{ record }">
            <a-space>
              <a-button type="text" size="small" @click="editKnowledgeBase(record)">
                编辑
              </a-button>
              <a-button type="text" size="small" @click="viewStatistics(record)">
                统计
              </a-button>
              <a-popconfirm
                content="确定要删除这个知识库吗？"
                @ok="deleteKnowledgeBase(record.id)"
              >
                <a-button type="text" size="small" status="danger">
                  删除
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </a-table>
      </div>

      <!-- 右侧详情面板 - 占据整个内容区域 -->
      <div v-if="selectedKB" class="detail-panel-full">
        <KnowledgeBaseDetail
          :knowledge-base="selectedKB"
          @refresh="refreshKnowledgeBases"
          @close="selectedKB = null"
        />
      </div>
    </div>

    <!-- 创建/编辑知识库弹窗 -->
    <KnowledgeBaseFormModal
      :visible="isFormModalVisible"
      :knowledge-base="editingKB"
      @submit="handleSubmitKnowledgeBase"
      @cancel="closeFormModal"
    />

    <!-- 统计信息弹窗 -->
    <KnowledgeBaseStatsModal
      :visible="isStatsModalVisible"
      :knowledge-base-id="statsKBId"
      @close="closeStatsModal"
    />

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { Message } from '@arco-design/web-vue';
import { IconPlus } from '@arco-design/web-vue/es/icon';
import { useProjectStore } from '@/store/projectStore';
import { KnowledgeService } from '../services/knowledgeService';
import type { KnowledgeBase } from '../types/knowledge';
import KnowledgeBaseDetail from '../components/KnowledgeBaseDetail.vue';
import KnowledgeBaseFormModal from '../components/KnowledgeBaseFormModal.vue';
import KnowledgeBaseStatsModal from '../components/KnowledgeBaseStatsModal.vue';

const projectStore = useProjectStore();

// 响应式数据
const knowledgeBases = ref<KnowledgeBase[]>([]);
const loading = ref(false);
const searchKeyword = ref('');
const statusFilter = ref('');
const selectedKB = ref<KnowledgeBase | null>(null);
const editingKB = ref<KnowledgeBase | null>(null);
const isFormModalVisible = ref(false);
const isStatsModalVisible = ref(false);
const statsKBId = ref('');

// 分页配置
const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showTotal: true,
  showPageSize: true,
});

// 表格列配置
const columns = [
  {
    title: '知识库名称',
    dataIndex: 'name',
    slotName: 'name',
    width: 200,
    align: 'center',
  },
  {
    title: '描述',
    dataIndex: 'description',
    width: 200,
    align: 'center',
    render: ({ record }: { record: KnowledgeBase }) => {
      return record.description || '暂无描述';
    },
  },
  {
    title: '所属项目',
    slotName: 'project',
    width: 150,
    align: 'center',
  },
  {
    title: '状态',
    dataIndex: 'is_active',
    slotName: 'status',
    width: 80,
    align: 'center',
  },
  {
    title: '统计',
    slotName: 'stats',
    width: 100,
    align: 'center',
  },
  {
    title: '创建者',
    dataIndex: 'creator_name',
    width: 100,
    align: 'center',
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    width: 150,
    align: 'center',
    render: ({ record }: { record: KnowledgeBase }) => {
      return new Date(record.created_at).toLocaleDateString();
    },
  },
  {
    title: '操作',
    slotName: 'actions',
    width: 150,
    align: 'center',
    fixed: 'right',
  },
];

// 方法
const fetchKnowledgeBases = async () => {
  loading.value = true;
  try {
    const params: any = {
      ordering: '-created_at', // 默认按创建时间倒序排列
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    };

    // 如果有选中的项目，只显示该项目的知识库
    if (projectStore.currentProjectId) {
      params.project = projectStore.currentProjectId;
    }

    if (searchKeyword.value) {
      params.search = searchKeyword.value;
    }

    if (statusFilter.value) {
      params.is_active = statusFilter.value === 'true';
    }

    const data = await KnowledgeService.getKnowledgeBases(params);

    // 检查返回的数据格式
    if (data && typeof data === 'object' && 'results' in data) {
      // 分页响应格式
      knowledgeBases.value = data.results;
      pagination.value.total = data.count;
    } else if (Array.isArray(data)) {
      // 数组格式（向后兼容）
      knowledgeBases.value = data;
      pagination.value.total = data.length;
    } else {
      knowledgeBases.value = [];
      pagination.value.total = 0;
    }
  } catch (error: any) {
    console.error('获取知识库列表失败:', error);
    // 显示具体的错误消息
    const errorMessage = error?.message || '获取知识库列表失败';
    Message.error(errorMessage);
    knowledgeBases.value = [];
    pagination.value.total = 0;
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  pagination.value.current = 1;
  fetchKnowledgeBases();
};

const handlePageChange = (page: number) => {
  pagination.value.current = page;
  fetchKnowledgeBases();
};

const handlePageSizeChange = (pageSize: number) => {
  pagination.value.pageSize = pageSize;
  pagination.value.current = 1;
  fetchKnowledgeBases();
};

const selectKnowledgeBase = (kb: KnowledgeBase) => {
  selectedKB.value = kb;
};

const showCreateModal = () => {
  editingKB.value = null;
  isFormModalVisible.value = true;
};

const editKnowledgeBase = (kb: KnowledgeBase) => {
  editingKB.value = kb;
  isFormModalVisible.value = true;
};

const closeFormModal = () => {
  isFormModalVisible.value = false;
  editingKB.value = null;
};

const handleSubmitKnowledgeBase = async () => {
  const isEdit = !!editingKB.value;
  closeFormModal();
  await refreshKnowledgeBases();
  Message.success(isEdit ? '知识库更新成功' : '知识库创建成功');
};

const deleteKnowledgeBase = async (id: string) => {
  try {
    await KnowledgeService.deleteKnowledgeBase(id);
    Message.success('知识库删除成功');
    await refreshKnowledgeBases();

    // 如果删除的是当前选中的知识库，清除选中状态
    if (selectedKB.value?.id === id) {
      selectedKB.value = null;
    }
  } catch (error: any) {
    console.error('删除知识库失败:', error);
    // 显示具体的错误消息
    const errorMessage = error?.message || '删除知识库失败';
    Message.error(errorMessage);
  }
};

const viewStatistics = (kb: KnowledgeBase) => {
  statsKBId.value = kb.id;
  isStatsModalVisible.value = true;
};

const closeStatsModal = () => {
  isStatsModalVisible.value = false;
  statsKBId.value = '';
};

const refreshKnowledgeBases = () => {
  fetchKnowledgeBases();
};

const getProjectName = (projectId: number | string) => {
  // 首先尝试从知识库数据中获取项目名称
  const kb = knowledgeBases.value.find(kb => kb.project === Number(projectId));
  if (kb && kb.project_name) {
    return kb.project_name;
  }

  // 如果没有，从项目store中获取
  const project = projectStore.projectOptions.find(p => p.value === Number(projectId));
  return project ? project.label : String(projectId);
};

// 监听项目变化，重新加载数据
watch(() => projectStore.currentProjectId, (newProjectId, oldProjectId) => {
  if (newProjectId !== oldProjectId) {
    // 项目切换时重置状态
    pagination.value.current = 1;
    searchKeyword.value = '';
    statusFilter.value = '';
    selectedKB.value = null;

    // 重新获取知识库列表
    fetchKnowledgeBases();
  }
}, { immediate: false });

// 生命周期
onMounted(async () => {
  // 等待项目store初始化完成
  if (projectStore.loading) {
    await new Promise((resolve) => {
      const unwatch = watch(() => projectStore.loading, (loading) => {
        if (!loading) {
          unwatch();
          resolve(void 0);
        }
      });
    });
  }
  
  // 如果项目store没有项目列表，主动获取一次
  if (projectStore.projectList.length === 0) {
    await projectStore.fetchProjects();
  }
  
  fetchKnowledgeBases();
});
</script>

<style scoped>
.knowledge-management {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  font-size: 24px;
  font-weight: bold;
  margin: 0;
}

.content-container {
  flex: 1;
  display: flex;
  gap: 20px;
  overflow: hidden;
  margin-top: 0;
}

/* 当没有页面标题时，调整内容容器的上边距 */
.knowledge-management:has(.detail-panel-full) .content-container {
  margin-top: 20px;
}

.knowledge-base-list {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.detail-panel-full {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.search-bar {
  display: flex;
  gap: 12px;
}

.filter-bar {
  display: flex;
  gap: 12px;
}



.stats-cell {
  font-size: 12px;
  color: #666;
}
</style>
