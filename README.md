# kb-manager

**OpenClaw 知识库管理 Skill** — 为 AI Agent 提供开箱即用的知识检索、资料入库和健康检查能力。

> 基于 SQLite FTS5 全文搜索引擎，零外部依赖，轻量、快速、可嵌入。

## 为什么需要

AI Agent 需要可靠的知识管理基础设施：
- **检索**：Agent 能快速搜到相关知识，而不是依赖上下文窗口硬塞
- **入库**：从 URL/文件抓取正文、暂存待审、确认写入知识库
- **规范**：强制 frontmatter、标签体系、健康检查，防止知识库腐烂
- **透明**：Agent 搜索后附上查询条件和结果，让回答可追溯

kb-manager 就是为此而生。

## 快速安装

### 1. 安装 CLI

```bash
git clone https://github.com/kenteng/kb-manager.git
cd kb-manager
pip install .
```

或直接从 GitHub 安装：

```bash
pip install git+https://github.com/kenteng/kb-manager.git
```

### 2. 安装到 OpenClaw

```bash
cp -r skills/kb-manager ~/.openclaw/skills/
```

### 3. 配置知识库根目录

```bash
export KB_ROOT=/path/to/workspace
kb init
kb build
```

> `kb-manager` 本身不调用大模型，不需要配置 `OPENAI_API_KEY`、模型名或 base URL。关键词提取、摘要判断、标签选择等推理能力由 OpenClaw 当前 Agent 使用其已配置的模型完成；本项目只提供本地 CLI 和 skill 调用规程。

## Agent 使用方式

### 搜索知识

Agent 收到用户问题后，自动搜索知识库：

```bash
KB_ROOT=/workspace kb search "关键词" --limit 5
```

**透明度要求**：Agent 在回复中必须附上查询条件和搜索结果，让回答可追溯。

### 写入知识

创建/编辑知识页面后，同一轮自动更新索引：

```bash
KB_ROOT=/workspace kb update
```

### 自动入库

从 URL 抓取正文并放入待审区：

```bash
KB_ROOT=/workspace kb ingest add-url "https://example.com/article" --tags "tech,AI"
KB_ROOT=/workspace kb ingest list
KB_ROOT=/workspace kb ingest commit --all
```

流程：URL 抓取 → 正文抽取 → 待审队列 → 确认写入。需要摘要、提炼或标签判断时，由 OpenClaw Agent 在调用 CLI 前后完成。

### 健康检查

定期检查知识库质量：

```bash
KB_ROOT=/workspace kb lint
```

检查项：frontmatter 完整性、标签缺失、交叉引用断裂

### 初始化知识库

为新 workspace 创建标准知识库结构：

```bash
KB_ROOT=/workspace kb init
```

支持三种模板：
- **通用**：articles / notes / tags / raw
- **客户/项目**：clients / meetings / pitches / products / tech / insights（默认）
- **最小**：articles / raw（按需自建）

## 架构设计

### 知识空间

```
┌─────────────────────────────────────────────────┐
│  kb/                                            │
│  稳定、可复用、跨 Agent 共享的知识                   │
│  维度：clients / meetings / pitches / tech / ...  │
├─────────────────────────────────────────────────┤
│  rules/                                         │
│  行为约束和规则（_ 开头的文件不被索引）              │
└─────────────────────────────────────────────────┘
```

### 检索流程

```
用户问题 → Agent 提取关键词 → kb search
    │
    ├── FTS5 全文索引（主路径）
    │   └── SQLite FTS5 + unicode61 tokenizer
    │   └── 英文分词 / 中文连续词匹配 + 多词 OR 召回 + BM25 排序
    │   └── 按 type 过滤（kb / rule）
    │
    └── 返回结果 → Agent 附在回复中 → 用户可见
```

### 知识页面格式

```markdown
---
title: 页面标题
tags:
  - client/acme
  - tech/AI
updated: 2026-05-19
---

正文内容...
```

每个知识页面必须包含 YAML frontmatter（title / tags / updated），确保可检索、可归类、可追溯。

> 当前检索使用 SQLite FTS5 `unicode61` tokenizer。它适合英文分词和中文完整短语匹配，但不提供中文语义分词；例如完整短语可能命中，单独拆出的中文词不一定命中。后续可以扩展 ngram 或中文分词索引。

## CLI 命令速查

| 命令 | 说明 |
|------|------|
| `kb init [path]` | 初始化知识库 |
| `kb build` | 构建/重建全文索引 |
| `kb update` | 增量更新索引 |
| `kb search "关键词"` | 全文搜索 |
| `kb status` | 查看索引状态 |
| `kb lint` | 健康检查 |
| `kb manifest` | 生成机器可读清单 |
| `kb ingest add-url <url>` | 从 URL 导入 |
| `kb ingest add-file <path>` | 从本地文件导入 |
| `kb ingest list` | 列出待入库内容 |
| `kb ingest commit <id>` | 确认写入 |

所有命令支持 `--root /path/to/workspace` 参数，或设置 `KB_ROOT` 环境变量。

## 与 OpenClaw 集成

在 workspace 的 `AGENTS.md` 中添加：

```markdown
## 前置搜索（强制）
收到直聊消息或群聊被@时，回复前先执行一次 FTS5 搜索：
kb search "关键词" --limit 5
- 搜索词：从用户消息中提取 2-3 个核心词
- 结果展示：在回复末尾附上 KB 查询结果摘要，证明已查阅
```

写入知识后同一轮执行：
```bash
kb update
```

## 模型能力边界

`kb-manager` 是工具型 skill，不直接访问任何大模型服务：

- CLI 只做本地文件、SQLite FTS5、URL 抓取和 Markdown/frontmatter 处理
- OpenClaw Agent 负责理解用户意图、选择搜索词、判断是否需要入库、生成摘要或整理标签
- 用户只需要配置 OpenClaw 自身的模型能力；本仓库没有额外模型环境变量
- 本仓库不会因为执行 `kb search`、`kb update`、`kb lint` 产生模型 API 费用

## 技术特点

- **零外部依赖**：仅用 Python 标准库（sqlite3 / pathlib / json）
- **轻量**：SQLite 单文件数据库，无额外服务
- **快速**：FTS5 全文索引，毫秒级搜索
- **可嵌入**：无数据库/Redis/ES 等外部组件，即装即用
- **Python 3.9+**

## 开发

```bash
git clone https://github.com/kenteng/kb-manager.git
cd kb-manager

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
python3 -m pytest tests/

# 无 pytest 环境下可先跑核心 unittest 回归
python3 -m unittest tests.test_index_regressions

# 本地测试 CLI
python3 -c "from src.kb_manager.cli import main; import sys; sys.argv=['kb','init','/tmp/test']; main()"
```

## 开源协作

- 提交代码前运行测试和 `kb lint` 相关场景的手工验证
- 行为变更优先补测试，尤其是索引、搜索、入库、frontmatter 解析
- 默认保持零运行时外部依赖；如果引入依赖，需要说明收益和失败模式

## License

MIT
