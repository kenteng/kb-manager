# SCHEMA.md — 知识库维护规范

本文件定义了 `kb-manager` 知识库的目录结构、页面格式、标签体系和操作流程。
每个使用 kb-manager 的项目都应有一份自己的 SCHEMA.md，根据业务需求裁剪。

## 目录结构

```
workspace/
├── kb/                    ← 知识空间
│   ├── SCHEMA.md          ← 本文件
│   ├── index.md           ← 多维索引
│   ├── log.md             ← 操作日志
│   ├── _manifest.jsonl    ← 机器可读清单
│   ├── raw/               ← 原始资料（只读）
│   ├── clients/           ← 客户知识
│   ├── meetings/          ← 会议纪要
│   ├── pitches/           ← 比稿资料
│   ├── products/          ← 产品知识
│   ├── tech/              ← 技术/行业知识
│   ├── insights/          ← 跨案例洞察
│   └── ...
└── rules/                 ← 行为约束规则
```

### 层级边界

| 层级 | 存什么 | 稳定性 |
|------|--------|--------|
| `kb/` | 稳定、可复用、跨 Agent 有价值的知识 | 高 |
| `rules/` | 行为约束（`_` 开头的文件不被索引） | 高 |
| `raw/` | 原始资料，只读 | 只读 |

## 页面格式

每个 Wiki 页面顶部必须包含 YAML frontmatter：

```yaml
---
title: 页面标题
tags:
  - category/item
updated: YYYY-MM-DD
sources: []
related:
  - other-page.md
---
```

**字段说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `title` | ✅ | 页面标题 |
| `tags` | ✅ | 标签数组（见下方标签体系） |
| `updated` | ✅ | 最后更新日期 |
| `sources` | 可选 | 原始来源路径 |
| `related` | 可选 | 相关页面路径（会被 lint 检查连通性） |

## 标签体系

标签用于多维检索和过滤。建议按以下维度定义：

### 客户标签

`client/<客户标识>`，如 `client/acme`、`client/contoso`。

### 产品标签

`product/<产品标识>`，如 `product/cdp`、`product/ma`。

### 阶段标签

| 标签 | 含义 |
|------|------|
| `stage/active` | 进行中 |
| `stage/pitch` | 比稿中 |
| `stage/closed` | 已结束 |
| `stage/won` | 中标 |

### 技术标签

`tech/<技术名称>`，如 `tech/agent`、`tech/llm`、`tech/rag`。

### 行业标签

`domain/<行业>`，如 `domain/retail`、`domain/automotive`、`domain/pharma`。

### 类型标签

| 标签 | 含义 |
|------|------|
| `type/architecture` | 架构设计 |
| `type/meeting` | 会议纪要 |
| `type/pitch` | 比稿方案 |
| `type/methodology` | 方法论 |

## 操作流程

### 新建页面

1. 在对应目录下创建 `.md` 文件
2. 写入 frontmatter（title / tags / updated）
3. 写入正文
4. 运行 `kb update` 更新索引

### URL 自动入库

```bash
kb ingest add-url "https://example.com/article" --tags "tech,AI"
kb ingest list          # 查看暂存区
kb ingest commit --all  # 正式写入 kb/
```

### 健康检查

```bash
kb lint
```

检查项：
- 缺 frontmatter
- 缺 title
- 缺 tags
- 缺 updated
- related 引用的文件不存在

### 手动更新索引

```bash
kb update    # 增量更新（跳过未变更文件）
kb build     # 全量重建
```

## 命名约定

- 文件名使用小写连字符：`acme-corp.md`、`meeting-2026-05-15.md`
- 目录名使用小写：`clients/`、`tech/`
- 标题使用中文

## 演进路线

| 阶段 | 特征 |
|------|------|
| 当前 | frontmatter + 标签 + FTS5 全文检索 + lint 健检 |
| 下一阶段（100+ 文件） | 本地向量检索，支持自然语言语义搜索 |
| 远期 | 知识关联可视化（Graph View） |
