---
name: scope-issue
description: >
  Issue description writer. Issues are pulled from a board days or weeks later with no
  conversation context, so the text runs context, then problem, then a concrete proposal. Use
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

- Three parts, in order: context, problem, proposal.
- Context: the conditions that led here.
- Context opens the description unlabeled. No `## Context` heading.
- Problem: the defect or gap the context leads to, under `## Problem`.
- Proposal: the next step, under `## Proposal`. Always present.
- Proposal is concrete: a list of actions, a person to engage, or a scout's questions.
- Never end at the problem.

### Scout

- Proposal would need a guess or an assumption → scout issue, not a guessed proposal.
- Title starts `Scout:`.
- Proposal lists the questions to answer and a time box.
- Deliverable: a note in the repo's research docs plus one follow-up issue per gap found. No code.
- Done when every question has an answer or its own issue.

### Evidence

- Milestone exit gate is field evidence → one evidence issue in that milestone.
- Title starts `Evidence:`.
- Proposal lists what to deploy and where, the start date, the measurement, and how to collect it.
- Closes with the milestone.

### Meta

- Work spans milestones, or waits on features not built yet → one meta issue tracking it.
- Title starts `Meta:`.
- Proposal is a `- [ ]` checklist, one line per piece of work.
- A line is a child issue link, or plain text naming the feature it waits on.
- File a child issue only when its work can start; tick its box when it closes.
- No milestone; each child carries its own.
- Closes when every line is ticked or ruled out.

### Blockers

- Work cannot start until another issue closes → a `Blocked by #<n>` line, one per blocker.
- Blocker lines end the description.

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
- `- [ ]` boxes only for complex multi-stage work, or a meta issue's checklist.
- A paragraph contains an action → pull the action into an item; the paragraph keeps only the why.
- Terse only after the next action is stated. "Stand up the lab" is a title, not a description.

### Skimming

- Context: one paragraph, ~80 words. Never two.
- Context holds only what's needed to act. The reader already works on the project.
- Cite the brief or docs for depth; don't repeat them.
- Problem carries the substance. Longest part.
- Proposal is the outro.

### Format

- Bold the claim a skimmer must land on, not a keyword.
- One bolded phrase per paragraph at most.
- Inline code for identifiers only: file, path, command, config key, label, version, symbol.
- No inline code for emphasis or ordinary nouns.
- Two or more commands or snippets → one fenced block, a `#` comment per case; never inline code in bullets.
- One line per paragraph or list item; never hard-wrap.

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

- ~250 words the shape. 500 hard cap.
- Fenced blocks are evidence, not prose; they don't count toward the cap.
- Context overgrows first. Cut it first.
