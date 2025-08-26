# 前端组件依赖

## 技术栈概览

WHartTest 前端基于 Vue 3 生态构建，采用现代化的前端技术栈，提供响应式的用户界面和流畅的用户体验。

## 版本控制说明

在依赖管理中，我们使用以下版本控制符号：

- **==**: 精确版本匹配（如 `vue==3.5.13`）
- **>=**: 大于或等于指定版本
- **^**: 兼容版本（主版本号不变，次版本号和修订号可以升级）
  - 例如：`^3.5.13` 表示 `>=3.5.13 <4.0.0`
- **~**: 近似版本（次版本号不变，修订号可以升级）
  - 例如：`~5.8.3` 表示 `>=5.8.3 <5.9.0`

## 核心框架

### Vue 3
- **版本**: ^3.5.13
- **作用**: 渐进式 JavaScript 框架，构建用户界面的核心
- **特点**: Composition API、更好的 TypeScript 支持、性能优化
- **开源协议**: MIT License

### TypeScript
- **版本**: ~5.8.3
- **作用**: 为 JavaScript 提供类型系统，增强代码可维护性
- **开源协议**: MIT License

## 构建工具

### Vite
- **版本**: ^6.3.5
- **作用**: 下一代前端构建工具，提供快速的开发体验
- **特点**: 
  - 极速的冷启动
  - 即时热更新（HMR）
  - 优化的构建产物
- **开源协议**: MIT License

## UI 组件库

### Arco Design Vue
- **版本**: ^2.57.0
- **作用**: 基于 Vue 3 的企业级设计系统组件库
- **特点**: 丰富的组件、主题定制、国际化支持
- **开源协议**: MIT License

### Wired Elements
- **版本**: ^3.0.0-rc.6
- **作用**: 手绘风格的 Web Components UI 库
- **特点**: 独特的手绘风格视觉效果
- **开源协议**: MIT License

## 状态管理

### Pinia
- **版本**: ^3.0.2
- **作用**: Vue 官方状态管理库，替代 Vuex
- **特点**: 
  - 更简洁的 API
  - 更好的 TypeScript 支持
  - 模块化设计
- **开源协议**: MIT License

## 路由管理

### Vue Router
- **版本**: ^4.5.1
- **作用**: Vue 官方路由管理器
- **特点**: 支持嵌套路由、路由守卫、动态路由
- **开源协议**: MIT License

## HTTP 客户端

### Axios
- **版本**: ^1.9.0
- **作用**: 基于 Promise 的 HTTP 客户端
- **配置**: 
  - 请求/响应拦截器
  - 错误处理
  - 超时设置
- **开源协议**: MIT License

## Markdown 处理

### Marked
- **版本**: ^15.0.12
- **作用**: 高性能 Markdown 解析器
- **开源协议**: MIT License

### DOMPurify
- **版本**: ^3.2.6
- **作用**: HTML 清理和 XSS 防护
- **开源协议**: MPL-2.0 或 Apache-2.0

### DOMPurify 类型定义
- **版本**: ^3.0.5
- **作用**: DOMPurify 库的 TypeScript 类型定义
- **开源协议**: MIT License

### Marked 类型定义
- **版本**: ^5.0.2
- **作用**: Marked 库的 TypeScript 类型定义
- **开源协议**: MIT License

## 实用工具库

### VueUse
- **版本**: ^13.1.0
- **作用**: Vue 组合式工具集
- **开源协议**: MIT License

## 样式处理

### Tailwind CSS
- **版本**: ^4.1.6
- **作用**: 实用优先的 CSS 框架
- **开源协议**: MIT License

### PostCSS
- **版本**: ^8.5.3
- **作用**: CSS 处理工具
- **开源协议**: MIT License

### Autoprefixer
- **版本**: ^10.4.21
- **作用**: 为 CSS 规则添加供应商前缀
- **开源协议**: MIT License

## 开发工具

### Vue TypeScript Plugin
- **版本**: ^0.7.0
- **作用**: Vue TypeScript 支持
- **开源协议**: MIT License

### Vite Vue Plugin
- **版本**: ^5.2.3
- **作用**: Vue 支持的 Vite 插件
- **开源协议**: MIT License

### Vue TSConfig
- **版本**: ^0.7.0
- **作用**: Vue 项目的 TypeScript 配置
- **开源协议**: MIT License

## 类型定义

### Node.js 类型定义
- **版本**: ^22.15.17
- **作用**: Node.js API 的 TypeScript 类型定义
- **开源协议**: MIT License

## 编译工具

### Vue TSC
- **版本**: ^2.2.8
- **作用**: Vue 的 TypeScript 编译器
- **开源协议**: MIT License



