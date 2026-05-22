# kb-manager 技能

> 知识库全文检索 + 自动入库 + 健康检查 + **缺口检测与询问**

## 触发条件

- 用户要求查询知识库内容
- 写入知识后需要更新索引
- 知识库健康检查
- 从 URL 导入文章到知识库
- **主动检测知识库缺口**（心跳/事件/手动触发）

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

从 URL 导入文章：

```bash
KB_ROOT=<workspace> kb ingest add-url "https://..." --tags "tech,AI"
KB_ROOT=<workspace> kb ingest list
KB_ROOT=<workspace> kb ingest commit --all
```

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

### 缺口检测与询问

**扫描缺口**：
```bash
KB_ROOT=<workspace> kb gap                          # 扫描所有缺口
KB_ROOT=<workspace> kb gap --stale-days 14          # 自定义过期阈值（天）
KB_ROOT=<workspace> kb gap --output gaps.json       # 保存为 JSON
KB_ROOT=<workspace> kb gap --context mentioned.txt  # 从文件读取对话中提到的页面
```

**缺口类型**：
- `empty` — 有页面但正文为空或极少（<50 字）
- `missing_field` — 缺少关键字段（根据页面类型定义）
- `stale` — 超过 N 天未更新
- `no_page` — 对话中提到但 kb 中无对应页面

**询问策略**（Agent 端实现）：
1. 心跳时自动执行 `kb gap --output gaps.json`
2. 按 `_score`（类型权重 × 紧急度）排序
3. 攒满 3-5 个高价值缺口后，批量向用户发起询问
4. 使用结构化模板提问，降低用户回答成本：
   ```
   📋 知识库缺口报告
   
   📭 空页面（2 项）
   • 客户 A
     → 正文仅 12 字，需要补充内容
     💬 建议问：「能否补充客户 A 的详细信息？」
   
   🔍 缺少关键字段（1 项）
   • 项目 B
     → 缺少关键字段：决策链、竞品
     💬 建议问：「项目 B 的决策链、竞品是什么？」
   ```
5. 用户回复后自动写入对应 KB 页面并执行 `kb update`

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
