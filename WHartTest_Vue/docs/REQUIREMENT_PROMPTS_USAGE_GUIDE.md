# 需求评审提示词系统使用指南

## 📋 概述

本指南介绍如何使用新集成的需求评审提示词系统，该系统允许用户创建和管理专用于需求评审的自定义提示词。

## 🎯 功能特性

### 1. 提示词类型分离
- **对话提示词**：用于普通聊天，支持多个提示词和默认设置
- **需求评审提示词**：专用于需求评审流程，每种类型只能创建一个

### 2. 需求评审提示词类型
- `requirement_structure` - 需求结构分析
- `requirement_direct` - 需求直接分析  
- `requirement_global` - 需求全局分析
- `requirement_module` - 需求模块分析
- `requirement_consistency` - 需求一致性检查

## 🚀 使用方法

### 1. 创建需求评审提示词

#### 通过提示词管理界面
1. 点击聊天界面的"系统提示词"按钮
2. 在弹出的提示词管理窗口中
3. 点击"新建提示词"按钮
4. 选择提示词类型（从下拉菜单中选择需求评审类型）
5. 填写提示词信息：
   - **名称**：提示词的显示名称
   - **描述**：可选的描述信息
   - **内容**：具体的提示词内容
6. 点击"保存"完成创建

#### 注意事项
- 每种需求评审类型只能创建一个提示词
- 需求评审类型的提示词不支持设置为默认
- 如果尝试创建重复类型的提示词，系统会提示错误

### 2. 管理需求评审提示词

#### 查看现有提示词
- 在提示词管理界面中，需求评审类型的提示词会显示对应的类型标签
- 可以通过编辑按钮修改现有的需求评审提示词

#### 编辑提示词
1. 点击提示词卡片上的编辑按钮
2. 修改提示词内容
3. 保存更改

#### 删除提示词
1. 点击提示词卡片上的删除按钮
2. 确认删除操作

### 3. 在需求评审中使用

#### 自动集成
- 当启动需求评审时，系统会自动检查用户是否有自定义的需求评审提示词
- 如果有自定义提示词，系统会自动使用这些提示词进行评审
- 如果没有自定义提示词，系统会使用默认的系统提示词

#### 启动评审
1. 在需求文档详情页面或需求管理列表页面
2. 点击"开始评审"或"直接开始评审"按钮
3. 系统会自动应用用户的自定义提示词（如果存在）

## 🔧 开发者指南

### API 接口

#### 获取需求评审提示词列表
```typescript
import { getRequirementPrompts } from '@/features/prompts/services/promptService';

const response = await getRequirementPrompts();
```

#### 获取指定类型的需求评审提示词
```typescript
import { getRequirementPrompt } from '@/features/prompts/services/promptService';

const response = await getRequirementPrompt({ 
  prompt_type: 'requirement_direct' 
});
```

#### 创建需求评审提示词
```typescript
import { createUserPrompt } from '@/features/prompts/services/promptService';

const response = await createUserPrompt({
  name: '我的需求分析提示词',
  content: '你是一位资深的需求分析师...',
  description: '自定义的需求分析提示词',
  prompt_type: 'requirement_direct'
});
```

### 类型定义

```typescript
// 提示词类型
type PromptType = 
  | 'chat'
  | 'requirement_structure'
  | 'requirement_direct'
  | 'requirement_global'
  | 'requirement_module'
  | 'requirement_consistency';

// 需求评审提示词ID集合
interface RequirementPromptIds {
  requirement_structure?: number;
  requirement_direct?: number;
  requirement_global?: number;
  requirement_module?: number;
  requirement_consistency?: number;
}
```

## 🧪 测试验证

### 浏览器控制台测试

#### 测试需求评审提示词功能
```javascript
// 运行完整的需求评审提示词测试
window.testRequirementPrompts.runAll();

// 测试获取需求评审提示词列表
window.testRequirementPrompts.getRequirementPrompts();

// 测试创建需求评审提示词
window.testRequirementPrompts.createRequirementPrompt('requirement_direct');
```

#### 测试系统集成
```javascript
// 运行完整的集成测试
window.testIntegration.runAll();

// 测试向后兼容性
window.testIntegration.backwardCompatibility();

// 测试需求评审流程集成
window.testIntegration.requirementReviewIntegration();
```

## ⚠️ 注意事项

### 1. 兼容性
- 新功能完全向后兼容，不会影响现有的对话提示词功能
- 现有的需求评审流程会自动适配新的提示词系统

### 2. 限制
- 每种需求评审类型只能创建一个提示词
- 需求评审提示词不支持设置为默认（因为每种类型只有一个）
- 删除需求评审提示词后，系统会回退到使用默认的系统提示词

### 3. 最佳实践
- 建议为每种需求评审类型创建专门的提示词以获得最佳效果
- 提示词内容应该针对具体的分析类型进行优化
- 定期更新和优化提示词内容以提高评审质量

## 🔗 相关文件

- `src/features/prompts/types/prompt.ts` - 类型定义
- `src/features/prompts/services/promptService.ts` - API服务
- `src/features/requirements/services/requirementPromptService.ts` - 需求评审提示词服务
- `src/features/langgraph/components/SystemPromptModal.vue` - 提示词管理界面
- `src/test-requirement-prompts.ts` - 功能测试
- `src/test-integration.ts` - 集成测试

## 📞 支持

如果在使用过程中遇到问题，请：
1. 首先运行浏览器控制台测试验证功能
2. 检查浏览器开发者工具的控制台是否有错误信息
3. 查看网络请求是否正常
4. 联系开发团队获取技术支持
