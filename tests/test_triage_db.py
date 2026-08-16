import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from triage_agent import triage_db
from triage_agent.llvm_issues import LlvmIssue


def _issue(number: int, created_at: str) -> LlvmIssue:
    return LlvmIssue(
        number=number,
        title=f"issue {number}",
        body="body",
        url=f"https://github.com/llvm/llvm-project/issues/{number}",
        created_at=datetime.fromisoformat(created_at).replace(tzinfo=timezone.utc),
    )


class TestExtractSourceIssueNumber(unittest.TestCase):
    def test_extracts_number_from_issue_line(self):
        body = "## Source\n\n- **Issue:** https://github.com/llvm/llvm-project/issues/12345\n"
        self.assertEqual(triage_db.extract_source_issue_number(body), 12345)

    def test_returns_none_when_marker_missing(self):
        self.assertIsNone(triage_db.extract_source_issue_number("no marker here"))

    def test_returns_none_for_empty_body(self):
        self.assertIsNone(triage_db.extract_source_issue_number(""))

    def test_ignores_unrelated_github_links(self):
        body = "See https://github.com/llvm/llvm-project/pull/999 for context."
        self.assertIsNone(triage_db.extract_source_issue_number(body))


class TestFetchTrackedLlvmIssueNumbers(unittest.TestCase):
    @patch("triage_agent.triage_db.subprocess.run")
    def test_parses_markers_from_all_issues(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                [
                    {
                        "title": "t1",
                        "body": "- **Issue:** https://github.com/llvm/llvm-project/issues/1",
                    },
                    {"title": "t2", "body": "no marker"},
                    {
                        "title": "t3",
                        "body": "- **Issue:** https://github.com/llvm/llvm-project/issues/2",
                    },
                ]
            )
        )

        result = triage_db.fetch_tracked_llvm_issue_numbers()

        self.assertEqual(result, {1, 2})
        (argv,), kwargs = mock_run.call_args
        self.assertIn("--repo", argv)
        self.assertEqual(argv[argv.index("--repo") + 1], "vbvictor/triage-agent")
        self.assertIn("--label", argv)
        self.assertEqual(argv[argv.index("--label") + 1], "clang-tidy-triage")
        self.assertIn("--state", argv)
        self.assertEqual(argv[argv.index("--state") + 1], "open")
        self.assertTrue(kwargs["check"])


class TestSelectNewIssues(unittest.TestCase):
    def test_filters_tracked_and_caps_oldest_first(self):
        issues = [
            _issue(3, "2026-08-03"),
            _issue(1, "2026-08-01"),
            _issue(2, "2026-08-02"),
            _issue(4, "2026-08-04"),
        ]

        result = triage_db.select_new_issues(issues, tracked={2}, cap=2)

        self.assertEqual([issue.number for issue in result], [1, 3])


class TestCreateTrackingIssue(unittest.TestCase):
    @patch("triage_agent.triage_db.subprocess.run")
    def test_creates_issue_via_body_file_and_returns_url(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="https://github.com/vbvictor/triage-agent/issues/9\n"
        )

        url = triage_db.create_tracking_issue(title="Title", body="Body text")

        self.assertEqual(url, "https://github.com/vbvictor/triage-agent/issues/9")
        (argv,), kwargs = mock_run.call_args
        self.assertEqual(argv[:3], ["gh", "issue", "create"])
        self.assertIn("--body-file", argv)
        self.assertIn("--label", argv)
        self.assertEqual(argv[argv.index("--label") + 1], "clang-tidy-triage")
        self.assertTrue(kwargs["check"])


if __name__ == "__main__":
    unittest.main()
