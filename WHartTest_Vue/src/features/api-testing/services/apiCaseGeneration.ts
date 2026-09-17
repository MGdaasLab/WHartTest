/**
 * AI 生成接口测试用例：编排服务。
 * 负责文档约束提取、已有用例名收集、生成指令（message）拼装。
 */
import axiosInstance from '@/utils/request';
import { useProjectStore } from '@/store/projectStore';
import { getInterfaceCases } from './interfaceCaseService';
import { getTestCases } from './testcaseService';

const base = (projectId: number) => `/projects/${projectId}/api-interfaces`;

export type ApiCaseType = 'interface_case' | 'scenario';

export interface GenerationFormData {
  caseType: ApiCaseType;
  dimensions: string[];
  archetypes: string[];
  interfaceIds: number[];
  loginInterfaceId: number | null;
  useKnowledgeBase: boolean;
  knowledgeBaseId: string | null;
  businessNotes: string;
  dbVerification: boolean;
  groupId: number | null;
  caseLimit: number;
  promptId: number | null;
}

export interface ConstraintExtractResult {
  format: string;
  version: string;
  interfaces: Array<Record<string, any>>;
  unmatched: Array<Record<string, any>>;
}

export interface GenerationInterfaceInfo {
  id: number;
  name: string;
  method: string;
  url: string;
  type: string;
  module_name?: string;
  validators?: any;
  params?: any;
  body?: any;
  headers?: any;
  path_params?: any;
  sql_method?: string;
  sql?: string;
}

/**
 * 上传接口文档并提取选中接口的参数约束。
 * @param file 文档文件
 * @param interfaceIds 选中的接口 ID
 */
export async function extractConstraints(
  file: File,
  interfaceIds: number[],
): Promise<ConstraintExtractResult> {
  const pid = useProjectStore().currentProjectId ?? 0;
  const formData = new FormData();
  formData.append('file', file);
  formData.append('interface_ids', JSON.stringify(interfaceIds));
  const response = await axiosInstance({
    url: `${base(pid)}/extract-constraints/`,
    method: 'POST',
    data: formData,
  });
  const payload = (response.data as any)?.data ?? response.data;
  return payload as ConstraintExtractResult;
}

/**
 * 收集选中接口下已有的单接口用例名（用于去重与撞名检测）。
 */
export async function collectExistingInterfaceCaseNames(interfaceIds: number[]): Promise<string[]> {
  const response = await getInterfaceCases({ page_size: 500 });
  if (!response?.success || !response.data) return [];
  const payload: any = response.data;
  const list = Array.isArray(payload) ? payload : payload?.results || [];
  const idSet = new Set(interfaceIds);
  return list
    .filter((item: any) => idSet.has(item.interface) || idSet.has(item?.interface_info?.id))
    .map((item: any) => item.name)
    .filter(Boolean);
}

/**
 * 收集项目下已有的场景用例名（用于去重与撞名检测）。
 */
export async function collectExistingScenarioCaseNames(): Promise<string[]> {
  const response = await getTestCases({ page_size: 500 });
  if (!response?.success || !response.data) return [];
  const payload: any = response.data;
  const list = Array.isArray(payload) ? payload : payload?.results || [];
  return list.map((item: any) => item.name).filter(Boolean);
}

const formatConstraintsText = (constraints: ConstraintExtractResult | null): string => {
  if (!constraints || !constraints.interfaces.length) return '';
  const sections = constraints.interfaces.map((item) => {
    const lines: string[] = [];
    lines.push(`### 接口 [${item.interface_id}] ${item.name}（${item.method} ${item.url}）`);
    const paramGroups = item.params || {};
    for (const location of ['path', 'query', 'header']) {
      const params = paramGroups[location] || [];
      if (params.length) {
        lines.push(`- ${location} 参数：`);
        for (const param of params) {
          const constraintText = Object.keys(param.constraints || {}).length
            ? JSON.stringify(param.constraints)
            : '未知';
          lines.push(`  - ${param.name}：类型=${param.type}${param.default !== undefined ? `，默认=${JSON.stringify(param.default)}` : ''}，约束=${constraintText}`);
        }
      }
    }
    if (item.body_fields && item.body_fields.length) {
      lines.push(`- body 字段：`);
      for (const field of item.body_fields) {
        const constraintText = Object.keys(field.constraints || {}).length
          ? JSON.stringify(field.constraints)
          : '未知';
        lines.push(`  - ${field.name}：类型=${field.type}，必填=${field.required ? '是' : '否'}，约束=${constraintText}${field.description ? `，说明=${field.description}` : ''}`);
      }
      if (item.body_required && item.body_required.length) {
        lines.push(`- body 必填清单：${item.body_required.join('、')}`);
      }
    } else if (item.notes && item.notes.length) {
      // body 为空但带有说明（如同 schema 去重引用），把说明原样呈现，避免被误读为"无约束"
      for (const note of item.notes) {
        lines.push(`- body：${note}`);
      }
    } else {
      lines.push('- body：该接口未声明请求体，无字段级约束信息');
    }
    if (item.response) {
      const successCode = item.response.success_code || (item.response.success_codes && item.response.success_codes[0]);
      if (successCode) lines.push(`- 成功状态码：${successCode}`);
      if (item.response.fields && item.response.fields.length) {
        lines.push(`- 响应字段：${item.response.fields.map((f: any) => `${f.name}(${f.type})`).join('、')}`);
      }
    }
    return lines.join('\n');
  });
  const unmatchedNote = constraints.unmatched.length
    ? `\n\n注意：以下接口在文档中未匹配到（生成时按约束未知处理）：${constraints.unmatched.map((item) => item.name || item.interface_id).join('、')}`
    : '';
  return `\n\n## 接口文档参数约束清单\n\n${sections.join('\n\n')}${unmatchedNote}`;
};

const formatInterfacesText = (
  interfaces: GenerationInterfaceInfo[],
  constraints: ConstraintExtractResult | null,
): string => {
  const constrainedIds = new Set((constraints?.interfaces || []).map(item => item.interface_id));
  const sections = interfaces.map((item) => {
    // 已有约束清单的接口只给精简定义，避免重复
    if (constrainedIds.has(item.id)) {
      return `- 接口 [${item.id}] ${item.name}（${item.method} ${item.url}）模块=${item.module_name || '未分组'}`;
    }
    return `- 接口 [${item.id}] ${item.name}（${item.method} ${item.url}）模块=${item.module_name || '未分组'}\n  定义 JSON：${JSON.stringify({
      method: item.method,
      url: item.url,
      params: item.params,
      path_params: item.path_params,
      body: item.body,
      validators: item.validators,
    })}`;
  });
  return sections.join('\n');
};

/**
 * 拼装发送给 Agent 的生成指令。
 */
export function buildGenerationMessage(options: {
  formData: GenerationFormData;
  interfaces: GenerationInterfaceInfo[];
  projectId: number;
  existingNames: string[];
  constraints: ConstraintExtractResult | null;
  documentName: string;
  loginInterface?: GenerationInterfaceInfo | null;
}): string {
  const { formData, interfaces, projectId, existingNames, constraints, documentName, loginInterface } = options;

  const lines: string[] = [];
  lines.push('请基于以下信息生成接口测试用例。');
  lines.push('');
  lines.push(`## 任务类型：${formData.caseType === 'scenario' ? '场景用例（ApiTestCase）' : '单接口用例（ApiInterfaceCase）'}`);
  lines.push(`项目 ID：${projectId}`);

  if (formData.caseType === 'interface_case') {
    lines.push(`本次生成维度：${formData.dimensions.join('、')}（未列出的维度跳过；D1 未列出时仍须先生成 D1 基线用例）`);
    lines.push(`单接口条数上限：${formData.caseLimit} 条`);
    lines.push('处理方式：按接口逐个生成，每个接口独立按上述上限与维度处理。');
  } else {
    lines.push(`本次生成原型：${formData.archetypes.join('、')}（未列出的原型跳过）`);
    lines.push(`场景用例上限：${formData.caseLimit} 条，每条 2~8 步`);
  }

  // 鉴权前置：登录接口在选中接口集合外时，其定义已包含在下方"登录接口"区块
  if (loginInterface) {
    const inSelection = formData.interfaceIds.includes(loginInterface.id);
    lines.push('');
    lines.push('## 鉴权前置（必须遵守）');
    lines.push(`登录接口：[${loginInterface.id}] ${loginInterface.name}（${loginInterface.method} ${loginInterface.url}）${inSelection ? '（属于选中接口集合）' : '（不在选中接口集合内，仅作为登录前置使用，不要为它生成用例）'}。`);
    lines.push('所有需要鉴权的用例必须包含登录 precondition 步骤：登录步骤从响应 extract 变量名 token（extract_meta 的 variable_type 为 temporary、source 为 response），main 步骤在请求头注入 ${token}（如 Authorization: Bearer ${token}，以登录接口实际响应结构为准）。');
    lines.push('登录接口自身或明确无需鉴权的接口（如公开查询）可不加登录前置。');
  } else {
    lines.push('');
    lines.push('## 鉴权前置：未提供登录接口。如目标接口需要鉴权才能访问，请在对应用例的 description 中标注"需人工补充鉴权前置"，不要臆造 token 来源。');
  }

  lines.push('');
  lines.push('## 选中接口');
  lines.push(formatInterfacesText(interfaces, constraints));

  lines.push(formatConstraintsText(constraints));
  if (documentName) {
    lines.push(`（约束提取自文档：${documentName}）`);
  }

  if (formData.dbVerification) {
    lines.push('');
    lines.push('## DB 校验：开启');
    lines.push('允许生成 SQL 步骤。清理 SQL 一律前置（precondition 区，按业务唯一键删除）；校验 SQL 后置于关键写操作之后（每条用例最多 1 个），断言写在 SQL 步骤自身 validators。db_config 引用环境配置，禁止明文密码。');
  } else {
    lines.push('');
    lines.push('## DB 校验：关闭（禁止生成 SQL 步骤）');
  }

  lines.push('');
  lines.push('## 试跑验证（默认行为，必须执行）');
  lines.push('每条用例保存成功后，先调用 list_environments 查询项目执行环境；仅一个环境时直接使用，多个环境时逐个列出让用户选择确认后再继续（不要自行猜测环境）。');
  lines.push('环境确认后必须调用 run_interface_case（payload 传所选 environment_id）真实执行验证：');
  lines.push('1. 执行通过 → 该条完成，继续下一条。');
  lines.push('2. 执行失败 → 分析失败原因（断言预期不符 / 参数错误 / 变量链断裂 / 环境问题），修订用例（update_interface_case，需传完整 interface_data）后重新执行验证。失败修复上限 5 次。');
  lines.push('3. 修复 5 次仍失败 → 保留用例，在 description 追加"试跑失败原因：xxx（已修复 5 次）"，登记到待确认清单，继续下一条。禁止删除已保存的用例。');
  lines.push('4. 执行失败若属"预期数据依赖缺失"（如需要上传 multipart 文件、需要预置专属数据），不消耗修复次数：保留骨架用例 + description 登记依赖说明，登记到待补充清单。');
  lines.push('5. 每条用例的试跑结果（通过/修复后通过/仍失败）计入最终总结。');
  lines.push('6. 写操作用例（新增/修改/删除）试跑后必须清理测试数据（或确保用例自带自清理步骤），避免污染环境。');
  lines.push('7. 用户在对话中明确表示"跳过验证/不要试跑"时：本条及后续用例仅静态生成并说明。');

  if (formData.useKnowledgeBase && formData.knowledgeBaseId) {
    lines.push('');
    lines.push('## 知识库：已启用，请先检索业务知识再设计用例；检索结果与业务对象关联模糊时跳过相关场景并登记，禁止编造。');
  } else {
    lines.push('');
    lines.push('## 知识库：未启用（本次仅基于接口定义与下方业务描述生成）。');
  }

  if (formData.businessNotes) {
    lines.push('');
    lines.push('## 用户业务描述（生成 D3/D4 与 S3/S4 的最高优先级依据）');
    lines.push(formData.businessNotes);
  } else {
    lines.push('');
    lines.push('## 用户业务描述：无。D3 异常场景（业务状态拒绝类）、D4 业务逻辑（业务规则/依赖类）、S3 业务分支、S4 状态前置相应场景按无规则输入跳过。');
  }

  if (existingNames.length) {
    lines.push('');
    lines.push('## 已有用例名清单（去重与撞名检测用，禁止生成同名用例）');
    lines.push(existingNames.slice(0, 200).map(name => `- ${name}`).join('\n'));
  }

  if (formData.groupId) {
    lines.push('');
    lines.push(`目标分组 ID：${formData.groupId}（保存时填入 group 字段）`);
  }

  lines.push('');
  lines.push('生成完成后按提示词要求输出总结（含保存数量、维度/原型统计、待补充清单、待确认清单）。');

  return lines.filter(line => line !== undefined).join('\n');
}
