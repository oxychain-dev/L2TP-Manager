#!/usr/bin/env python3
"""Pure tests for issue draft parsing; no GitHub access needed."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "issue_publisher", ROOT / "tools" / "publish-issue-backlog.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class BacklogTests(unittest.TestCase):
    def test_real_backlog_has_unique_issues_and_dod(self):
        drafts = mod.drafts((ROOT / "ISSUE-BACKLOG.md").read_text("utf-8"))
        self.assertGreaterEqual(len(drafts), 25)
        ids = [item["id"] for item in drafts]
        self.assertEqual(len(ids), len(set(ids)))
        for issue in drafts:
            self.assertIn("Definition of Done", issue["body"])
            self.assertTrue(issue["title"].startswith(("[P0]", "[P1]", "[P2]")))
            self.assertIn("Tracking ID: " + issue["id"], issue["body"])

    def test_duplicate_identifiers_are_rejected(self):
        fragment = "\n**Evidence**\n" + "this is evidence and scope. " * 16
        text = ("## TASK-001 — [P0] First\n" + fragment + "\n---\n"
                "## TASK-001 — [P1] Second\n" + fragment)
        with self.assertRaises(mod.Problem):
            mod.drafts(text)

    def test_unparseable_backlog_rejected(self):
        with self.assertRaises(mod.Problem):
            mod.drafts("# No numbered drafts here")


if __name__ == "__main__":
    unittest.main()
