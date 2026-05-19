# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.1.0] - 2026-05-19

### Added
- `kb init` 支持交互式模板选择（通用/客户项目/最小）
- FTS5 全文搜索引擎，支持中英文混合搜索
- `kb search` 支持多词 OR 召回 + BM25 排序，可按 type 过滤
- `kb ingest` 自动入库流程：URL 抓取 → 正文提取 → 元数据生成 → 待审 → 提交
- `kb lint` 健康检查：frontmatter 完整性、标签缺失、交叉引用断裂检测
- `kb manifest` 生成机器可读的 JSONL 清单
- `kb build` / `kb update` 构建/增量更新索引
- 三层知识架构：shared kb / kb-private / rules
- YAML frontmatter + 多维标签体系
- 完整的测试套件（26 tests）
- 零外部依赖，仅用 Python 标准库
