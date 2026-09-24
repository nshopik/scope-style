---
name: scope-mr
description: >
  Merge-request / pull-request description writer. Review-facing text in up to four parts —
  why it is needed (the problem removed or the capability added), how the change addresses
  it, the root cause of a fixed bug, then any behaviour a reviewer cannot read off the diff —
  never a restatement of the commits. Use when writing or editing an MR/PR description
  (`glab mr create`, `gh pr create`, `-f description=`). Also the rule source the
  `body-cap.py` PreToolUse hook quotes back when it blocks one. Commit messages: use
  `scope-commit` instead.
---

MR description is review-facing. Different text from the commit body. Never `--fill`.

`hooks/body-cap.py` extracts the `## <id>` sections below verbatim and shows
them when an MR/PR command is blocked. Edit rules here — the hook holds no prose. Keep
heading ids stable; sub-headings stay `###` (any `##` closes a section); `{over_cap}` is
a hook-filled placeholder.

## mr-style

{over_cap}Reviewer has the diff open and ten minutes. They read code, not your session.

### Shape

- Parts, in order: why, how, root cause, behaviour.
- Write each part in prose, `-` bullets, or a table.
- Two or more commands or snippets → one fenced block, a `#` comment per case; never inline code in bullets.
- Three or more numbers a reviewer would compare → one table, a row per case; never prose.
- Each part after why is optional.
- Nothing to say for a part → omit it.
- Under ~50 changed lines → one or two sentences. Anything else goes to the user.
- One fix repeated at several sites → a short why paragraph, then a short how paragraph.
- Four parts is the ceiling, never the target.
- Bugfix and feature share this shape; a feature has no root cause.

### Why

- Always first.
- One or two sentences.
- Bugfix: name the symptom removed.
- Feature: name what it adds and what it buys.
- Docs: name what was undocumented.
- Link the issue it closes.
- Commits already say everything → that one line is the whole description.

### How

- What the change does to resolve the why.
- Bullets when several independent pieces; one clause each.
- Big or multi-file diff → name the spot to read first, inside this part.
- Never narrate step-by-step control flow.

### Root cause

- Bugfix only.
- Why already names the cause → omit this part; never say it twice.
- Why the bug happened, in one or two sentences.
- Only a cause you verified. Unverified → omit this part; a guessed cause reads as a
  finding and outlives the guess.

### Names

- Describe behaviour in plain words; a backticked code name is the exception.
- User-facing name (flag, config key, metric, exit code, error string) → no limit.
- Code name (function, type, field — own code or library) → at most five distinct names in
  the whole text; repeating one costs nothing.

### Behaviour

- The part a reviewer cannot read off the diff.
- Bugfix leans here on the behaviour delta; feature on the user-facing surface and compat.
- A new or changed config, default, flag, output, or stat counter.
- A consequence the diff cannot show: breaking change, migration, security fix, revert.
- Data that starts or stops flowing.
- An interaction or precedence rule between the new knob and an existing one.
- Existing behaviour this change does not alter → not a part; tell the user it was left out.
- A decision worth questioning, written as behaviour — "when both set, whichever fires
  first wins", not "Decision worth challenging: ...".

### Never

- A rung rubric as a heading or lead-in: "Look at first", "Where to look first:",
  "Decision worth challenging:", "Blast radius:", "Riskiest part:".
- The ladder picks what to write; its rung names never appear in the text.
- A "deferred" or "left out" section → that item is an issue, not a description line.
- A bare content tag ("Default:", "Deferred:") names the thing, not the rubric — allowed.
- Per-commit summaries.
- Restatements of the diff.
- Restatements of a commit body, except its why, how, or root cause.
- A single-commit MR may use that commit's body as the description.
- A sentence the title already says: "this adds / documents / fixes X".
- Verification logs, test counts.
- Background already on the issue → link it, don't repeat it.
- Addressing the reader.
- Narrating your order of work.
- What you tried first, rules you rejected, follow-up ideas → issue.
- Risk-grading words: "riskiest", "dangerous", "be careful", "watch out".
- Mid-sentence bold.
- `*` bullets — use `-`.
- Hard-wrapped lines — one line per paragraph or list item.
- `Generated with Claude Code` or any other AI-attribution line, unless the user asks for one.

### Length

- Most descriptions fit well under 150 words.
- 300 hard cap.
- Fenced blocks and table rows do not count toward the cap.
- Never pad a short description toward either number.
- A small diff binds tighter than the ceiling: the budget scales with the change.
- Longer than the diff → cut parts, not words.

## rung-four

Description says something was deliberately left out. Apply the boundary, then re-run
the same command unchanged to pass.

- In-diff and fine: a knob inside the changed lines, a next step this change stops short of.
- Off-diff and not fine: an audit finding, a rule you rejected, a follow-up idea —
  however deliberate the omission.
- An off-diff item reads as scope the reviewer must evaluate; it is not in front of them.
- Fix: move it to an issue and cite the issue, or drop the line.

## fill

`--fill` writes the description from the commit message. Drop it, pass the description
explicitly (`--description`, `-f description=`), then re-run.

- Commit body = permanent history. Why the change exists.
- Description = review-facing. What to look at first.
- They coincide often enough that `--fill` looks harmless. That is how it stops the
  question being asked.
- Commits genuinely say everything → one line is a fine description. Write that line.

## Examples

❌ rubric headings, and sentences the diff already covers
```
Closes #39.

## What it does
- withRecover reports whether it panicked

## Look at first
flushDesignated.

## Challenge
whole-batch no_sink accounting.
```

✅ bugfix — why, how (bullets fine), behaviour; no rubric headings
```
A recovered panic in a flush worker was swallowed with no accounting, so
one bad frame could drop a whole batch while every alert stayed green.

`withRecover` now reports the panic, and the flush, spill, and best-effort
workers each charge the lost batch to their own drop counter. The crux is
`flushDesignated`, the shared durable-path helper both flush arms call.

Under a multi-primary config the whole batch is charged to `no_sink` even
when an earlier primary already succeeded; the single-primary default
never hits it.

Closes #39
```

✅ feature — why, then the user-facing behaviour to know
```
Adds an opt-in `client-wait-timeout` directive: a client waiting on
recursion longer than the limit gets SERVFAIL while recursion continues
in the background, so the cache still fills. Default `0` (disabled), no
existing behavior changes.

When both `client-wait-timeout` and `serve-expired-client-timeout` are
set, whichever fires first answers. A new `num.queries_client_wait_timeout`
counter reports how often it triggered.
```
