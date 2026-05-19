"""
manifest.py — 生成 kb/_manifest.jsonl
每行一条 JSON：{path, title, tags[], updated, summary}
"""

import json
import re
from pathlib import Path

from .workspace import get_kb_dir


def parse_frontmatter(text: str) -> dict:
    result = {"title": "", "tags": [], "updated": ""}
    if not text.startswith("---"):
        return result
    end = text.find("---", 3)
    if end < 0:
        return result
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
                tags = [t.strip().strip('"').strip("'") for t in rest.strip("[]").split(",") if t.strip()]
                break
            in_tags = True
            continue
        if in_tags:
            if stripped.startswith("- "):
                tags.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("-"):
                break
    result["tags"] = tags
    return result


def extract_summary(text: str, max_chars: int = 120) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            text = text[end + 3:]
    text = re.sub(r'^#.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{2,}', '\n', text).strip()
    summary = text[:max_chars].replace("\n", " ").strip()
    if len(text) > max_chars:
        summary += "\u2026"
    return summary


SKIP_FILES = {"SCHEMA.md", "index.md", "log.md", "README.md", "_manifest.jsonl"}


def generate_manifest(root: Path):
    kb_dir = get_kb_dir(root)
    files = sorted(kb_dir.rglob("*.md"))
    files = [f for f in files if "raw/" not in str(f) and f.name not in SKIP_FILES]

    manifest_path = kb_dir / "_manifest.jsonl"
    missing_meta = []
    entries = []

    for fpath in files:
        rel = str(fpath.relative_to(kb_dir))
        text = fpath.read_text(encoding="utf-8", errors="ignore")
        meta = parse_frontmatter(text)
        if not meta["title"]:
            meta["title"] = fpath.stem.replace("-", " ").replace("_", " ")
            missing_meta.append(rel)
        entry = {
            "path": rel, "title": meta["title"],
            "tags": meta["tags"], "updated": meta["updated"],
            "summary": extract_summary(text),
        }
        entries.append(entry)

    with open(str(manifest_path), "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"_manifest.jsonl \u5df2\u751f\u6210\uff1a{len(entries)} \u6761\u8bb0\u5f55")
    if missing_meta:
        print(f"\u26a0\ufe0f {len(missing_meta)} \u4e2a\u6587\u4ef6\u7f3a title\uff08\u4f7f\u7528\u6587\u4ef6\u540d\u66ff\u4ee3\uff09")
    return entries, missing_meta
