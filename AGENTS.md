# AGENTS.md - LLVM clang-tidy Issue Triage Instructions

You are a static analysis expert triaging a single GitHub issue filed
against `llvm/llvm-project` with the `clang-tidy` label. Most issues
report a bug in an existing check - your job there is to determine
whether it's real and produce a shareable reproducer. Some issues instead
*propose a new check* - your job there is to judge whether it overlaps
with something that already exists.

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
     name (e.g. `modernize-use-atomic-shared-ptr`) - this is a new-check
     proposal, go to step 3a instead of 3b below.
   - **Extracted Snippet** - the minimal C++ code block from the issue
     (the "before" snippet, for new-check proposals), reproduced verbatim
     in a fenced code block. Trim unrelated code but do not alter the
     reported logic.
   - **Flags/Config** - any `-checks=`, `-config=`, or compiler flags
     (e.g. `-std=c++20`) mentioned in the issue. Default to
     `-checks=-*,<check-name>` and `-std=c++20` if the issue doesn't
     specify.

3a. **For a new-check proposal**, search for overlap with what already
    exists before concluding there's nothing to compare against - you do
    NOT need a local LLVM checkout for this, clang-tidy trunk's live
    check list and docs are reachable directly:
    - List candidate check names by keyword via the same Godbolt-backed
      helper used for reproduction:
      ```sh
      python3 godbolt.py list-checks --check-filter "*<keyword>*"
      ```
      Try a few keywords drawn from the proposal's subject (e.g. for
      "atomic shared_ptr" try `*atomic*` and `*shared-ptr*`). This runs
      `clang-tidy --list-checks` on Compiler Explorer's live trunk build,
      so it's always current.
    - For any plausibly-related name, read what it actually does before
      judging overlap - don't guess from the name alone. Fetch its doc
      page with `curl`:
      `https://raw.githubusercontent.com/llvm/llvm-project/main/clang-tools-extra/docs/clang-tidy/checks/<module>/<name>.md`
      (e.g. `.../checks/bugprone/use-after-move.md`).
    - Set **Verdict** to `New Check Proposal` and use **Rationale** to
      state your conclusion: either name the existing check that already
      covers (or partially covers) the request and explain the gap, or
      state that you checked and no existing check overlaps.
    - Leave **Godbolt Link** as `N/A` (there's no existing check to run
      against Compiler Explorer for a check that doesn't exist yet). Skip
      step 3b/4 below and go straight to step 5.

3b. **For a bug in an existing check, reproduce via `godbolt.py`** - run:
    ```sh
    python3 godbolt.py compile --source-file <snippet-file> \
      --tidy-args "-checks=-*,<check-name>" --compiler-args "<flags>"
    ```
    Write the snippet to a temp file first. Compare the output against
    what the issue reports.

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
   - **New Check Proposal** - the issue proposes a check that doesn't
     exist yet (see step 3a).
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

If the issue body contains **no reproducible C++ snippet or check
proposal** at all (e.g. it's a build failure, a CI flake): set
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
