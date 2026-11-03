/**
 * UI 自动化用例智能自愈：编排服务。
 * 负责失败现场（最近一次失败执行记录）收集、自愈指令（message）拼装与任务启动。
 */
import { executionRecordApi } from '../api';
import type { UiExecutionRecord, UiTestCase } from '../types';
import { sendChatMessageStream } from '@/features/langgraph/services/chatService';
import type { ChatRequest } from '@/features/langgraph/types/chat';

/** 步骤执行流水里允许保留的单条文本最大长度（防止超长报错撑爆上下文） */
const STEP_MESSAGE_MAX_LENGTH = 300;
/** 送入自愈消息的步骤流水条数上限（仅保留尾部最近步骤，失败步骤必含） */
const STEP_HISTORY_LIMIT = 20;
/** 环境快照里提取的 baseURL 递归查找深度 */
const ENV_SCAN_MAX_DEPTH = 3;

/** 从步骤结果中剥除截图等大字段后的干净结构 */
interface SanitizedStepResult {
  step_id?: number;
  status?: number | string;
  message?: string;
  description?: string;
  duration?: number;
  element_found?: boolean;
}

/** 拉取指定用例最近一次失败的执行记录（含 step_results 完整字段） */
export async function fetchLatestFailureRecord(caseId: number): Promise<UiExecutionRecord | null> {
  const listRes = await executionRecordApi.list({ test_case: caseId, status: 3, page_size: 1 } as never);
  const listPayload: any = (listRes.data as any)?.data ?? listRes.data;
  const list = Array.isArray(listPayload) ? listPayload : listPayload?.results || [];
  if (!list.length) return null;
  const detailRes = await executionRecordApi.get(list[0].id);
  const detail: any = (detailRes.data as any)?.data ?? detailRes.data;
  return detail as UiExecutionRecord;
}

/** 截断过长文本，保留头部与尾部（报错关键信息常在两头） */
const truncate = (text: string, maxLength: number): string => {
  if (text.length <= maxLength) return text;
  const head = text.slice(0, Math.ceil(maxLength * 0.7));
  const tail = text.slice(-Math.floor(maxLength * 0.3));
  return `${head}\n...(中间内容过长已省略)...\n${tail}`;
};

/** 剥除 base64 截图/超长字段，把步骤结果规整为可读流水 */
const sanitizeStepResults = (steps: unknown[]): SanitizedStepResult[] => {
  if (!Array.isArray(steps)) return [];
  return steps
    .filter((step): step is Record<string, any> => !!step && typeof step === 'object')
    .map((step) => {
      const rawMessage = step.message ?? step.error ?? '';
      return {
        step_id: step.step_id,
        status: step.status,
        description: typeof step.description === 'string' ? step.description : undefined,
        message: rawMessage ? truncate(String(rawMessage).replace(/\s+/g, ' ').trim(), STEP_MESSAGE_MAX_LENGTH) : undefined,
        duration: typeof step.duration === 'number' ? step.duration : undefined,
        element_found: typeof step.element_found === 'boolean' ? step.element_found : undefined,
      };
    });
};

/** 从环境快照中提取 base_url（结构因执行器版本而异，做浅层递归查找） */
const extractBaseUrl = (environment: unknown, depth = 0): string | undefined => {
  if (!environment || typeof environment !== 'object' || depth > ENV_SCAN_MAX_DEPTH) return undefined;
  for (const [key, value] of Object.entries(environment as Record<string, unknown>)) {
    if (typeof value === 'string' && /^https?:\/\//.test(value) && /url|base|host|domain/i.test(key)) {
      return value;
    }
  }
  for (const value of Object.values(environment as Record<string, unknown>)) {
    const found = extractBaseUrl(value, depth + 1);
    if (found) return found;
  }
  return undefined;
};

/** 提取失败步骤上下文：最后一条失败步骤 + 其前一条成功步骤 */
const extractFailureFocus = (steps: SanitizedStepResult[]): { failed: SanitizedStepResult | null; previous: SanitizedStepResult | null } => {
  let failedIndex = -1
  for (let i = steps.length - 1; i >= 0; i--) {
    if (steps[i].status === 3 || steps[i].status === 'failed') {
      failedIndex = i
      break
    }
  }
  if (failedIndex === -1) {
    return { failed: steps[steps.length - 1] ?? null, previous: steps[steps.length - 2] ?? null };
  }
  return { failed: steps[failedIndex], previous: steps[failedIndex - 1] ?? null };
};

const formatStepLine = (index: number, step: SanitizedStepResult): string => {
  const statusText = step.status === 2 || step.status === 'success' ? '成功' : '失败';
  const desc = step.description || `步骤 ${step.step_id ?? index + 1}`;
  const message = step.message ? ` - ${step.message}` : '';
  return `[${statusText}] ${desc}${message}`;
};

/**
 * 拼装发送给 Agent 的自愈指令。
 * 头部注入 self_heal 会话标记：后端检测后挂载自愈守护中间件并追加自愈规范指令。
 */
export function buildSelfHealMessage(options: {
  testCase: UiTestCase;
  failureRecord: UiExecutionRecord;
  projectId: number;
}): string {
  const { testCase, failureRecord, projectId } = options;

  const steps = sanitizeStepResults(failureRecord.step_results);
  const recentSteps = steps.slice(-STEP_HISTORY_LIMIT);
  const { failed: failedStep } = extractFailureFocus(steps);

  const lines: string[] = [];
  lines.push('<!-- wharttest:generation_mode=self_heal -->');
  lines.push('');
  lines.push('【UI 自动化用例执行失败 - 智能自愈与编辑任务】');
  lines.push('请按自愈规范诊断该 UI 自动化用例的失败根因，修复用例资产后自动复测验证。');
  lines.push('');
  lines.push('## 目标用例（只允许修复该用例相关资产）');
  lines.push(`项目 ID：${projectId}`);
  lines.push(`UI 用例 ID：${testCase.id}`);
  lines.push(`用例名称：${testCase.name}`);
  if (testCase.module_name) lines.push(`所属模块：${testCase.module_name}`);
  if (testCase.description) lines.push(`用例描述：${truncate(testCase.description, 300)}`);

  lines.push('');
  lines.push('## 执行失败现场（最近一次失败执行记录）');
  lines.push(`执行记录 ID：${failureRecord.id}`);
  if (failureRecord.error_message) {
    lines.push(`整体报错：${truncate(String(failureRecord.error_message).replace(/\s+/g, ' ').trim(), STEP_MESSAGE_MAX_LENGTH * 2)}`);
  }
  const baseUrl = extractBaseUrl(failureRecord.environment);
  if (baseUrl) lines.push(`环境地址：${baseUrl}`);

  if (failedStep) {
    lines.push('');
    lines.push('## 失败步骤');
    const failedIndex = steps.indexOf(failedStep) + 1;
    lines.push(formatStepLine(failedIndex, failedStep));
  }

  if (recentSteps.length) {
    lines.push('');
    lines.push('## 步骤执行流水（按执行顺序）');
    const startIndex = steps.length - recentSteps.length;
    lines.push(recentSteps.map((step, i) => formatStepLine(startIndex + i, step)).join('\n'));
  }

  lines.push('');
  lines.push('自愈完成后请按规范输出总结（根因、修改点、复测结果）。');

  return lines.join('\n');
}

/**
 * 启动自愈任务（SSE 流式），流开始后回调 sessionId。
 * 进度在 AI 对话页查看（langgraph_session_id 已写入 localStorage）。
 */
export function startSelfHealTask(
  requestData: ChatRequest,
  onStarted?: (sessionId: string) => void,
): void {
  sendChatMessageStream(requestData, (sessionId) => {
    localStorage.setItem('langgraph_session_id', sessionId)
    onStarted?.(sessionId)
  })
}
