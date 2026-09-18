# CLAUDE.md

- Write skill rules as atomic `-` bullets, one condition and one action each; never as prose
  paragraphs.
- Keep rules out of `README.md`; it points at the skills instead of restating them.
- Keep `skills/*/evals/` out of git; the eval corpus is local and unpublished.
- Run evals with `--plugin-dir .`; without it they measure the installed plugin cache, not the
  working tree.
- In `hooks/test_body_cap.py`, match an over-cap deny on `-word ceiling`, not `ceiling`; the
  skill text the hook quotes back contains the bare word.
