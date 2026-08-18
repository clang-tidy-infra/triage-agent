# triage-agent

An AI agent that triages `clang-tidy`-labeled issues on
[LLVM](https://github.com/llvm/llvm-project) and tries reproduces each
one via [Compiler Explorer](https://godbolt.org). Triage information is posted in this repository
with a verdict and recommended labels.

## Workflows

There are multiple workflows that have different purposes:

| Workflow | Schedule | What Discovers | What Labels | Why needed |
| --- | --- | --- | --- | --- |
| Triage new issues | hourly | issues created in the last 7 days | `clang-tidy-triage` | Help triage incoming [clang-tidy](https://github.com/llvm/llvm-project/issues?q=is%3Aissue%20state%3Aopen%20label%3Aclang-tidy) issues in LLVM |
| Triage old issues | daily | old and untagged issues | `clang-tidy-triage-backlog` | Help triage old, unattended [clang-tidy](https://github.com/llvm/llvm-project/issues?q=is%3Aissue%20state%3Aopen%20label%3Aclang-tidy) issues in LLVM |

As an artifact, each job create tracking issue in current repository that links to an issue in
[LLVM](https://github.com/llvm/llvm-project) repository. Each issue has a **Verdict**, **Godbolt Link** and
recommended **Type**/**Tags** to apply for upstream LLVM issue.
Maintainers should double check Type/Tags before applying them to LLVM issue.

### How to tag old issues

One of the workflows discovers "untagged old issues".
An untagged issue is one that's open, labeled `clang-tidy` but missing a
GitHub Issue Type or every recognized triage label:

- `false-positive`
- `false-negative`
- `enhancement`
- `check-request`
- `documentation`
- `build-problem`
- `code-cleanup`
- `metaissue`
- `question`

See the live list at [untriaged clang-tidy issues](https://github.com/llvm/llvm-project/issues?q=is%3Aissue+is%3Aopen+label%3Aclang-tidy+-label%3Afalse-positive+-label%3Afalse-negative+-label%3Aenhancement+-label%3Acheck-request+-label%3Adocumentation+-label%3Abuild-problem+-label%3Acode-cleanup+-label%3Ametaissue+-label%3Aquestion+no%3Atype).

Maintainer should apply appropriate **Type**/**Tags** for untagged LLVM issue, or close it if no longer valid.
After resolving upstream LLVM issue, close corresponding issue in this repository as completed.

## When to close issues in this repository

Close a tracking issue once you've handled it, for both labels - closing is
permanent and the bot won't auto-retry it.

To force a re-triage (e.g. the check was fixed upstream, or the agent got it wrong), comment `/redo`
on the tracking issue. The bot re-runs the same analysis and posts the fresh result as a new comment.
