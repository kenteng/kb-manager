"""
ingest.py — 多格式自动入库

把 URL / 文件 / 文本 自动解析并导入知识库暂存区。
"""

import sys
import json
import re
import unicodedata
import urllib.request
from pathlib import Path
from datetime import datetime

from .workspace import get_kb_dir, get_raw_dir


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def load_manifest(raw_dir: Path):
    meta = raw_dir / ".ingest-manifest.jsonl"
    items = []
    if meta.exists():
        for line in meta.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return items


def save_manifest(raw_dir: Path, items):
    ensure_dir(raw_dir)
    meta = raw_dir / ".ingest-manifest.jsonl"
    meta.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n",
        encoding="utf-8",
    )


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r'[^\w\u4e00-\u9fff-]', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')[:80] or "untitled"


def generate_id(title: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    s = slugify(title)[:30]
    return f"{ts}-{s}"


def fetch_url(url: str, timeout: int = 20):
    """抓取 URL 并提取正文。"""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    body = re.sub(r'<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL)
    body = re.sub(r'<[^>]+>', '\n', body)
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    seen = set()
    deduped = [l for l in lines if l not in seen and len(l) > 2 and (seen.add(l) or True)]
    body = '\n'.join(deduped)
    if len(body) < 50:
        raise RuntimeError(f"\u63d0\u53d6\u5185\u5bb9\u8fc7\u77ed\uff08{len(body)} \u5b57\u7b26\uff09")
    return {"title": title, "content": body, "source": url}


def read_file(path: str):
    fpath = Path(path).expanduser().resolve()
    if not fpath.exists():
        raise FileNotFoundError(f"\u6587\u4ef6\u4e0d\u5b58\u5728\uff1a{fpath}")
    text = fpath.read_text(encoding="utf-8", errors="ignore")
    title = fpath.stem.replace("-", " ").replace("_", " ")
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            fm = text[3:end]
            for line in fm.splitlines():
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"')
                    break
    return {"title": title, "content": text, "source": str(fpath)}


def save_to_raw(raw_dir: Path, item: dict) -> str:
    ensure_dir(raw_dir)
    item_id = item["id"]
    target_dir = raw_dir / item_id
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "content.md").write_text(item["content"], encoding="utf-8")
    (target_dir / "metadata.json").write_text(json.dumps({
        "id": item["id"], "title": item.get("title", ""),
        "tags": item.get("tags", []), "source": item.get("source", ""),
        "ingested_at": item.get("ingested_at", ""), "status": "pending",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    items = load_manifest(raw_dir)
    items.append(item)
    save_manifest(raw_dir, items)
    return item_id


def cmd_add_url(args, root: Path) -> None:
    raw_dir = get_raw_dir(root)
    print(f"\U0001f310 \u6b63\u5728\u6293\u53d6 {args.url} ...")
    try:
        data = fetch_url(args.url)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    title = args.title or data.get("title") or "\u672a\u547d\u540d"
    tags = args.tags.split(",") if args.tags else []
    item = {"id": generate_id(title), "title": title, "content": data["content"],
            "tags": tags, "source": data.get("source", args.url),
            "ingested_at": datetime.now().isoformat(), "type": "pending"}
    item_id = save_to_raw(raw_dir, item)
    print(f"\u2705 \u5df2\u5165\u5e93\u6682\u5b58\u533a\uff1a{item_id} | \u6807\u9898\uff1a{title} | \u5b57\u6570\uff1a{len(data['content'])}")


def cmd_add_file(args, root: Path) -> None:
    raw_dir = get_raw_dir(root)
    print(f"\U0001f4c2 \u6b63\u5728\u8bfb\u53d6 {args.path} ...")
    try:
        data = read_file(args.path)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    title = args.title or data.get("title") or "\u672a\u547d\u540d"
    tags = args.tags.split(",") if args.tags else []
    item = {"id": generate_id(title), "title": title, "content": data["content"],
            "tags": tags, "source": data.get("source", args.path),
            "ingested_at": datetime.now().isoformat(), "type": "pending"}
    item_id = save_to_raw(raw_dir, item)
    print(f"\u2705 \u5df2\u5165\u5e93\u6682\u5b58\u533a\uff1a{item_id} | \u6807\u9898\uff1a{title} | \u5b57\u6570\uff1a{len(data['content'])}")


def cmd_add_stdin(args, root: Path) -> None:
    raw_dir = get_raw_dir(root)
    print("\u8bf7\u8f93\u5165\u5185\u5bb9\uff08Ctrl+D \u7ed3\u675f\uff09\uff1a")
    content = sys.stdin.read()
    title = args.title or content[:50].strip().replace("\n", " ")
    if len(title) > 50:
        title = title[:50] + "..."
    tags = args.tags.split(",") if args.tags else []
    item = {"id": generate_id(title), "title": title, "content": content,
            "tags": tags, "source": "stdin",
            "ingested_at": datetime.now().isoformat(), "type": "pending"}
    item_id = save_to_raw(raw_dir, item)
    print(f"\u2705 \u5df2\u5165\u5e93\u6682\u5b58\u533a\uff1a{item_id} | \u5b57\u6570\uff1a{len(content)}")


def cmd_list(args, root: Path) -> None:
    raw_dir = get_raw_dir(root)
    items = load_manifest(raw_dir)
    if not items:
        print("\U0001f4ed \u6682\u65e0\u5f85\u5165\u5e93\u5185\u5bb9")
        return
    print(f"\U0001f4cb \u5f85\u5165\u5e93\u6e05\u5355\uff08{len(items)} \u9879\uff09\n")
    for item in items:
        status = item.get("type", "unknown")
        emoji = {"pending": "\u23f3", "committed": "\u2705", "removed": "\u274c"}.get(status, "\U0001f4c4")
        tags = ", ".join(item.get("tags", [])) or "\u65e0"
        print(f"  {emoji} {item['id']}")
        print(f"     \u6807\u9898\uff1a{item.get('title', '')}")
        print(f"     \u6765\u6e90\uff1a{item.get('source', '')}")
        print(f"     \u6807\u7b7e\uff1a{tags}")
        print(f"     \u5b57\u6570\uff1a{len(item.get('content', ''))}")
        print()


def cmd_commit(args, root: Path) -> None:
    raw_dir = get_raw_dir(root)
    items = load_manifest(raw_dir)
    if not items:
        print("\U0001f4ed \u6ca1\u6709\u5f85\u5165\u5e93\u5185\u5bb9")
        return
    target_ids = set()
    if args.all:
        target_ids = {i["id"] for i in items if i.get("type") == "pending"}
    elif args.id:
        target_ids = {args.id}
    else:
        print("[ERROR] \u8bf7\u6307\u5b9a ID \u6216\u4f7f\u7528 --all", file=sys.stderr)
        sys.exit(1)
    kb_dir = get_kb_dir(root)
    committed = 0
    for item in items:
        if item["id"] not in target_ids or item.get("type") != "pending":
            continue
        target_name = f"{datetime.now().strftime('%Y-%m')}-{slugify(item['title'])}"
        target_path = kb_dir / target_name
        target_path.mkdir(parents=True, exist_ok=True)
        filename = f"{slugify(item['title'])}.md"
        counter = 1
        while (target_path / filename).exists():
            filename = f"{slugify(item['title'])}-{counter}.md"
            counter += 1
        tags_str = ", ".join(f'"{t.strip()}"' for t in item.get("tags", []) if t.strip())
        frontmatter = f'---\ntitle: "{item.get("title", "未命名")}"\ndate: "{item.get("ingested_at", "")[:10]}"\nsource: "{item.get("source", "")}"\ntags: [{tags_str}]\n---\n\n'
        (target_path / filename).write_text(frontmatter + item["content"], encoding="utf-8")
        item["type"] = "committed"
        item["committed_at"] = datetime.now().isoformat()
        item["target_path"] = f"{target_name}/{filename}"
        committed += 1
        print(f"  \u2705 {item['title']} \u2192 kb/{target_name}/{filename}")
    save_manifest(raw_dir, items)
    if committed > 0:
        print(f"\n\U0001f389 \u6210\u529f\u5165\u5e93 {committed} \u7bc7\u6587\u6863")
        print("\u63d0\u793a\uff1a\u8fd0\u884c 'kb build' \u6216 'kb update' \u66f4\u65b0\u7d22\u5f15")
    else:
        print("\u6ca1\u6709\u53ef\u63d0\u4ea4\u7684\u6587\u6863")


def cmd_remove(args, root: Path) -> None:
    import shutil
    raw_dir = get_raw_dir(root)
    items = load_manifest(raw_dir)
    found = False
    for item in items:
        if item["id"] == args.id:
            item["type"] = "removed"
            found = True
            item_dir = raw_dir / args.id
            if item_dir.exists():
                shutil.rmtree(str(item_dir))
            print(f"\u274c \u5df2\u5220\u9664\uff1a{item.get('title', args.id)}")
            break
    if not found:
        print(f"[ERROR] \u627e\u4e0d\u5230 ID\uff1a{args.id}", file=sys.stderr)
        sys.exit(1)
    save_manifest(raw_dir, items)
