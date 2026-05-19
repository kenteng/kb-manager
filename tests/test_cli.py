"""
tests/test_cli.py — kb-manager 核心功能测试
"""

import sys
import os
import shutil
import subprocess
import pytest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kb_manager.workspace import resolve_kb_root, get_kb_dir
from kb_manager.index import build_index, search, status
from kb_manager.lint import run_lint
from kb_manager.manifest import generate_manifest
from kb_manager.init import init_knowledge_base

TEST_ROOT = Path("/tmp/kb-test-pytest")


@pytest.fixture(autouse=True)
def clean_test_dir():
    if TEST_ROOT.exists():
        shutil.rmtree(str(TEST_ROOT))
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    yield
    if TEST_ROOT.exists():
        shutil.rmtree(str(TEST_ROOT))


class TestInit:
    def test_init_creates_dirs(self):
        init_knowledge_base(TEST_ROOT, template_key="2")
        assert (TEST_ROOT / "kb" / "clients").is_dir()
        assert (TEST_ROOT / "kb" / "meetings").is_dir()
        assert (TEST_ROOT / "kb" / "tech").is_dir()
        assert (TEST_ROOT / "kb" / "SCHEMA.md").is_file()
        assert (TEST_ROOT / "kb" / "index.md").is_file()
        assert (TEST_ROOT / "kb" / "log.md").is_file()
        assert (TEST_ROOT / "rules").is_dir()
        assert (TEST_ROOT / "state").is_dir()
        assert (TEST_ROOT / ".gitignore").is_file()
        # kb-private no longer exists
        assert not (TEST_ROOT / "kb-private").exists()

    def test_init_idempotent(self):
        init_knowledge_base(TEST_ROOT, template_key="2")
        init_knowledge_base(TEST_ROOT, template_key="2")
        assert (TEST_ROOT / "kb" / "SCHEMA.md").is_file()

    def test_init_template_1(self):
        init_knowledge_base(TEST_ROOT, template_key="1")
        assert (TEST_ROOT / "kb" / "articles").is_dir()
        assert (TEST_ROOT / "kb" / "notes").is_dir()

    def test_init_template_3(self):
        init_knowledge_base(TEST_ROOT, template_key="3")
        assert (TEST_ROOT / "kb" / "articles").is_dir()
        assert (TEST_ROOT / "kb" / "raw").is_dir()


class TestWorkspace:
    def _res(self, p):
        return Path(p).resolve()

    def test_resolve_from_env(self, monkeypatch):
        init_knowledge_base(TEST_ROOT, template_key="2")
        monkeypatch.setenv("KB_ROOT", str(TEST_ROOT))
        result = resolve_kb_root()
        assert self._res(result) == self._res(TEST_ROOT)

    def test_resolve_from_cli(self):
        init_knowledge_base(TEST_ROOT, template_key="2")
        result = resolve_kb_root(str(TEST_ROOT))
        assert self._res(result) == self._res(TEST_ROOT)

    def test_resolve_from_cwd(self, monkeypatch):
        init_knowledge_base(TEST_ROOT, template_key="2")
        monkeypatch.chdir(TEST_ROOT)
        monkeypatch.delenv("KB_ROOT", raising=False)
        result = resolve_kb_root()
        assert self._res(result) == self._res(TEST_ROOT)

    def test_resolve_raises_when_not_found(self, monkeypatch):
        monkeypatch.delenv("KB_ROOT", raising=False)
        monkeypatch.chdir("/")
        with pytest.raises(ValueError, match="未指定知识库根目录"):
            resolve_kb_root()

    def test_raises_for_invalid_path(self):
        with pytest.raises(ValueError, match="不存在"):
            resolve_kb_root("/nonexistent/path")


class TestIndex:
    @pytest.fixture
    def kb_root(self):
        init_knowledge_base(TEST_ROOT, template_key="2")
        clients = get_kb_dir(TEST_ROOT) / "clients"
        (clients / "acme.md").write_text(
            "---\ntitle: Acme Corp\ntags: [client/acme, stage/active]\nupdated: 2026-05-18\n---\nAcme 是一家零售公司。",
            encoding="utf-8"
        )
        (clients / "contoso.md").write_text(
            "---\ntitle: Contoso Ltd\ntags: [client/contoso, stage/pitch]\nupdated: 2026-05-17\n---\nContoso 是一家制造企业。",
            encoding="utf-8"
        )
        tech = get_kb_dir(TEST_ROOT) / "tech"
        (tech / "ai-agent.md").write_text(
            "---\ntitle: AI Agent 实践\ntags: [tech/Agent, type/methodology]\nupdated: 2026-05-18\n---\nAI Agent 在 CDP 中的应用实践。",
            encoding="utf-8"
        )
        return TEST_ROOT

    def test_build_index(self, kb_root):
        total = build_index(kb_root)
        assert total >= 3

    def test_search(self, kb_root):
        build_index(kb_root)
        results = search(kb_root, "CDP")
        assert len(results) >= 1
        assert "ai-agent" in results[0]["path"]

    def test_search_with_type_filter(self, kb_root):
        build_index(kb_root)
        results = search(kb_root, "Acme", type_filter="kb")
        assert len(results) >= 1
        assert all(r["type"] == "kb" for r in results)

    def test_search_multi_term(self, kb_root):
        build_index(kb_root)
        results = search(kb_root, "Agent CDP")
        assert len(results) >= 1

    def test_status(self, kb_root):
        build_index(kb_root)
        s = status(kb_root)
        assert s["total"] >= 3
        assert s["last_build"] != "从未"

    def test_incremental_update(self, kb_root):
        build_index(kb_root)
        tech = get_kb_dir(TEST_ROOT) / "tech"
        (tech / "new.md").write_text(
            "---\ntitle: New Article\ntags: [tech/new]\nupdated: 2026-05-18\n---\n新内容。",
            encoding="utf-8"
        )
        build_index(kb_root, update_only=True)
        results = search(kb_root, "新内容")
        assert len(results) >= 1

    def test_deleted_files_cleaned(self, kb_root):
        build_index(kb_root)
        clients = get_kb_dir(TEST_ROOT) / "clients"
        (clients / "acme.md").unlink()
        build_index(kb_root, update_only=True)
        results = search(kb_root, "Acme")
        assert len(results) == 0

    def test_json_output(self, kb_root):
        build_index(kb_root)
        results = search(kb_root, "Acme")
        assert "path" in results[0]
        assert "title" in results[0]
        assert "type" in results[0]
        assert "snippet" in results[0]

    def test_no_private_type(self, kb_root):
        """确认不再有 private 类型"""
        build_index(kb_root)
        s = status(kb_root)
        assert "private" not in s["types"]


class TestLint:
    def test_clean_kb_passes(self):
        init_knowledge_base(TEST_ROOT, template_key="2")
        kb_dir = get_kb_dir(TEST_ROOT) / "clients"
        (kb_dir / "test.md").write_text(
            "---\ntitle: Test\ntags: [client/test]\nupdated: 2026-05-18\n---\nTest content.",
            encoding="utf-8"
        )
        _, total = run_lint(TEST_ROOT)
        assert total == 0

    def test_missing_frontmatter(self):
        init_knowledge_base(TEST_ROOT, template_key="2")
        kb_dir = get_kb_dir(TEST_ROOT) / "clients"
        (kb_dir / "bad.md").write_text("No frontmatter here.", encoding="utf-8")
        issues, total = run_lint(TEST_ROOT)
        assert total > 0
        assert "clients/bad.md" in issues["no_frontmatter"]

    def test_missing_tags(self):
        init_knowledge_base(TEST_ROOT, template_key="2")
        kb_dir = get_kb_dir(TEST_ROOT) / "clients"
        (kb_dir / "notags.md").write_text(
            "---\ntitle: No Tags\nupdated: 2026-05-18\n---\nContent.",
            encoding="utf-8"
        )
        issues, total = run_lint(TEST_ROOT)
        assert "clients/notags.md" in issues["no_tags"]

    def test_broken_related(self):
        init_knowledge_base(TEST_ROOT, template_key="2")
        kb_dir = get_kb_dir(TEST_ROOT) / "clients"
        (kb_dir / "ref.md").write_text(
            "---\ntitle: Ref\ntags: [client/ref]\nupdated: 2026-05-18\nrelated:\n  - nonexistent.md\n---\nContent.",
            encoding="utf-8"
        )
        issues, total = run_lint(TEST_ROOT)
        assert "clients/ref.md → nonexistent.md" in issues["related_broken"]


class TestManifest:
    def test_generate(self):
        init_knowledge_base(TEST_ROOT, template_key="2")
        kb_dir = get_kb_dir(TEST_ROOT) / "clients"
        (kb_dir / "test.md").write_text(
            '---\ntitle: "Test"\ntags: ["client/test"]\nupdated: 2026-05-18\n---\nContent.',
            encoding="utf-8"
        )
        entries, missing = generate_manifest(TEST_ROOT)
        assert len(entries) >= 1
        manifest = TEST_ROOT / "kb" / "_manifest.jsonl"
        assert manifest.exists()


class TestCLI:
    def test_init_via_cli_with_template(self):
        from kb_manager.cli import main
        sys.argv = ["kb", "init", str(TEST_ROOT), "--template", "2"]
        main()
        assert (TEST_ROOT / "kb").is_dir()
        assert (TEST_ROOT / "kb" / "clients").is_dir()

    def test_help(self):
        from kb_manager.cli import main
        sys.argv = ["kb", "--help"]
        with pytest.raises(SystemExit):
            main()

    def test_search_no_private_type(self):
        """确认 --type private 不再有效"""
        r = subprocess.run(
            [sys.executable, "-c",
             "import argparse; p=argparse.ArgumentParser(); p.add_argument('--type',choices=['kb','rule']); p.parse_args(['--type','private'])"],
            capture_output=True, text=True
        )
        assert r.returncode != 0  # should fail
