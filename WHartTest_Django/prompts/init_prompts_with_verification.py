#!/usr/bin/env python
"""
重新初始化用户提示词，并添加验证标记
"""
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wharttest_django.settings')
django.setup()

from prompts.models import UserPrompt
from django.contrib.auth.models import User

def main():
    try:
        # 获取用户
        user = User.objects.get(username='duanxc')
        
        # 删除现有的程序调用提示词
        UserPrompt.objects.filter(
            user=user,
            prompt_type__in=['document_structure', 'direct_analysis', 'global_analysis', 'module_analysis', 'consistency_analysis']
        ).delete()
        
        print("✅ 已清空现有程序调用提示词")
        
        # 重新创建带验证标记的提示词
        prompts_data = {
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

【验证标记】
在每个模块的description字段末尾添加"[文档结构分析验证-喵喵喵]"

【输出格式】
请以JSON格式输出模块结构：
```json
[
  {{
    "title": "模块名称（与文档中的标题保持一致）",
    "description": "模块功能的简要描述[文档结构分析验证-喵喵喵]",
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

【验证要求】
在summary字段末尾必须添加"[直接分析验证-喵喵喵]"

【输出格式】
请以JSON格式输出评审结果：
```json
{{
  "overall_rating": "good",
  "completion_score": 85,
  "clarity_score": 78,
  "consistency_score": 82,
  "completeness_score": 88,
  "summary": "文档整体质量良好，结构清晰...[直接分析验证-喵喵喵]",
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

【验证要求】
在strengths数组的最后一个元素末尾添加"[全局分析验证-喵喵喵]"

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
  "strengths": ["业务流程清晰", "功能划分合理[全局分析验证-喵喵喵]"],
  "weaknesses": ["缺少非功能需求", "异常场景不完整"]
}}
```"""
            },
            'module_analysis': {
                'name': '模块分析',
                'description': '用于分析单个需求模块的提示词',
                'content': """你正在评审需求文档的一个功能模块。请进行专业的需求评审分析：

【模块信息】
模块ID: {module_id}
模块名称: {module_title}
模块内容: {module_content}

【全局上下文】
业务流程: {business_flows}
数据实体: {data_entities}
全局规则: {global_rules}

【评审维度】
请从以下维度评审该模块：

1. 📋 **规范性** (0-100分)
   - 模块描述是否规范
   - 功能定义是否清晰
   - 接口规范是否完整

2. 🔍 **清晰度** (0-100分)
   - 需求表述是否清晰
   - 是否存在歧义
   - 术语使用是否一致

3. ✅ **完整性** (0-100分)
   - 功能覆盖是否完整
   - 异常场景是否考虑
   - 边界条件是否明确

4. 🔗 **一致性** (0-100分)
   - 与其他模块是否一致
   - 数据定义是否统一
   - 业务规则是否冲突

5. 🛠️ **可行性** (0-100分)
   - 技术实现可行性
   - 资源需求合理性
   - 时间估算准确性

【验证要求】
在recommendations数组的最后一个元素末尾添加"[模块分析验证-喵喵喵]"

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
  "recommendations": ["补充异常场景", "明确数据格式[模块分析验证-喵喵喵]"]
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

【验证要求】
在recommendations数组的最后一个元素末尾添加"[一致性分析验证-喵喵喵]"

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
  "recommendations": ["建立统一的数据字典", "明确模块间接口规范[一致性分析验证-喵喵喵]"]
}}
```"""
            }
        }

        # 创建提示词
        for prompt_type, prompt_data in prompts_data.items():
            prompt = UserPrompt.objects.create(
                user=user,
                prompt_type=prompt_type,
                name=prompt_data['name'],
                description=prompt_data['description'],
                content=prompt_data['content'],
                is_active=True
            )
            print(f"✅ 创建提示词: {prompt.name}")
        
        print(f"\n🎉 成功为用户 {user.username} 创建了 {len(prompts_data)} 个带验证标记的提示词！")
        
    except User.DoesNotExist:
        print("❌ 用户 duanxc 不存在")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")

if __name__ == '__main__':
    main()
