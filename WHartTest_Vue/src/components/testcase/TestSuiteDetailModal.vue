<template>
  <a-modal
    v-model:visible="modalVisible"
    title="测试套件详情"
    width="800px"
    :footer="false"
    @cancel="handleClose"
  >
    <a-spin :loading="loading" style="width: 100%;">
      <div v-if="suiteDetail" class="suite-detail-content">
        <!-- 基本信息 -->
        <div class="detail-section">
          <h3 class="section-title">基本信息</h3>
          <a-descriptions :column="2" bordered>
            <a-descriptions-item label="套件名称">
              {{ suiteDetail.name }}
            </a-descriptions-item>
            <a-descriptions-item label="套件ID">
              {{ suiteDetail.id }}
            </a-descriptions-item>
            <a-descriptions-item label="创建者">
              {{ suiteDetail.creator_detail?.username || '-' }}
            </a-descriptions-item>
            <a-descriptions-item label="用例数量">
              <a-tag color="blue">{{ suiteDetail.testcase_count }} 个</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="创建时间">
              {{ formatDate(suiteDetail.created_at) }}
            </a-descriptions-item>
            <a-descriptions-item label="更新时间">
              {{ formatDate(suiteDetail.updated_at) }}
            </a-descriptions-item>
            <a-descriptions-item label="描述" :span="2">
              {{ suiteDetail.description || '暂无描述' }}
            </a-descriptions-item>
          </a-descriptions>
        </div>

        <!-- 用例列表 -->
        <div class="detail-section">
          <h3 class="section-title">关联用例列表</h3>
          <a-table
            v-if="suiteDetail.testcases_detail && suiteDetail.testcases_detail.length > 0"
            :columns="testCaseColumns"
            :data="suiteDetail.testcases_detail"
            :pagination="false"
            :bordered="{ cell: true }"
            row-key="id"
            size="small"
          >
            <template #level="{ record }">
              <a-tag :color="getLevelColor(record.level)">
                {{ record.level }}
              </a-tag>
            </template>
          </a-table>
          <a-empty v-else description="该套件暂无关联用例" />
        </div>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { Message } from '@arco-design/web-vue';
import { getTestSuiteDetail, type TestSuite } from '@/services/testSuiteService';
import type { TestCase } from '@/services/testcaseService';

interface Props {
  visible: boolean;
  currentProjectId: number | null;
  suiteId: number | null;
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  currentProjectId: null,
  suiteId: null,
});

const emit = defineEmits<{
  (e: 'update:visible', visible: boolean): void;
}>();

const loading = ref(false);
const suiteDetail = ref<TestSuite | null>(null);

const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
});

const testCaseColumns = [
  { title: 'ID', dataIndex: 'id', width: 80, align: 'center' as const },
  { title: '用例名称', dataIndex: 'name', ellipsis: true, tooltip: true, align: 'center' as const },
  { title: '优先级', dataIndex: 'level', slotName: 'level', width: 100, align: 'center' as const },
  { title: '模块', dataIndex: 'module_detail', ellipsis: true, tooltip: true, width: 200, align: 'center' as const },
];

const formatDate = (dateString: string) => {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const getLevelColor = (level: string) => {
  const colorMap: Record<string, string> = {
    'P0': 'red',
    'P1': 'orange',
    'P2': 'blue',
    'P3': 'gray',
  };
  return colorMap[level] || 'gray';
};

const fetchSuiteDetail = async () => {
  if (!props.currentProjectId || !props.suiteId) {
    return;
  }

  loading.value = true;
  try {
    const response = await getTestSuiteDetail(props.currentProjectId, props.suiteId);
    
    if (response.success && response.data) {
      suiteDetail.value = response.data;
    } else {
      Message.error(response.error || '获取测试套件详情失败');
      handleClose();
    }
  } catch (error) {
    console.error('获取测试套件详情出错:', error);
    Message.error('获取测试套件详情时发生错误');
    handleClose();
  } finally {
    loading.value = false;
  }
};

const handleClose = () => {
  modalVisible.value = false;
  suiteDetail.value = null;
};

watch(() => props.visible, (newVal) => {
  if (newVal) {
    fetchSuiteDetail();
  }
});
</script>

<style scoped>
.suite-detail-content {
  padding: 16px 0;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.section-title {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
  border-left: 3px solid #165dff;
  padding-left: 8px;
}
</style>