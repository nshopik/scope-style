---
name: scope-issue
description: >
  Issue description writer. Issues are pulled from a board days or weeks later with no
  conversation context, so the text runs context, then analysis, then a concrete proposal. Use
  when writing or editing an issue (`gh issue create`, `glab issue create`, `-f description=`).
  Also the rule source the `body-cap.py` PreToolUse hook quotes back when it blocks one. Commit
  messages: use `scope-commit`; MR/PR descriptions: use `scope-mr`.
---

Issue is actionable items, not prose. Read days or weeks later with zero conversation context.

`hooks/body-cap.py` extracts the `## <id>` sections below verbatim and shows them when an issue
command is blocked. Edit rules here — the hook holds no prose. Keep heading ids stable;
sub-headings stay `###` (any `##` closes a section); `{over_cap}` is a hook-filled placeholder.

## issue-style

{over_cap}Reader starts the task from the description alone — no comment threads, no chat history.

### Goal

- Every issue answers: what do I do next.
- Every issue answers: how do I know it's done.

### Shape

- Three parts, in order: context, analysis, proposal.
- Context: the conditions that led here.
- Context opens the description unlabeled. No `## Context` heading.
- Analysis: the problem or idea the context leads to, under `## Analysis`.
- Proposal: the next step, under `## Proposal`. Always present.
- Proposal is concrete: a list of actions, a person to engage, or a named investigation.
- Never end at analysis.

### Title

- Under 80 chars.
- Name the thing, not the history.
- ❌ "Refactoring the plugins structure to take into account changes in the Express.js library".
- ✅ "Plugins structure refactoring".

### Items

- Multi-part work → `-` bullet list.
- Each item independently completable and verifiable.
- Done-condition not obvious from the items → state it.
- Default: plain `-` bullets.
- `- [ ]` boxes only for complex multi-stage work, or a meta issue tracking other issues.
- A paragraph contains an action → pull the action into an item; the paragraph keeps only the why.
- Terse only after the next action is stated. "Stand up the lab" is a title, not a description.

### Skimming

- Context: one paragraph, ~80 words. Never two.
- Context holds only what's needed to act. The reader already works on the project.
- Cite the brief or docs for depth; don't repeat them.
- Analysis carries the substance. Longest part.
- Proposal is the outro.

### Format

- Bold the claim a skimmer must land on, not a keyword.
- One bolded phrase per paragraph at most.
- Inline code for identifiers only: file, path, command, config key, label, version, symbol.
- No inline code for emphasis or ordinary nouns.

### Names

- Describe behaviour in plain words; a backticked code name is the exception.
- User-facing name (flag, config key, metric, exit code, error string) → no limit.
- Code name (function, type, field — own code or library) → at most three backticked
  occurrences in the whole text.

### Updates

- Findings, decisions, progress → comments.
- A finding changes the work remaining → update the description too.
- Description is the current spec. Comments are the log.

### Length

- ~200 words the shape. 400 hard cap.
- Context overgrows first. Cut it first.
