---
name: url-reader
description: 读取和分析任意在线 URL，包括普通网页、文章、产品/帮助文档、Markdown、JSON/YAML、纯文本、PDF 入口、Swagger/OpenAPI/Redoc 接口文档等。用户提供链接并要求获取页面内容、总结网页、提取标题/正文/链接/结构化数据/接口信息、判断访问状态、分析文档内容，或基于 URL 内容生成代码、测试、说明文档时使用。
---

# URL Reader

## 工作流

1. 先确认用户目标：摘要、正文提取、字段/链接提取、接口文档解析、状态排查，还是基于页面内容生成代码或测试。
2. 对公开静态 URL，优先运行 `scripts/read_url.py` 获取状态码、内容类型、标题、正文预览、链接、结构化数据摘要；如果发现 Swagger/OpenAPI/Redoc，会自动解析接口规格。
3. 如果页面需要登录、验证码、浏览器运行 JavaScript，或脚本只能抓到空壳页面，改用浏览器 skill 读取页面状态；必要时让用户先在浏览器中登录。
4. 如果 URL 指向 PDF、图片、音视频或二进制文件，只用脚本判断类型和入口信息；需要读内容时切换到对应文件/PDF/视觉流程。
5. 输出时说明实际读取的 URL、状态码和内容类型。对未能确认的内容标记为“页面未提供”或“无法从静态抓取确认”，不要臆造页面内容。

## 脚本用法

```bash
python scripts/read_url.py "https://example.com/page"
python scripts/read_url.py "https://example.com/swagger-ui/index.html" --api-discovery always
python scripts/read_url.py "https://example.com/openapi.json" --output url-summary.json
```

常用输出字段：

- `document_kind`: `html`、`json`、`yaml`、`text`、`openapi`、`swagger`、`binary` 或 `error`
- `fetched_url`: 实际成功读取的 URL
- `status` / `content_type` / `size_bytes`: 访问状态与内容信息
- `title` / `description` / `headings` / `text_preview` / `links`: HTML 页面提取结果
- `structured_summary`: 普通 JSON/YAML 的顶层结构摘要
- `discovered_specs` / `api` / `endpoints`: OpenAPI/Swagger 规格发现和接口解析结果

## 判断规则

- JSON/YAML 如果包含 `openapi` 或 `swagger` + `paths`，按接口规格解析；否则按普通结构化数据摘要。
- HTML 页面默认提取标题、meta 描述、H1-H3、正文预览和链接。
- 页面里出现 Swagger UI、Redoc、`openapi.json`、`swagger.json`、`api-docs` 等线索时，再尝试发现接口规格。
- Markdown、日志、robots.txt、sitemap 等纯文本内容保留前几千字符作为预览，由 Codex 再按用户目标总结。
- PDF、图片和其他二进制内容不要当成文本解析；只报告类型、大小和后续建议。

## 失败处理

- `401` / `403`: 页面需要鉴权，要求用户提供可访问内容或在浏览器中登录。
- 只抓到前端壳页面: 改用浏览器读取运行后的页面，或从网络请求中找真实数据接口。
- 内容被截断: 用 `--max-bytes` 增大抓取上限，或请求用户明确需要读取的页面范围。
- 发现多个 OpenAPI 规格: 优先选择与用户给定 URL 同域、路径最接近、能成功解析且接口数量最多的规格。
