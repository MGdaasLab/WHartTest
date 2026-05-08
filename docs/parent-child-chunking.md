# Parent-Child 双层切分检索功能

## 1. 功能概述

知识库 RAG 系统新增 Parent-Child 双层分块能力。文档入库时切分为两层：小块（Child）用于向量化精确召回，大块（Parent）用于返回给 LLM 作上下文。多个 Child 命中同一 Parent 时自动去重合并，减少语义断裂，提升长文档的回答质量。

## 2. 背景与动机

### 2.1 原有问题

原有系统使用单层 flat 分块结构：

- `chunk_size` 默认 1000 字符，切分粒度固定
- 检索命中的是小 chunk，返回给 LLM 的也是同一个 chunk
- 短 chunk 通过 `_expand_context`（±3 邻居拼接，350-850 字符）补偿上下文
- 对于需求文档、测试规范、流程说明等长文档，容易出现：
  - 语义断裂：上下文被硬切分截断，LLM 缺少完整背景
  - 召回碎片化：同一个主题被切成多个小块，检索结果冗余但都不完整

### 2.2 设计目标

| 目标 | 说明 |
|------|------|
| 召回与上下文解耦 | 小 chunk 精确匹配查询，大 chunk 提供完整语境 |
| 减少语义断裂 | Parent chunk 保留段落/章节级别的完整信息 |
| 去重合并 | 同一 Parent 下多个 Child 命中时合并为一条结果 |
| 向后兼容 | 旧文档不强制重处理，新旧数据可共存 |
| 可配置 | 全局开关 + Parent/Child 尺寸可调 |

## 3. 功能说明

### 3.1 核心机制

```
文档原文
  │
  ▼ 按 parent_chunk_size 切分（默认 2000 字符）
Parent Chunks（存 PostgreSQL，不向量化）
  │
  ▼ 每个 Parent 按 child_chunk_size 切分（默认 800 字符）
Child Chunks（向量化后存 Qdrant，payload 含 parent_chunk_id）
```

检索流程：

```
用户查询
  │
  ▼ Embedding → Qdrant 检索
Child Chunks（命中的小块）
  │
  ▼ 按 parent_chunk_id 分组，替换为 Parent 内容
Parent Chunks（返回给 LLM 的上下文）
```

### 3.2 分数合并策略

当同一 Parent 下有多个 Child 被命中时：

```
final_score = min(max(child_scores) + 0.15 * (命中数 - 1), 1.0)
```

- 取最高子分数为基础分
- 每多命中一个 Child 加 0.15 分（上限 0.3）
- 总分不超过 1.0
- 含义：多点命中说明该段落与查询更相关，给予适当加分

### 3.3 向后兼容

| 场景 | 行为 |
|------|------|
| 功能关闭 | 完全走原有逻辑，无任何影响 |
| 功能开启，旧文档（无 parent_chunk_id） | 检索时自动走原有 `_expand_context` 邻居扩展 |
| 功能开启，新文档 | 走 Parent-Child 流程 |
| 重新处理旧文档 | 旧 chunks 被清除，新 chunks 使用 Parent-Child 结构 |

## 4. 配置项

### 4.1 全局配置（知识库全局配置弹窗）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `parent_child_enabled` | 开关 | 关闭 | 是否启用 Parent-Child 模式 |
| `parent_chunk_size` | 数字 | 2000 | Parent 块最大字符数，建议 2000-4000 |
| `parent_chunk_overlap` | 数字 | 200 | Parent 块间重叠字符数 |
| `child_chunk_size` | 数字 | 800 | Child 块最大字符数，建议与 embedding 模型最优输入对齐 |
| `child_chunk_overlap` | 数字 | 200 | Child 块间重叠字符数 |

### 4.2 知识库级别覆盖

每个知识库可单独覆盖 `parent_chunk_size`、`parent_chunk_overlap`、`child_chunk_size`、`child_chunk_overlap`。留空时使用全局配置。

### 4.3 配置生效规则

- 配置变更后，仅对新上传或重新处理的文档生效
- 已入库的文档不会自动重新切分，需手动触发"重新处理"

## 5. 数据模型变更

### 5.1 DocumentChunk 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `parent_chunk` | ForeignKey(self) | 指向父块的引用，null 表示独立块或自身为父块 |
| `chunk_level` | CharField | `parent` 或 `child`，默认 `child` |

约束变更：`unique_together` 从 `["document", "chunk_index"]` 改为 `["document", "chunk_index", "chunk_level"]`，允许 Parent 和 Child 各自独立编号。

### 5.2 KnowledgeGlobalConfig 新增字段

| 字段 | 类型 | 默认值 |
|------|------|--------|
| `parent_child_enabled` | BooleanField | False |
| `parent_chunk_size` | PositiveIntegerField | 2000 |
| `parent_chunk_overlap` | PositiveIntegerField | 200 |
| `child_chunk_size` | PositiveIntegerField | 800 |
| `child_chunk_overlap` | PositiveIntegerField | 200 |

### 5.3 KnowledgeBase 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `parent_chunk_size` | PositiveIntegerField(null) | 覆盖全局值，null 使用全局默认 |
| `parent_chunk_overlap` | PositiveIntegerField(null) | 同上 |
| `child_chunk_size` | PositiveIntegerField(null) | 同上 |
| `child_chunk_overlap` | PositiveIntegerField(null) | 同上 |

## 6. 存储结构

### 6.1 PostgreSQL

Parent 块：

| 字段 | 值 |
|------|-----|
| `chunk_level` | `parent` |
| `vector_id` | null（不向量化） |
| `embedding_hash` | null |
| `parent_chunk` | null |
| `content` | Parent 级别完整文本（2000-4000 字符） |

Child 块：

| 字段 | 值 |
|------|-----|
| `chunk_level` | `child` |
| `vector_id` | UUID（Qdrant 点 ID） |
| `embedding_hash` | MD5(content) |
| `parent_chunk` | 指向对应 Parent 的 UUID |
| `content` | Child 级别文本（300-800 字符） |

### 6.2 Qdrant

仅 Child 块被索引到 Qdrant。Payload 中新增字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `parent_chunk_id` | string(UUID) | 对应 PostgreSQL 中 Parent 块的 ID |

## 7. 接口变更

### 7.1 查询响应

查询结果的 `sources` 中，每条结果的 `metadata` 新增：

| 字段 | 类型 | 说明 |
|------|------|------|
| `parent_chunk_id` | string | Parent 块 ID（仅 Parent-Child 模式） |
| `child_count` | number | 被合并的 Child 命中数（仅去重后 >1 时存在） |
| `child_chunk_ids` | string[] | 被合并的 Child vector_id 列表 |

### 7.2 分块列表接口

`GET /knowledge/chunks/` 返回的分块对象新增：

| 字段 | 类型 | 说明 |
|------|------|------|
| `parent_chunk` | string(UUID) | 父块 ID |
| `chunk_level` | string | `parent` 或 `child` |

### 7.3 全局配置接口

`GET/PUT /knowledge/global-config/` 新增 5 个字段：`parent_child_enabled`、`parent_chunk_size`、`parent_chunk_overlap`、`child_chunk_size`、`child_chunk_overlap`。

### 7.4 知识库接口

`POST/PUT /knowledge/knowledge-bases/` 新增 4 个可选字段：`parent_chunk_size`、`parent_chunk_overlap`、`child_chunk_size`、`child_chunk_overlap`。

## 8. 使用方式

### 8.1 启用功能

1. 进入「知识库全局配置」
2. 找到「Parent-Child 双层切分」区域
3. 开启开关
4. 按需调整 Parent/Child 块大小（默认值即可用）
5. 保存配置

### 8.2 应用到文档

- **新文档**：上传后自动使用 Parent-Child 切分
- **已有文档**：在文档详情页点击「重新处理」

### 8.3 验证效果

- 查询后返回的 `sources` 中 `content` 字段应为 Parent 级别文本（比原来的 Child 更长）
- 若 `metadata.child_count > 1`，说明多个子段落被合并
- 文档分块列表中可看到 `chunk_level` 为 `parent` 或 `child` 的记录

## 9. 与现有切分策略的配合

Parent-Child 模式与现有切分策略（`recursive_character`、`heading_aware`、`markdown_header`）兼容：

| 策略 | Parent 层切分行为 |
|------|-------------------|
| `recursive_character` | 使用默认分隔符按 parent_chunk_size 递归切分 |
| `heading_aware` | 优先按标题、段落边界切分 Parent |
| `markdown_header` | 先按 Markdown 标题拆分，再递归切分为 Parent |

Child 层统一使用默认递归切分（因为 Parent 已经捕获了结构边界）。

## 10. 注意事项

1. **存储开销**：Parent 块仅存 PostgreSQL 不向量化，存储增量约为原文档的 1-2 倍（Parent + Child 文本），但不增加向量存储
2. **向量化开销**：仅 Child 块需要计算 embedding，相比单层模式的总向量化量基本持平
3. **重处理必要性**：切换配置后必须对已有文档执行「重新处理」，否则 Qdrant 中仍是旧的单层分块
4. **混合状态**：功能开启后，未重处理的旧文档查询时自动走原有的邻居扩展逻辑，不会报错
