# Agent Loop 对于弱模型优化

## 复现步骤

1. 登录页面 → 测试管理 → 用例管理，根据需求文档生成测试用例
2. 在LLM对话查看新对话执行情况

## 问题现象

1. Agent长时间执行，未成功生成测试用例
2. Agent长时间执行过程中，点击页面，页面出现加载未响应情况，性能差

## 问题定位

1. 用例管理执行用例生成，调用接口为 `POST /api/orchestrator/agent-loop/`
   - WHartTest_Django\orchestrator_integration\agent_loop_view.py 代码中 create_agent() 构建 Agent 执行核心循环逻辑
   - Agent自主执行通过 skills tool实现用例管理

2. 实际测试，Agent Loop 针对强模型，具备长上下文，具备较好的执行结果与性能表现，但针对弱模型，上下文较短，执行结果错误、且页面卡死

## 建议解决方案

1. 保留原Agent Loop 适配强模型
2. 新增Agent Loop 适配弱模型，并针对弱模型进行优化

## 测试环境

弱模型配置：

- apiBase: http://192.168.2.180:3000/v1
- apiKey: sk-Cra0HlWnPgKnL8VP03Df097eA3B24dBcB1904d32C3812783
- model: qwen3-coder

测试环境:

- 本地已部署 Docker 容器, 请在 Docker 容器环境内测试代码
