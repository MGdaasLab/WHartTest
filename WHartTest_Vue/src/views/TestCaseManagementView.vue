<template>
  <div class="testcase-management-container">
    <!-- 始终显示模块管理面板 -->
    <div class="list-view-layout">
      <ModuleManagementPanel
        :current-project-id="currentProjectId"
        @module-selected="handleModuleSelected"
        @module-updated="handleModuleUpdated"
        ref="modulePanelRef"
      />

      <!-- 右侧内容区域 - 根据视图模式动态切换 -->
      <div class="right-content-area">
        <!-- 列表视图 -->
        <TestCaseList
          v-if="viewMode === 'list'"
          :current-project-id="currentProjectId"
          :selected-module-id="selectedModuleId"
          @add-test-case="showAddTestCaseForm"
          @generate-test-cases="showGenerateCasesModal"
          @edit-test-case="showEditTestCaseForm"
          @view-test-case="showViewTestCaseDetail"
          @test-case-deleted="handleTestCaseDeleted"
          ref="testCaseListRef"
        />

        <!-- 添加/编辑测试用例表单 -->
        <TestCaseForm
          v-else-if="viewMode === 'add' || viewMode === 'edit'"
          :is-editing="viewMode === 'edit'"
          :test-case-id="currentEditingTestCaseId"
          :current-project-id="currentProjectId"
          :initial-selected-module-id="selectedModuleId"
          :module-tree="moduleTreeForForm"
          @close="backToList"
          @submit-success="handleFormSubmitSuccess"
        />

        <!-- 查看测试用例详情 -->
        <TestCaseDetail
          v-else-if="viewMode === 'view'"
          :test-case-id="currentViewingTestCaseId"
          :current-project-id="currentProjectId"
          :modules="allModules"
          @close="backToList"
          @edit-test-case="showEditTestCaseForm"
          @test-case-deleted="handleViewDetailTestCaseDeleted"
        />
      </div>
    </div>

    <GenerateCasesModal
      v-model:visible="isGenerateCasesModalVisible"
      :test-case-module-tree="moduleTreeForForm"
      @submit="handleGenerateCasesSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { h, ref, computed, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProjectStore } from '@/store/projectStore';
import type { TestCase } from '@/services/testcaseService';
import type { TestCaseModule } from '@/services/testcaseModuleService';
import type { TreeNodeData } from '@arco-design/web-vue';
import { getTestCaseModules } from '@/services/testcaseModuleService';
import { Message, Notification } from '@arco-design/web-vue';

import ModuleManagementPanel from '@/components/testcase/ModuleManagementPanel.vue';
import TestCaseList from '@/components/testcase/TestCaseList.vue';
import TestCaseForm from '@/components/testcase/TestCaseForm.vue';
import TestCaseDetail from '@/components/testcase/TestCaseDetail.vue';
import GenerateCasesModal from '@/components/testcase/GenerateCasesModal.vue';
import {
  sendChatMessageStream
} from '@/features/langgraph/services/chatService';

const router = useRouter();
const projectStore = useProjectStore();
const currentProjectId = computed(() => projectStore.currentProjectId || null);

const viewMode = ref<'list' | 'add' | 'edit' | 'view'>('list');
const selectedModuleId = ref<number | null>(null);
const currentEditingTestCaseId = ref<number | null>(null);
const currentViewingTestCaseId = ref<number | null>(null);
const isGenerateCasesModalVisible = ref(false);

const modulePanelRef = ref<InstanceType<typeof ModuleManagementPanel> | null>(null);
const testCaseListRef = ref<InstanceType<typeof TestCaseList> | null>(null);

// 存储所有模块数据，用于传递给详情页和表单
const allModules = ref<TestCaseModule[]>([]);
const moduleTreeForForm = ref<TreeNodeData[]>([]); // 用于表单的模块树

const fetchAllModulesForForm = async () => {
  if (!currentProjectId.value) {
    allModules.value = [];
    moduleTreeForForm.value = [];
    return;
  }
  try {
    const response = await getTestCaseModules(currentProjectId.value, {}); // 获取所有模块
    if (response.success && response.data) {
      allModules.value = response.data;
      moduleTreeForForm.value = buildModuleTree(response.data);
    } else {
      allModules.value = [];
      moduleTreeForForm.value = [];
      Message.error(response.error || '加载模块数据失败');
    }
  } catch (error) {
    Message.error('加载模块数据时发生错误');
    allModules.value = [];
    moduleTreeForForm.value = [];
  }
};

// 构建模块树 (扁平列表转树形) - 这个函数也可以放到 utils 中
const buildModuleTree = (modules: TestCaseModule[], parentId: number | null = null): TreeNodeData[] => {
  return modules
    .filter(module => module.parent === parentId || module.parent_id === parentId)
    .map(module => ({
      key: module.id, // ArcoDesign tree-select 使用 key 作为选中值
      title: module.name, // ArcoDesign tree-select 使用 title 作为显示文本
      id: module.id, // 保留原始id用于兼容
      name: module.name, // 保留原始name用于兼容
      children: buildModuleTree(modules, module.id),
      // selectable: true, // 根据需要设置
    }));
};


const handleModuleSelected = (moduleId: number | null) => {
  selectedModuleId.value = moduleId;
  // 列表组件会自动 watch selectedModuleId 并刷新
};

const handleModuleUpdated = () => {
  // 模块更新后，可能需要刷新模块面板自身（如果它没有自动刷新的话）
  // modulePanelRef.value?.refreshModules(); // 假设 ModuleManagementPanel 有此方法
  // 同时刷新模块数据给表单用
  fetchAllModulesForForm();
  // 如果用例列表依赖模块信息（比如显示模块名），也可能需要刷新用例列表
  // testCaseListRef.value?.refreshTestCases();
};

const showAddTestCaseForm = () => {
  currentEditingTestCaseId.value = null;
  viewMode.value = 'add';
};

const showEditTestCaseForm = (testCaseOrId: TestCase | number) => {
  currentEditingTestCaseId.value = typeof testCaseOrId === 'number' ? testCaseOrId : testCaseOrId.id;
  viewMode.value = 'edit';
};

const showViewTestCaseDetail = (testCase: TestCase) => {
  currentViewingTestCaseId.value = testCase.id;
  viewMode.value = 'view';
};

const backToList = () => {
  viewMode.value = 'list';
  currentEditingTestCaseId.value = null;
  currentViewingTestCaseId.value = null;
};

const handleFormSubmitSuccess = () => {
  backToList();
  testCaseListRef.value?.refreshTestCases(); // 刷新列表
  // 如果用例创建/更新影响了模块的用例数量，需要通知模块面板刷新
  modulePanelRef.value?.refreshModules();
};

const handleTestCaseDeleted = () => {
  // 用例在列表组件内部删除并刷新列表，这里可能需要刷新模块面板的用例计数
  modulePanelRef.value?.refreshModules();
};

const handleViewDetailTestCaseDeleted = () => {
    // 从详情页删除后，返回列表并刷新
    backToList();
    testCaseListRef.value?.refreshTestCases();
    modulePanelRef.value?.refreshModules();
};

const showGenerateCasesModal = () => {
  isGenerateCasesModalVisible.value = true;
};

const handleGenerateCasesSubmit = async (formData: {
  requirementDocumentId: string,
  requirementModuleId: string,
  promptId: number,
  useKnowledgeBase: boolean,
  knowledgeBaseId?: string | null,
  testCaseModuleId: number,
  selectedModule: { title: string, content: string }
}) => {
  if (!currentProjectId.value) {
    Message.error('没有有效的项目ID');
    return;
  }

  isGenerateCasesModalVisible.value = false;

  // 构造一个结构清晰、更接近自然语言的 message
  const message = `
请根据以下需求模块信息，为我生成测试用例。

---
[需求模块标题]
${formData.selectedModule.title}

---
[需求模块内容]
${formData.selectedModule.content}
---

请注意：生成的测试用例最终需要被保存在 **项目ID "${currentProjectId.value}"** 下的 **测试用例模块ID "${formData.testCaseModuleId}"** 中。
(此需求模块来源于需求文档ID: ${formData.requirementDocumentId})
  `.trim();

  const requestData: any = {
    message: message,
    project_id: String(currentProjectId.value),
    prompt_id: formData.promptId,
    use_knowledge_base: formData.useKnowledgeBase,
  };

  // 如果启用了知识库并且选择了具体的知识库，则添加ID
  if (formData.useKnowledgeBase && formData.knowledgeBaseId) {
    requestData.knowledge_base_id = formData.knowledgeBaseId;
  }

  // 使用改造后的 service，它将自动处理全局流状态
  sendChatMessageStream(
    requestData,
    (sessionId) => {
      // onStart 回调，在收到 session_id 后立即执行
      // 将会话ID保存到 localStorage，以便聊天页面可以加载它
      localStorage.setItem('langgraph_session_id', sessionId);
      
      const notificationReturn = Notification.info({
        title: '任务已开始',
        content: '用例生成任务已在后台开始处理。',
        footer: () => h(
          'div',
          {
            style: 'text-align: right; margin-top: 12px;',
          },
          [
            h(
              'a',
              {
                href: 'javascript:;',
                onClick: () => {
                  // 点击后，跳转到聊天页面
                  router.push({ name: 'LangGraphChat' });
                  // 关闭通知
                  if (notificationReturn) {
                    notificationReturn.close();
                  }
                },
              },
              '点此查看生成过程'
            ),
          ]
        ),
        duration: 10000, // 10秒后自动关闭
        id: `gen-case-${sessionId}`, // 使用唯一的通知ID
      });

      // 这里不再需要手动处理 onComplete 和 onError,
      // 因为流的状态被全局管理了。
      // 可以在 LangGraphChatView 的 onActivated 或 watch 中处理完成后的逻辑，
      // 例如刷新用例列表。
      // 为了保持简单，我们暂时让用户手动刷新。
    }
  );
};


watch(currentProjectId, (newVal) => {
  selectedModuleId.value = null; // 项目切换时清空已选模块
  // 列表和模块面板会各自 watch projectId 并刷新
  if (newVal) {
    fetchAllModulesForForm(); // 项目切换时，重新加载模块给表单
  } else {
    allModules.value = [];
    moduleTreeForForm.value = [];
  }
});

onMounted(() => {
    if (currentProjectId.value) {
        fetchAllModulesForForm();
    }
});

</script>

<style scoped>
.testcase-management-container {
  display: flex;
  height: 100%;
  background-color: var(--color-bg-1);
  overflow: hidden;
}

.list-view-layout {
  display: flex;
  width: 100%;
  height: 100%;
  gap: 10px;
  overflow: hidden;
}

/* 右侧内容区域样式 */
.right-content-area {
  flex: 1;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 4px 0 10px rgba(0, 0, 0, 0.2), 0 4px 10px rgba(0, 0, 0, 0.2), 0 0 10px rgba(0, 0, 0, 0.15);
  padding: 20px; /* 添加内边距，与其他卡片保持一致 */
}

/* 确保右侧内容区域中的所有组件都能正确显示 */
.right-content-area > * {
  flex: 1;
  height: 100%;
  overflow: auto; /* 允许子组件自行滚动，修复表单无法滚动的问题 */
  /* 移除子组件自身的阴影、边框和内边距，因为它们现在在右侧内容区域内 */
  box-shadow: none !important;
  border-radius: 0 !important;
  padding: 0 !important;
}
</style>
