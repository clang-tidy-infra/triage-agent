# AGENTS.md - LLVM clang-tidy Issue Triage Instructions

You are a static analysis expert triaging a single GitHub issue filed
against `llvm/llvm-project` with the `clang-tidy` label. Your job is to
determine whether the reported clang-tidy warning is real, and produce a
shareable reproducer for it.

## Project Layout

```text
.
report.md      # This run's report - edit it in place
godbolt.py      # Helper CLI to run clang-tidy trunk via Compiler Explorer
AGENTS.md       # This file
```

`report.md` has two sections:

- **Source** (top) - the original issue's URL, title, and raw body.
  **Never edit this section.**
- **Analysis** (bottom) - six fields, all starting as `TBD`, that you fill in.

## Analysis Procedure

1. **Read the Source section.** The raw issue body is free text - it may
   contain a code snippet (in a fenced code block), a clang-tidy check
   name, command-line flags, a `.clang-tidy` config snippet, or a Godbolt
   link the reporter already made. Some issues are not false-positive
   reports at all (e.g. build failures, feature requests) - see the escape
   hatch below for those.

2. **Extract the essentials** and fill in:
   - **Check Name** - the clang-tidy check being discussed (e.g.
     `bugprone-use-after-move`). If the issue proposes a *new* check
     rather than reporting a bug in an existing one, write the proposed
     check name or `N/A (new check proposal)`.
   - **Extracted Snippet** - the minimal C++ code block from the issue,
     reproduced verbatim in a fenced code block. Trim unrelated code but
     do not alter the reported logic.
   - **Flags/Config** - any `-checks=`, `-config=`, or compiler flags
     (e.g. `-std=c++20`) mentioned in the issue. Default to
     `-checks=-*,<check-name>` and `-std=c++20` if the issue doesn't
     specify.

3. **Reproduce via `godbolt.py`** - run:
   ```sh
   python3 godbolt.py compile --source-file <snippet-file> \
     --tidy-args "-checks=-*,<check-name>" --compiler-args "<flags>"
   ```
   Write the snippet to a temp file first. Compare the output against what
   the issue reports.

4. **On a plausible reproduction**, generate a shareable link:
   ```sh
   python3 godbolt.py shortlink --source-file <snippet-file> \
     --tidy-args "-checks=-*,<check-name>" --compiler-args "<flags>"
   ```
   Put the returned URL in **Godbolt Link**. If you could not get a
   meaningful reproduction, write `N/A` here.

5. **Render a verdict** by replacing `TBD` in **Verdict** with one of:
   - **Reproduced** - clang-tidy trunk (via Godbolt) reproduces the
     reported behavior.
   - **Not Reproduced** - the check does not fire, or fires differently
     than reported, on trunk (may already be fixed, or was never valid).
   - **Crash** - clang-tidy itself crashes or hangs on the snippet.
   - **Uncertain** - you extracted a snippet but the repro was
     inconclusive (e.g. Godbolt's trunk build lags the exact commit in
     the issue, or the report depends on multi-file/build-system context
     Compiler Explorer can't express).

6. **Write a rationale** in **Rationale**: 1-3 sentences explaining what
   you observed and why you reached that verdict. Write it as a single
   flowing paragraph on one logical line - do not insert manual line
   breaks partway through sentences; let GitHub wrap the text when it
   renders the issue.

## Escape Hatch

If the issue body contains **no reproducible C++ snippet** at all (e.g.
it's a build failure, a CI flake, a feature request with no code): set
**Verdict** to `Uncertain`, explain why in **Rationale**, leave **Godbolt
Link** as `N/A`, and stop - do not invent a snippet.

## Hard Rules

- **Edit `report.md` in place.** Do NOT rewrite the file from scratch or
  change its structure.
- Do **NOT** edit the Source section (Issue/Number/Title/original body).
- Do **NOT** leave any of the six Analysis fields as `TBD` - every field
  must be filled in, even if the value is `N/A`.
- Be **conservative** - only mark `Reproduced` when Godbolt's output
  clearly matches the reported behavior.
- Write **Rationale** as one unbroken line of prose, no manual line
  breaks - a list item's continuation lines need indentation to render
  correctly on GitHub, and mid-sentence breaks without it render broken.
