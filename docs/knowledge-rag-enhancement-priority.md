# Knowledge RAG Enhancement Priority Plan

## 1. 背景

当前项目的知识库已经具备基础 RAG 能力，包括：

- 文档解析与入库
- Embedding 向量化
- Qdrant 存储
- BM25 + Dense 混合检索
- RRF 融合
- 可选 Reranker 精排
- Query Rewrite
- 邻近 chunk 上下文扩展

但如果要更适合测试平台场景，比如按项目、模块、版本、文档阶段精确召回，或者减少硬切分带来的上下文断裂，还需要继续补强。

## 2. 当前优先级

```text
P0: 检索级元数据过滤
P1: Parent-Child 检索
P2: 切分策略增强
P3: 查询增强策略配置化
```

当前建议顺序仍然是：

```text
先完成 P0/P2 的收口
再推进 P1
最后做 P3
```

## 3. 当前实现状态

### 3.1 已完成：P0 元数据过滤主链

已落地能力：

- `Document` 已支持：
  - `tags`
  - `metadata`
  - `module`
  - `version`
  - `business_domain`
  - `document_stage`
- `QueryLog` 已记录本次查询使用的 `metadata_filter`
- 文档入库 Qdrant 时，chunk payload 会继承文档元数据
- 查询 API 已支持：
  - `document_ids`
  - `document_type`
  - `tags`
  - `module`
  - `version`
  - `business_domain`
  - `document_stage`
  - `metadata_filter`
- Dense 检索和 Hybrid 检索都已经支持 Qdrant `query_filter`
- 前端已支持：
  - 上传文档时录入元数据
  - 查询面板传入过滤条件
  - 文档详情展示元数据
  - 批量重处理知识库文档

当前结论：

**P0 已经不是方案阶段，而是已落地并可用。**

### 3.2 已完成：P2 第一阶段

已落地能力：

- `KnowledgeGlobalConfig` 已新增 `chunk_strategy`
- 前端“知识库全局配置”已支持切分策略选择
- 当前支持三种策略：
  - `recursive_character`
  - `heading_aware`
  - `markdown_header`
- 后端索引时会按 `chunk_strategy` 选择切分逻辑

当前策略说明：

- `recursive_character`
  - 仍是固定 `chunk_size/chunk_overlap` 的字符级切分
- `heading_aware`
  - 优先按标题、段落、换行和中英文句号等分隔符切分
- `markdown_header`
  - 对 Markdown 文档按标题层级先切，再递归细分

当前结论：

**P2 已完成第一阶段，但还不是完整版本。**

### 3.3 未完成：P1 Parent-Child 检索

目前还没有真正的双层 chunk 结构。

现状仍然是：

- 检索命中的是普通 chunk
- 返回上下文依赖相邻 chunk 扩展
- 没有：
  - `parent_chunk_id`
  - `chunk_level`
  - parent chunk 回查逻辑

### 3.4 未完成：P3 查询增强配置化

虽然系统内部已经有：

- Query Rewrite
- MMR
- Reranker

但这些还不是一套完整的“策略配置体系”。目前还缺：

- 前端或全局配置层的显式开关
- 多路查询配置
- HyDE
- reranker top_n / MMR 参数等产品化配置

## 4. 当前推荐下一步

### 第一优先级：推进 P1 Parent-Child 检索

这是下一阶段最值得做的部分。

目标：

- 小 chunk 用于召回
- 大 chunk 用于返回上下文
- 命中 child 后回查 parent

推荐结构：

```text
DocumentChunk
  - parent_chunk_id
  - chunk_level
```

或者：

```text
Document
  ParentDocumentChunk
    DocumentChunk
```

推荐策略：

- Parent chunk：2000-4000 字
- Child chunk：300-800 字
- Qdrant 主索引 child chunk
- payload 中保存 `parent_chunk_id`
- 最终给 LLM 的上下文来自 parent chunk

价值：

- 减少小切块导致的语义断裂
- 比单纯继续调 `chunk_size` 更有效
- 对需求文档、测试规范、流程说明这类长文档收益明显

### 第二优先级：补齐 P2 第二阶段

当前切分策略已经接通，但还有收尾项。

建议补齐：

- 文档详情页展示 chunk 的结构信息
- 对 `markdown_header` 命中的 chunk 展示标题路径
- 对 `heading_aware` 增加更明确的结构来源元数据
- 增加切分策略切换后的重处理提示和状态反馈

### 第三优先级：再考虑 P3

P3 仍然不建议抢在 P1 前面做。

## 5. 最新实施顺序建议

```text
阶段 A：已完成
1. Document 增加 metadata/tags
2. 上传与查询 UI 支持元数据
3. Qdrant payload 写入元数据
4. Dense/Hybrid 检索支持 metadata_filter
5. QueryLog 记录过滤条件

阶段 B：已完成第一阶段
6. 全局配置增加 chunk_strategy
7. 后端接通 recursive_character / heading_aware / markdown_header
8. 前端全局配置弹窗支持切分策略

阶段 C：建议下一步
9. Parent-Child 数据结构
10. Parent-Child 入库逻辑
11. Parent-Child 检索返回逻辑
12. 同 parent 多 child 命中的去重逻辑

阶段 D：后续增强
13. 结构路径展示
14. 查询增强策略配置化
15. 多路查询 / HyDE / reranker 参数配置
```

## 6. 验收口径

### P0 验收

- 查询能按模块、版本、标签、业务域、阶段过滤
- Dense/Hybrid 检索结果一致遵守过滤条件
- QueryLog 可追踪本次过滤条件

### P2 第一阶段验收

- 全局配置里可切换 `chunk_strategy`
- 新上传或重处理文档时按选定策略切分
- Markdown 文档可按标题层级切分

### P1 未来验收

- 入库生成 parent/child 双层 chunk
- Qdrant payload 含 `parent_chunk_id`
- 命中 child 时返回 parent 作为最终上下文
- 同 parent 下多 child 命中时能去重

## 7. 当前注意事项

- 当前默认配置值仍可能是 `recursive_character`
- 即使代码已支持新策略，也需要在全局配置里手动切换
- 切分策略切换后，历史文档必须重处理，否则 Qdrant 中仍是旧切法
- 目前 `KnowledgeBase` 级别还没有独立的 `chunk_strategy` 覆盖能力，当前以全局配置为主

## 8. 结论

当前方案应更新为：

- **P0：已完成**
- **P2：已完成第一阶段**
- **下一步主目标：P1 Parent-Child 检索**
- **P3：继续后置**

也就是说，当前不该再把重点放在“是否支持切分策略”上，而应该转向：

**如何把召回粒度和返回上下文解耦，也就是 Parent-Child 检索。**
