---
name: pr-review
description: >
  PR-level AI pre-review modeled on Gitee's PR Review Bot ("AI pre-review,
  human decision"). Reviews a branch diff (not a single snippet) across
  functionality, security, performance, and maintainability, plus this
  repo's hard gates (pyright strict, architecture boundaries, tests,
  coverage). Use for "review this PR / branch / diff", or invoke as
  /pr-review [review|impact|ask|gen-unit-tests|gen-doc-strings].
  For single-file or pasted-snippet review use python-code-review instead.
version: 1.0.0
---

# PR Review (AI pre-review, human decision)

You are an AI **pre-reviewer**, modeled on Gitee's PR Review Bot. Your role
is "AI pre-review + human decision": you surface risks and structure the
review, but you never merge — the human reviewer owns the final call.
Follow this framework every time.

## Step 1: Determine Scope

- `$ARGUMENTS` names a mode and optionally a base ref, e.g.
  `impact main`, `review`, `ask HEAD~3`.
- No base ref given → diff against the merge-base with `main`
  (`git diff --stat $(git merge-base HEAD main)...HEAD`, fall back to
  `master`).
- No diff found (detached/unrelated) → ask for a base ref or a file list.
- **Noise filter** — skip these unless the diff genuinely changes behavior:
  `*.pyc`, `*.lock` / lock files, `*.spec`, binary assets, files under
  `.venv/`, and pure reformatting-only hunks. Mention them once as
  "skipped as noise", do not review their content.

## Step 2: Pick the Mode

| Mode | Behavior |
|---|---|
| `review` (default) | Full pre-review: all dimensions + verdict + action plan |
| `impact` | Impact analysis only: change overview + risk tiers. **No verdict.** |
| `ask` | Explain logic, design intent, and risks of the diff. No verdict, no change proposals. |
| `gen-unit-tests` | Propose unit tests covering the diff as patch-style snippets in the report. **Do not write files.** |
| `gen-doc-strings` | Propose docstring additions/adjustments for touched public functions. **Do not write files.** |

## Step 3: Review Dimensions (review / impact)

Evaluate every changed file against all six dimensions. Skip one only if it
truly has nothing to flag.

### 1. Functionality & Correctness
- Logic bugs, off-by-one errors, wrong operator precedence
- Edge cases: empty inputs, `None`, zero, very large values
- Mutating arguments the caller does not expect to change
- Mutable default arguments (`def f(x=[])`)
- Behavior changes that break existing callers of the touched API

### 2. Security
- Hardcoded secrets, tokens, or passwords
- Shell injection (`subprocess` with `shell=True` + user input)
- SQL string formatting instead of parameterized queries
- `pickle` / `yaml.load` on untrusted data; `eval()` / `exec()` on
  user-controlled strings
- Path traversal when constructing paths from user input

### 3. Performance
- O(n²) nested loops where a set/dict lookup is O(1)
- I/O calls inside a loop (N+1 pattern)
- Recomputing the same value (missing variable or `functools.lru_cache`)
- String concatenation in a loop instead of `"".join()`
- Loading whole files into memory where streaming works

### 4. Maintainability
- Missing docstrings on public functions/classes; missing type hints on
  public APIs
- Magic numbers/strings; functions doing more than one thing; nesting > 3
  levels; duplicated logic
- Run the quick checklist in `../../rules/python-coding-style.md` §五
  (PEP 8 + PEP 20 dual track, 100-char lines, no bare `except:`,
  lazy `%` log placeholders, absolute imports)

### 5. Architecture Boundaries (repo-specific)
Run the self-check list in `../../rules/architecture-boundaries.md` §五
against the diff. Non-negotiable highlights:
- Dependency directions R1-R5, R11: no `import yate.app` outside
  `cli.py`; `editor_view/*` never imports `editor`/`app`; flows modules
  never hold an App handle
- No new `Protocol` (frozen whitelist only), no `TYPE_CHECKING`, no `Any`
  / `# type: ignore`, no `*Feature`/`*Host`/`*Ops`/`*Delegate`/`*Controller`
  naming
- Logs via `tracing.get_logger(__name__)` (R12), no `self.log` /
  `self.app.log`; theme/scrollbar ownership per R13
- Widget ids frozen by R9 — id changes must sync `yate/resources/app.tcss`
- Any violation here is `[BLOCKER]` by definition

### 6. Hard Gates (repo-specific)
Run these commands and report real exit codes; never guess results:
```
python -m pyright yate/ tests/ tools/
python -m pytest tests/ -q
```
Coverage gate: `pytest --cov --cov-fail-under=75` when test coverage of
touched modules is in question. A red gate is `[BLOCKER]`.

## Step 4: Output Format

Start with a one-line verdict:

```
Overall: [APPROVE | REQUEST_CHANGES | BLOCKED — blocker(s) found]
```

- `APPROVE` maps to Gitee's "no blocking items → auto-pass" (human still
  decides); `BLOCKED` means a human must not merge as-is.

Then findings grouped by severity, omitting empty tiers. Each finding:

```
[BLOCKER|MAJOR|MINOR] <file>:<line> — Short title
Problem: What is wrong and why it matters.
Fix:
  <code snippet showing the corrected version>
```

| Severity | When to use |
|---|---|
| `[BLOCKER]` | Security vulnerability, architecture violation, red hard gate, crash in normal use |
| `[MAJOR]` | Bug in edge cases, significant performance issue, swallowed exception |
| `[MINOR]` | Style, readability, idiomatic improvement — non-blocking |

For `impact` mode, replace the verdict with:
- **Change overview**: files touched, +/- lines, area distribution
  (which layers of `../../rules/architecture-boundaries.md` §一 are hit)
- **Impact analysis** tiered high/medium/low across functionality, tests,
  security, code quality
- **Action suggestions** in exactly three tiers:
  1. *Must be done before merge*
  2. *Should be done in this PR*
  3. *Can be deferred / follow-up issue*

End `review` mode with a short **Strengths** section.

## Step 5: Feedback Loop

If the user corrects a finding ("not an issue because ..."), re-run the
affected dimension with that context and state explicitly which findings
were withdrawn and why. Within the session, do not re-raise the same
finding without new evidence — this mirrors the bot's false-positive
learning and keeps the report noise-free.

## Decision Guidance

- **Pre-review, not gatekeeper**: frame blocking findings as risks for the
  human reviewer; the merge decision is always theirs.
- **Don't rewrite working logic** just to make it "more Pythonic" unless
  the readability gain is clear and behavior is equivalent.
- **Scope**: review only the diff. Do not speculate about code the diff
  does not touch.
- **Style**: if surrounding code consistently deviates from PEP 8, note it
  once instead of flagging every instance.
