"""
cli.py — 统一 CLI 入口
支持 --root 在任意位置（子命令前或后）
"""

import argparse
import sys
import json

from .workspace import resolve_kb_root
from .index import build_index, search, status
from .lint import run_lint
from .manifest import generate_manifest
from .init import init_knowledge_base
from .ingest import (
    cmd_add_url, cmd_add_file, cmd_add_stdin,
    cmd_list, cmd_commit, cmd_remove,
)


class RootAwareParser(argparse.ArgumentParser):
    """支持 --root 出现在任意位置的参数解析器"""
    def parse_known_args(self, args=None, namespace=None):
        all_args = args if args is not None else sys.argv[1:]
        root_val = None
        cleaned = []
        skip_next = False
        for i, arg in enumerate(all_args):
            if skip_next:
                skip_next = False
                continue
            if arg == "--root" and i + 1 < len(all_args):
                root_val = all_args[i + 1]
                skip_next = True
                continue
            if arg.startswith("--root="):
                root_val = arg.split("=", 1)[1]
                continue
            cleaned.append(arg)
        if root_val:
            cleaned = ["--root", root_val] + cleaned
        return super().parse_known_args(cleaned, namespace)


def main():
    parser = RootAwareParser(
        prog="kb",
        description="知识库管理框架 — FTS5 全文检索 + 自动入库 + 健康检查",
    )
    parser.add_argument("--root", help="知识库根目录（或设置 KB_ROOT 环境变量）")
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="初始化知识库目录结构")
    p_init.add_argument("path", nargs="?", default=".", help="目标目录（默认当前目录）")
    p_init.add_argument("--template", choices=["1", "2", "3"], help="目录模板：1=通用, 2=客户/项目, 3=最小")
    p_init.set_defaults(func=_cmd_init)

    p_build = sub.add_parser("build", help="构建/重建全文索引")
    p_build.set_defaults(func=_cmd_build)

    p_update = sub.add_parser("update", help="增量更新索引")
    p_update.set_defaults(func=_cmd_update)

    p_search = sub.add_parser("search", help="全文搜索")
    p_search.add_argument("query", help="搜索关键词")
    p_search.add_argument("--type", choices=["kb", "rule"], help="按类型过滤")
    p_search.add_argument("--limit", type=int, default=8, help="结果数量（默认 8）")
    p_search.add_argument("--json", action="store_true", help="JSON 输出")
    p_search.set_defaults(func=_cmd_search)

    p_status = sub.add_parser("status", help="查看索引状态")
    p_status.set_defaults(func=_cmd_status)

    p_lint = sub.add_parser("lint", help="知识库健康检查")
    p_lint.set_defaults(func=_cmd_lint)

    p_manifest = sub.add_parser("manifest", help="生成机器可读清单")
    p_manifest.set_defaults(func=_cmd_manifest)

    # ingest
    p_ingest = sub.add_parser("ingest", help="多格式自动入库")
    ingest_sub = p_ingest.add_subparsers(dest="ingest_command")

    p_i_url = ingest_sub.add_parser("add-url", help="从 URL 抓取入库")
    p_i_url.add_argument("url")
    p_i_url.add_argument("--title")
    p_i_url.add_argument("--tags")
    p_i_url.set_defaults(func=_cmd_ingest_url)

    p_i_file = ingest_sub.add_parser("add-file", help="从本地文件入库")
    p_i_file.add_argument("path")
    p_i_file.add_argument("--title")
    p_i_file.add_argument("--tags")
    p_i_file.set_defaults(func=_cmd_ingest_file)

    p_i_stdin = ingest_sub.add_parser("add-stdin", help="从 stdin 入库")
    p_i_stdin.add_argument("--title")
    p_i_stdin.add_argument("--tags")
    p_i_stdin.set_defaults(func=_cmd_ingest_stdin)

    p_i_list = ingest_sub.add_parser("list", help="列出待入库")
    p_i_list.set_defaults(func=_cmd_ingest_list)

    p_i_commit = ingest_sub.add_parser("commit", help="正式写入 kb/")
    p_i_commit.add_argument("id", nargs="?", help="待入库 ID")
    p_i_commit.add_argument("--all", action="store_true")
    p_i_commit.set_defaults(func=_cmd_ingest_commit)

    p_i_remove = ingest_sub.add_parser("remove", help="删除待入库")
    p_i_remove.add_argument("id")
    p_i_remove.set_defaults(func=_cmd_ingest_remove)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


def _get_root(args):
    from pathlib import Path
    cli_root = getattr(args, 'root', None)
    if not cli_root:
        cli_root = None
    return resolve_kb_root(cli_root)


def _cmd_init(args):
    from pathlib import Path
    target = Path(args.path).expanduser().resolve()
    init_knowledge_base(target, template_key=args.template)


def _cmd_build(args):
    root = _get_root(args)
    build_index(root)


def _cmd_update(args):
    root = _get_root(args)
    build_index(root, update_only=True)


def _cmd_search(args):
    root = _get_root(args)
    results = search(root, args.query, args.limit, args.type)

    if getattr(args, 'json', False):
        output = [
            {"path": r["path"], "type": r.get("type") or "kb", "title": r["title"],
             "tags": r["tags"], "updated": r["updated"], "snippet": r["snippet"]}
            for r in results
        ]
        print(json.dumps(output, ensure_ascii=False))
        return

    if not results:
        print(f"未找到与 '{args.query}' 相关的内容")
        return

    print(f"\n搜索 '{args.query}' — 找到 {len(results)} 条结果\n")
    grouped = {}
    for r in results:
        t = r.get("type") or "kb"
        grouped.setdefault(t, []).append(r)

    emoji = {"kb": "\U0001f4c4", "rule": "\U0001f4cf"}
    sep = '\u2500' * 40
    for t, items in grouped.items():
        print(sep)
        print(f"  [{t.upper()}] {len(items)} 条结果")
        print(sep)
        em = emoji.get(t, '\U0001f4c4')
        for r in items:
            print(f"{em} {r['title']}")
            print(f"   路径：{r['path']}")
            if r["tags"]:
                print(f"   标签：{r['tags']}")
            if r["updated"]:
                print(f"   更新：{r['updated']}")
            print(f"   摘要：{r['snippet']}")
            print()


def _cmd_status(args):
    root = _get_root(args)
    s = status(root)
    print(f"索引状态：{s['total']} 个文件")
    for t, c in sorted(s["types"].items()):
        print(f"  [{t}] {c} 个文件")
    print(f"最后构建：{s['last_build']}")


def _cmd_lint(args):
    root = _get_root(args)
    _, total = run_lint(root)
    sys.exit(1 if total > 0 else 0)


def _cmd_manifest(args):
    root = _get_root(args)
    generate_manifest(root)


def _cmd_ingest_url(args):
    root = _get_root(args)
    cmd_add_url(args, root)


def _cmd_ingest_file(args):
    root = _get_root(args)
    cmd_add_file(args, root)


def _cmd_ingest_stdin(args):
    root = _get_root(args)
    cmd_add_stdin(args, root)


def _cmd_ingest_list(args):
    root = _get_root(args)
    cmd_list(args, root)


def _cmd_ingest_commit(args):
    root = _get_root(args)
    cmd_commit(args, root)


def _cmd_ingest_remove(args):
    root = _get_root(args)
    cmd_remove(args, root)
