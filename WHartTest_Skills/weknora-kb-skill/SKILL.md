---
name: weknora-kb
description: WeKnora知识库查询工具。用于在WeKnora知识管理平台中搜索知识库文档片段。当用户需要检索知识库内容、搜索相关文档时使用。
---

# WeKnora 知识库查询工具

## 快速开始

```bash
# 设置环境变量
export WEKNORA_BASE_URL="http://your-weknora:8080/api/v1"
export WEKNORA_API_KEY="sk-your-api-key"

# 执行操作
python weknora_kb.py --action <action_name> [--参数名 参数值]
```

## 可用操作

| Action | 描述 | 参数 |
|--------|------|------|
| `list_knowledge_bases` | 列出所有可用知识库 | 无 |
| `search_knowledge` | 搜索知识库文档片段 | `--query`, `--knowledge_base_ids`(逗号分隔), `--knowledge_ids`(可选,逗号分隔) |

### 参数说明

- `--query` — 搜索的文本内容
- `--knowledge_base_ids` — 要搜索的知识库ID列表，多个用逗号分隔
- `--knowledge_ids` — 可选，限定搜索的文档ID列表，多个用逗号分隔

## 使用示例

```bash
# 列出所有知识库
python weknora_kb.py --action list_knowledge_bases

# 在指定知识库中搜索
python weknora_kb.py --action search_knowledge \
  --query "用户管理" \
  --knowledge_base_ids "kb-id-1,kb-id-2"
```

## 输出格式

所有操作返回 JSON 格式结果，便于解析处理。

- `list_knowledge_bases` 返回：`[{"id": "...", "name": "...", "description": "..."}]`
- `search_knowledge` 返回：`[{"content": "...", "knowledge_title": "...", "score": 0.95, "chunk_index": 0}]`
