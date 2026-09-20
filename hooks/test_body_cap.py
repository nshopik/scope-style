import json, os, shlex, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "body-cap.py")
os.environ["CLAUDE_PLUGIN_DATA"] = tempfile.mkdtemp()   # keep real bounce state untouched
SEEN = os.path.join(os.environ["CLAUDE_PLUGIN_DATA"], "body-cap-seen")
C = "c" + "ommit"   # keep this file's own text from tripping the hook that runs on us

def run(cmd):
    p = subprocess.run([sys.executable, HOOK], text=True, capture_output=True,
                       input=json.dumps({"tool_input": {"command": cmd}}))
    out = p.stdout.strip()
    if not out:
        return "ALLOW-SILENT", ""
    return verdict(out)

def verdict(out):
    h = json.loads(out)["hookSpecificOutput"]
    if h.get("permissionDecision") == "deny":
        return "DENY", h["permissionDecisionReason"]
    return "ALLOW+RULES", h["additionalContext"]

def show(name, cmd):
    v, r = run(cmd)
    print(f"{name:34} {v:12} {r.splitlines()[0][:70] if r else ''}")

BODY = "docs: document dedup\n\nCloses #4 - the remaining work is operator-side, not irontap-side."

# 1. bug: `git commit` mentioned only inside a heredoc payload -> not a commit
show("mention inside heredoc", "cat > x.py <<'PY'\nprint('git " + C + " -m nope')\nPY\npython3 x.py")

# 2. bug: earlier unrelated heredoc must not be measured as the message. Its own
# body, so the verdict does not depend on whether case 3 has run yet — the note
# text would trip the "I"/"now" bans if it were the text being measured.
two = ("cat > note.txt <<'NOTE'\nI wrote this and now it is here\nNOTE\n"
       "git " + C + " -F - <<'MSG'\n"
       + BODY.replace("operator-side", "elsewhere") + "\nMSG")
show("second heredoc is the message", two)

# 3. gate: first submission bounced, identical resubmission passes
os.path.exists(SEEN) and os.remove(SEEN)
one = "git add -A && git " + C + " -q -F - <<'EOF'\n" + BODY + "\nEOF"
show("body, 1st submission", one)
show("body, same again", one)
show("body, reworded", one.replace("operator-side", "server-side"))

# 4. subject-only still silent; over-cap still denies; subject check still fires
show("subject only", "git " + C + " -m 'docs: tidy'")
show("over cap", "git " + C + " -F - <<'EOF'\ndocs: x\n\n" + ("word " * 200) + "\nEOF")
show("bad subject", "git " + C + " -m 'feat: add thing'")
show("revert exempt", "git " + C + " -F - <<'EOF'\nRevert \"docs: x\"\n\nThis reverts commit abc.\nEOF")

# 5. wrap: a runaway line denies at 80; 73-79 is tolerated; a long bare token is exempt
wide = "row: widen the field\n\n" + ("prose " * 20)
show("runaway body line", "git " + C + " -F - <<'EOF'\n" + wide + "\nEOF")
near = "row: widen the field\n\n" + "w" * 40 + " " + "x" * 34   # 75 columns
show("75 cols tolerated", "git " + C + " -F - <<'EOF'\n" + near + "\nEOF")
url = ("row: widen the field\n\nSee\nhttps://example.invalid/"
       + "x" * 90 + "\nfor the shape.")
show("long bare URL exempt", "git " + C + " -F - <<'EOF'\n" + url + "\nEOF")

# 7. MR rubric: a rung rubric stamped as a heading or lead-in denies; prose passes.
def mr(desc):
    return ("glab api -X POST projects/1/merge_requests -f description=- <<'EOF'\n"
            + desc + "\nEOF")

os.path.exists(SEEN) and os.remove(SEEN)
show("rubric heading: look at first", mr("Fixes the leak.\n\n## Look at first\n\nspool.rs."))
show("rubric heading: challenge",     mr("Fixes it.\n\n## Challenge\n\nWe went with X over Y."))
show("rubric lead-in with colon",     mr("Fixes it.\n\nWhere to look first: spool.rs is the spot."))
# A "what it does" content section is endorsed, not a rubric — it passes.
show("what-it-does section passes",    mr("Fixes the leak.\n\n## What it does\n\n- withRecover reports the panic."))
# Prose that merely mentions the words inline (no heading, no `rubric:` lead-in) passes.
show("inline mention passes",         mr("Look at `spool.rs` first for the parking path that\nchanges behavior on restart."))
show("plain prose passes",            mr("Spill replay orders by the filename date, stamped before\nthe first byte, so a stale batch can no longer land last."))

assert run(mr("x.\n\n## Look at first\n\ny."))[0] == "DENY"
assert run(mr("x.\n\n## Challenge\n\ny."))[0] == "DENY"
assert run(mr("x.\n\nWhere to look first: y."))[0] == "DENY"
assert run(mr("x.\n\n## What it does\n\n- y."))[0] == "ALLOW+RULES"
assert run(mr("Look at `spool.rs` first for the parking path."))[0] == "ALLOW+RULES"
assert run(mr("Spill replay orders by the filename date."))[0] == "ALLOW+RULES"
print(f"{'mr rubric detector agrees':34} {'OK':12} 3 deny / 3 pass")

# 6. drift: the scopes the skill bans in prose must be exactly the ones the hook rejects.
# This is the class of bug an LLM eval only catches by luck.
import re
skill = open(os.path.join(HERE, "..", "skills", "scope-commit", "SKILL.md")).read()
# Whole `## subject` section; "\n## " (with space) stops at the next section, so the
# `### Shape`/`### Scope` sub-headings stay in.
subject = skill.split("## subject")[1].split("\n## ")[0]
# The "Never the kind of change" bullet lists the banned scopes.
line = next((l for l in subject.splitlines()
             if re.search(r'never the kind of change', l, re.I)), None)
assert line, "scope-commit '## subject' no longer names the banned-scope line"
banned = set(re.findall(r'`(\w+):`', line))
hook = set(re.search(r"^CC_TYPE = re\.compile\(r'\^\((.*?)\)", open(HOOK).read(),
                     re.M).group(1).split("|"))
assert banned == hook, f"prose bans {sorted(banned)}, hook rejects {sorted(hook)}"
print(f"{'prose/hook ban sets agree':34} {'OK':12} {sorted(hook)}")

# 8. file flags: `gh --body-file` / `git -F <path>` measure what the file holds.
# Before this, a body passed by file was measured as nothing and posted unchecked.
fd = tempfile.mkdtemp()
def wrote(name, text):
    p = os.path.join(fd, name)
    open(p, "w").write(text)
    return p

big = wrote("big.md", "word " * 400)
rubric = wrote("rubric.md", "Fixes it.\n\n## Look at first\n\nspool.rs.")
commit_big = wrote("commit.md", "docs: x\n\n" + "word " * 200)

show("mr --body-file over cap", f"gh pr create --body-file {big}")
show("mr -F over cap",          f"gh pr create -F {big}")
show("mr --body-file= rubric",  f"gh pr create --body-file={rubric}")
show(C + " -F file over cap",   "git " + C + f" -F {commit_big}")
show("gh api -F key=value",     "gh api repos/x/y -F description=@z.md")
show("unreadable file allows",  "gh pr create --body-file /nonexistent/none.md")

assert run(f"gh pr create --body-file {big}")[0] == "DENY"
assert run(f"gh pr create -F {big}")[0] == "DENY"
assert run(f"gh pr create --body-file={rubric}")[0] == "DENY"
assert run("git " + C + f" -F {commit_big}")[0] == "DENY"
# gh api's -F is a raw field, not a file; glab's short flags are the reverse.
assert run("gh api repos/x/y -F description=@z.md")[0] == "ALLOW-SILENT"
assert run("gh pr create --body-file /nonexistent/none.md")[0] == "ALLOW-SILENT"
print(f"{'file-flag bodies measured':34} {'OK':12} 4 deny / 2 pass")

# 9. diff budget: a description that outruns the change it describes bounces once.
# Needs a repo with a known base, so build a throwaway one.
def run_in(cmd, cwd):
    p = subprocess.run([sys.executable, HOOK], text=True, capture_output=True, cwd=cwd,
                       input=json.dumps({"tool_input": {"command": cmd}}))
    out = p.stdout.strip()
    if not out:
        return "ALLOW-SILENT", ""
    return verdict(out)

repo = tempfile.mkdtemp()
def git(*a):
    subprocess.run(("git",) + a, cwd=repo, capture_output=True, check=True)
git("init", "-qb", "main")
git("config", "user.email", "t@t"); git("config", "user.name", "t")
open(os.path.join(repo, "f"), "w").write("base\n")
git("add", "f"); git(C, "-qm", "seed: add f")
git("checkout", "-qb", "topic")
open(os.path.join(repo, "f"), "w").write("base\n" + "line\n" * 19)   # 19 lines added
git("add", "f"); git(C, "-qm", "f: extend")

# 19 changed lines -> budget max(80, 5*19) = 95 words.
long_body = "gh pr create --body " + json.dumps("word " * 140)
short_body = "gh pr create --body " + json.dumps("word " * 90)
os.path.exists(SEEN) and os.remove(SEEN)
v, r = run_in(long_body, repo)
print(f"{'over diff budget':34} {v:12} {r.splitlines()[0][:70]}")
print(f"{'over budget, re-issued':34} {run_in(long_body, repo)[0]}")
print(f"{'under diff budget':34} {run_in(short_body, repo)[0]}")
print(f"{'outside a repo passes':34} {run_in(long_body, tempfile.mkdtemp())[0]}")

os.path.exists(SEEN) and os.remove(SEEN)
assert run_in(long_body, repo)[0] == "DENY"
assert run_in(long_body, repo)[0] == "ALLOW+RULES"      # unchanged re-issue passes
assert run_in(short_body, repo)[0] == "ALLOW+RULES"
assert run_in(long_body, tempfile.mkdtemp())[0] == "ALLOW+RULES"   # unmeasurable, never blocks
print(f"{'diff budget':34} {'OK':12} 1 deny / 3 pass")

# 10. gates are keyed per gate, so a body that trips two owes a bounce to each.
over_and_rung4 = ("gh pr create --body "
                  + json.dumps("word " * 140 + "The setting is deliberately left out."))
os.path.exists(SEEN) and os.remove(SEEN)
first = run_in(over_and_rung4, repo)
second = run_in(over_and_rung4, repo)
third = run_in(over_and_rung4, repo)
print(f"{'two gates: 1st':34} {first[0]:12} {first[1].splitlines()[0][:60]}")
print(f"{'two gates: 2nd':34} {second[0]:12} {second[1].splitlines()[0][:60]}")
print(f"{'two gates: 3rd':34} {third[0]:12}")
assert first[0] == "DENY" and "deliberately left out" in first[1]
assert second[0] == "DENY" and "budget" in second[1]
assert third[0] == "ALLOW+RULES"
print(f"{'per-gate bounce':34} {'OK':12} 2 deny / 1 pass")

# 11. issues: scope-issue section rides along under the cap, 500-word cap denies.
under = "gh issue create --title t --body " + json.dumps("word " * 490)
over = "glab issue create -t t -d " + json.dumps("word " * 510)
show("issue under cap", under)
show("issue over cap", over)
v, r = run(under)
assert v == "ALLOW+RULES" and "<issue_style>" in r and "## Proposal" in r
v, r = run(over)
assert v == "DENY" and "over the 500-word ceiling" in r
print(f"{'issue gate':34} {'OK':12} 1 deny / 1 pass")

# 11b. a fenced log is evidence, not prose: it does not count toward the ceiling.
log = "```\n" + "\n".join("word " * 40 for _ in range(10)) + "\n```"
for prefix, want in (("", "ALLOW+RULES"), ("```\n", "DENY")):
    cmd = "gh issue create --title t --body " + shlex.quote("word " * 480 + "\n\n" + prefix + log)
    show("issue with fenced log", cmd)
    v, r = run(cmd)
    assert v == want and ("ceiling" in r) == (want == "DENY")
print(f"{'issue fenced evidence':34} {'OK':12} 400 fenced words free")

# 11c. table rows are measurements too: charging per cell would price the table
# above the paragraph it replaces.
table = "\n".join("| " + " | ".join(["word"] * 6) + " |" for _ in range(20))
for rows, want in ((table, "ALLOW+RULES"), (table.replace("|", " "), "DENY")):
    cmd = "gh issue create --title t --body " + shlex.quote("word " * 480 + "\n\n" + rows)
    show("issue with table", cmd)
    v, r = run(cmd)
    assert v == want and ("ceiling" in r) == (want == "DENY")
print(f"{'issue table rows free':34} {'OK':12} 120 table words free")

# 12. commit cap is 160, matching scope-commit's hard cap.
def commit_of(n):
    body = "\n".join(" ".join(["word"] * 10) for _ in range(n // 10))
    return "git " + C + " -F - <<'EOF'\ndocs: x\n\n" + body + "\nEOF"
v, r = run(commit_of(150))
assert "ceiling" not in r
v, r = run(commit_of(170))
assert v == "DENY" and "over the 160-word ceiling" in r
print(f"{'commit cap 160':34} {'OK':12} 150 under / 170 over")

# 13. bodies reached indirectly: `$(cat)`, `--input` JSON, `gh api`, heredoc-written files.
words = "word " * 350
md = wrote("desc.md", words)
short = wrote("short.md", "word " * 20)
js = wrote("desc.json", json.dumps({"description": words}))
gh_js = wrote("gh.json", json.dumps({"body": words}))
commit_md = wrote("commit170.md", "docs: x\n\n" + "\n".join(["word " * 10] * 17))
fresh = os.path.join(fd, "fresh.md")                     # written by the command itself
half = "word " * 200
q = shlex.quote
shapes = [
    ("$(cat) in -f description=", "DENY", f'glab api -X PUT projects/1/merge_requests/9 -f description="$(cat {md})"'),
    ("$(cat) in --body",          "DENY", f'gh pr edit 9 --body "$(cat {md})"'),
    ("$(cat) under cap",   "ALLOW+RULES", f'gh pr edit 9 --body "$(cat {short})"'),
    ("$(cat) in commit -m",       "DENY", "git " + C + f' -m "$(cat {commit_md})"'),
    ("glab api --input json",     "DENY", f"glab api -X PUT projects/1/merge_requests/9 --input {js}"),
    ("gh api --input body key",   "DENY", f"gh api -X PATCH repos/o/r/pulls/9 --input {gh_js}"),
    ("gh api pulls -f body=",     "DENY", f'gh api -X PATCH repos/o/r/pulls/9 -f body="$(cat {md})"'),
    ("gh api issues -f body=",    "DENY", f"gh api -X PATCH repos/o/r/issues/7 -f body={q('word ' * 550)}"),
    ("heredoc then --body-file",  "DENY", f"cat > {fresh} <<'EOF'\nit's {words}\nEOF\ngh pr edit 9 --body-file {fresh}"),
    ("heredoc then @path",        "DENY", f"cat <<'EOF' > {fresh}\n{words}\nEOF\nglab api projects/1/merge_requests -F description=@{fresh}"),
    ("heredoc appended",          "DENY", f"cat > {fresh} <<'EOF'\n{half}\nEOF\ncat >> {fresh} <<'EOF'\n{half}\nEOF\ngh pr edit 9 --body-file {fresh}"),
    # Comments, reviews and notes are not the description; reads send no body at all.
    ("gh api issue comment", "ALLOW-SILENT", f"gh api repos/o/r/issues/7/comments -f body={q(words)}"),
    ("gh api PR review",     "ALLOW-SILENT", f"gh api repos/o/r/pulls/9/reviews -f body={q(words)}"),
    ("comment naming /pulls", "ALLOW-SILENT", f"gh api repos/o/r/issues/7/comments -f body={q('see /pulls ' + words)}"),
    ("comment quoting PR path", "ALLOW-SILENT", f"gh api repos/o/r/issues/7/comments -f body={q('dup of repos/o/r/pulls/3 ' + words)}"),
    ("glab note naming issues", "ALLOW-SILENT", f"glab api -X POST projects/1/merge_requests/9/notes -f body={q('fixes the issues here ' + 'word ' * 600)}"),
    ("append to existing file",   "DENY", f"cat >> {wrote('draft.md', half)} <<'EOF'\n{'word ' * 150}\nEOF\ngh pr edit 9 --body-file {os.path.join(fd, 'draft.md')}"),
    ("glab MR note",         "ALLOW-SILENT", f"glab api -X POST projects/1/merge_requests/9/notes -f body={q(words)}"),
    ("gh api read piped",    "ALLOW-SILENT", f"gh api repos/o/r/pulls --paginate | python3 - <<'EOF'\n{words}\nEOF"),
    ("gh api search piped",  "ALLOW-SILENT", f"gh api 'search/issues?q=repo:o/r' | python3 - <<'EOF'\n{words}\nEOF"),
]
for name, want, cmd in shapes:
    show(name, cmd)
    v, r = run(cmd)
    assert v == want and ("-word ceiling" in r) == (want == "DENY"), name
assert not os.path.exists(fresh)
print(f"{'indirect file bodies measured':34} {'OK':12} {len(shapes)} cases")
