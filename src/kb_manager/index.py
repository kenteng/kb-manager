"""
index.py — 统一全文检索索引（基于 SQLite FTS5）

支持中英文全文搜索、多类型（kb/rule）索引、增量更新。
"""

import sqlite3
import hashlib
import re
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from datetime import datetime

from .workspace import (
    resolve_kb_root, get_kb_dir,
    get_rules_dir, get_index_db
)


def get_db(root: Path) -> sqlite3.Connection:
    db_path = get_index_db(root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> bool:
    """初始化数据库表结构。返回是否需要全量重建。"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            type TEXT DEFAULT 'kb',
            mtime REAL,
            hash TEXT,
            title TEXT,
            tags TEXT,
            updated TEXT,
            indexed_at TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(
            path UNINDEXED,
            type UNINDEXED,
            title,
            tags,
            content,
            tokenize = "unicode61"
        );
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    try:
        conn.execute("SELECT type FROM files LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE files ADD COLUMN type TEXT DEFAULT 'kb'")
        conn.commit()

    try:
        conn.execute("SELECT type FROM kb_fts LIMIT 1")
    except sqlite3.OperationalError:
        print("\u26a0\ufe0f FTS 表结构需要升级，执行 rebuild...")
        conn.execute("DROP TABLE IF EXISTS kb_fts")
        conn.execute("""
            CREATE VIRTUAL TABLE kb_fts USING fts5(
                path UNINDEXED, type UNINDEXED,
                title, tags, content,
                tokenize = "unicode61"
            );
        """)
        conn.commit()
        return True
    conn.commit()
    return False


def extract_frontmatter(text: str) -> Tuple[str, str, str]:
    """提取 YAML frontmatter，返回 (title, tags, updated)"""
    title, tags, updated = "", "", ""
    if not text.startswith("---"):
        return title, tags, updated
    end = text.find("---", 3)
    if end <= 0:
        return title, tags, updated
    fm = text[3:end]
    for line in fm.splitlines():
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("updated:") or (line.startswith("date:") and not updated):
            updated = line.split(":", 1)[1].strip()
        elif line.startswith("tags:"):
            tags_raw = line.split(":", 1)[1].strip()
            tags = tags_raw.strip("[]").replace(",", " ")
    if not tags:
        in_tags = False
        tag_list = []
        for line in fm.splitlines():
            if line.strip().startswith("tags:"):
                in_tags = True
                continue
            if in_tags:
                if line.startswith(" ") or line.startswith("\t"):
                    tag_list.append(line.strip().lstrip("- "))
                else:
                    break
        tags = " ".join(tag_list)
    return title, tags, updated


def strip_markdown(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            text = text[end + 3:]
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`[^`]+`', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|[-:]+\|', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _search_terms(query: str) -> List[str]:
    return re.findall(r"[\w\u4e00-\u9fff-]+", query, flags=re.UNICODE)


def _fts_query(query: str) -> str:
    terms = _search_terms(query)
    if not terms:
        return ""
    quoted = [f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms]
    return " OR ".join(quoted)


def _collect_sources(root: Path) -> List[Tuple[Path, str, str]]:
    """收集所有需要索引的文件：(文件路径, 相对路径, 类型)"""
    sources = []
    kb_dir = get_kb_dir(root)
    rules_dir = get_rules_dir(root)

    # shared kb
    if kb_dir.is_dir():
        for f in kb_dir.rglob("*.md"):
            if "raw/" not in str(f) and f.name not in ("log.md", "SCHEMA.md"):
                rel = str(f.relative_to(kb_dir))
                sources.append((f, f"kb/{rel}", "kb"))

    # rules
    if rules_dir.is_dir():
        for f in rules_dir.rglob("*.md"):
            if not f.name.startswith("_"):
                rel = str(f.relative_to(rules_dir))
                sources.append((f, f"rules/{rel}", "rule"))

    return sources


def build_index(root: Path, update_only: bool = False) -> int:
    conn = get_db(root)
    needs_rebuild = init_db(conn)
    if needs_rebuild:
        update_only = False

    sources = _collect_sources(root)
    added, updated, skipped = 0, 0, 0

    for fpath, rel_path, ftype in sources:
        mtime = fpath.stat().st_mtime
        fhash = file_hash(fpath)
        row = conn.execute("SELECT hash FROM files WHERE path = ?", (rel_path,)).fetchone()
        old_hash = row["hash"] if row else None

        if update_only:
            if old_hash == fhash:
                skipped += 1
                continue

        text = fpath.read_text(encoding="utf-8", errors="ignore")
        title, tags, file_updated = extract_frontmatter(text)
        if not title:
            title = fpath.stem.replace("-", " ").replace("_", " ")
        content = strip_markdown(text)

        conn.execute(
            "INSERT OR REPLACE INTO files (path, type, mtime, hash, title, tags, updated, indexed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (rel_path, ftype, mtime, fhash, title, tags, file_updated, datetime.now().isoformat()))
        conn.execute("DELETE FROM kb_fts WHERE path = ?", (rel_path,))
        conn.execute(
            "INSERT INTO kb_fts (path, type, title, tags, content) VALUES (?, ?, ?, ?, ?)",
            (rel_path, ftype, title, tags, content))

        if old_hash is None:
            added += 1
        else:
            updated += 1

    conn.commit()

    indexed_paths = set(r[0] for r in conn.execute("SELECT path FROM files"))
    current_paths = set(rel for _, rel, _ in sources)
    for p in indexed_paths - current_paths:
        conn.execute("DELETE FROM files WHERE path = ?", (p,))
        conn.execute("DELETE FROM kb_fts WHERE path = ?", (p,))
    conn.commit()

    total = len(sources)
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_build', ?)", (datetime.now().isoformat(),))
    conn.commit()
    conn.close()

    print(f"\u7d22\u5f15\u5b8c\u6210\uff1a\u5171 {total} \u4e2a\u6587\u4ef6\uff0c\u65b0\u589e {added}\uff0c\u66f4\u65b0 {updated}\uff0c\u8df3\u8fc7 {skipped}")
    type_counts = {}
    for _, _, t in sources:
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, c in sorted(type_counts.items()):
        print(f"  [{t}] {c} \u4e2a\u6587\u4ef6")
    return total


def search(root: Path, query: str, limit: int = 8, type_filter: Optional[str] = None) -> List[dict]:
    conn = get_db(root)
    init_db(conn)

    fts_query = _fts_query(query)
    if not fts_query:
        conn.close()
        return []

    try:
        if type_filter:
            results = conn.execute(
                "SELECT f.path, f.type, f.title, f.tags, f.updated, snippet(kb_fts, 4, '\u3010', '\u3011', '...', 32) as snippet, rank FROM kb_fts JOIN files f ON kb_fts.path = f.path WHERE kb_fts MATCH ? AND f.type = ? ORDER BY rank LIMIT ?",
                (fts_query, type_filter, limit)).fetchall()
        else:
            results = conn.execute(
                "SELECT f.path, f.type, f.title, f.tags, f.updated, snippet(kb_fts, 4, '\u3010', '\u3011', '...', 32) as snippet, rank FROM kb_fts JOIN files f ON kb_fts.path = f.path WHERE kb_fts MATCH ? ORDER BY rank LIMIT ?",
                (fts_query, limit)).fetchall()
    except sqlite3.OperationalError as e:
        print(f"\u641c\u7d22\u9519\u8bef: {e}")
        print("\u63d0\u793a\uff1a\u8bf7\u5148\u8fd0\u884c 'kb build' \u6784\u5efa\u7d22\u5f15")
        return []

    conn.close()
    return [dict(r) for r in results]


def status(root: Path) -> dict:
    conn = get_db(root)
    init_db(conn)
    total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    last_build = conn.execute("SELECT value FROM meta WHERE key = 'last_build'").fetchone()
    type_stats = conn.execute("SELECT type, COUNT(*) as cnt FROM files GROUP BY type").fetchall()
    conn.close()
    return {
        "total": total,
        "last_build": last_build[0] if last_build else "\u4ece\u672a",
        "types": {r["type"]: r["cnt"] for r in type_stats},
    }
