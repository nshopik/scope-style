---
name: scope-commit
description: >
  Scoped Commits message generator (https://scopedcommits.com/): `<scope>: <description>`
  subject, body only when the "why" isn't obvious. Use when writing or amending a commit
  message. Also the rule source the `body-cap.py` PreToolUse hook quotes back when it
  blocks a `git commit`. MR/PR descriptions: use `scope-mr` instead.
---

Subject `<scope>: <description>`. Body = the why. Most commits don't need one.

`hooks/body-cap.py` extracts the `## <id>` sections below verbatim and shows
them when a commit is blocked. Edit rules here — the hook holds no prose. Keep heading
ids stable; sub-headings stay `###` (any `##` closes a section); `{subject}`,
`{problems}`, `{over_cap}` are hook-filled placeholders.

## subject

Commit subject `{subject}` breaks Scoped Commits (https://scopedcommits.com/):
{problems}
Rewrite it, then re-run.

### Shape

- `<scope>: <description>`. Scope lowercase.
- Imperative: "add", "fix", "remove". Never "added" / "adds" / "adding".
- ≤50 chars target. 72 hard cap.
- No trailing period.

### Scope

- Names the area touched: `ansible:`, `preseed:`, `docs:`, `watchdog:`.
- Never the kind of change: no `feat:`, `feature:`, `chore:`, `perf:`, `style:`.
- Several areas → one broader scope. Else comma-separate.
- Tree-wide → `treewide:`.
- A project `CLAUDE.md` scope vocabulary or stricter pattern wins.

## commit-style

{over_cap}### When a body earns its place

- Default: no body.
- Write one only to carry a fact the diff cannot show: the original problem, why this
  approach, a known limit.
- Name that fact before you start. Can't name it → padding.
- Runs past one paragraph → padding.
- Always a body: breaking changes, security fixes, data migrations.

### Content

- Cite, don't restate. Issues and `docs/decisions/` by number.
- A diff that is itself prose — docs, rules, comments, config — is cited the same way,
  never re-explained.
- No work log: verification output, test counts, sweep tables. CI's job.
- No review-facing content. That is the MR description.

### Format

- ~80 words the shape. 160 hard cap. Length tracks rationale, not diff size.
- Wrap at 72 columns (`git log` indents four; patches stay under RFC 2822's 78).
- Bullets `-`, never `*`.
- Issue refs (`Closes #42`) on their own line at the end.

## body-issues

Commit body breaks style:
{problems}
Rewrite it, then re-run.

- Impersonal prose. No self-narration.
- No "I" / "we".
- No "now" / "currently".
- Wrapped at 72.

## trailers

- Follow-up fix to your own commit → `git commit --amend`. One logical change, one commit.
- Reverts and merges keep Git's default format.
- A revert adds one line saying why.

## Examples

❌ `feat: added a new endpoint to get user profile information from the database`

✅
```
api: add GET /users/:id/profile

Mobile needs profile data without the full user payload — cold-launch
on LTE was fetching 40 KB to render three fields.

Closes #128
```

✅ subject-only, needs no body: `spill: drop unused zstd level knob`
