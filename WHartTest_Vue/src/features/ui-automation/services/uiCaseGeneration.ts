/**
 * AI 一键生成 UI 自动化测试用例：编排服务。
 * 负责需求模块/环境/登录态/已有对象收集，以及生成指令（message）拼装。
 */
import axiosInstance from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import { moduleApi, pageApi, testCaseApi, envConfigApi, authStateApi } from '../api';
import type { UiModule, UiPage, UiTestCase, UiEnvironmentConfig, UiAuthState } from '../types';
import type { DocumentModule } from '@/features/requirements/types';

const base = (projectId: number) => `/projects/${projectId}`;

export type UiGenerationDepth = 'positive' | 'full';

export interface UiGenerationFormData {
  requirementDocumentId: string | null;
  requirementModuleId: string | null;
  targetModuleId: number | null;
  envConfigId: number | null;
  authMode: 'auth_state' | 'credentials' | 'none';
  authStateId: number | null;
  username: string;
  password: string;
  depth: UiGenerationDepth;
  caseLimit: number;
  useKnowledgeBase: boolean;
  knowledgeBaseId: string | null;
  businessNotes: string;
}

export interface UiGenerationRequirementModule extends DocumentModule {
  document_id: string;
  document_title?: string;
}

/** 获取项目下已拆分模块的需求文档列表（用于级联选择需求模块） */
export async function fetchRequirementDocuments(projectId: number): Promise<Array<{ id: string; title: string }>> {
  const response = await axiosInstance({
    url: `/requirements/documents/`,
    method: 'GET',
    params: { project: projectId, page_size: 100 },
  });
  const payload = (response.data as any)?.data ?? response.data;
  const list = Array.isArray(payload) ? payload : payload?.results || [];
  // 仅取已完成模块拆分的文档，未拆分文档没有可选模块
  return list
    .filter((item: any) => ['module_split', 'user_reviewing', 'ready_for_review', 'reviewing', 'review_completed'].includes(item.status))
    .map((item: any) => ({ id: item.id, title: item.title || item.id }));
}

/** 获取需求文档下已拆分的模块列表 */
export async function fetchRequirementModules(documentId: string): Promise<DocumentModule[]> {
  const response = await axiosInstance({
    url: `/requirements/modules/`,
    method: 'GET',
    params: { document: documentId, page_size: 200 },
  });
  const payload = (response.data as any)?.data ?? response.data;
  const list = Array.isArray(payload) ? payload : payload?.results || [];
  return list as DocumentModule[];
}

/** 获取项目环境配置列表 */
export async function fetchEnvConfigs(projectId: number): Promise<UiEnvironmentConfig[]> {
  const response = await envConfigApi.list({ project: projectId, page_size: 100 } as any);
  const payload: any = (response.data as any)?.data ?? response.data;
  return (Array.isArray(payload) ? payload : payload?.results || []) as UiEnvironmentConfig[];
}

/** 获取环境绑定的登录态列表 */
export async function fetchAuthStates(envConfigId: number): Promise<UiAuthState[]> {
  const response = await authStateApi.list({ env_config: envConfigId, is_active: true } as any);
  const payload: any = (response.data as any)?.data ?? response.data;
  return (Array.isArray(payload) ? payload : payload?.results || []) as UiAuthState[];
}

/** 展开模块树为扁平列表（带层级前缀，用于下拉展示） */
export function flattenModuleTree(tree: UiModule[], depth = 0, out: Array<{ id: number; label: string }> = []) {
  for (const node of tree) {
    out.push({ id: node.id, label: `${'　'.repeat(depth)}${node.name}` });
    if (node.children?.length) flattenModuleTree(node.children, depth + 1, out);
  }
  return out;
}

/** 获取保存目标模块树 */
export async function fetchModuleTree(projectId: number): Promise<UiModule[]> {
  const response = await moduleApi.tree(projectId);
  const payload: any = (response.data as any)?.data ?? response.data;
  return (Array.isArray(payload) ? payload : payload?.results || []) as UiModule[];
}

/**
 * 收集已有页面名/URL 与用例名（用于生成前查重）。
 */
export async function collectExistingUiObjects(projectId: number): Promise<{
  pageNames: string[];
  pageUrls: string[];
  caseNames: string[];
}> {
  const [pageRes, caseRes] = await Promise.all([
    pageApi.list({ project: projectId, page_size: 500 } as any).catch(() => null),
    testCaseApi.list({ project: projectId, page_size: 500 } as any).catch(() => null),
  ]);
  const extractList = (res: any): any[] => {
    const payload: any = (res?.data as any)?.data ?? res?.data;
    return Array.isArray(payload) ? payload : payload?.results || [];
  };
  const pages = extractList(pageRes) as UiPage[];
  const cases = extractList(caseRes) as UiTestCase[];
  return {
    pageNames: pages.map((p) => p.name).filter(Boolean),
    pageUrls: pages.map((p) => p.url).filter(Boolean) as string[],
    caseNames: cases.map((c) => c.name).filter(Boolean),
  };
}

const promptRequirementModule = (module: DocumentModule): string => {
  const lines = [`### ${module.title || '未命名模块'}`];
  if (module.content) {
    lines.push(module.content);
  }
  return lines.join('\n');
};

/**
 * 拼装发送给 Agent 的 UI 生成指令。
 */
export function buildUiGenerationMessage(options: {
  formData: UiGenerationFormData;
  projectId: number;
  requirementModule: DocumentModule | null;
  envConfig: UiEnvironmentConfig | null;
  existing: { pageNames: string[]; pageUrls: string[]; caseNames: string[] };
}): string {
  const { formData, projectId, requirementModule, envConfig, existing } = options;

  const lines: string[] = [];
  // 会话守护标记：后端检测后挂载 UI 守护中间件 + 追加 UI 生成规范指令 + 注入凭据 env
  lines.push('<!-- wharttest:generation_mode=ui_case -->');
  lines.push('');
  lines.push('请基于以下信息一键生成 UI 自动化测试用例（页面元素、页面步骤、测试用例全部落库）。');
  lines.push('');
  lines.push('## 任务类型：UI 自动化用例（UiPage / UiElement / UiPageSteps / UiTestCase）');
  lines.push(`项目 ID：${projectId}`);

  // 保存归属
  lines.push('');
  lines.push('## 保存归属（必须遵守）');
  lines.push(`目标模块 ID：${formData.targetModuleId}（页面与用例均保存到该模块，module_id 一律使用此值）`);

  // 环境与登录声明
  lines.push('');
  lines.push('## 执行环境与登录方式');
  if (envConfig?.base_url) {
    lines.push(`起始 URL：${envConfig.base_url}（环境 base_url）`);
  } else {
    lines.push('起始 URL：未提供，请根据需求模块内容与用户确认入口页面。');
  }
  if (formData.authMode === 'auth_state' && formData.authStateId) {
    lines.push(`登录方式：平台已注入登录态（auth_state_id=${formData.authStateId}），storageState 文件路径在环境变量 WHARTTEST_UI_AUTH_STATE_FILE，先注入登录态再访问起始 URL。`);
  } else if (formData.authMode === 'credentials') {
    lines.push('登录方式：账号密码登录，凭据在环境变量 WHARTTEST_UI_USERNAME / WHARTTEST_UI_PASSWORD，从环境变量读取填表登录，禁止在任何输出中复述凭据。登录成功后调用 create_auth_state 沉淀登录态。');
  } else {
    lines.push('登录方式：无鉴权，直接访问起始 URL 开始生成。');
  }

  // 生成深度与数量
  lines.push('');
  lines.push('## 生成范围');
  lines.push(`生成深度：${formData.depth === 'full' ? '完整覆盖（正向主流程 + 表单校验 + 边界条件 + 异常场景 + 页面状态流转）' : '正向主流程（核心业务路径端到端）'}`);
  lines.push(`用例数量上限：${formData.caseLimit} 条（超出时按 P0 > P1 > P2 裁剪，被裁剪场景登记到待补充清单）`);

  // 需求模块内容（业务流程最高优先级依据）
  lines.push('');
  lines.push('## 需求模块内容（业务流程与场景设计的最高优先级依据）');
  if (requirementModule) {
    lines.push(promptRequirementModule(requirementModule));
  } else {
    lines.push('（未选择需求模块，仅按用户业务描述生成）');
  }

  // 知识库
  if (formData.useKnowledgeBase && formData.knowledgeBaseId) {
    lines.push('');
    lines.push('## 知识库：已启用，请围绕选中需求模块的内容检索业务流程补充用例设计依据；检索结果与业务关联模糊时跳过相关场景并登记，禁止编造。');
  } else {
    lines.push('');
    lines.push('## 知识库：未启用（仅基于需求模块内容与业务描述生成）。');
  }

  // 业务描述
  if (formData.businessNotes) {
    lines.push('');
    lines.push('## 用户业务描述（优先级高于知识库检索结果）');
    lines.push(formData.businessNotes);
  }

  // 已有对象查重
  if (existing.pageNames.length || existing.pageUrls.length || existing.caseNames.length) {
    lines.push('');
    lines.push('## 已有对象清单（查重用，禁止重复创建同名页面/同名用例）');
    if (existing.pageNames.length) {
      lines.push(`已有页面名：${existing.pageNames.slice(0, 100).join('、')}`);
    }
    if (existing.pageUrls.length) {
      lines.push(`已有页面 URL：${existing.pageUrls.slice(0, 100).join('、')}`);
    }
    if (existing.caseNames.length) {
      lines.push(existing.caseNames.slice(0, 200).map((name) => `- ${name}`).join('\n'));
    }
  }

  lines.push('');
  lines.push('生成完成后按规范输出总结（保存数量、优先级统计、试跑结果、待确认清单）。');

  return lines.join('\n');
}
