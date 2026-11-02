# WHartTest - AI-Powered Intelligent Test Case Generation Platform

English | [中文](README.md)

## Overview

WHartTest is an AI-powered intelligent testing platform built on **Django 5.2 + DRF** and modern LLM technologies. The platform adopts a frontend-backend separated Monorepo architecture, consisting of 6 sub-projects (Django backend, Vue frontend, UI automation executor, MCP tool service, Agent skill library, and online document editor). By aggregating natural language understanding, knowledge base retrieval, and embedding search capabilities, combined with **LangChain/LangGraph** and **MCP (Model Context Protocol)** tool calls, it achieves automated generation, management, and execution of test cases from requirements to executable test cases, providing a complete intelligent testing management solution for QA teams.

## Official website address
https://wharttest.mgdaas.com/

## Core Features

### AI-Powered Test Case Generation
Based on large language model (LLM) technology, WHartTest intelligently transforms requirements into test cases:
- **Multi-source input**: supports requirement documents, conversational interaction, API documentation, and other input methods
- **Structured output**: automatically generates complete test cases including test steps, preconditions, input data, expected results, and priority levels (P0-P3)
- **Multi-model support**: integrates OpenAI, Azure OpenAI, Ollama, Xinference, and other embedding services
- **Failure Self-Healing**: Automatically triggers an AI self-healing task when a test case fails, with the entire process displayed in real time within the chat.

### Knowledge Base Management and Document Understanding
Build project-level knowledge bases to provide accurate context for AI generation:
- **Multi-format support**: PDF, Word, Excel, PPT, Markdown, web links, and more
- **Intelligent chunking**: automatic document parsing, chunking, and vectorized storage
- **Semantic retrieval**: precise knowledge retrieval based on vector similarity
- **Reranker refinement**: supports configurable reranking models to improve retrieval accuracy

### MCP Tool Integration
Seamlessly connect AI with testing tools through Model Context Protocol:
- **Browser automation**: integrates Playwright and supports page operations, element locating, screenshots, and screen recording
- **Multi-protocol support**: supports transport protocols such as streamable-http and SSE
- **HITL human approval**: sensitive operations support a human confirmation mechanism
- **Custom extensions**: supports integration with third-party tools and services

### Requirement Review and Risk Analysis
AI-driven requirement quality assessment helps identify potential risks early:
- **Six-dimension scoring system**: completeness, clarity, consistency, testability, feasibility, and logic
- **Issue tracking**: automatically identifies ambiguities, conflicts, and omissions in requirements
- **Improvement suggestions**: provides targeted requirement optimization and testing strategy recommendations

### Test Case Management
Full-lifecycle test case management capabilities:
- **Multi-level modules**: supports a test case organization structure with up to 5 levels of submodules
- **Case review**: supports status transitions such as pending review, approved, optimized, and unavailable
- **Test suites**: flexibly combine test cases and configure concurrent execution
- **Batch operations**: supports batch creation, editing, moving, and deletion of test cases

### UI Automation Testing
Low-code UI automation lowers the barrier to automation testing:
- **Multiple locator strategies**: CSS, XPath, Text, Role, Label, and other element locating methods
- **Visual orchestration**: drag-and-drop step orchestration with support for conditions, loops, and assertions
- **Environment management**: multi-browser support (Chromium/Firefox/WebKit) and environment configuration switching
- **Execution records**: complete screenshots, videos, Trace tracking, and execution logs
- **Step Recording**: Supports recording user operation steps, eliminating the need to manually write scripts.
- **Login State Management**: Allows capturing the login state via manual login and automatically injecting it in subsequent tests to skip repeated logins.

### Mobile App Automation Testing
Integrated with mobile-mcp to support mobile application automation testing:
- **Multi-platform support**: automation for Android and iOS mobile devices
- **Device management**: device connection status checks and device information retrieval
- **Application operations**: app install, uninstall, launch, and stop
- **Element interactions**: tap, swipe, input, and gesture operations
- **Screen operations**: screenshots, screen recording, brightness and volume adjustment
- **System operations**: notification panel operations, permission management, and network switching

### Skill-Based Intelligent Skill System
An extensible Agent skill management framework:
- **Multiple import sources**: supports ZIP file upload and Git repository import
- **SKILL.md specification**: standardized skill description file
- **Security isolation**: skill files are stored independently to prevent path traversal attacks
- **Exclusive resources**: join the technical community to obtain fine-tuned Skills and MCP toolkits
- **Skill Sandbox**: The Skill execution chain adopts a three-layer defense-in-depth architecture to fully mitigate execution risks from LLM-generated commands.

### Execution Reports and Analysis
Comprehensive analysis of test execution results:
- **Real-time monitoring**: execution progress and status are updated in real time
- **Multi-dimensional statistics**: pass rate, execution duration, and failure cause analysis
- **Historical comparison**: supports historical trend analysis of execution results

## Quick Start

### Docker Deployment (Recommended - out of the box)

```bash
# 1. Clone the repo
git clone https://github.com/MGdaasLab/WHartTest.git
cd WHartTest

# 2. Prepare config (use defaults with auto-generated API Key)
cp .env.example .env

# 3. One-command start (choose one of the two)
# Option A: use the deployment script (recommended, auto-selects registry mirrors)
./run_compose.sh

# Option B: use docker-compose directly
docker-compose up -d

# 4. Open the system
# http://localhost:8913 (admin/admin123456)
```

**That's it!**

### Unified Deployment Script

If you use the built-in deployment script, it now asks you to choose between **remote image pull** and **local image build** at startup:

```bash
./run_compose.sh
```



> ⚠️ **Production note**: Log in to the admin panel, delete the default API Key, and create a new secure key.


## Common Environment Variables

After copying `.env.example` to `.env`, you can adjust file-management settings as needed:

```env
# File management: single-file upload size limit in bytes, default 100MB
FILE_MANAGEMENT_MAX_FILE_SIZE=104857600

# LLM attachments: per-file parsed text character limit; 0 means unlimited. Over-limit files fail with an error and are not truncated.
FILE_MANAGEMENT_LLM_MAX_CHARS_PER_FILE=0
```

## Contact

For questions or suggestions:
- Open an Issue
- Use the project Discussions
- When adding WeChat, please mention `github`!!! We will invite you to the WeChat group.
- Join the group to get the latest updates and Skills.


## When adding WeChat: please mention Github or WHartTest!!!

<img width="400" alt="image" src="img/wx.png" />

---

## IMPORTANT SECURITY NOTICE: Skills Permissions and Deployment Safety (v1.4.0 and later)
Because the Skills module has high system execution privileges, please take the following security precautions:

Deployment recommendation: Only deploy in an intranet or trusted private network.
Access control: Do not expose the service to the public Internet or grant access to unauthenticated or untrusted users.
Disclaimer: This project (WHartTest) is for learning and research purposes only. Users are responsible for all security risks and consequences caused by unsafe deployment (such as public exposure or missing authentication). The WHartTest team is not liable for any security incidents, including data leaks or server compromise, caused by improper configuration.

**WHartTest** - AI-powered test case generation that makes testing smarter and development more efficient!
