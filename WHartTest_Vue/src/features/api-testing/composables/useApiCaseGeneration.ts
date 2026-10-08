/**
 * AI 生成接口测试用例：弹窗与提交编排（供接口用例/场景用例面板共用）。
 */
import { h, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { Notification } from '@arco-design/web-vue';
import { useProjectStore } from '@/store/projectStore';
import { useAppI18n } from '@/composables/useAppI18n';
import { sendChatMessageStream } from '@/features/langgraph/services/chatService';
import type { ChatRequest } from '@/features/langgraph/types/chat';
import { getInterfaces } from '../services/interfaceService';
import {
  extractConstraints,
  collectExistingInterfaceCaseNames,
  collectExistingScenarioCaseNames,
  buildGenerationMessage,
  type GenerationFormData,
  type ConstraintExtractResult,
  type GenerationInterfaceInfo,
} from '../services/apiCaseGeneration';
import type { ApiInterface } from '../types/interface';

type GenerateApiCasesModalInstance = InstanceType<typeof import('../components/generate/GenerateApiCasesModal.vue').default>;

export function useApiCaseGeneration() {
  const projectStore = useProjectStore();
  const router = useRouter();
  const { tl } = useAppI18n();

  const showGenerateModal = ref(false);
  const modalRef = ref<GenerateApiCasesModalInstance | null>(null);
  const projectId = computed(() => projectStore.currentProjectId);

  const fetchSelectedInterfaces = async (ids: number[]): Promise<GenerationInterfaceInfo[]> => {
    const idSet = new Set(ids);
    // getInterfaces 返回 { data: { results, count }, status } 形状（无 success 字段），与弹窗 fetchData 一致的读取方式
    const response: any = await getInterfaces({ page_size: 200 });
    const payload: any = response?.data;
    const list: ApiInterface[] = Array.isArray(payload) ? payload : payload?.results || [];
    return list.filter(item => idSet.has(item.id)) as GenerationInterfaceInfo[];
  };

  const showStartNotification = () => {
    const notificationReturn = Notification.info({
      title: tl('AI 生成任务已启动'),
      content: tl('用例将逐条生成并保存（含试跑验证），完成后可在对话页查看总结'),
      footer: () => h(
        'div',
        { style: 'text-align: right; margin-top: 12px;' },
        [
          h(
            'a',
            {
              href: 'javascript:;',
              onClick: () => {
                router.push({ name: 'LangGraphChat' });
                if (notificationReturn) notificationReturn.close();
              },
            },
            tl('查看生成进度'),
          ),
        ],
      ),
      duration: 10000,
    });
  };

  const handleGenerateSubmit = async (formData: GenerationFormData) => {
    if (!projectId.value) return;
    try {
      // 0. 登录接口 ID（选中集合外的也要拉取定义）
      const allNeededIds = formData.loginInterfaceId
        ? Array.from(new Set([...formData.interfaceIds, formData.loginInterfaceId]))
        : formData.interfaceIds;

      // 1. 获取接口定义（带完整 body/params/validators 的详情字段）
      const allInterfaces = await fetchSelectedInterfaces(allNeededIds);
      const interfaces = allInterfaces.filter(item => formData.interfaceIds.includes(item.id));
      const loginInterface = formData.loginInterfaceId
        ? allInterfaces.find(item => item.id === formData.loginInterfaceId) || null
        : null;
      if (!interfaces.length) {
        Notification.warning({
          title: tl('获取接口定义失败'),
          content: tl('未能获取选中接口的完整定义，请重试'),
          duration: 5000,
        });
        return;
      }

      // 2. 约束提取（有文档时）：弹窗关闭前直接从组件实例取用户上传的文件
      let constraints: ConstraintExtractResult | null = null;
      let documentName = '';
      const file = modalRef.value?.getDocumentFile() || null;
      if (file) {
        try {
          constraints = await extractConstraints(file, formData.interfaceIds);
          documentName = file.name;
        } catch {
          Notification.warning({
            title: tl('约束提取失败'),
            content: tl('接口文档解析失败，将按无约束模式生成'),
            duration: 5000,
          });
        }
      }

      // 3. 已有用例名清单
      const existingNames = formData.caseType === 'scenario'
        ? await collectExistingScenarioCaseNames().catch(() => [])
        : await collectExistingInterfaceCaseNames(formData.interfaceIds).catch(() => []);

      // 4. 拼装指令并发送
      const message = buildGenerationMessage({
        formData,
        interfaces,
        projectId: projectId.value,
        existingNames,
        constraints,
        documentName,
        loginInterface,
      });

      const requestData: ChatRequest = {
        message,
        project_id: String(projectId.value),
        module_key: 'testcase_generation',
        use_knowledge_base: formData.useKnowledgeBase && !!formData.knowledgeBaseId,
      };
      if (formData.knowledgeBaseId) {
        requestData.knowledge_base_id = formData.knowledgeBaseId;
      }

      showStartNotification();

      sendChatMessageStream(
        requestData,
        (sessionId) => {
          localStorage.setItem('langgraph_session_id', sessionId);
          localStorage.setItem('langgraph_knowledge_settings', JSON.stringify({
            useKnowledgeBase: requestData.use_knowledge_base || false,
            selectedKnowledgeBaseId: formData.knowledgeBaseId || null,
            similarityThreshold: 0.3,
            topK: 5,
          }));
        },
      );
    } catch (error: any) {
      Notification.error({
        title: tl('启动失败'),
        content: error?.message || tl('生成任务启动失败，请重试'),
        duration: 5000,
      });
    }
  };

  return {
    showGenerateModal,
    modalRef,
    handleGenerateSubmit,
  };
}
