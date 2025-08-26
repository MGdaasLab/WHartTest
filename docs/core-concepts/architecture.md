---
title: 架构概览
---

# 架构概览

WHartTest 平台采用现代化的前后端分离架构，旨在实现高度的可扩展性、可维护性和卓越的用户体验。整个系统分为两个核心部分：

- **前端应用 (Vue 3)**：负责用户界面和交互逻辑。
- **后端服务 (Django)**：负责业务逻辑、数据持久化和 AI 能力集成。

这种分离的架构使得团队可以并行开发，并且能够独立地对前端或后端进行技术升级和部署。

## 1. 前端架构

前端是一个基于 **Vue 3**、**TypeScript** 和 **Vite** 构建的单页应用 (SPA)，提供了丰富、响应式的用户界面。它通过 **Pinia** 管理全局状态，使用 **Vue Router** 控制页面导航，并利用 **Axios** 与后端 API 安全地通信。

[**➡️ 查看详细前端架构**](./frontend-architecture.md)

## 2. 后端架构

后端是一个基于 **Django** 和 **Django REST Framework** 构建的强大 API 服务。它不仅提供了标准的 CRUD 功能，还深度集成了 **LangChain** 和 **LangGraph** 作为 AI 引擎，利用 **ChromaDB** 和 **HuggingFace 模型** 构建了先进的知识库检索能力 (RAG)。

[**➡️ 查看详细后端架构**](./permission-system.md)
