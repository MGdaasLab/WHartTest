/**
 * AI 生成接口测试用例：编排服务。
 * 负责已有用例名收集、生成指令（message）拼装。
 * 参数约束由模型通过 api-automation 技能的 get_interface_constraints 按需读取。
 */
import { getInterfaceCases } from './interfaceCaseService';

export type ApiCaseType = 'interface_case' | 'scenario';

export interface FunctionalCaseRef {
  case_id: number;
  module_name: string;
  name: string;
  test_type: string;
  level: string;
}

export interface GenerationFormData {
  caseType: ApiCaseType;
  dimensions: string[];
  interfaceIds: number[];
  loginInterfaceId: number | null;
  useKnowledgeBase: boolean;
  knowledgeBaseId: string | null;
  businessNotes: string;
  functionalCaseRefs: FunctionalCaseRef[];
  groupId: number | null;
  caseLimit: number;
  promptId: number | null;
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

const formatInterfacesText = (interfaces: GenerationInterfaceInfo[]): string => {
  const sections = interfaces.map((item) => (
    `- 接口 [${item.id}] ${item.name}（${item.method} ${item.url}）模块=${item.module_name || '未分组'}\n  定义 JSON：${JSON.stringify({
      method: item.method,
      url: item.url,
      params: item.params,
      path_params: item.path_params,
      body: item.body,
      validators: item.validators,
    })}`
  ));
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
  loginInterface?: GenerationInterfaceInfo | null;
  functionalCaseRefs?: FunctionalCaseRef[];
}): string {
  const { formData, interfaces, projectId, existingNames, loginInterface, functionalCaseRefs } = options;

  const lines: string[] = [];
  // 会话守护标记：后端检测到后挂载工具守护中间件（拦截 create_testcase 等漂移、剥除误传 group）
  if (formData.caseType === 'interface_case') {
    lines.push('<!-- wharttest:generation_mode=interface_case -->');
    lines.push('');
  }
  lines.push('请基于以下信息生成接口测试用例。');
  lines.push('');
  lines.push(`## 任务类型：${formData.caseType === 'scenario' ? '场景用例（ApiTestCase）' : '单接口用例（ApiInterfaceCase）'}`);
  lines.push(`项目 ID：${projectId}`);

  if (formData.caseType === 'interface_case') {
    const dimNames = formData.dimensions.map(d => (d === 'D2' ? '参数验证' : '基本功能验证'));
    lines.push(`本次生成范围：${dimNames.join('、')}（未列出的类别跳过，只生成勾选类别的用例）`);
    lines.push(`条数上限：每个接口最多 ${formData.caseLimit} 条（这是"单接口上限"，不是全部接口的总上限）`);
    lines.push(`接口数量：${formData.interfaceIds.length} 个，全部 ${formData.interfaceIds.length} 个接口都必须逐一处理并生成用例，理论总量最多 ${formData.interfaceIds.length * formData.caseLimit} 条。`);
    lines.push('处理方式：按接口逐个生成，每个接口独立按上述上限与维度处理。禁止以任何"总量/配额/轮次"理由跳过未处理的接口——确实无法生成用例的接口（如纯文件依赖缺失）才允许登记到待补充清单。');
    lines.push(`处理进度自检：每完成一个接口，确认剩余待处理接口数量；全部 ${formData.interfaceIds.length} 个接口处理完毕后才输出最终总结。`);
  } else {
    lines.push('场景条数由命中的业务来源决定（一条功能用例映射一条场景，每条 2~8 步），无固定上限。');
    lines.push('严禁结构推断填充：禁止基于接口结构关系（生命周期链路、数据传递链、查询组合）凭空生成场景。');
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
  lines.push(formatInterfacesText(interfaces));

  // 参数约束不在消息中展开：导入文档时平台已固化约束快照，
  // 模型通过 api-automation 技能的 get_interface_constraints（--interface_ids）按接口按需读取
  lines.push('');
  lines.push('## 参数约束获取方式（必须遵守）');
  lines.push('参数约束不随本消息下发。处理每个接口前，先调用 api-automation 技能的 get_interface_constraints 工具（--interface_ids 传当前接口 ID）读取平台固化的约束快照（类型/必填/枚举/范围/长度/响应结构），一次只取当前接口；接口出现在返回的 missing 清单中时按约束未知处理（参数验证收缩为必填缺失+类型错误，跳过边界值），并在总结中登记。禁止臆造约束。');

  lines.push('');
  lines.push('## SQL 步骤：禁止生成。不允许操作数据库（安全约束），任何用例不得包含 type 为 sql 的步骤，数据校验只通过接口响应断言完成。');

  lines.push('');

  // 业务来源：功能用例摘要行（场景模式；仅场景模式使用，单接口为空数组）
  const funcRefs = formData.caseType === 'scenario' ? (functionalCaseRefs || []) : [];
  if (formData.caseType === 'scenario') {
    lines.push('');
    if (funcRefs.length) {
      lines.push('## 业务来源：功能用例参考（业务依据，按需自取详情）');
      lines.push('以下功能用例 ID 属于功能用例库（whart-test 技能的 get_testcase_detail --case_id），与接口 ID / 场景用例 ID 是不同命名空间，严禁混用：');
      for (const ref of funcRefs) {
        lines.push(`- 功能用例 case_id=${ref.case_id}：${ref.module_name} | ${ref.name} | ${ref.test_type} | ${ref.level}`);
      }
      lines.push('命中判定：仅当功能用例业务与选中接口高度匹配时，才调用 get_testcase_detail 读取其前置/步骤/预期作为场景编排依据；每个功能用例的命中情况（如何映射 / 未命中原因）必须写进最终总结。');
      lines.push('未命中处理：功能用例未命中、且知识库/业务描述也未命中时，停止生成并总结原因，严禁用生命周期/数据传递链等结构推断场景填充。');
      lines.push('缺口授权：命中的功能用例所需接口不在选中集合时，允许用 api-automation 技能的 list_interfaces / get_interface 按业务语义检索补充；检索不到则该场景跳过并登记待补充接口。');
    } else {
      lines.push('## 业务来源：功能用例。未选择功能用例（本区块无业务参考）。');
    }
  }

  if (formData.businessNotes) {
    lines.push('');
    lines.push('## 用户业务描述（业务规则类场景的最高优先级依据）');
    lines.push(formData.businessNotes);
  } else {
    lines.push('');
    lines.push('## 用户业务描述：无。依赖业务规则的场景（如重复提交拒绝、业务状态拒绝）按无规则输入跳过，仅生成基本功能验证与参数验证用例。');
  }

  if (formData.caseType === 'interface_case' && existingNames.length) {
    lines.push('');
    lines.push('## 已有用例名清单（去重与撞名检测用，禁止生成同名用例）');
    lines.push(existingNames.slice(0, 200).map(name => `- ${name}`).join('\n'));
  }

  if (formData.caseType === 'scenario' && formData.groupId) {
    lines.push('');
    lines.push(`目标分组 ID：${formData.groupId}（保存时填入 group 字段）`);
  } else if (formData.caseType === 'interface_case') {
    lines.push('');
    lines.push('保存位置（必须遵守）：调用 create_interface_case 时**不要传 group 字段**（也不要传 group: null 或 group: 0），用例通过顶层 interface_id 关联主接口实现归属，会出现在接口用例模块对应接口下。**严禁把用例保存到场景用例（create_testcase）或场景用例分组中**。');
  }

  lines.push('');
  lines.push('生成完成后按提示词要求输出总结（含保存数量、维度/原型统计、待补充清单、待确认清单）。');

  return lines.filter(line => line !== undefined).join('\n');
}
