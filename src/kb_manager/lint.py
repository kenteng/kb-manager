"""
lint.py — 知识库健康检查

检查项：缺 frontmatter、缺 title、缺 tags、缺 updated、related 失联
"""

import sys
from typing import Optional, List, Dict, Tuple
from pathlib import Path

from .workspace import get_kb_dir


def parse_frontmatter(text: str) -> Optional[dict]:
    result = {"title": "", "tags": [], "updated": "", "related": []}
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end < 0:
        return None
    fm = text[3:end]

    for line in fm.splitlines():
        if line.startswith("title:"):
            result["title"] = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("updated:") or (line.startswith("date:") and not result["updated"]):
            result["updated"] = line.split(":", 1)[1].strip()

    in_tags = False
    tags = []
    for line in fm.splitlines():
        stripped = line.strip()
        if stripped.startswith("tags:"):
            rest = stripped[5:].strip()
            if rest.startswith("["):
                tags = [t.strip().strip('"') for t in rest.strip("[]").split(",") if t.strip()]
                break
            in_tags = True
            continue
        if in_tags:
            if stripped.startswith("- "):
                tags.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("-"):
                break
    result["tags"] = tags

    in_related = False
    for line in fm.splitlines():
        stripped = line.strip()
        if stripped.startswith("related:"):
            in_related = True
            continue
        if in_related:
            if stripped.startswith("- "):
                result["related"].append(stripped[2:].strip())
            elif stripped and not stripped.startswith("-"):
                break

    return result


SKIP_FILES = {"SCHEMA.md", "index.md", "log.md", "README.md", "_manifest.jsonl"}


def run_lint(root: Path) -> Tuple[dict, int]:
    kb_dir = get_kb_dir(root)
    files = sorted(kb_dir.rglob("*.md"))
    files = [f for f in files if "raw/" not in str(f) and f.name not in SKIP_FILES]

    all_paths = set(str(f.relative_to(kb_dir)) for f in files)

    issues = {
        "no_frontmatter": [],
        "no_title": [],
        "no_tags": [],
        "no_updated": [],
        "related_broken": [],
    }

    for fpath in files:
        rel = str(fpath.relative_to(kb_dir))
        text = fpath.read_text(encoding="utf-8", errors="ignore")
        fm = parse_frontmatter(text)

        if fm is None:
            issues["no_frontmatter"].append(rel)
            continue
        if not fm["title"]:
            issues["no_title"].append(rel)
        if not fm["tags"]:
            issues["no_tags"].append(rel)
        if not fm["updated"]:
            issues["no_updated"].append(rel)
        for r in fm["related"]:
            normalized = r.removeprefix("kb/") if r.startswith("kb/") else r
            if normalized not in all_paths and not normalized.startswith("memory/"):
                issues["related_broken"].append(f"{rel} \u2192 {r}")

    total = sum(len(v) for v in issues.values())
    if total == 0:
        print(f"\u2705 kb/ 健检通过：{len(files)} 个文件，0 个问题")
    else:
        labels = {
            "no_frontmatter": "缺 frontmatter",
            "no_title": "缺 title",
            "no_tags": "缺 tags",
            "no_updated": "缺 updated",
            "related_broken": "related 失联",
        }
        print(f"\u26a0\ufe0f kb/ 健检发现 {total} 个问题（共 {len(files)} 个文件）：\n")
        for key, label in labels.items():
            items = issues[key]
            if items:
                print(f"  [{label}] ({len(items)})")
                for item in items:
                    print(f"    - {item}")
                print()

    return issues, total
