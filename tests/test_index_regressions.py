import io
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kb_manager.index import build_index, search
from kb_manager.init import init_knowledge_base


class IndexRegressionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="kb-index-regression-"))
        init_knowledge_base(self.root, template_key="3")

    def tearDown(self):
        shutil.rmtree(self.root)

    def write_article(self, body: str):
        article = self.root / "kb" / "articles" / "demo.md"
        article.write_text(
            "---\n"
            "title: Demo\n"
            "tags: [tech/ai]\n"
            "updated: 2026-05-20\n"
            "---\n"
            f"{body}\n",
            encoding="utf-8",
        )
        return article

    def test_incremental_update_reports_changed_file_as_updated(self):
        article = self.write_article("old content")
        with redirect_stdout(io.StringIO()):
            build_index(self.root)

        article.write_text(
            "---\n"
            "title: Demo\n"
            "tags: [tech/ai]\n"
            "updated: 2026-05-20\n"
            "---\n"
            "new content\n",
            encoding="utf-8",
        )

        output = io.StringIO()
        with redirect_stdout(output):
            build_index(self.root, update_only=True)

        self.assertIn("新增 0，更新 1，跳过 1", output.getvalue())

    def test_search_with_fts_syntax_characters_falls_back_to_safe_lookup(self):
        self.write_article("Agent (CDP) architecture notes")
        with redirect_stdout(io.StringIO()):
            build_index(self.root)

        results = search(self.root, 'Agent "CDP')

        self.assertTrue(results)
        self.assertEqual("kb/articles/demo.md", results[0]["path"])


if __name__ == "__main__":
    unittest.main()
