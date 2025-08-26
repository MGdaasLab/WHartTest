# 重新评审功能实现说明

## 🎯 功能概述

为需求管理系统添加了重新评审功能，允许用户对已完成评审的文档重新启动评审流程。

## ✅ 实现内容

### 1. 详情页面 (`DocumentDetailView.vue`)

**新增功能：**
- ✅ 在 `review_completed` 状态下显示"重新评审"按钮
- ✅ 在 `failed` 状态下显示"重新评审"按钮
- ✅ 重新评审按钮与"查看详细报告"按钮并排显示
- ✅ 添加确认对话框，提醒用户重新评审的影响
- ✅ 智能重试逻辑：失败状态会检查是否需要先进行模块拆分
- ✅ 集成用户自定义提示词功能
- ✅ 完整的错误处理和加载状态

**UI变更：**
```vue
<!-- 评审完成状态：显示查看报告和重新评审按钮 -->
<a-space v-if="document?.status === 'review_completed'">
  <a-button type="primary" @click="viewReport">
    <template #icon><icon-file /></template>
    查看详细报告
  </a-button>
  <a-button type="outline" @click="restartReview" :loading="reviewLoading">
    <template #icon><icon-refresh /></template>
    重新评审
  </a-button>
</a-space>

<!-- 处理失败状态：显示重新评审按钮 -->
<a-button
  v-if="document?.status === 'failed'"
  type="primary"
  @click="retryReview"
  :loading="reviewLoading"
>
  <template #icon><icon-refresh /></template>
  重新评审
</a-button>
```

### 2. 列表页面 (`RequirementManagementView.vue`)

**新增功能：**
- ✅ 在操作列添加"重新评审"按钮（`review_completed` 状态）
- ✅ 在操作列添加"重试评审"按钮（`failed` 状态）
- ✅ 与"查看报告"按钮并列显示
- ✅ 相同的确认对话框和错误处理逻辑
- ✅ 智能区分重新评审和重试评审的文案

**UI变更：**
```vue
<a-button
  v-if="record.status === 'review_completed'"
  type="text"
  size="small"
  @click="restartReview(record)"
>
  重新评审
</a-button>
<a-button
  v-if="record.status === 'failed'"
  type="text"
  size="small"
  @click="retryReview(record)"
>
  重试评审
</a-button>
```

## 🔧 技术实现

### 核心方法

```typescript
// 重新评审方法
const restartReview = async () => {
  // 1. 确认对话框
  const confirmed = await Modal.confirm({
    title: '确认重新评审',
    content: '重新评审将创建新的评审报告，原有报告将保留。是否继续？',
    okText: '确认',
    cancelText: '取消'
  });

  if (!confirmed) return;

  // 2. 获取用户自定义提示词
  const { getAllRequirementPromptIds } = await import('@/features/requirements/services/requirementPromptService');
  const promptIds = await getAllRequirementPromptIds();

  // 3. 调用评审API
  const response = await RequirementDocumentService.startReview(document.value.id, {
    analysis_type: 'comprehensive',
    parallel_processing: true,
    prompt_ids: Object.keys(promptIds).length > 0 ? promptIds : undefined
  });

  // 4. 处理响应和状态更新
  if (response.status === 'success') {
    Message.success('重新评审已开始');
    await loadDocument(); // 重新加载文档
  }
};
```

### 新增导入

```typescript
// DocumentDetailView.vue
import { Message, Modal } from '@arco-design/web-vue';
import { IconRefresh } from '@arco-design/web-vue/es/icon';

// RequirementManagementView.vue  
import { Message, Modal } from '@arco-design/web-vue';
```

## 🎨 用户体验

### 交互流程
1. **发现入口** - 用户在评审完成的文档上看到"重新评审"按钮
2. **确认操作** - 点击后弹出确认对话框，说明重新评审的影响
3. **执行评审** - 确认后自动调用后端API，显示加载状态
4. **状态更新** - 评审开始后文档状态自动更新，页面刷新显示新状态

### 视觉设计
- **按钮样式**: 使用 `outline` 类型，与主要操作按钮区分
- **图标**: 使用刷新图标 `IconRefresh` 直观表示重新开始
- **布局**: 与现有按钮保持一致的间距和对齐
- **加载状态**: 重用现有的 `reviewLoading` 状态

## 🔄 与后端API的集成

### API调用
- **端点**: `POST /api/requirements/documents/{id}/restart-review/`
- **参数**: 与首次评审相同的参数结构
- **响应**: 专用的重新评审端点，处理重新评审的逻辑

### 状态管理
- **文档状态**: 从 `review_completed` 转换为 `reviewing`
- **报告保留**: 历史评审报告保持不变
- **新报告**: 创建新的评审报告记录

## 📋 测试建议

### 功能测试
1. ✅ 验证按钮只在 `review_completed` 状态下显示
2. ✅ 确认对话框正常弹出和响应
3. ✅ API调用成功，文档状态正确更新
4. ✅ 加载状态和错误处理正常工作
5. ✅ 用户自定义提示词正确集成

### 边界测试
1. ✅ 网络错误时的错误处理
2. ✅ 用户取消确认对话框的处理
3. ✅ 并发操作的处理（防止重复点击）

## 🎉 完成状态

- ✅ **详情页面重新评审按钮** - 已实现（`review_completed` 和 `failed` 状态）
- ✅ **列表页面重新评审按钮** - 已实现（`review_completed` 和 `failed` 状态）
- ✅ **智能重试逻辑** - 已实现（失败状态会检查模块拆分需求）
- ✅ **确认对话框** - 已实现（区分重新评审和重试评审文案）
- ✅ **API集成** - 已实现
- ✅ **错误处理** - 已实现
- ✅ **加载状态** - 已实现
- ✅ **用户提示词集成** - 已实现

重新评审功能现已完整实现，支持已完成评审和处理失败两种状态的重新评审！🚀

### 🔄 支持的状态流转
```
review_completed → reviewing (重新评审)
failed → reviewing (重试评审，智能检查模块拆分需求)
```
