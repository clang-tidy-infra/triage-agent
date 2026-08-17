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

As artifacts, all jobs create tracking issue in current repository that links to an issue in
[LLVM](https://github.com/llvm/llvm-project) repository has a **Verdict**, **Godbolt Link** and
recommended **Type**/**Tags** for the LLVM issue.
Maintainers should double check it and then apply the Type/Tags to the LLVM issue if it looks right.

### How to tag old issues

An untagged old issue is one that's open, labeled `clang-tidy` but missing a
GitHub Issue Type and every recognized triage label:

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
After that, close the issue in this repository as completed - the issue was successfully triaged.

## When to close issues in this repository

Close a tracking issue once you've handled it, for both labels - closing is
permanent and the bot won't auto-retry it.

To force a re-triage (e.g. the check was fixed upstream, or the agent got it wrong), comment `/redo`
on the tracking issue. The bot re-runs the same analysis and posts the fresh result as a new comment.
