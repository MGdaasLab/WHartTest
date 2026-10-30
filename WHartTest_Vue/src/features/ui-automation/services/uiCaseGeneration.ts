/**
 * AI 一键生成 UI 自动化测试用例：编排服务。
 * 负责功能用例/环境/登录态/已有对象收集，以及生成指令（message）拼装。
 */
import { useProjectStore } from '@/store/projectStore';
import { moduleApi, pageApi, testCaseApi, envConfigApi, authStateApi } from '../api';
import type { UiModule, UiPage, UiTestCase, UiEnvironmentConfig, UiAuthState } from '../types';
import { getTestCaseList, type TestCase } from '@/services/testcaseService';

export interface UiGenerationFormData {
  selectedFunctionalCaseIds: number[];
  targetModuleId: number | null;
  envConfigId: number | null;
  authMode: 'auth_state' | 'credentials' | 'none';
  authStateId: number | null;
  username: string;
  password: string;
  businessNotes: string;
}

/** 获取项目功能用例列表（含绑定状态，用于多选与置灰已绑定项） */
export async function fetchFunctionalCases(projectId: number): Promise<TestCase[]> {
  const response = await getTestCaseList(projectId, { page: 1, pageSize: 1000 });
  if (!response.success) return [];
  return response.data || [];
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

/**
 * 拼装发送给 Agent 的 UI 生成指令。
 */
export function buildUiGenerationMessage(options: {
  formData: UiGenerationFormData;
  projectId: number;
  functionalCases: TestCase[];
  envConfig: UiEnvironmentConfig | null;
  existing: { pageNames: string[]; pageUrls: string[]; caseNames: string[] };
}): string {
  const { formData, projectId, functionalCases, envConfig, existing } = options;

  const lines: string[] = [];
  // 会话守护标记：后端检测后挂载 UI 守护中间件 + 追加 UI 生成规范指令 + 注入凭据 env
  lines.push('<!-- wharttest:generation_mode=ui_case -->');
  lines.push('');
  lines.push('请基于以下选中的功能测试用例，逐条生成对应的 UI 自动化测试用例（页面元素、页面步骤、测试用例全部落库，试跑通过后回写绑定关系）。');
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
    lines.push('起始 URL：未提供，请根据功能用例步骤与用户确认入口页面。');
  }
  if (formData.authMode === 'auth_state' && formData.authStateId) {
    lines.push(`登录方式：平台已注入登录态（auth_state_id=${formData.authStateId}），storageState 文件路径在环境变量 WHARTTEST_UI_AUTH_STATE_FILE，先注入登录态再访问起始 URL。`);
  } else if (formData.authMode === 'credentials') {
    lines.push('登录方式：账号密码登录，凭据在环境变量 WHARTTEST_UI_USERNAME / WHARTTEST_UI_PASSWORD，从环境变量读取填表登录，禁止在任何输出中复述凭据。登录成功后调用 create_auth_state 沉淀登录态。');
  } else {
    lines.push('登录方式：无鉴权，直接访问起始 URL 开始生成。');
  }

  // 生成范围：忠实翻译所选功能用例
  lines.push('');
  lines.push('## 生成范围');
  lines.push('生成方式：忠实翻译所选功能用例，生成数量与所选用例一一对应；不自行扩展场景。');

  // 功能用例清单（生成依据，Agent 用 get_testcase_detail 按 ID 自取详情）
  lines.push('');
  lines.push('## 生成依据：选中的功能测试用例（逐条串行处理，一条完整闭环后再处理下一条）');
  for (const tc of functionalCases) {
    const bound = tc.ui_test_case ? `，已绑定 UI 用例 ${tc.ui_test_case}` : '';
    lines.push(`- 功能用例 ID：${tc.id}｜名称：${tc.name}｜等级：${tc.level || 'P1'}${bound}`);
  }
  lines.push('处理方式：用 wharttest 技能 get_testcase_detail（--case_id）读取每条用例的步骤与预期结果，按规范转换为 UI 自动化用例；全部处理完后逐条试跑验证，试跑通过才回写绑定关系（edit_testcase --ui_test_case_id）。');

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
  lines.push('生成完成后按规范输出总结（功能用例处理数、UI 用例保存数、试跑通过/失败统计、绑定成功统计、元素复用/新增统计、待确认清单）。');

  return lines.join('\n');
}
