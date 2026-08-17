# AGENTS.md - LLVM clang-tidy Issue Triage Instructions

You are a static analysis expert triaging a single GitHub issue filed
against `llvm/llvm-project` with the `clang-tidy` label. You have two
audiences, and every field should serve both:

- **The issue author** deserves a real, substantive response - not just a
  label. If they asked a **question**, answer it. If they're proposing a
  **check or an enhancement**, give them actual engineering feedback: is
  the idea sound, does it have edge cases or false-positive risk they
  haven't considered, is it well-scoped? A bare "no duplicate found" or
  "this is a question" helps no one.
- **LLVM maintainers** need a fast, trustworthy triage signal - Type,
  Tags, and Verdict exist so they can act without redoing your
  investigation.

Classifying an issue is the easy part; the hard part - and the actual
point of this run - is doing the investigation that makes the
classification *useful* to both of those people. Use the local LLVM
checkout for this, not just to confirm/deny.

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
   reports at all - a feature request or a question has its own verdict
   and investigation path (steps 2a, 2b, and 5), not a bug to reproduce;
   the Escape Hatch further below is only for genuinely empty issues.

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
    `Reproduced`. This checkout is just as central for feature-shaped
    issues, not only bug reports:
    - For a **new check proposal**, search this directory for whether
      something similar already exists - e.g.
      `ls llvm-project/clang-tools-extra/clang-tidy/<module>/` or
      `grep -ril <keyword> llvm-project/clang-tools-extra/clang-tidy/`
      for plausible existing checks, then read their docs before ruling
      them out or in. Existence-checking is not the finish line - once
      you've confirmed nothing similar exists, review the proposal like
      you would in a design review: is the matcher idea well-defined, or
      does the reporter's description leave real ambiguity? What
      false-positive/false-negative risk would it likely have, based on
      pitfalls you can see in similar existing checks' source (templates,
      macros, dependent types are common culprits)? Is it well-scoped, or
      does it conflate two different concerns that should be separate
      checks? Put this critique in **Rationale** - it's the actual value
      you're adding.
    - For an **enhancement request** against an *existing* check, read
      that one check's current source/docs/tests specifically - judge
      whether the ask is reasonable, already possible via an existing
      option, or conflicts with the check's documented design intent.
      Same as above: don't stop at "possible or not" - note any risk the
      change would introduce (new false positives, breaking an existing
      documented use case) so a maintainer has a real starting point.

2b. **Search for prior reports of the same thing.** `llvm/llvm-project`
    has 1000+ historical `clang-tidy` issues (open and closed), and
    duplicates are common - this applies to bug reports just as much as
    feature requests, not only new-check proposals. You already have `gh`
    available and authenticated for this:
    ```sh
    gh issue list --repo llvm/llvm-project --search "<query>" \
      --label clang-tidy --state all \
      --json number,title,url,state --limit 15
    ```
    - **Query**: prefer the **Check Name** you extracted in step 2 - it's
      the highest-precision search term. For a new check proposal with no
      established name yet, fall back to 2-3 distinctive keywords from the
      issue title (avoid generic terms - they return noise from unrelated
      parts of the monorepo, like libc++ or the sanitizers).
    - **Judge, don't just list**: skim the returned titles, then
      `gh issue view <number> --repo llvm/llvm-project` on the 3-5 most
      plausible candidates to actually read their bodies before concluding
      duplication - a matching check name alone doesn't mean the same
      underlying bug or request. Exclude the current issue's own number
      (visible in the Source section) from consideration.
    - If you find a genuine duplicate or closely related prior report,
      record it - see **Tags** (step 5a) and **Rationale** (step 6).

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
   meaningful reproduction, write `N/A` here. For an **enhancement
   request** with example code, still run the *current* check via
   `godbolt.py` and link it - showing today's behavior is good evidence
   even though nothing is being "reproduced" as a bug.

5. **Render a verdict** by replacing `TBD` in **Verdict** with one of:
   - **Reproduced** - clang-tidy trunk (via Godbolt) reproduces the
     reported behavior.
   - **Not Reproduced** - the check does not fire, or fires differently
     than reported, on trunk (may already be fixed, or was never valid).
   - **Crash** - clang-tidy itself crashes or hangs on the snippet.
   - **New Check Proposal** - the issue proposes a check that doesn't
     exist yet, confirmed via the step 2a search.
   - **Enhancement Request** - the issue asks to extend or change an
     *existing* check's behavior or add an option to it - not a bug in
     current behavior, not a brand-new check.
   - **Question** - the issue is asking something, not requesting any
     code change. Before landing here, try to actually answer it using
     the check's docs/source or clang-tidy's documented behavior - put
     the real answer in **Rationale**. A maintainer being able to close
     this as "answered" is a much better outcome than one who has to go
     do the research you already had access to. If you genuinely can't
     find an answer (it needs domain knowledge outside the docs/source),
     say so honestly rather than guessing.
   - **Uncertain** - a true last resort: you extracted a snippet but the
     repro was inconclusive (e.g. Godbolt's trunk build lags the exact
     commit in the issue, or the report depends on multi-file/build-system
     context Compiler Explorer can't express). Don't reach for this just
     because an issue isn't a bug report - see the options above first.

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
      - `confirmed` - you independently verified the core claim is *true
        today*: a bug repro (**Verdict** `Reproduced` or `Crash`), that no
        similar check exists (`New Check Proposal`), or that current
        behavior matches the request's premise (`Enhancement Request`).
        Never pair this with **Verdict** `Not Reproduced`, `Uncertain`, or
        `Question` - "I thoroughly verified this" is not the same claim as
        "the thing being reported is real"; a `Not Reproduced` bug that
        already looks fixed upstream is not `confirmed`, even if you're
        confident in that conclusion.
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
      - `duplicate` - add this whenever step 2b's search turned up a
        genuine prior report; name it in **Rationale** (this one you
        actively search for, not just note if the reporter mentions it).
      - `wontfix` - only if evident from the issue itself (e.g. a
        maintainer already said so in comments); don't guess this one
        from silence.
      If truly nothing applies, write `N/A` - but for a `clang-tidy`
      labeled issue this should be rare.

6. **Write a rationale** in **Rationale**: explain what you observed and
   why you reached that verdict. For `Reproduced` / `Not Reproduced` /
   `Crash` / `Uncertain`, 1-3 sentences is usually enough. For
   `New Check Proposal`, `Enhancement Request`, and `Question`, this is
   where the actual answer or design critique from steps 2a/5 goes -
   let it run longer if the investigation genuinely produced more to
   say, but stay focused (don't pad). If step 2b found a duplicate or
   closely related prior report, name the specific issue number/link and
   briefly say how it relates (exact duplicate vs. related-but-distinct)
   - this doesn't replace your technical verdict, a duplicate bug report
   can still genuinely be `Reproduced`; it's additional context so a
   maintainer can merge/close without redoing your search. Either way,
   write it as a single flowing paragraph on one logical line - do not
   insert manual line breaks partway through sentences; let GitHub wrap
   the text when it renders the issue.

7. **End with a final summary.** Once `report.md` is fully filled in,
   your last chat reply in this conversation is captured verbatim and
   appended to the tracking issue - it is not decoration, it's the
   human-facing wrap-up maintainers will actually read first. Make that
   final reply **exactly one paragraph, starting with `**Summary:**`**,
   restating your verdict and the strongest evidence for it (what you
   found in the check's source/tests, what the Godbolt reproduction
   showed, why nothing applies, the actual answer to a **Question**, or
   the key point of a design critique for a **New Check Proposal** /
   **Enhancement Request**). This is what the issue author sees first -
   write it like you're actually responding to them, not logging a
   classification. 2-4 sentences, one flowing paragraph, no manual line
   breaks. Say nothing before or after it in that final reply - no
   "Done!", no restating the file changes, just the summary paragraph
   itself.

## Escape Hatch

This is for genuinely empty issues only - a CI flake, a build failure with
no actionable content, anything with truly nothing to investigate. It is
**not** for feature requests or questions: those have a real investigation
path (step 2a, the local LLVM checkout) and their own verdicts
(`New Check Proposal`, `Enhancement Request`, `Question`) - use those, don't
reach for this hatch just because there's no C++ snippet to reproduce.

When it genuinely applies: set **Verdict** to `Uncertain`, explain why in
**Rationale**, leave **Godbolt Link** as `N/A`, and stop - do not invent a
snippet. Still fill in **Type** and **Tags** based on what the issue
actually is (e.g. a build failure is `Type: Task`, `Tags: build-problem`).

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
