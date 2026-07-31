# Agent 指南

## 开发与测试

### WHartTest_Django

1. 后端环境为 Docker 容器 `wharttest-backend`
2. 执行代码 `patch.bat` 更新容器代码

### WHartTest_Vue

1. 后端环境为 Docker 容器 `wharttest-frontend`
2. 执行代码 `patch.bat` 更新容器代码

### WHartTest_Actuator

1. 此目录为UI自动化执行器代码，参考 `WHartTest_Actuator/README.md`
2. 使用 `uv` 运行 Python 与依赖安装

## 模型配置

- apiBase: http://192.168.2.180:3000/v1
- apiKey: sk-Cra0HlWnPgKnL8VP03Df097eA3B24dBcB1904d32C3812783
- model: qwen3-coder

