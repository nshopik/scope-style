#!/usr/bin/env python3
"""PreToolUse gate: Scoped Commits subjects, over-long and over-wide bodies,
descriptions that outrun the diff they describe, `--fill` MRs, and MR
descriptions that stamp a rung rubric as a heading/lead-in. Text passed by file
(`gh --body-file`, `git -F <path>`) is measured the same as text on the flag.

Also bounces every distinct commit body once (see CONFIRM): whether a body earns
its place is judgment, not a measurement, so the gate forces the judgment to be
made rather than trying to make it.

Reads the hook payload on stdin. Allows silently (exit 0, no output) on anything
it cannot confidently parse — a false block is worse than a missed one.

All rules live in the `scope-commit`, `scope-mr` and `scope-issue` skills, not here: this file
detects and measures, then quotes back the matching `## <id>` section of the skill for
that kind. Rule edits go to the skill; only detection logic and the caps belong here.

Caps derive from measured baselines; the commit that sets a cap records its derivation.

The subject checks are deliberately narrow. Only the Conventional Commits types
that could never plausibly name a subsystem are rejected — `docs:`, `ci:`,
`test:`, `fix:` are all legitimate Scoped Commits scopes and must pass.
"""
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

CAPS = {'commit': 160, 'mr': 300, 'issue': 400}

SKILLS_DIR = Path(__file__).resolve().parent.parent / 'skills'
SKILL = {'commit': 'scope-commit', 'mr': 'scope-mr', 'issue': 'scope-issue'}
FALLBACK = 'Follow Scoped Commits — https://scopedcommits.com/'

# Prepended to the style block when the body is also over the ceiling. The style
# block itself ships on every body — the content rules apply at any length, and
# gating them behind the ceiling is how a short body made entirely of restatement
# and verification output reaches history unchallenged.
OVER_CAP = "{what} is {n} words — over the {cap}-word ceiling. Rewrite it, then re-run.\n\n"


def sections(text):
    """`## id` headings of a markdown document mapped to their body text.

    Any `##` closes the open section; only lowercase-slug ones are kept, so prose
    headings (`## Examples`) end a section without becoming one.
    """
    out, key, buf = {}, None, []
    for line in text.split('\n'):
        m = re.match(r'##\s+(\S+)\s*$', line)
        if m:
            if key:
                out[key] = '\n'.join(buf).strip()
            key = m.group(1) if re.fullmatch(r'[a-z-]+', m.group(1)) else None
            buf = []
        elif key is not None:
            buf.append(line)
    if key:
        out[key] = '\n'.join(buf).strip()
    return out


def reminder(kind, section, **fields):
    """That kind's skill section, wrapped in its style tag, with fields filled in."""
    path = SKILLS_DIR / SKILL[kind] / 'SKILL.md'
    try:
        body = sections(path.read_text(encoding='utf-8'))[section]
    except Exception:
        body = FALLBACK
    tag = f'{kind}_style'
    fields.setdefault('over_cap', '')
    try:
        body = body.format(**fields)
    except (KeyError, IndexError):
        pass
    return f'<{tag}>\n{body}\n</{tag}>'


FILL_FLAGS = {'--fill', '--fill-first', '--fill-verbose'}


def uses_fill(cmd):
    """True when --fill is passed as a flag, not merely quoted inside one.

    Call with heredoc bodies already excised: prose about `--fill` is data, and
    denying on it blocks the very description that explains the rule.
    """
    try:
        return bool(FILL_FLAGS.intersection(shlex.split(cmd)))
    except ValueError:
        return False


# Conventional Commits types with no plausible reading as a subsystem name.
CC_TYPE = re.compile(r'^(feat|feature|chore|perf|style)(\([^)]*\))?!?:', re.I)
EXEMPT = re.compile(r'^(merge\b|revert\b|fixup!|squash!|amend!)', re.I)

# Non-imperative first word of the description ("fix:" then "added ..." etc).
NON_IMPERATIVE = re.compile(
    r':\s*(added|adds|adding|fixed|fixes|fixing|removed|removes|removing|'
    r'updated|updates|updating|changed|changes|changing|renamed|renames|'
    r'renaming|refactored|refactors|refactoring)\b', re.I)

SUBJECT_HARD_CAP = 72
SUBJECT_TARGET = 50


def subject_issues(text):
    """Scoped Commits violations in the subject line, as a list of strings."""
    subject = next((l.strip() for l in text.split('\n') if l.strip()), '')
    if not subject or EXEMPT.match(subject):
        return []
    out = []
    if CC_TYPE.match(subject):
        out.append('- Names a change kind, not an area touched — use the '
                   'subsystem instead.')
    elif ':' not in subject:
        out.append('- No `<scope>:` prefix.')
    if subject.endswith('.'):
        out.append('- Trailing period.')
    m = NON_IMPERATIVE.search(subject)
    if m:
        out.append(f"- Non-imperative mood ('{m.group(1)}') — use imperative: "
                    "add/fix/remove.")
    if len(subject) > SUBJECT_HARD_CAP:
        out.append(f'- {len(subject)} chars — hard cap is {SUBJECT_HARD_CAP} '
                    f'(target ≤{SUBJECT_TARGET}).')
    return out


# Body self-narration and formatting bans.
BODY_BAN = [
    (re.compile(r'\bthis (commit|change) (does|adds|fixes|removes|makes)\b', re.I),
     "narrates itself (\"this commit/change does...\") — the diff shows what changed"),
    (re.compile(r'^\s*(I|We)\b', re.M),
     "refers to the author (\"I\"/\"We\") — state the why, not who did it"),
    (re.compile(r'^\s*(Now|Currently),?\s', re.M),
     "narration word (\"now\"/\"currently\") — describe the why, not the state change"),
    (re.compile(r'^\s*\*\s', re.M),
     "`*` bullet — use `-`"),
]


# Wrap at 72 is the instruction (the skill carries the reason); 80 is where the
# gate fires. The split is deliberate and measured: across 669 commits in this
# repo and dnstap2clck, 81% of over-wide lines land at 73-76 columns, median 74.
# Denying at 72 would block 24% of real commits over a one-character overflow;
# anything under 80 still renders fine everywhere we care about, so the gate
# catches only the genuine runaway line — 1% of that history.
WRAP_HARD = 80

# A line only counts if wrapping it is possible: a bare URL or path longer than
# the limit is left alone rather than reported as unfixable. Indented and quoted
# lines are NOT exempt — in that same history the over-wide lines were prose
# overflow, not preformatted blocks.
# ponytail: add an indent exemption if real code blocks start tripping it.
def wrap_issues(lines):
    out = []
    for i, line in enumerate(lines, 1):
        if len(line) > WRAP_HARD and max(map(len, line.split()), default=0) <= WRAP_HARD:
            out.append(f'- body line {i} is {len(line)} columns — wrap at 72.')
    return out[:3] + ([f'- …and {len(out) - 3} more over 72.'] if len(out) > 3 else [])


def body_issues(body):
    """Self-narration, formatting and wrap violations in the body, as strings."""
    kept = strip_trailers(body)
    text = '\n'.join(kept)
    return ([f'- {msg}.' for pattern, msg in BODY_BAN if pattern.search(text)]
            + wrap_issues(kept))


MR_CMD = re.compile(r'\bglab\b(?:[^\n|;&]*\bmerge_requests\b'
                    r'|\s+mr\s+(?:create|update|edit)\b)'
                    r'|\bgh\b\s+pr\s+(?:create|edit)\b')

ISSUE_CMD = re.compile(r'\bglab\b(?:[^\n|;&]*\bissues\b'
                       r'|\s+issue\s+(?:create|update|edit)\b)'
                       r'|\bgh\b\s+issue\s+(?:create|edit)\b')

# No regex measures whether a body earns its place, so the gate is procedural:
# bounce each distinct body once and let re-issuing it be the judgment. MRs are
# exempt from the blanket bounce — a description is mandatory there, so the same
# gate is pure toll — but a rung-4 claim gets its own bounce below: "deliberately
# left out" is the one line that reliably smuggles unrelated findings into an MR.
CONFIRM = ("This commit has a body — bounced once so the judgment below gets made. "
           "Re-run the same command unchanged to pass; otherwise drop or shorten "
           "the body.\n\n")

# Rung-4 leaders. The explicit phrases are specific enough to match anywhere in
# the prose; the bare "unchanged:"-style ones only lead a line, where prose that
# merely mentions the word cannot reach them.
# The prescriptive set is the same smuggling in forward-looking grammar: work
# the diff does not contain, written as an instruction rather than as an
# omission ("a contact point still needs to exist before this delivers").
RUNG4 = re.compile(r"""\b deliberately \s+ (?:unchanged|left|omitted|out)
                     | \b left \s+ (?:as[- ]is|alone|untouched)
                     | \b out \s+ of \s+ scope \s*:
                     | ^\W{0,4} (?:not \s+)? (?:changed|touched|addressed|unchanged
                                       |deferred|postponed)
                       \s*:
                     | \b (?:still \s+ )? needs? \s+ to \s+ be \b
                     | \b still \s+ (?:needs?|requires?|required) \b
                     | \b needs? \s+ to \s+ (?:exist|happen|land|follow)
                     | \b must \s+ (?:first|still|be \s+ (?:created|configured|set))
                     | \b before \s+ this \s+ (?:works|delivers|takes \s+ effect)
                     """, re.X | re.I | re.M)

RUNG4_CONFIRM = ("This MR description claims something was deliberately left out — "
                 "bounced once so the boundary below gets applied. Re-run the same "
                 "command unchanged to pass; otherwise move the item to an issue.\n\n")

# A description that outruns the change it describes is restating the diff. The
# 300-word cap cannot see that: 175 words over a 23-line diff sits well under it.
# Budget scales with the diff; the floor keeps a one-line fix writable.
DIFF_FACTOR = 5
DIFF_FLOOR = 80

OVER_DIFF = ("MR description is {n} words against a {lines}-line diff, over the "
             "{allow}-word budget for a change that size — bounced once so the "
             "judgment gets made. Re-run the same command unchanged to pass; "
             "otherwise cut it to what the diff cannot show.\n\n")


# `cd <path> && glab …` is the shape of every cross-repo forge command. The hook
# runs in the session cwd, so without this the diff budget silently measures the
# wrong repo — and a clean session repo reads as 0 lines, disabling the check.
CD_PREFIX = re.compile(r"""(?:^|[;&|]|\bdo\b|\bthen\b)\s*
                           cd \s+ (?: '([^']+)' | "([^"]+)" | ([^\s;&|]+) )""",
                       re.X)


def cmd_cwd(cmd, at):
    """Directory the forge command runs in: the last `cd` preceding it."""
    path = None
    for m in CD_PREFIX.finditer(cmd, 0, at):
        path = next(g for g in m.groups() if g is not None)
    if not path or path.startswith('-'):
        return None
    path = os.path.expanduser(os.path.expandvars(path))
    return path if os.path.isdir(path) else None


def diff_lines(cwd=None):
    """Lines changed on this branch against its base, or None if unmeasurable."""
    def git(*args):
        try:
            p = subprocess.run(('git',) + args, capture_output=True, text=True,
                               timeout=5, cwd=cwd)
        except (OSError, subprocess.SubprocessError):
            return None
        return p.stdout if p.returncode == 0 else None

    def numstat(*args):
        out = git('diff', '--numstat', *args)
        if out is None:
            return None
        return sum(int(c) for line in out.splitlines()
                   for c in line.split('\t')[:2] if c.isdigit())

    base = None
    for ref in ('origin/HEAD', 'main', 'master'):
        out = git('merge-base', 'HEAD', ref)
        if out and out.strip():
            base = out.strip()
            break
    if not base:
        return None
    committed = numstat(f'{base}..HEAD')
    if committed is None:
        return None
    # An MR is often written before the last commit lands, so the committed
    # range alone reads 0 and every description falls back to the floor. The
    # working tree against HEAD is disjoint from that range; summing them sizes
    # the change the description actually covers.
    return committed + (numstat('HEAD') or 0)

# Rung rubrics stamped as a heading or lead-in. The scope-mr ladder decides what
# to write; naming the rung in the text ("## Look at first", "Decision worth
# challenging:") is the tell the writer stamped the rubric instead of the fact.
# Curated to the skill's own offender list (## mr-style, Never). A content section
# ("## What it does", bullets) is endorsed there, so it is deliberately absent
# here; only the where-to-look and challenge rubrics are banned.
_RUBRIC = (r'look\s+at\s+first'
           r'|where\s+to\s+look(?:\s+first)?'
           r'|(?:a\s+)?decision\s+worth\s+challenging'
           r'|what\s+to\s+challenge'
           r'|challenges?'
           r'|blast\s+radius'
           r'|riskiest\s+part')
MR_RUBRIC = re.compile(
    rf'^\s*#{{1,6}}\s+(?:{_RUBRIC})\s*:?\s*$'        # markdown heading form
    rf'|^\s*(?:[-*]\s+)?(?:{_RUBRIC})\s*:\s',        # lead-in "Rubric: ..." form
    re.I | re.M)

RUBRIC_DENY = ("This MR description names a rung rubric as a heading or lead-in "
               "({hit!r}) — the ladder picks what to write, it never appears in the "
               "text. Rewrite as prose, then re-run.\n\n")

# Never /tmp: a predictable path there can be pre-created as a symlink.
# CLAUDE_PLUGIN_DATA survives plugin updates; the plugin root does not.
SEEN_FILE = Path(os.environ.get('CLAUDE_PLUGIN_DATA')
                 or Path.home() / '.claude' / '.cache') / 'body-cap-seen'


def seen(body, gate):
    """True if this exact body was bounced by this gate before. Records it either way.

    Keyed per gate: a body that trips two of them owes a bounce to each, or the
    re-issue that answers the first silently clears the rest.

    Any I/O failure reports the body as already seen: the gate must never crash
    or nag twice over its own bookkeeping.
    """
    digest = hashlib.sha256(
        (gate + '\n' + '\n'.join(body).strip()).encode()).hexdigest()[:16]
    try:
        prior = SEEN_FILE.read_text(encoding='utf-8').split() \
            if SEEN_FILE.exists() else []
        if digest in prior:
            return True
        SEEN_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        SEEN_FILE.write_text('\n'.join(prior + [digest]), encoding='utf-8')
    except OSError:
        return True                             # cannot remember — do not nag twice
    return False


# [^\n] as well as the separators: without it `git push` on one line and the
# word `commit` inside a later heredoc read as one commit command, and a plain
# MR description got judged against commit-subject rules.
GIT_COMMIT = re.compile(r'\bgit\b[^\n|;&]*\bcommit\b')


def classify(cmd, spans):
    """(kind, offset) of the committing/MR-opening command, or (None, None).

    Matches inside a heredoc body are skipped: that text is data, not shell — a
    script or payload that merely mentions `git commit` is not a commit.
    """
    def first_outside(pattern):
        # Both ends: a match that starts on the command line and reaches into a
        # heredoc body is still reading data as shell.
        return next((m.start() for m in pattern.finditer(cmd)
                     if not any(s <= m.start() < e or s < m.end() <= e
                                for s, e, _ in spans)), None)

    at = first_outside(GIT_COMMIT)
    if at is not None:
        return 'commit', at
    at = first_outside(MR_CMD)
    if at is not None:
        return 'mr', at
    at = first_outside(ISSUE_CMD)
    return ('issue', at) if at is not None else (None, None)


# [^\n]* after the delimiter: a heredoc opener may be followed by more of the
# command (`git commit -F - <<'MSG' && git log -1`). Requiring the newline to
# follow the delimiter directly made those bodies invisible, and an unmeasured
# body is allowed silently — the gate failed open.
HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n(.*?)\n\s*\2\b",
    re.DOTALL)


def heredoc_spans(cmd):
    """(start, end, body) per heredoc, in command order. Start is at the `<<`."""
    return [(m.start(), m.end(), m.group(3)) for m in HEREDOC.finditer(cmd)]


def without_heredocs(cmd, spans):
    """cmd with every heredoc body blanked out, leaving only shell text."""
    out = list(cmd)
    for start, end, _ in spans:
        out[start:end] = ' ' * (end - start)
    return ''.join(out)


def heredoc_body(spans, after):
    """The first heredoc opened after `after` — the one the command at that
    offset consumes. A command may carry several (`cat <<A` … `git commit <<B`);
    taking the first in the string measures the wrong text."""
    return next((body for start, _, body in spans if start > after), None)


def file_text(path):
    """`gh --body-file`, `git -F`. Unreadable or stdin measures as nothing, the
    same as a command that carries no text at all."""
    if path == '-':
        return ''
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


def flag_text(cmd, kind):
    """Pull the message/description out of explicit flags."""
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return None
    out, i = [], 0
    while i < len(parts):
        p = parts[i]
        nxt = parts[i + 1] if i + 1 < len(parts) else None
        if kind == 'commit':
            # -m, --message, and bundled short flags ending in m (-am, -sm).
            if (p == '--message' or re.fullmatch(r'-[a-zA-Z]*m', p)) \
                    and nxt is not None:
                out.append(nxt); i += 2; continue
            if p in ('-F', '--file') and nxt is not None:
                out.append(file_text(nxt)); i += 2; continue
            if p.startswith('--file='):
                out.append(file_text(p.split('=', 1)[1]))
            elif p.startswith('--message='):
                out.append(p.split('=', 1)[1])
            elif p.startswith('-m') and len(p) > 2:
                out.append(p[2:])
        else:
            # glab api -F description=@file expands the @path itself, so the
            # value carries the file rather than the text.
            if p in ('-F', '-f', '--field', '--raw-field') and nxt is not None \
                    and nxt.startswith('description='):
                v = nxt.split('=', 1)[1]
                out.append(file_text(v[1:]) if v.startswith('@') else v)
                i += 2; continue
            # gh -F body.md. A value carrying '=' is `gh api -F key=value`, whose
            # short flags are the reverse of glab's, not a file.
            if p in ('-F', '--body-file') and nxt is not None and '=' not in nxt:
                out.append(file_text(nxt)); i += 2; continue
            if p.startswith('--body-file='):
                out.append(file_text(p.split('=', 1)[1])); i += 1; continue
            # glab api -f description=...  /  --description=  /  gh --body
            if p in ('-f', '--field', '--raw-field') and nxt is not None:
                if nxt.startswith('description='):
                    out.append(nxt.split('=', 1)[1])
                i += 2; continue
            if p in ('-d', '--description', '-b', '--body') and nxt is not None:
                out.append(nxt); i += 2; continue
            if p.startswith('--description=') or p.startswith('--body='):
                out.append(p.split('=', 1)[1])
        i += 1
    return '\n\n'.join(out) if out else None


# Named keys only. A bare `Word:` opener is ordinary prose — "Deferred:",
# "Note:" — and treating it as a trailer silently drops the line from the count.
TRAILER = re.compile(
    r'^(?:closes|fixes|resolves|refs|references|related|see[- ]also'
    r'|signed-off-by|co-authored-by|reviewed-by|acked-by|tested-by'
    r'|reported-by|suggested-by|part-of|change-id|cc|bug):\s'
    r'|^\(cherry picked from', re.I)


def strip_trailers(lines):
    end = len(lines)
    while end and (not lines[end - 1].strip() or TRAILER.match(lines[end - 1])):
        end -= 1
    return lines[:end]


def body_of(text):
    """Lines after the (possibly wrapped) subject line."""
    lines = text.split('\n')
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    while i < len(lines) and lines[i].strip():       # subject may wrap
        i += 1
    return lines[i:]


def count(lines):
    return sum(len(l.split()) for l in strip_trailers(lines))


CHAINED = ''


def main():
    try:
        cmd = json.load(sys.stdin).get('tool_input', {}).get('command', '')
    except Exception:
        return
    spans = heredoc_spans(cmd)
    kind, at = classify(cmd, spans)
    if not kind:
        return
    # A denied call runs none of the command. Re-issuing only the commit half of
    # `git add -A && git commit` then commits a stale index, silently.
    if re.search(r'[;&|]', cmd[:at]):
        global CHAINED
        CHAINED = ('\n\nNothing in this command ran: the steps chained before '
                   'it did not happen either.\n')
    # Checked before the text lookup: --fill puts no description on the command
    # line, so there is nothing for the ceiling check to measure.
    if kind == 'mr' and uses_fill(without_heredocs(cmd, spans)):
        return deny(reminder('mr', 'fill'))
    text = heredoc_body(spans, at) or flag_text(cmd, kind)
    if not text:
        return                                  # editor-based, --no-edit, etc.
    body = text.split('\n')
    if kind == 'commit':
        issues = subject_issues(text)
        if issues:
            subject = next(l.strip() for l in text.split('\n') if l.strip())
            return deny(reminder('commit', 'subject', subject=subject,
                                 problems='\n'.join(issues)))
        body = body_of(text)
        b_issues = body_issues(body)
        if b_issues:
            return deny(reminder('commit', 'body-issues',
                                 problems='\n'.join(b_issues)))
    n = count(body)
    if not n:
        return                                  # subject-only commit, nothing to style
    cap = CAPS[kind]
    over = '' if n <= cap else OVER_CAP.format(
        what={'commit': 'Commit body', 'mr': 'MR description',
              'issue': 'Issue description'}[kind],
        n=n, cap=cap)
    out = reminder(kind, f'{kind}-style', over_cap=over)
    if over:
        return deny(out)
    if kind == 'commit' and not EXEMPT.match(text.lstrip()) and not seen(body, 'confirm'):
        return deny(CONFIRM + out)
    if kind == 'mr':
        m = MR_RUBRIC.search('\n'.join(strip_trailers(body)))
        if m:
            return deny(RUBRIC_DENY.format(hit=m.group(0).strip()) + out)
        if RUNG4.search('\n'.join(body)) and not seen(body, 'rung4'):
            return deny(RUNG4_CONFIRM + reminder('mr', 'rung-four'))
        lines = diff_lines(cmd_cwd(cmd, at))
        budget = (max(DIFF_FLOOR, DIFF_FACTOR * lines) if lines is not None
                  else None)
        if budget and n > budget and not seen(body, 'budget'):
            return deny(OVER_DIFF.format(n=n, lines=lines, allow=budget) + out)
    emit(additionalContext=out)


def deny(reason):
    emit(permissionDecision="deny", permissionDecisionReason=reason + CHAINED)


# PreToolUse plain stdout never reaches the model; only hookSpecificOutput does.
def emit(**fields):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **fields}}))


if __name__ == '__main__':
    main()
