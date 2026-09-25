# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/2.0.0/).

## [Unreleased]

## [0.3.6] - 2026-09-25

### Added

- `scope-issue` writes a `Scout:` issue, with questions and a time box, when a proposal would need
  a guess.

## [0.3.5] - 2026-09-25

### Changed

- `scope-mr` opens a bugfix description with what the code did wrong, not where it happens or what
  it caused.
- `scope-mr` leaves before/after measurements out of a description.

## [0.3.4] - 2026-09-25

### Changed

- `scope-mr` writes a small fix repeated at several sites as a short why paragraph and a short how
  paragraph.

## [0.3.3] - 2026-09-20

### Added

- `scope-mr` puts three or more numbers a reviewer would compare in a table, not prose.

### Changed

- `body-cap.py` does not count table rows toward a body's word ceiling.

## [0.3.2] - 2026-09-18

### Changed

- `scope-issue` and `scope-mr` put two or more commands in one fenced block, not inline code.

### Fixed

- `body-cap.py` measures `gh api` PR/issue bodies and bodies passed by `$(cat <file>)`, `--input`,
  or a heredoc-written file.

## [0.3.1] - 2026-09-18

### Added

- `package.json` declaring the skills as a pi package, installable with `pi install`.

### Changed

- `scope-issue` and `scope-mr` ban hard-wrapped lines in descriptions.

## [0.3.0] - 2026-09-18

### Changed

- `scope-issue` renames its `## Analysis` section to `## Problem`.
- `scope-issue` raises the issue ceiling to 500 words and the shape target to 250.
- `body-cap.py` excludes fenced blocks from every word count.

## [0.2.0] - 2026-09-18

### Added

- `scope-commit` and `scope-mr` skills with the `body-cap.py` PreToolUse hook.
- `scope-issue` skill, with issue descriptions checked by the hook against a 400-word cap.
- `scope-mr` and `scope-issue` cap code names at three backticked occurrences per description.

### Changed

- `scope-mr` splits its intro into a `why` part and a bugfix-only `root cause` part.
- `scope-mr` caps code names at five distinct names, repeats free.

### Fixed

- `body-cap.py` returns its allow-path rules through `hookSpecificOutput`, not plain stdout.
- `body-cap.py` denies commit bodies at 160 words, matching `scope-commit`.
