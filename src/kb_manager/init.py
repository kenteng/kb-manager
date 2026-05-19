"""
init.py — 知识库目录结构初始化

支持多种目录模板，用户可交互式选择或通过命令行指定。
"""

from pathlib import Path

# 目录模板定义
TEMPLATES = {
    "1": {
        "name": "通用",
        "desc": "适用于个人/团队通用知识管理",
        "dirs": [
            "kb/articles",
            "kb/notes",
            "kb/tags",
            "kb/raw",
            "rules",
            "state",
        ],
    },
    "2": {
        "name": "客户/项目",
        "desc": "适用于 B2B 客户管理和项目交付",
        "dirs": [
            "kb/clients",
            "kb/meetings",
            "kb/pitches",
            "kb/products",
            "kb/tech",
            "kb/insights",
            "kb/raw",
            "rules",
            "state",
        ],
    },
    "3": {
        "name": "最小",
        "desc": "只创建核心目录，其余按需自建",
        "dirs": [
            "kb/articles",
            "kb/raw",
            "rules",
            "state",
        ],
    },
}


def print_templates():
    """打印可选模板列表"""
    print("\n可选目录模板：\n")
    for key, tpl in TEMPLATES.items():
        print(f"  [{key}] {tpl['name']}")
        print(f"      {tpl['desc']}")
        print(f"      目录: {', '.join(d.split('/')[1] for d in tpl['dirs'] if d.startswith('kb/'))}")
        print()


def choose_template() -> str:
    """交互式选择模板"""
    print_templates()
    while True:
        choice = input("请选择模板 [1/2/3，默认 2]: ").strip() or "2"
        if choice in TEMPLATES:
            return choice
        print(f"  无效选择，请输入 1/2/3")


def init_knowledge_base(target: Path, template_key: str = None) -> Path:
    """在 target 目录下初始化知识库目录结构。

    Args:
        target: 目标目录路径
        template_key: 模板编号（1=通用, 2=客户/项目, 3=最小），None 时交互式选择
    """
    target.mkdir(parents=True, exist_ok=True)

    if template_key is None:
        template_key = choose_template()

    tpl = TEMPLATES[template_key]
    dirs = tpl["dirs"]

    created = []
    for d in dirs:
        full = target / d
        full.mkdir(parents=True, exist_ok=True)
        created.append(d)

    # 写入 .gitignore
    gitignore = target / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("# 运行态文件\nstate/\n__pycache__/\n*.db\n", encoding="utf-8")

    # 写入 SCHEMA.md 模板
    schema_path = target / "kb" / "SCHEMA.md"
    if not schema_path.exists():
        schema_path.write_text(_SCHEMA_TEMPLATE, encoding="utf-8")

    # 写入 index.md 模板
    index_path = target / "kb" / "index.md"
    if not index_path.exists():
        index_path.write_text(_INDEX_TEMPLATE, encoding="utf-8")

    # 写入 log.md
    log_path = target / "kb" / "log.md"
    if not log_path.exists():
        log_path.write_text("# kb 操作日志\n\n", encoding="utf-8")

    print(f"\n知识库初始化完成：{target}")
    print(f"模板：{tpl['name']}（{tpl['desc']}）")
    print(f"创建目录：{len(created)} 个")
    for d in created:
        print(f"  {d}/")
    print()
    print("下一步：")
    print("  kb build   构建全文索引")
    print("  kb search '关键词'  测试搜索")
    print("  kb lint    健康检查")
    return target


_SCHEMA_TEMPLATE = """# SCHEMA.md — 知识库维护规范

本文件是知识库的操作手册，定义目录结构、页面格式和标签体系。

## 目录结构

```
kb/
├── SCHEMA.md          ← 本文件
├── index.md           ← 多维索引
├── log.md             ← 操作日志（append-only）
├── _manifest.jsonl    ← 机器可读清单
├── raw/               ← 原始资料（只读）
├── articles/          ← 知识文章（或自定义目录）
└── ...
```

## 页面格式

每个 Wiki 页面顶部必须包含 YAML frontmatter：

```yaml
---
title: 页面标题
tags:
  - category/item
updated: YYYY-MM-DD
sources: []
related: []
---
```

## 标签体系

请根据自身业务自定义标签。建议维度：
- 客户标签：`client/XXX`
- 产品标签：`product/XXX`
- 阶段标签：`stage/active`、`stage/pitch`、`stage/closed`
- 技术标签：`tech/XXX`
- 行业标签：`domain/XXX`
- 类型标签：`type/architecture`、`type/meeting`、`type/pitch`
"""

_INDEX_TEMPLATE = """# kb 知识库目录

> 人工导航 / 兜底定位。agent 查询默认走 FTS5 索引（`kb search`），本文件仅在 FTS5 无结果时作为 fallback。

## 索引一：按分类

| 分类 | 核心页面 | 说明 |
|------|----------|------|
| （暂无） | — | — |

## 索引二：按标签

| 标签 | 相关文件 |
|------|----------|
| （暂无） | — |
"""
