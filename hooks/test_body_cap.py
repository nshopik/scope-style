import json, os, subprocess, sys, tempfile

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

# 11. issues: scope-issue section rides along under the cap, 400-word cap denies.
under = "gh issue create --title t --body " + json.dumps("word " * 380)
over = "glab issue create -t t -d " + json.dumps("word " * 420)
show("issue under cap", under)
show("issue over cap", over)
v, r = run(under)
assert v == "ALLOW+RULES" and "<issue_style>" in r and "## Proposal" in r
v, r = run(over)
assert v == "DENY" and "over the 400-word ceiling" in r
print(f"{'issue gate':34} {'OK':12} 1 deny / 1 pass")
