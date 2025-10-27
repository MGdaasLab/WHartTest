from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from wharttest_django.viewsets import BaseModelViewSet
from wharttest_django.permissions import HasModelPermission
from .models import UserPrompt, PromptType
from .serializers import (
    UserPromptSerializer,
    UserPromptListSerializer
)


class UserPromptViewSet(BaseModelViewSet):
    """
    用户提示词管理视图集
    提供用户级别的提示词CRUD操作
    """
    serializer_class = UserPromptSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_default', 'is_active', 'prompt_type']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']
    ordering = ['-updated_at']

    def get_permissions(self):
        """返回此视图所需权限的实例列表"""
        return [
            HasModelPermission(),
        ]

    def get_queryset(self):
        """只返回当前用户的提示词"""
        return UserPrompt.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """根据操作类型返回不同的序列化器"""
        if self.action == 'list':
            return UserPromptListSerializer
        return UserPromptSerializer

    def perform_create(self, serializer):
        """创建时自动设置用户"""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def default(self, request):
        """获取用户的默认提示词"""
        default_prompt = UserPrompt.get_user_default_prompt(request.user)

        if default_prompt:
            serializer = self.get_serializer(default_prompt)
            return Response(serializer.data)
        else:
            return Response({
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": "用户暂无默认提示词",
                "data": None,
                "errors": {}
            })

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """根据类型获取提示词"""
        prompt_type = request.query_params.get('type')
        if not prompt_type:
            return Response({
                "status": "error",
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "缺少type参数",
                "data": None,
                "errors": {"type": ["此字段是必需的"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        prompt = UserPrompt.get_user_prompt_by_type(request.user, prompt_type)
        if prompt:
            serializer = self.get_serializer(prompt)
            return Response(serializer.data)
        else:
            return Response({
                "status": "success",
                "code": status.HTTP_200_OK,
                "message": f"用户暂无{prompt_type}类型的提示词",
                "data": None,
                "errors": {}
            })

    @action(detail=False, methods=['get'])
    def types(self, request):
        """获取所有提示词类型"""
        types = [
            {
                'value': choice[0],
                'label': choice[1],
                'is_program_call': choice[0] in UserPrompt.PROGRAM_CALL_TYPES
            }
            for choice in PromptType.choices
        ]
        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": "获取成功",
            "data": types,
            "errors": {}
        })

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """设置指定提示词为默认提示词"""
        prompt = self.get_object()

        # 检查提示词是否属于当前用户且处于激活状态
        if not prompt.is_active:
            return Response({
                "status": "error",
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "无法设置未激活的提示词为默认",
                "data": {},
                "errors": {"prompt": ["提示词未激活"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 检查是否为程序调用类型（程序调用类型不允许设为默认）
        if prompt.prompt_type in UserPrompt.PROGRAM_CALL_TYPES:
            return Response({
                "status": "error",
                "code": status.HTTP_400_BAD_REQUEST,
                "message": "程序调用类型的提示词不能设为默认",
                "data": {},
                "errors": {"prompt_type": ["程序调用类型的提示词不能设为默认，会影响对话功能"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 取消其他默认提示词
        UserPrompt.objects.filter(
            user=request.user,
            is_default=True
        ).exclude(pk=prompt.pk).update(is_default=False)

        # 设置当前提示词为默认
        prompt.is_default = True
        prompt.save()

        serializer = self.get_serializer(prompt)
        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": "默认提示词设置成功",
            "data": serializer.data,
            "errors": {}
        })

    @action(detail=False, methods=['post'])
    def clear_default(self, request):
        """清除用户的默认提示词设置"""
        updated_count = UserPrompt.objects.filter(
            user=request.user,
            is_default=True
        ).update(is_default=False)

        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": f"已清除默认提示词设置，影响{updated_count}条记录",
            "data": {"updated_count": updated_count},
            "errors": {}
        })

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """复制提示词"""
        original_prompt = self.get_object()

        # 创建副本
        new_prompt = UserPrompt.objects.create(
            user=request.user,
            name=f"{original_prompt.name} (副本)",
            content=original_prompt.content,
            description=f"复制自: {original_prompt.description}" if original_prompt.description else "复制的提示词",
            is_default=False,  # 副本不设为默认
            is_active=True
        )

        serializer = self.get_serializer(new_prompt)
        return Response({
            "status": "success",
            "code": status.HTTP_201_CREATED,
            "message": "提示词复制成功",
            "data": serializer.data,
            "errors": {}
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def initialize(self, request):
        """初始化用户的默认提示词"""
        # 默认提示词模板
        default_prompts = {
            'general': {
                'name': '默认对话助手',
                'description': '通用的AI对话助手，适用于日常交流和问题解答',
                'content': """你是一位专业的AI助手，可以帮助用户解答各种问题。

【基本原则】
1. 友好、专业、准确地回答用户问题
2. 对不确定的内容诚实告知，避免臆测
3. 根据用户需求提供有针对性的建议
4. 保持客观中立的态度

【回答要求】
- 言简意赅，突出要点
- 结构清晰，便于理解
- 实用性强，可操作性高
- 及时关注用户的后续需求

请根据用户的具体问题，提供专业、有用的回答。"""
            },
            'document_structure': {
                'name': '文档结构分析',
                'description': '用于分析需求文档结构，识别功能模块边界的提示词',
                'content': """你是一个专业的需求分析师，请仔细分析以下需求文档，识别出所有的主要功能模块。

【分析标准】
1. 以一级标题（#）或二级标题（##）作为模块划分的主要依据
2. 每个模块应该包含完整的功能描述，不要遗漏任何部分
3. 模块应该相对独立，有明确的功能边界
4. 确保所有内容都被分配到某个模块中，不要遗漏

【文档内容】
{content}

【输出要求】
请仔细阅读整个文档，识别出所有的功能模块。对于每个模块：
- 准确识别模块的开始和结束位置
- 确保模块内容完整，不要截断
- 给出合理的置信度评分

【输出格式】
请以JSON格式输出模块结构：
```json
[
  {{
    "title": "模块名称（与文档中的标题保持一致）",
    "description": "模块功能的简要描述",
    "start_marker": "模块开始的确切文本（包含标题）",
    "end_marker": "下一个模块开始的文本（如果是最后一个模块则为空）",
    "confidence": 0.95,
    "estimated_complexity": "medium"
  }}
]
```

重要：请确保识别出文档中的所有主要模块，不要遗漏任何部分！"""
            },
            'direct_analysis': {
                'name': '直接分析',
                'description': '用于直接分析整个需求文档的提示词',
                'content': """你是一位资深的需求分析师，正在对需求文档进行专业评审。请对以下文档进行全面分析：

【文档内容】
{content}

【评审要求】
请从以下维度进行专业评审：

1. 📋 **规范性检查** (0-100分)
   - 文档结构是否清晰
   - 格式是否规范
   - 必要信息是否完整

2. 🔍 **清晰度评估** (0-100分)
   - 需求描述是否清晰
   - 是否存在歧义表述
   - 术语使用是否一致

3. ✅ **完整性验证** (0-100分)
   - 功能需求是否完整
   - 非功能需求是否考虑
   - 异常场景是否覆盖

4. 🔗 **一致性检查** (0-100分)
   - 内部逻辑是否一致
   - 业务规则是否冲突
   - 数据定义是否统一

【输出格式】
请以JSON格式输出评审结果：
```json
{{
  "overall_rating": "good",
  "completion_score": 85,
  "clarity_score": 78,
  "consistency_score": 82,
  "completeness_score": 88,
  "summary": "文档整体质量良好，结构清晰...",
  "recommendations": "建议完善异常处理场景...",
  "issues": [
    {{
      "title": "问题标题",
      "description": "问题描述",
      "priority": "high",
      "category": "completeness",
      "location": "第2章用户管理模块",
      "suggestion": "改进建议"
    }}
  ]
}}
```"""
            },
            'global_analysis': {
                'name': '全局分析',
                'description': '用于分析需求文档全局结构和上下文的提示词',
                'content': """你是一位资深的需求分析师，正在进行需求评审。请对以下需求文档进行全局结构分析：

【文档信息】
标题: {title}
描述: {description}
内容: {content}

【分析要求】
请从以下维度进行全局分析：

1. 📋 **文档结构规范性**
   - 文档组织结构是否清晰
   - 章节编号是否规范
   - 标题层级是否合理

2. 🎯 **业务完整性**
   - 业务流程是否完整
   - 核心功能是否遗漏
   - 业务边界是否清晰

3. 🔗 **逻辑一致性**
   - 整体逻辑是否自洽
   - 业务规则是否一致
   - 数据流是否合理

4. 📊 **质量评估**
   - 需求描述的清晰度
   - 可实现性评估
   - 风险点识别

【输出格式】
请以JSON格式输出分析结果：
```json
{{
  "structure_score": 85,
  "completeness_score": 78,
  "consistency_score": 90,
  "clarity_score": 82,
  "overall_score": 84,
  "business_flows": ["用户注册流程", "订单处理流程"],
  "data_entities": ["用户", "商品", "订单"],
  "global_rules": ["所有操作需要登录", "支付必须验证"],
  "missing_aspects": ["异常处理", "性能要求"],
  "risk_points": ["支付安全", "数据一致性"],
  "strengths": ["业务流程清晰", "功能划分合理"],
  "weaknesses": ["缺少非功能需求", "异常场景不完整"]
}}
```"""
            },
            'module_analysis': {
                'name': '模块分析',
                'description': '用于分析单个需求模块的提示词',
                'content': """你正在评审需求文档的一个功能模块。请进行专业的需求评审分析：

【模块信息】
模块名称: {module_title}
模块内容: {module_content}

【全局上下文】
业务流程: {business_flows}
数据实体: {data_entities}
全局规则: {global_rules}

【评审维度】
请从以下维度进行详细分析：

1. 📋 **规范性检查**
   - 需求描述是否完整
   - 格式是否符合标准
   - 必要信息是否缺失

2. 🔍 **清晰度评估**
   - 表述是否模糊不清
   - 是否存在歧义
   - 术语使用是否一致

3. ✅ **完整性验证**
   - 功能需求是否完整
   - 异常场景是否考虑
   - 边界条件是否明确

4. 🔗 **一致性检查**
   - 与全局规则是否一致
   - 与其他模块是否冲突
   - 数据定义是否统一

5. ⚠️ **可行性评估**
   - 技术实现难度
   - 业务合理性
   - 资源需求评估

【输出格式】
请以JSON格式输出分析结果：
```json
{{
  "module_id": "{module_id}",
  "module_name": "{module_title}",
  "specification_score": 85,
  "clarity_score": 78,
  "completeness_score": 90,
  "consistency_score": 82,
  "feasibility_score": 88,
  "overall_score": 84,
  "issues": [
    {{
      "type": "clarity",
      "priority": "high",
      "title": "用户权限定义模糊",
      "description": "权限等级的具体定义不清晰",
      "location": "权限管理部分",
      "suggestion": "建议明确定义各权限等级的具体权限范围"
    }}
  ],
  "strengths": ["功能描述清晰", "业务流程合理"],
  "weaknesses": ["缺少异常处理", "边界条件不明确"],
  "recommendations": ["补充异常场景", "明确数据格式"]
}}
```"""
            },
            'consistency_analysis': {
                'name': '一致性分析',
                'description': '用于分析需求文档跨模块一致性的提示词',
                'content': """你正在进行需求文档的跨模块一致性检查。请分析各模块间的一致性问题：

【全局上下文】
{global_context}

【各模块分析结果】
{module_analyses}

【一致性检查要求】
请重点检查以下方面：

1. 🔗 **接口一致性**
   - 模块间接口定义是否一致
   - 数据传递格式是否统一
   - 调用关系是否清晰

2. 📊 **数据一致性**
   - 数据实体定义是否统一
   - 状态定义是否一致
   - 数据流转是否合理

3. 📋 **业务规则一致性**
   - 业务规则在各模块中是否一致
   - 权限控制是否统一
   - 异常处理是否一致

4. 🔄 **流程完整性**
   - 业务流程是否闭环
   - 是否存在流程断点
   - 异常流程是否完整

【输出格式】
请以JSON格式输出分析结果：
```json
{{
  "consistency_score": 85,
  "interface_consistency": 78,
  "data_consistency": 90,
  "business_rule_consistency": 82,
  "process_completeness": 88,
  "cross_module_issues": [
    {{
      "type": "data_inconsistency",
      "priority": "high",
      "title": "用户状态定义不一致",
      "description": "用户管理模块和订单模块对用户状态定义不同",
      "affected_modules": ["用户管理", "订单管理"],
      "suggestion": "统一用户状态定义，建立数据字典"
    }}
  ],
  "missing_connections": ["支付模块与库存模块缺少连接"],
  "redundant_functions": ["用户验证功能在多个模块重复"],
  "recommendations": ["建立统一的数据字典", "明确模块间接口规范"]
}}
```"""
            },
            'test_case_execution': {
                'name': '测试用例执行提示词',
                'description': '用于驱动测试用例自动执行的系统提示词',
                'content': """# 角色
你是一个专业的软件测试执行引擎。

# 任务
根据下面提供的测试用例信息,使用你可用的工具(特别是Playwright浏览器工具和WHartTest MCP工具)来执行UI自动化测试。

# 测试用例信息
- **用例ID**: {testcase_id}
- **用例名称**: {testcase_name}
- **前置条件**: {precondition}

# 执行步骤
{steps}

# 执行要求
1. **浏览器管理**
   - 在开始执行前，如果需要请打开浏览器
   - **重要**：在所有步骤执行完毕后，必须关闭浏览器

2. **截图和上传（重要）**
   - **每个步骤执行后都必须截屏并上传**
   - **截图文件名必须唯一**：使用格式 `testcase-{{testcase_id}}-step-{{step_number}}-{{timestamp}}.png`
   - 步骤流程：
     a. 使用 Playwright 的 `take_screenshot` 工具截屏
        - 指定唯一文件名，例如：`testcase-{testcase_id}-step-1-1234567890.png`
        - 避免使用默认文件名，防止并发测试时文件冲突
     b. **立即使用 WHartTest MCP 工具的 `save_operation_screenshots_to_the_application_case` 上传截图**
     c. 记录上传后返回的截图路径
   - 参数示例：
     ```
     project_id: 项目ID
     case_id: {testcase_id}
     file_path: 截图的本地文件路径（必须是唯一的）
     title: "步骤X执行截图"
     description: 步骤描述
     step_number: 当前步骤编号
     page_url: 当前页面URL
     ```

3. **错误处理**
   - 如果步骤执行失败，记录详细的错误信息
   - 失败时也要截屏并上传
   - 失败后不要继续执行后续步骤

# 输出格式
在所有步骤执行完毕后,你**必须**返回一个JSON对象,格式如下:
```json
{{
  "testcase_id": {testcase_id},
  "status": "pass" | "fail",
  "summary": "对执行过程的简短总结。",
  "steps": [
    {{
      "step_number": 1,
      "description": "步骤的描述",
      "status": "pass" | "fail",
      "screenshot": "上传后的截图访问路径（来自upload_testcase_screenshot的返回值）",
      "error": "如果失败,记录错误信息" | null
    }},
    ...
  ]
}}
```

**重要提示**：
- **截图文件名唯一性**：必须为每个截图使用唯一的文件名，格式：`testcase-{{testcase_id}}-step-{{step_number}}-{{timestamp}}.png`
- **工具名称修正**：上传截图使用 `save_operation_screenshots_to_the_application_case` 工具
- **每个步骤都必须调用 WHartTest 的工具上传截图**
- 每个步骤的screenshot字段必须包含上传后的截图路径
- 执行完所有步骤后，务必关闭浏览器
- 确保JSON格式正确，可以被程序解析
- **并发安全**：使用唯一文件名避免多个测试用例同时执行时的文件冲突"""
            }
        }

        created_prompts = []
        skipped_prompts = []

        # 遍历所有提示词类型，检查用户是否已有，没有则创建
        for prompt_type, prompt_data in default_prompts.items():
            existing_prompt = UserPrompt.objects.filter(
                user=request.user,
                prompt_type=prompt_type
            ).first()

            if existing_prompt:
                # 已存在，跳过
                skipped_prompts.append({
                    'type': prompt_type,
                    'name': prompt_data['name'],
                    'reason': '已存在'
                })
            else:
                # 创建新提示词
                new_prompt = UserPrompt.objects.create(
                    user=request.user,
                    name=prompt_data['name'],
                    description=prompt_data['description'],
                    content=prompt_data['content'],
                    prompt_type=prompt_type,
                    is_default=False,  # 程序调用类型不能设为默认
                    is_active=True
                )
                serializer = self.get_serializer(new_prompt)
                created_prompts.append(serializer.data)

        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": f"初始化完成！创建了 {len(created_prompts)} 个提示词，跳过 {len(skipped_prompts)} 个",
            "data": {
                "created": created_prompts,
                "skipped": skipped_prompts,
                "summary": {
                    "created_count": len(created_prompts),
                    "skipped_count": len(skipped_prompts),
                    "total_types": len(default_prompts)
                }
            },
            "errors": {}
        })

    @action(detail=False, methods=['get'])
    def init_status(self, request):
        """获取用户提示词初始化状态"""
        # 获取用户现有的提示词类型
        existing_types = set(UserPrompt.objects.filter(
            user=request.user
        ).values_list('prompt_type', flat=True))

        # 所有可用的提示词类型
        all_types = dict(PromptType.choices)
        
        status_info = []
        for prompt_type, display_name in all_types.items():
            status_info.append({
                'type': prompt_type,
                'name': display_name,
                'exists': prompt_type in existing_types,
                'is_program_call': prompt_type in UserPrompt.PROGRAM_CALL_TYPES
            })

        missing_types = [
            info for info in status_info
            if not info['exists']
        ]

        return Response({
            "status": "success",
            "code": status.HTTP_200_OK,
            "message": "获取初始化状态成功",
            "data": {
                "all_types": status_info,
                "missing_types": missing_types,
                "summary": {
                    "total_types": len(all_types),
                    "existing_count": len(existing_types),
                    "missing_count": len(missing_types),
                    "can_initialize": len(missing_types) > 0
                }
            },
            "errors": {}
        })
