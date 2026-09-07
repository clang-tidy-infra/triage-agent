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
        self.assertEqual(argv[argv.index("--state") + 1], "open")
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


class TestFetchUntaggedClangTidyIssues(unittest.TestCase):
    @patch("triage_agent.llvm_issues.subprocess.run")
    def test_builds_expected_gh_command(self, mock_run):
        mock_run.return_value = MagicMock(stdout="[]")

        llvm_issues.fetch_untagged_clang_tidy_issues()

        (argv,), kwargs = mock_run.call_args
        self.assertEqual(argv[:3], ["gh", "issue", "list"])
        self.assertIn("--repo", argv)
        self.assertEqual(argv[argv.index("--repo") + 1], "llvm/llvm-project")
        self.assertIn("--label", argv)
        self.assertEqual(argv[argv.index("--label") + 1], "clang-tidy")
        self.assertIn("--state", argv)
        self.assertEqual(argv[argv.index("--state") + 1], "open")
        self.assertIn("--search", argv)
        self.assertEqual(argv[argv.index("--search") + 1], llvm_issues.UNTAGGED_QUERY)
        self.assertTrue(kwargs["check"])

    @patch("triage_agent.llvm_issues.subprocess.run")
    def test_sorts_oldest_first_without_date_filtering(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps([NEWEST_ISSUE, OLD_ISSUE, NEW_ISSUE])
        )

        result = llvm_issues.fetch_untagged_clang_tidy_issues()

        self.assertEqual([issue.number for issue in result], [1, 2, 3])


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


class TestFetchIssueTriageStatus(unittest.TestCase):
    @patch("triage_agent.llvm_issues.subprocess.run")
    def test_builds_expected_gh_command(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"state": "OPEN", "labels": [], "issueType": None})
        )

        status = llvm_issues.fetch_issue_triage_status(42)

        (argv,), kwargs = mock_run.call_args
        self.assertEqual(argv[:3], ["gh", "issue", "view"])
        self.assertIn("42", argv)
        self.assertIn("--json", argv)
        self.assertEqual(argv[argv.index("--json") + 1], "state,labels,issueType")
        self.assertTrue(kwargs["check"])
        self.assertEqual(status.number, 42)
        self.assertEqual(status.state, "OPEN")
        self.assertEqual(status.labels, [])
        self.assertFalse(status.has_issue_type)

    @patch("triage_agent.llvm_issues.subprocess.run")
    def test_parses_labels_and_issue_type(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "state": "CLOSED",
                    "labels": [{"name": "clang-tidy"}, {"name": "false-positive"}],
                    "issueType": {"name": "Bug"},
                }
            )
        )

        status = llvm_issues.fetch_issue_triage_status(7)

        self.assertEqual(status.state, "CLOSED")
        self.assertEqual(status.labels, ["clang-tidy", "false-positive"])
        self.assertTrue(status.has_issue_type)


class TestIsIssueTriaged(unittest.TestCase):
    def test_open_untagged_issue_is_not_triaged(self):
        status = llvm_issues.LlvmIssueTriageStatus(
            number=1, state="OPEN", labels=["clang-tidy"], has_issue_type=False
        )
        self.assertFalse(llvm_issues.is_issue_triaged(status))

    def test_closed_issue_is_triaged(self):
        status = llvm_issues.LlvmIssueTriageStatus(
            number=1, state="CLOSED", labels=[], has_issue_type=False
        )
        self.assertTrue(llvm_issues.is_issue_triaged(status))

    def test_issue_type_set_is_triaged(self):
        status = llvm_issues.LlvmIssueTriageStatus(
            number=1, state="OPEN", labels=[], has_issue_type=True
        )
        self.assertTrue(llvm_issues.is_issue_triaged(status))

    def test_recognized_label_is_triaged(self):
        status = llvm_issues.LlvmIssueTriageStatus(
            number=1,
            state="OPEN",
            labels=["clang-tidy", "enhancement"],
            has_issue_type=False,
        )
        self.assertTrue(llvm_issues.is_issue_triaged(status))

    def test_unrecognized_label_alone_is_not_triaged(self):
        status = llvm_issues.LlvmIssueTriageStatus(
            number=1, state="OPEN", labels=["good first issue"], has_issue_type=False
        )
        self.assertFalse(llvm_issues.is_issue_triaged(status))


if __name__ == "__main__":
    unittest.main()
