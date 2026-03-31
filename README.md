# WHartTest - AI驱动的智能测试用例生成平台

中文 | [English](README_EN.md)

## 项目简介

WHartTest 是一个基于 Django REST Framework 构建的AI驱动测试自动化平台，核心功能是通过AI智能生成测试用例。平台集成了 LangChain、MCP（Model Context Protocol）工具调用、项目管理、需求评审、测试用例管理以及先进的知识库管理和文档理解功能。利用大语言模型和多种嵌入服务（OpenAI、Azure OpenAI、Ollama等）的能力，自动化生成高质量的测试用例，并结合知识库提供更精准的测试辅助，为测试团队提供一个完整的智能测试管理解决方案。

## 平台功能

###  AI智能测试用例生成
基于大语言模型（LLM）技术，实现从需求到测试用例的智能转化：
- **多源输入**：支持需求文档、对话交互、API文档等多种输入方式
- **结构化输出**：自动生成包含测试步骤、前置条件、输入数据、期望结果、优先级（P0-P3）的完整用例
- **多模型支持**：集成 OpenAI、Azure OpenAI、Ollama、Xinference 等多种嵌入服务

###  知识库管理与文档理解
构建项目级知识库，为AI生成提供精准上下文：
- **多格式支持**：PDF、Word、Excel、PPT、Markdown、网页链接等
- **智能分块**：自动文档解析、分块与向量化存储
- **语义检索**：基于向量相似度的精准知识检索
- **Reranker精排**：支持配置重排序模型提升检索精度

###  MCP工具集成
通过 Model Context Protocol 实现AI与测试工具的无缝对接：
- **浏览器自动化**：集成 Playwright，支持页面操作、元素定位、截图录屏
- **多协议支持**：streamable-http、SSE 等传输协议
- **HITL人工审批**：敏感操作支持人工确认机制
- **自定义扩展**：支持接入第三方工具和服务

###  需求评审与风险分析
AI驱动的需求质量评估，提前识别潜在风险：
- **六维评分体系**：完整度、清晰度、一致性、可测性、可行性、逻辑性
- **问题追踪**：自动识别需求中的模糊点、矛盾点、遗漏点
- **改进建议**：提供针对性的需求优化和测试策略建议

###  测试用例管理
全生命周期的测试用例管理能力：
- **多级模块**：支持5级子模块的用例组织结构
- **用例审核**：待审核、通过、优化、不可用等状态流转
- **测试套件**：灵活组合用例，支持并发执行配置
- **批量操作**：用例的批量创建、编辑、移动、删除

###  UI自动化测试
低代码UI自动化，降低自动化测试门槛：
- **多定位策略**：CSS、XPath、Text、Role、Label 等元素定位方式
- **可视化编排**：拖拽式步骤编排，支持条件判断、循环、断言
- **环境管理**：多浏览器支持（Chromium/Firefox/WebKit）、环境配置切换
- **执行记录**：完整的截图、视频、Trace追踪、执行日志

###  APP自动化测试
集成 mobile-mcp，支持移动端应用自动化测试：
- **多平台支持**：Android、iOS 移动设备自动化
- **设备管理**：设备连接状态检测、设备信息获取
- **应用操作**：应用安装/卸载/启动/停止
- **元素交互**：点击、滑动、输入、手势操作
- **屏幕操作**：截图、录屏、屏幕亮度/音量调节
- **系统操作**：通知栏操作、权限管理、网络切换

### Skill智能技能系统
可扩展的Agent技能管理框架：
- **多来源导入**：支持 ZIP 文件上传、Git 仓库导入
- **SKILL.md规范**：标准化的技能描述文件
- **安全隔离**：技能文件独立存储，防止路径穿越攻击
- **专属资源**：加入技术交流群获取经过微调优化的 Skills 和 MCP 工具包
###  执行报告与分析
全面的测试执行结果分析：
- **实时监控**：执行进度、状态实时更新
- **多维度统计**：通过率、执行时长、失败原因分析
- **历史对比**：支持执行结果的历史趋势分析

## 文档
详细文档请访问：https://mgdaaslab.github.io/WHartTest/

## 快速开始

### Docker 部署（推荐 - 开箱即用）

```bash
# 1. 克隆仓库
git clone https://github.com/MGdaasLab/WHartTest.git
cd WHartTest

# 2. 准备配置（使用默认配置，包含自动生成的API Key）
cp .env.example .env

# 3. 一键启动（以下两种方式二选一）
# 方式一：使用部署脚本（推荐，支持镜像源择优）
./run_compose.sh

# 方式二：直接使用 docker-compose
docker-compose up -d

# 4. 访问系统
# http://localhost:8913 (admin/admin123456)
```

**就这么简单！** 系统会自动创建默认API Key，MCP服务开箱即用。

### 统一部署脚本

如果你使用仓库自带脚本部署，现在启动后会先让你在“远程拉镜像”和“本地构建镜像”之间二选一：

```bash
./run_compose.sh
```

这个脚本现在会：

- 先选择部署方式：`remote` 远程镜像下载，或 `local` 本地构建镜像
- `remote` 模式会自动在内置远程镜像仓库候选里测速择优，用户只需选择 `1` 即可
- `remote` 会按仓库类型分别选择：Docker Hub 使用官方 / `docker.1panel.live` / `docker.1ms.run` / `docker.xuanyuan.me` / `docker.m.daocloud.io`，GHCR 使用官方 / `ghcr.1ms.run` / `ghcr.nju.edu.cn` / `ghcr.m.daocloud.io`，MCR 使用官方 / `mcr.azure.cn` / `mcr.m.daocloud.io`
- `local` 模式会自动探测当前网络下更快的 `APT / PyPI / npm / Hugging Face` 下载地址
- Python 依赖安装现在支持自动回退：首选测速最快的 PyPI 源，某个包下载超时会顺序切到其余候选继续安装
- `local` 内置候选包含官方源、清华、中科大、阿里云、腾讯云、华为云、北外、上海交大、`npmmirror`、`hf-mirror` 等
- 支持通过环境变量继续追加你自己的候选镜像源
- 本地构建默认使用 Docker 缓存，不再每次都 `--no-cache`

常用示例：

```bash
# 交互选择部署方式
./run_compose.sh

# 直接使用远程预构建镜像
./run_compose.sh remote

# 直接使用本地构建，并自动选择更快下载源
./run_compose.sh local

# 本地构建时强制使用原生官方源
DOCKER_SOURCE_PROFILE=native ./run_compose.sh local

# 本地构建时强制只在镜像源里择优
DOCKER_SOURCE_PROFILE=mirror ./run_compose.sh local

# 给 PyPI 追加自定义候选源（注意用引号包起来）
DOCKER_PIP_CANDIDATES_EXTRA="corp|https://pypi.example.com/simple|https://pypi.example.com/simple/pip/" ./run_compose.sh local

# 只有在本地全量重建时才禁用缓存
DOCKER_BUILD_NO_CACHE=1 ./run_compose.sh local
```

> ⚠️ **生产环境提示**：请登录后台删除默认API Key并创建新的安全密钥。详见 [快速启动指南](./docs/QUICK_START.md)

详细的部署说明请参考：
- [快速启动指南](./docs/QUICK_START.md) - **推荐新用户阅读**
- [GitHub 自动构建部署指南](./docs/github-docker-deployment.md)
- [完整部署文档](https://mgdaaslab.github.io/WHartTest/)

## 页面展示

| | |
  |---|---|
  | ![alt text](docs/public/img/image-a1.png) | ![alt text](docs/public/img/image-a2.png) |
  | ![alt text](docs/public/img/image-a3.png) | ![alt text](docs/public/img/image-a4.png) |
  | ![alt text](docs/public/img/image-a5.png) | ![alt text](docs/public/img/image-a17.png) |
  | ![alt text](docs/public/img/image-a7.png) | ![alt text](docs/public/img/image-a8.png) |
  | ![alt text](docs/public/img/image-a9.png) | ![alt text](docs/public/img/image-a10.png) |
  | ![alt text](docs/public/img/image-a11.png) | ![alt text](docs/public/img/image-a12.png) |
  | ![alt text](docs/public/img/image-a13.png) | ![alt text](docs/public/img/image-a14.png) |
  | ![alt text](docs/public/img/image-a15.png) | ![alt text](docs/public/img/image-a16.png) |
## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request


## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 Issue
- 项目讨论区
- 添加微信时请备注   github   ，拉你进微信群聊。
- 加群获取最新更新信息及SKill。

<img width="400" alt="image" src="docs/public/img/wx.jpg" />

qq群：
1. 8xxxxxxxx0（已满）
2. 1017708746
---
## 【重要安全警示】关于 v1.4.0 以及后续版本 Skills 权限及部署安全的声明
鉴于 Skills 模块具备较高的系统执行权限，为了保障您的数据与环境安全，我们做出以下严正提示：

部署建议：强烈建议仅在内网环境或受信任的私有网络中部署使用。 访问控制：切勿将服务直接暴露于公网（Public Internet），或授予任何未经身份验证及不可信人员访问权限。 免责声明：本项目（WHartTest）仅供学习与研究使用。用户需自行承担因违规部署（如开放公网、未做鉴权等）所导致的一切安全风险与后果。对于因不当配置引发的数据泄露、服务器被入侵等安全事故，WHartTest 团队不承担任何法律及连带责任。
**WHartTest** - AI驱动测试用例生成，让测试更智能，让开发更高效！
