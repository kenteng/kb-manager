"""
workspace.py — 知识库根目录解析

极简设计：只认 KB_ROOT 环境变量或 --root 参数，不做多级回退猜测。
"""

import os
from typing import Optional
from pathlib import Path


def resolve_kb_root(cli_root: Optional[str] = None) -> Path:
    """解析知识库根目录。

    优先级：
    1. --root 命令行参数
    2. KB_ROOT 环境变量
    3. 当前目录（如果包含 kb/ 子目录）

    都找不到时抛出明确错误，不猜测。
    """
    if cli_root:
        p = Path(cli_root).expanduser().resolve()
        if p.is_dir():
            return p
        raise ValueError(f"--root 指定的目录不存在：{cli_root}")

    env = os.environ.get("KB_ROOT")
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p
        raise ValueError(f"KB_ROOT 环境变量指向的目录不存在：{env}")

    cwd = Path.cwd()
    if (cwd / "kb").is_dir():
        return cwd

    raise ValueError(
        "未指定知识库根目录。\n"
        "  方式一：设置环境变量 export KB_ROOT=/path/to/workspace\n"
        "  方式二：命令行参数 kb search 'xxx' --root /path/to/workspace\n"
        "  方式三：在包含 kb/ 子目录的工作目录下运行"
    )


def get_kb_dir(root: Path) -> Path:
    return root / "kb"


def get_rules_dir(root: Path) -> Path:
    return root / "rules"


def get_state_dir(root: Path) -> Path:
    return root / "state"


def get_index_db(root: Path) -> Path:
    return get_state_dir(root) / ".kb-index.db"


def get_raw_dir(root: Path) -> Path:
    return get_kb_dir(root) / "raw"
