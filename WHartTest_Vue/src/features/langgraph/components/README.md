# LangGraph 聊天组件拆分说明

## 概述

原来的 `LangGraphChatView.vue` 组件有1500多行代码，过于庞大。现在已经拆分为多个小组件，提高了代码的可维护性和复用性。

## 组件结构

### 主组件
- **LangGraphChatView.vue** - 主容器组件，负责数据管理和业务逻辑

### 子组件

#### 1. ChatSidebar.vue
**功能**: 左侧历史对话列表
- 显示历史对话列表
- 新建对话功能
- 会话切换
- 会话删除
- 时间格式化显示

**Props**:
- `sessions`: 会话列表
- `currentSessionId`: 当前会话ID
- `isLoading`: 加载状态

**Events**:
- `create-new-chat`: 创建新对话
- `switch-session`: 切换会话
- `delete-session`: 删除会话

#### 2. ChatHeader.vue
**功能**: 聊天区域头部
- 显示标题
- 流式输出开关
- 会话ID显示
- 清除对话按钮

**Props**:
- `sessionId`: 会话ID
- `isStreamMode`: 流式模式状态
- `hasMessages`: 是否有消息

**Events**:
- `update:is-stream-mode`: 更新流式模式
- `clear-chat`: 清除对话

#### 3. ChatMessages.vue
**功能**: 消息列表容器
- 消息列表渲染
- 空状态显示
- 自动滚动到底部

**Props**:
- `messages`: 消息列表
- `isLoading`: 加载状态

**Events**:
- `toggle-expand`: 切换消息展开状态

#### 4. MessageItem.vue
**功能**: 单个消息组件
- 消息气泡显示
- 头像显示
- 时间显示
- Markdown 渲染
- 工具消息折叠/展开
- 打字指示器动画

**Props**:
- `message`: 消息对象

**Events**:
- `toggle-expand`: 切换展开状态

#### 5. ChatInput.vue
**功能**: 消息输入区域
- 消息输入框
- 发送按钮
- 输入验证

**Props**:
- `isLoading`: 加载状态

**Events**:
- `send-message`: 发送消息

## 拆分优势

### 1. 代码可维护性
- 每个组件职责单一，易于理解和修改
- 组件间依赖关系清晰
- 便于单独测试

### 2. 代码复用性
- 子组件可以在其他地方复用
- 样式和逻辑分离

### 3. 开发效率
- 多人协作时可以并行开发不同组件
- 问题定位更精确
- 代码审查更容易

### 4. 性能优化
- 组件级别的更新优化
- 按需加载可能性

## 数据流

```
LangGraphChatView (主组件)
├── ChatSidebar (会话管理)
├── ChatHeader (头部控制)
├── ChatMessages (消息容器)
│   └── MessageItem (单个消息)
└── ChatInput (输入控制)
```

## 主要功能保持不变

- 流式和非流式聊天模式
- Markdown 渲染支持
- 工具消息处理
- 会话管理
- 历史记录加载
- 自动滚动
- 响应式设计

## 注意事项

1. 所有原有功能都已保留
2. 组件间通过 props 和 events 通信
3. 样式使用 scoped 避免冲突
4. TypeScript 类型定义完整
5. 支持深度样式穿透 (:deep())

## 后续优化建议

1. 可以考虑使用 Pinia 进行状态管理
2. 添加组件级别的单元测试
3. 考虑使用 composables 进一步抽取逻辑
4. 添加组件文档和示例
