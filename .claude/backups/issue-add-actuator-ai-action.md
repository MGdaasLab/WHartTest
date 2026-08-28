# Actuator 支持 AI 自主测试

## New Feature

需求背景：
- 当前 Actuator 仅支持确定性步骤，如：元素操作、元素断言等
- 参照 Midscene.js、Agent Browser 等Agent浏览器UI自动化实现，实现基于自然语言描述的UI自动化测试
- 要求可以基于自然语言描述，AI自主完成复杂步骤执行，包括：多步页面操作、数据处理、断言等，返回执行结果

## 相关改动项

1. 新增UI自动化页面步骤类型 `AI操作`，对应英文为 `AI Action`
    - 相关Django Model为 `WHartTest_Django\ui_automation\models.py` 中的 `STEP_TYPE_CHOICES` 
    - 页面选择 `AI操作`，支持文本框输入自然语言描述的UI测试内容

2. 修改 `WHartTest_Actuator` 执行器接受自动化测试任务支持 `AI操作`
    - `WHartTest_Actuator\executor.py` 执行引擎 `step_type`

## 建议方案

1. `WHartTest_Actuator\config.example.toml` 新增独立AI模型配置，如：

```toml
[model]
api_url = "http://192.168.2.180:3000/v1"
api_key = "sk-Cra0HlWnPgKnL8VP03Df097eA3B24dBcB1904d32C3812783"
model = "qwen3-coder"
provider = "openai_compatible"
supports_vision = false
context_limit = 100000
```

2. 基于已有的 playwright API 实现 AI 操作

3. `WHartTest_Actuator\agent\` 文件夹实现 AI Agent浏览器操作逻辑，包括：AI模型初始化、AI模型交互等流程

4. AI模型需做针对性适配
- context_limit 配置模型上下文上限
- supports_vision 配置模型是否为VLM模型
- 如模型支持视觉，则支持通过截图，VLM视觉理解
- 适配弱模型，比如小上下文模型，比如只有10k，提前对上下文执行压缩，避免模型执行性能下降
