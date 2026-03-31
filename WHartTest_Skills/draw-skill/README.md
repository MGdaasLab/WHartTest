# Draw.io Skill for Claude Code

A Claude Code skill that generates native `.drawio` files, with optional export to PNG, SVG, or PDF (with embedded XML so the exported file remains editable in draw.io). No MCP setup required.

## How It Works

When you ask Claude Code to create a diagram, it will:

1. Generate draw.io XML for your requested diagram
2. Write it to a `.drawio` file in your current directory
3. If you requested an export format, export using the draw.io desktop CLI
4. Open the result

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- [draw.io Desktop](https://github.com/jgraph/drawio-desktop/releases) installed (required for PNG/SVG/PDF export)

## Installation

Copy `drawio/SKILL.md` to your Claude Code skills directory:

**Global (all projects):**

```bash
mkdir -p ~/.claude/skills/drawio
cp drawio/SKILL.md ~/.claude/skills/drawio/SKILL.md
```

**Per-project:**

```bash
mkdir -p .claude/skills/drawio
cp drawio/SKILL.md .claude/skills/drawio/SKILL.md
```

## Usage

```
/drawio create a flowchart for user login
```

By default, this writes a `.drawio` file and opens it in draw.io. To export to an image format, mention the format in your request:

```
/drawio png flowchart for user login       → login-flow.drawio.png
/drawio svg: ER diagram for e-commerce     → er-diagram.drawio.svg
/drawio pdf architecture overview          → architecture-overview.drawio.pdf
```

More examples:

```
/drawio sequence diagram for API auth
/drawio png class diagram for the models in src/
```

## Export Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| (default) | `.drawio` | Native XML, editable in draw.io, no desktop CLI needed |
| `png` | `.drawio.png` | Viewable everywhere, embedded XML, editable in draw.io |
| `svg` | `.drawio.svg` | Scalable, embedded XML, editable in draw.io |
| `pdf` | `.drawio.pdf` | Printable, embedded XML, editable in draw.io |

The `.drawio.*` double extension signals that the file contains embedded diagram XML. Open any of these in draw.io to recover and edit the full diagram. The intermediate `.drawio` source file is deleted after export since the exported file contains the complete diagram.

## Why XML Only?

A `.drawio` file is just mxGraphModel XML. Mermaid and CSV formats require draw.io's server-side conversion — they can't be saved as native files. Claude generates XML directly for all diagram types, which means:

- No server dependency
- No conversion step
- Files are immediately editable in draw.io

## Other Variants

This repository offers multiple ways to integrate draw.io with AI assistants:

- **[MCP App Server](../mcp-app-server/README.md)** — Inline diagrams in chat (Claude.ai, VS Code)
- **[MCP Tool Server](../mcp-tool-server/README.md)** — Opens diagrams in browser via MCP (Claude Desktop)
- **[Project Instructions](../project-instructions/README.md)** — Claude.ai Projects, no install needed
