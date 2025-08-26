# 提示词管理API接口变更适配说明

## 概述

本次更新为提示词管理系统添加了**程序调用类型**支持，允许用户为需求管理功能配置专用的提示词。

## 已完成的适配工作

### 1. 类型定义更新

- 更新了提示词类型枚举，从原来的 `chat` 等类型改为 `general`, `document_structure` 等
- 添加了程序调用类型标识，用于区分通用对话和程序调用类型提示词
- 更新了相关工具函数，如 `isProgramCallPromptType`

### 2. API服务更新

- 添加了新的API端点：
  - `/api/prompts/user-prompts/types/` - 获取提示词类型列表
  - `/api/prompts/user-prompts/by_type/` - 根据类型获取提示词
- 更新了提示词服务，添加了新的方法：
  - `getPromptTypes()` - 获取提示词类型列表
  - `getPromptByType()` - 根据类型获取提示词

### 3. 组件更新

- 添加了新的组件：
  - `PromptTypeSelector` - 提示词类型选择器
  - `PromptTypeFilter` - 提示词类型过滤器
  - `PromptForm` - 包含类型选择和验证的提示词表单

### 4. 验证逻辑更新

- 添加了提示词验证工具函数，实现以下验证规则：
  - 程序调用类型不能设置为默认提示词
  - 每个用户每种程序调用类型只能有一个提示词

### 5. 需求评审服务更新

- 更新了需求评审提示词类型映射，使用新的类型名称
- 更新了获取提示词的方法，使用新的API端点

## 使用说明

### 1. 提示词类型选择器

```vue
<PromptTypeSelector
  v-model="form.prompt_type"
  @is-program-call-changed="handleProgramCallChange"
/>
```

### 2. 提示词类型过滤器

```vue
<PromptTypeFilter
  v-model="filterType"
  @update:modelValue="handleFilterChange"
/>
```

### 3. 提示词表单验证

```typescript
import { validatePromptForm } from '@/features/prompts/utils/promptValidation';

// 在表单提交前验证
const validationErrors = validatePromptForm(form);
if (validationErrors) {
  // 显示错误信息
  Object.assign(errors, validationErrors);
  return;
}
```

### 4. 处理需求管理功能的提示词缺失错误

```typescript
import { handleRequirementPromptError } from '@/features/prompts/utils/promptValidation';

// 处理错误
handleRequirementPromptError(error, () => {
  // 显示提示词配置对话框
  showPromptConfigDialog();
});
```

## 注意事项

1. 程序调用类型提示词不能设置为默认提示词
2. 每个用户每种程序调用类型只能有一个提示词
3. 通用对话类型可以有多个提示词
4. 需求管理功能现在依赖用户配置的提示词，如果用户没有配置相应类型的提示词，会返回错误提示用户配置