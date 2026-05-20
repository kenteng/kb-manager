---
name: kb-manager
description: Use when an OpenClaw agent needs to search a local Markdown knowledge base, update the SQLite FTS5 index after writing knowledge, ingest URL/file/stdin content into kb/raw for review, run knowledge-base lint checks, or generate a machine-readable manifest. This skill uses the host OpenClaw model for reasoning and only calls the local kb CLI for storage, indexing, and retrieval.
---

# kb-manager 技能

> 知识库全文检索 + 资料入库 + 健康检查

## 触发条件

- 用户要求查询知识库内容
- 写入知识后需要更新索引
- 知识库健康检查
- 从 URL 导入文章到知识库

## 能力边界

本 skill 不直接调用大模型，也不要求配置模型 API key。用户意图理解、关键词提取、摘要判断、标签选择等推理能力由 OpenClaw 当前 Agent 使用其已配置的模型完成。

`kb` CLI 只负责本地操作：
- SQLite FTS5 索引和搜索
- Markdown/frontmatter 解析
- URL/文件/stdin 内容暂存和提交
- lint 与 manifest 生成

## 前置条件

知识库管理工具已安装：
```bash
pip install git+https://github.com/kenteng/kb-manager.git
```

或在 workspace 中直接使用源码：
```
workspace/
└── kb-manager/          # 克隆的 kb-manager 仓库
    └── src/kb_manager/
```

## 环境变量

```bash
export KB_ROOT=/path/to/workspace
```

或在每次命令中指定 `--root` 参数。

## 核心命令

### 查询知识库

```bash
KB_ROOT=<workspace> kb search "关键词"
KB_ROOT=<workspace> kb search "CDP" --type kb --limit 5
KB_ROOT=<workspace> kb search "架构" --json
```

**搜索结果处理规则**：
- 结果按 type 分组：rule（行为约束）/ kb（知识）
- rule 类型结果作为行为约束遵守
- kb 类型结果作为背景知识参考

### 更新索引

每次写入 `kb/` 文件后，**同一轮**必须执行：

```bash
KB_ROOT=<workspace> kb update
```

### 初始化知识库

在新 workspace 中初始化：

```bash
KB_ROOT=<workspace> kb init
```

### 自动入库

从 URL 抓取正文并放入待审区：

```bash
KB_ROOT=<workspace> kb ingest add-url "https://..." --tags "tech,AI"
KB_ROOT=<workspace> kb ingest list
KB_ROOT=<workspace> kb ingest commit --all
```

需要摘要、提炼或标签判断时，由 OpenClaw Agent 在调用 CLI 前后完成；CLI 不调用模型。

### 健康检查

```bash
KB_ROOT=<workspace> kb lint
```

### 查看状态

```bash
KB_ROOT=<workspace> kb status
```

### 生成 Manifest

```bash
KB_ROOT=<workspace> kb manifest
```

## 知识库目录结构

```
workspace/
├── kb/                    # 知识
│   ├── clients/           # 客户知识
│   ├── meetings/          # 会议纪要
│   ├── pitches/           # 比稿资料
│   ├── tech/              # 技术知识
│   ├── insights/          # 洞察
│   └── ...
└── rules/                 # 规则（_ 开头文件不被索引）
```

## 页面格式

每个知识页面必须包含 frontmatter：

```yaml
---
title: 页面标题
tags:
  - client/acme
  - stage/active
updated: 2026-05-18
---

正文内容...
```

## 注意事项

- `kb search` 后在回复中附上搜索结果摘要，证明已查阅
- rule 类型结果作为行为约束，必须遵守
- raw/ 目录是只读层，不直接修改
- 写入 `kb/` 后同一轮运行 `kb update`
