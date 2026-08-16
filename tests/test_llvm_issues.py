import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from triage_agent import llvm_issues

OLD_ISSUE = {
    "number": 1,
    "title": "old issue",
    "body": "old body",
    "url": "https://github.com/llvm/llvm-project/issues/1",
    "createdAt": "2026-01-01T00:00:00Z",
}
NEW_ISSUE = {
    "number": 2,
    "title": "new issue",
    "body": "new body",
    "url": "https://github.com/llvm/llvm-project/issues/2",
    "createdAt": "2026-08-15T00:00:00Z",
}
NEWEST_ISSUE = {
    "number": 3,
    "title": "newest issue",
    "body": None,
    "url": "https://github.com/llvm/llvm-project/issues/3",
    "createdAt": "2026-08-16T00:00:00Z",
}


class TestFetchRecentClangTidyIssues(unittest.TestCase):
    @patch("triage_agent.llvm_issues.subprocess.run")
    def test_builds_expected_gh_command(self, mock_run):
        mock_run.return_value = MagicMock(stdout="[]")

        llvm_issues.fetch_recent_clang_tidy_issues(
            datetime(2026, 1, 1, tzinfo=timezone.utc)
        )

        (argv,), kwargs = mock_run.call_args
        self.assertEqual(argv[:3], ["gh", "issue", "list"])
        self.assertIn("--repo", argv)
        self.assertEqual(argv[argv.index("--repo") + 1], "llvm/llvm-project")
        self.assertIn("--label", argv)
        self.assertEqual(argv[argv.index("--label") + 1], "clang-tidy")
        self.assertIn("--state", argv)
        self.assertEqual(argv[argv.index("--state") + 1], "all")
        self.assertTrue(kwargs["check"])

    @patch("triage_agent.llvm_issues.subprocess.run")
    def test_filters_by_since_and_sorts_oldest_first(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps([NEWEST_ISSUE, OLD_ISSUE, NEW_ISSUE])
        )

        result = llvm_issues.fetch_recent_clang_tidy_issues(
            datetime(2026, 6, 1, tzinfo=timezone.utc)
        )

        self.assertEqual([issue.number for issue in result], [2, 3])
        self.assertEqual(result[1].body, "")


class TestFetchIssue(unittest.TestCase):
    @patch("triage_agent.llvm_issues.subprocess.run")
    def test_fetches_single_issue(self, mock_run):
        mock_run.return_value = MagicMock(stdout=json.dumps(OLD_ISSUE))

        issue = llvm_issues.fetch_issue(1)

        self.assertEqual(issue.number, 1)
        self.assertEqual(issue.title, "old issue")
        (argv,), _ = mock_run.call_args
        self.assertEqual(argv[:3], ["gh", "issue", "view"])
        self.assertIn("1", argv)


if __name__ == "__main__":
    unittest.main()
