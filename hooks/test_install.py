#!/usr/bin/env python3
"""install.sh keeps what is the user's. Run: ``python3 <this file>``; the exit code is the result.

Every run installs a copy of this repository into a temporary ``CLAUDE_HOME`` with a temporary
``HOME`` and a stub ``npm`` first on PATH: nothing here reads or writes the real ``~/.claude`` or
the network. The copy lets a test retire a hook or change a default the way a later version would.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = pathlib.Path("skills") / "design-taste"

NPM = """#!/bin/sh
# stub: `npm ci` without the network
if [ -n "${FAKE_NPM_FAIL:-}" ]; then echo "npm error simulated failure" >&2; exit 1; fi
mkdir -p node_modules && echo "added 1 package"
"""
OLD_PYTHON = """#!/bin/sh
case "$1" in --version) echo "Python 3.8.10"; exit 0 ;; esac
exit 1
"""
OLD_NODE = """#!/bin/sh
echo v16.20.2
"""
# The commands of the two-team layout, and how a harness command starts.
OLD_COMMANDS = ["backend", "frontend", "backend-resume", "frontend-resume",
                "backend-status", "frontend-status", "backend-config", "frontend-config"]
OLD_COMMAND = "---\ndescription: old\n---\n\n> **Read `~/.claude/CONSTITUTION.md` first.**\n"
NEW_COMMANDS = ["route", "route-resume", "route-status", "route-config"]


def stub(directory, name, text):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text)
    path.chmod(0o755)
    return directory


class Sandbox:
    """A source copy of the harness, a fake HOME and the CLAUDE_HOME installs go to."""

    def __init__(self, tmp):
        self.tmp = pathlib.Path(tmp)
        self.src = self.tmp / "src"
        shutil.copytree(ROOT, self.src, ignore=shutil.ignore_patterns(
            ".git", "node_modules", "__pycache__", ".pytest_cache", "docs", "REVIEW.md"))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.bin = stub(self.tmp / "bin", "npm", NPM)
        self.reports = self.tmp / "tmpdir" / "harness-reports"
        self.reports.mkdir(parents=True)
        (self.reports / "a1.txt").write_text("a kept report")

    def dest(self, name="claude"):
        return self.tmp / name

    def run(self, *args, dest=None, first_on_path=None, **env):
        path = os.pathsep.join([str(p) for p in (first_on_path, self.bin) if p] + [os.environ["PATH"]])
        return subprocess.run(
            ["sh", str(self.src / "install.sh"), *args], capture_output=True, text=True,
            env={**os.environ, "HOME": str(self.home), "CLAUDE_HOME": str(dest or self.dest()), "PATH": path,
                 "TMPDIR": str(self.reports.parent), **env})


def main() -> int:
    failures = cases = 0

    def ok(label, cond, detail=""):
        nonlocal failures, cases
        cases += 1
        if not cond:
            failures += 1
            print("FAIL", label, detail)

    with tempfile.TemporaryDirectory() as tmp:
        box = Sandbox(tmp)
        dest = box.dest()
        shipped_hooks = sorted(p.name for p in (box.src / "hooks").glob("*.py"))

        # -- prerequisites: tools and their versions ------------------------------------------
        p = box.run("--check")
        ok("--check passes here", p.returncode == 0 and "prerequisites ok" in p.stdout, p.stdout + p.stderr)
        ok("--check writes nothing", not dest.exists())
        old = stub(box.tmp / "old-python", "python3", OLD_PYTHON)
        for args in (["--check"], []):
            p = box.run(*args, first_on_path=old)
            ok("python older than 3.9 is refused (%s)" % (args or ["install"])[0],
               p.returncode == 1 and "Python 3.9 or newer" in p.stdout and "Python 3.8.10" in p.stdout, p.stdout)
        ok("a refused install writes nothing", not dest.exists())
        p = box.run("--check", first_on_path=stub(box.tmp / "old-node", "node", OLD_NODE))
        ok("node older than 18 is refused", p.returncode == 1 and "Node.js 18 or newer" in p.stdout, p.stdout)
        for args in (["--uninstall", "--check"], ["--check", "--uninstall"], ["--bogus"], ["--uninstall", "now"]):
            p = box.run(*args)
            ok("usage error: %s" % " ".join(args), p.returncode == 2 and "usage" in p.stderr and not dest.exists())

        # -- what the user had before the first install ---------------------------------------
        mine = {
            "hooks/my-hook.sh": "#!/bin/sh\necho mine\n",
            "hooks/my_hook.py": "print('mine')\n",
            "agents/mine.md": "my own agent\n",
            "commands/mine.md": "my own command\n",
            "commands/frontend.md": "my own command, named like one the harness retired\n",
            "harness-local/backend.json": '{"loops": {"max_rounds": 3}}\n',
            "harness-local/notes.txt": "my notes\n",
        }
        for rel, text in mine.items():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (dest / rel).write_text(text)
        (dest / "hooks" / "no-tree-restoring-git.py").write_text("# left by an earlier whole-directory install\n")

        def mine_intact():
            return [rel for rel, text in mine.items() if not (dest / rel).is_file() or (dest / rel).read_text() != text]

        # -- first install -------------------------------------------------------------------
        p = box.run()
        ok("install succeeds", p.returncode == 0 and "done." in p.stdout, p.stdout + p.stderr)
        version = json.loads((box.src / "harness" / "config.json").read_text())["harness_version"]
        ok("install prints the version of harness/config.json", "installed harness %s into" % version in p.stdout, p.stdout)
        ok("the harness config and the changelog are installed",
           (dest / "harness" / "config.json").read_bytes() == (box.src / "harness" / "config.json").read_bytes()
           and (dest / "harness" / "CHANGELOG.md").read_bytes() == (box.src / "CHANGELOG.md").read_bytes())
        ok("the run commands are installed", all(
            (dest / "commands" / (n + ".md")).read_bytes() == (box.src / "commands" / (n + ".md")).read_bytes()
            for n in NEW_COMMANDS))
        told = [line for line in p.stdout.split("\n") if "harness-local/backend.json" in line]
        ok("an old harness-local/<team>.json is reported in one line, and left alone",
           len(told) == 1 and "merge into harness-local/config.json" in told[0]
           and "harness-local/frontend.json" not in p.stdout, p.stdout)
        ok("the user's hooks, agents, commands and harness-local survive", mine_intact() == [], str(mine_intact()))
        ok("harness-local holds only the user's files",
           sorted(f.name for f in (dest / "harness-local").iterdir()) == ["backend.json", "notes.txt"])
        ok("every harness hook is installed", all(
            (dest / "hooks" / n).read_bytes() == (box.src / "hooks" / n).read_bytes() for n in shipped_hooks))
        manifest = (dest / ".harness-files").read_text().split()
        ok("the manifest lists the harness's hooks, agents and commands, and nothing of the user's",
           {"hooks/" + n for n in shipped_hooks} <= set(manifest) and "agents/be-developer.md" in manifest
           and {"commands/%s.md" % n for n in NEW_COMMANDS} <= set(manifest) and not set(manifest) & set(mine))
        ok("design-taste installed and recorded",
           (dest / SKILL / "SKILL.md").read_bytes() == (box.src / SKILL / "SKILL.md").read_bytes()
           and (dest / ".harness-design-taste").is_file())
        def installed_hook(command):  # the installed git hook, as a sub-agent's Bash call
            out = subprocess.run([sys.executable, str(dest / "hooks" / "no-tree-restoring-git.py"), "--role", "agent"],
                                 input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
                                 capture_output=True, text=True, cwd=str(box.tmp)).stdout
            return "deny" in out

        ok("the installed hooks run from the shared directory",
           installed_hook("git stash") and not installed_hook("git status"))
        ok("the installed copy's gate.py is the harness's gate",
           installed_hook("python3 %s p4" % (dest / "gates" / "gate.py"))
           and not installed_hook("python3 %s check p4" % (dest / "gates" / "gate.py")))
        ok("running a hook leaves no __pycache__ next to the user's hooks", not (dest / "hooks" / "__pycache__").exists())
        ok("gates dependencies installed", (dest / "gates" / "node_modules").is_dir() and "gates dependencies" in p.stdout)
        backups = sorted(dest.glob("backup-harness-*.tgz"))
        ok("what could be overwritten was backed up", len(backups) == 1)
        with tarfile.open(str(backups[0])) as t:
            ok("harness-local is not part of the install, not even of its backup",
               not [n for n in t.getnames() if n.startswith("harness-local")])
        ok("nothing went to $HOME/.claude", not (box.home / ".claude").exists())

        # -- an update that retires a hook and ships a new design-taste default -----------------
        (box.src / "hooks" / "no-foreign-process-kill.py").unlink()
        (box.src / SKILL / "SKILL.md").write_text("the second default\n")
        p = box.run()
        ok("update succeeds", p.returncode == 0, p.stdout + p.stderr)
        ok("a retired hook is removed", not (dest / "hooks" / "no-foreign-process-kill.py").exists()
           and "removed retired hooks/no-foreign-process-kill.py" in p.stdout, p.stdout)
        ok("the user's files survive an update", mine_intact() == [], str(mine_intact()))
        ok("an unedited design-taste takes the new default",
           (dest / SKILL / "SKILL.md").read_text() == "the second default\n" and "kept your edited" not in p.stdout)

        # -- the user edits design-taste; a later version ships another default -----------------
        (dest / SKILL / "SKILL.md").write_text("my own taste\n")
        (box.src / SKILL / "SKILL.md").write_text("the third default\n")
        p = box.run()
        kept = [line for line in p.stdout.split("\n") if "kept your edited" in line]
        ok("an edited design-taste is kept", p.returncode == 0 and (dest / SKILL / "SKILL.md").read_text() == "my own taste\n")
        ok("one line says so and where the new default is", len(kept) == 1 and str(box.src / SKILL) in kept[0], p.stdout)
        p = box.run()
        ok("and is kept on every later install", (dest / SKILL / "SKILL.md").read_text() == "my own taste\n"
           and "kept your edited" in p.stdout)

        # -- npm failing is an error, not a silent success --------------------------------------
        p = box.run(FAKE_NPM_FAIL="1")
        ok("npm ci failure exits non-zero", p.returncode != 0, str(p.returncode))
        ok("npm ci failure is reported", "npm ci failed" in p.stderr and "simulated failure" in p.stderr
           and "done." not in p.stdout, p.stdout + p.stderr)

        # -- uninstall --------------------------------------------------------------------------
        listed = (dest / ".harness-files").read_text().split()
        p = box.run("--uninstall")
        ok("uninstall succeeds", p.returncode == 0, p.stdout + p.stderr)
        ok("everything the manifest listed is removed", not [f for f in listed if (dest / f).exists()])
        ok("the replaced-whole parts are removed", not [n for n in (
            "CONSTITUTION.md", "ORCHESTRATOR.md", "backend", "frontend", "route", "gates", "harness")
            if (dest / n).exists()])
        ok("the manifest and the record are removed",
           not (dest / ".harness-files").exists() and not (dest / ".harness-design-taste").exists())
        ok("the user's files survive uninstall", mine_intact() == [], str(mine_intact()))
        ok("the edited design-taste survives uninstall", (dest / SKILL / "SKILL.md").read_text() == "my own taste\n")
        ok("backups and the temp report dir are left", len(list(dest.glob("backup-harness-*.tgz"))) >= 1
           and (box.reports / "a1.txt").is_file())
        left = p.stdout.split("left in place:")[-1]
        ok("uninstall prints what it left", all(s in left for s in (
            "backup-harness-", str(dest / "harness-local"), str(dest / SKILL), str(box.reports))), p.stdout)

        # -- a fresh home: nothing of the user's is invented; uninstall leaves nothing of ours ---
        fresh = box.dest("fresh")
        p = box.run(dest=fresh)
        ok("fresh install succeeds", p.returncode == 0, p.stdout + p.stderr)
        ok("install never creates harness-local", not (fresh / "harness-local").exists())
        ok("nothing to merge, nothing said about harness-local", "harness-local" not in p.stdout, p.stdout)
        ok("a first install makes no backup", not list(fresh.glob("backup-harness-*.tgz")))
        (fresh / "settings.json").write_text(json.dumps({"model": "x"}))
        p = box.run("--uninstall", dest=fresh)
        ok("uninstall of an unedited install leaves only the user's settings",
           p.returncode == 0 and sorted(f.name for f in fresh.iterdir()) == ["settings.json"],
           str(sorted(f.name for f in fresh.iterdir())))

        # -- a design-taste from before installs recorded one: unknown, so the user's -----------
        legacy = box.dest("legacy")
        (legacy / SKILL).mkdir(parents=True)
        (legacy / SKILL / "SKILL.md").write_text("edited before installs kept a record\n")
        p = box.run(dest=legacy)
        ok("a differing design-taste without a record is kept",
           p.returncode == 0 and (legacy / SKILL / "SKILL.md").read_text() == "edited before installs kept a record\n"
           and "kept your edited" in p.stdout, p.stdout + p.stderr)

        # -- an install of the two-team layout is updated: its configs, changelogs and commands go --
        old = box.dest("old")
        gone = ["backend/config.json", "frontend/config.json", "backend/CHANGELOG.md", "frontend/CHANGELOG.md"] \
            + ["commands/%s.md" % n for n in OLD_COMMANDS]
        for rel in gone:
            (old / rel).parent.mkdir(parents=True, exist_ok=True)
            (old / rel).write_text(OLD_COMMAND if rel.startswith("commands/") else "{}\n")
        # the first four commands were recorded by the install that wrote them; the rest predate the record
        (old / ".harness-files").write_text("".join("commands/%s.md\n" % n for n in OLD_COMMANDS[:4]))
        (old / "harness-local").mkdir()
        for n in ("backend", "frontend"):
            (old / "harness-local" / (n + ".json")).write_text("{}\n")
        cfg = json.loads((box.src / "harness" / "config.json").read_text())
        (box.src / "harness" / "config.json").write_text(json.dumps({**cfg, "harness_version": "99.1.2"}))
        p = box.run(dest=old)
        ok("update of a two-team install succeeds", p.returncode == 0, p.stdout + p.stderr)
        ok("its team configs, changelogs and the eight old commands are removed",
           not [rel for rel in gone if (old / rel).exists()], str([rel for rel in gone if (old / rel).exists()]))
        ok("each removed command is named", all("removed retired commands/%s.md" % n in p.stdout for n in OLD_COMMANDS),
           p.stdout)
        ok("the playbooks and the new commands are there", (old / "backend" / "PLAYBOOK.md").is_file()
           and all((old / "commands" / (n + ".md")).is_file() for n in NEW_COMMANDS))
        ok("the version printed is the one in harness/config.json", "installed harness 99.1.2 into" in p.stdout, p.stdout)
        told = [line for line in p.stdout.split("\n") if "merge into harness-local/config.json" in line]
        ok("both old harness-local files are named in one line and kept",
           len(told) == 1 and "harness-local/backend.json" in told[0] and "harness-local/frontend.json" in told[0]
           and sorted(f.name for f in (old / "harness-local").iterdir()) == ["backend.json", "frontend.json"], p.stdout)

        # -- uninstall removes both generations: what this version wrote, and an older one's commands --
        for n in OLD_COMMANDS[4:]:
            (old / "commands" / (n + ".md")).write_text(OLD_COMMAND)
        (old / "commands" / "backend.md").write_text("the user's own, written after the update\n")
        p = box.run("--uninstall", dest=old)
        ok("uninstall removes both generations and keeps the user's files",
           p.returncode == 0 and sorted(f.name for f in old.iterdir() if not f.name.startswith("backup-harness-"))
           == ["commands", "harness-local"] and [f.name for f in (old / "commands").iterdir()] == ["backend.md"],
           p.stdout + str(sorted(f.name for f in old.iterdir())))

    print("%d cases, %d failures" % (cases, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
