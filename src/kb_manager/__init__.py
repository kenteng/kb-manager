"""
kb-manager — 知识库管理框架

基于 SQLite FTS5 的知识库全文检索、自动入库、健康检查工具。

用法:
    kb init [path]          初始化知识库目录结构
    kb build [--root DIR]   构建/重建全文索引
    kb update [--root DIR]  增量更新索引
    kb search "关键词"      全文搜索
    kb status [--root DIR]  查看索引状态
    kb lint [--root DIR]    知识库健康检查
    kb ingest ...           多格式自动入库
    kb manifest [--root DIR] 生成机器可读清单
"""

__version__ = "0.1.0"
