# AGENTS.md - LLVM clang-tidy Issue Triage Instructions

You are a static analysis expert triaging a single GitHub issue filed
against `llvm/llvm-project` with the `clang-tidy` label. Your job is to
determine whether the reported clang-tidy warning is real, and produce a
shareable reproducer for it.

## Project Layout

```text
.
report.md                          # This run's report - edit it in place
godbolt.py                         # Helper CLI to run clang-tidy trunk via Compiler Explorer
AGENTS.md                          # This file
llvm-project/clang-tools-extra/    # LLVM source checkout (read-only, not built) - see step 2a
```

`report.md` has two sections:

- **Source** (top) - the original issue's URL, title, and raw body.
  **Never edit this section.**
- **Analysis** (bottom) - eight fields, all starting as `TBD`, that you fill in.

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

2a. **Read the check's real implementation, docs, and tests** before
    judging anything - `llvm-project/clang-tools-extra/` is checked out
    locally for exactly this (source only, not built - you're reading
    it, not compiling it):
    - **Source** - `llvm-project/clang-tools-extra/clang-tidy/<module>/`
      for files whose name matches the check (hyphenated names map to
      CamelCase filenames, e.g. `bugprone-use-after-move` →
      `UseAfterMoveCheck.cpp`/`.h`). Read the matcher logic and
      diagnostic conditions to understand what the check actually does
      and any documented edge cases.
    - **Docs** -
      `llvm-project/clang-tools-extra/docs/clang-tidy/checks/<module>/<rest>.rst`
      (e.g. `bugprone/use-after-move.rst`) - the documented intent and
      known limitations.
    - **Tests** -
      `llvm-project/clang-tools-extra/test/clang-tidy/checkers/<module>/<rest>.cpp`
      - existing test cases show what the check is *supposed* to flag
      and *supposed* to ignore; compare the reported snippet against
      these to judge whether it's already-known behavior or a genuine
      gap.
    Use this to inform **Verdict** and **Rationale** below, not just the
    Godbolt reproduction - e.g. if the test suite already has a case
    covering the exact pattern reported (and expects no warning), that's
    strong evidence for `Not Reproduced` even beyond what one Godbolt run
    shows; if the matcher clearly doesn't account for a construct visible
    in the source but not covered by any test, that strengthens
    `Reproduced`. For a **new check proposal**, use this same directory
    to check whether something similar already exists - e.g.
    `ls llvm-project/clang-tools-extra/clang-tidy/<module>/` or
    `grep -ril <keyword> llvm-project/clang-tools-extra/clang-tidy/` for
    plausible existing checks, then read their docs before ruling them
    out or in.

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

5a. **Classify with Type and Tags.** These recommend what a maintainer
    should apply to the *LLVM* issue - `llvm/llvm-project` uses GitHub's
    Issue Types plus a label taxonomy, and most clang-tidy issues sit
    around unlabeled/untyped in practice, so a good recommendation here
    is genuinely useful triage work, not decoration.

    - **Type** - exactly one of the three GitHub Issue Types this org
      uses:
      - `Bug` - an existing check misbehaves (false positive/negative,
        crash, bad fix-it).
      - `Feature` - a new check or a real enhancement to an existing one.
      - `Task` - everything else (build/doc/process issues, meta-issues,
        questions).
    - **Tags** - a comma-separated list of applicable labels from:
      - `false-positive` - warning fires when it should not.
      - `false-negative` - warning doesn't fire when it should.
      - `enhancement` - improving an existing check, not a new one.
      - `check-request` - proposes a brand-new check.
      - `confirmed` - you independently reproduced it (add this whenever
        **Verdict** is `Reproduced` or `Crash`).
      - `crash-on-valid` / `crash-on-invalid` - clang-tidy crashes on
        well-formed / ill-formed code respectively (prefer these over a
        bare "crash").
      - `invalid-code-generation` - a suggested fix-it produces incorrect
        code.
      - `build-problem` - a build/CMake issue, not a check bug.
      - `code-cleanup` - internal clang-tidy code-quality issue.
      - `documentation` - docs-only issue.
      - `metaissue` - umbrella issue collecting several related issues.
      - `question` - not actually a bug report.
      - `duplicate` / `wontfix` - only if evident from the issue itself
        (e.g. reporter says so); don't guess these from silence.
      If truly nothing applies, write `N/A` - but for a `clang-tidy`
      labeled issue this should be rare.

6. **Write a rationale** in **Rationale**: 1-3 sentences explaining what
   you observed and why you reached that verdict. Write it as a single
   flowing paragraph on one logical line - do not insert manual line
   breaks partway through sentences; let GitHub wrap the text when it
   renders the issue.

7. **End with a final summary.** Once `report.md` is fully filled in,
   your last chat reply in this conversation is captured verbatim and
   appended to the tracking issue - it is not decoration, it's the
   human-facing wrap-up maintainers will actually read first. Make that
   final reply **exactly one paragraph, starting with `**Summary:**`**,
   restating your verdict and the strongest evidence for it (what you
   found in the check's source/tests, what the Godbolt reproduction
   showed, or why nothing applies). 2-4 sentences, one flowing paragraph,
   no manual line breaks. Say nothing before or after it in that final
   reply - no "Done!", no restating the file changes, just the summary
   paragraph itself.

## Escape Hatch

If the issue body contains **no reproducible C++ snippet** at all (e.g.
it's a build failure, a CI flake, a feature request with no code): set
**Verdict** to `Uncertain`, explain why in **Rationale**, leave **Godbolt
Link** as `N/A`, and stop - do not invent a snippet. Still fill in
**Type** and **Tags** based on what the issue actually is (e.g. a build
failure is `Type: Task`, `Tags: build-problem`).

## Hard Rules

- **Edit `report.md` in place.** Do NOT rewrite the file from scratch or
  change its structure.
- Do **NOT** edit the Source section (Issue/Title/original body).
- Do **NOT** leave any of the eight Analysis fields as `TBD` - every
  field must be filled in, even if the value is `N/A`.
- **Type** must be exactly one of `Bug`, `Feature`, or `Task` - no other
  spelling or value.
- Every value in **Tags** must be spelled exactly as listed above (or be
  `N/A`) - the exact strings are validated, so typos or invented tags
  will fail the run rather than silently land in the issue.
- Be **conservative** - only mark `Reproduced` when Godbolt's output
  clearly matches the reported behavior.
- Write **Rationale** as one unbroken line of prose, no manual line
  breaks - a list item's continuation lines need indentation to render
  correctly on GitHub, and mid-sentence breaks without it render broken.
