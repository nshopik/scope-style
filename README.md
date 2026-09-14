# scope-style

A Claude Code plugin that keeps commit messages, MR/PR descriptions, and issues short and useful
to the people who read them.

- `scope-commit` skill: [Scoped Commits](https://scopedcommits.com/) subjects
  (`<scope>: <description>`), and a body only when it carries a fact the diff can't show.
- `scope-mr` skill: review-facing descriptions in up to three parts (intro, how, behaviour),
  never a restatement of the commits.
- `scope-issue` skill: issues in three parts (context, analysis, proposal) that can be started
  without the conversation that produced them.
- `body-cap.py` PreToolUse hook: checks `git commit`, `gh pr|issue create|edit`, and
  `glab mr|issue` commands before they run. It blocks rule violations and quotes the matching skill section back
  to Claude, so the fix happens in the same turn.

Status: under active tuning. Rules and caps change as they're measured against real repositories.

## Install

```
/plugin marketplace add nshopik/scope-style
/plugin install scope-style@scope-style
```

Requires `python3` on `PATH`.

The rules themselves are in each `SKILL.md`. The hook allows anything it can't parse.

## Development

Rules live in the `## <id>` sections of each `SKILL.md`; the hook holds only detection logic and
caps. Test a local checkout with:

```
claude --plugin-dir .
python3 hooks/test_body_cap.py
```

## License

MIT
