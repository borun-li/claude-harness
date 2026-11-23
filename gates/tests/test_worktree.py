#!/usr/bin/env python3
"""gatelib/worktree.py on real git: temporary repositories, real `git worktree add`, real merges.
Run: python3 -m pytest tests/test_worktree.py -q"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from gatelib import checks, runlog, snap, worktree  # noqa: E402
from gatelib.common import ConfigError  # noqa: E402

RUN = "docs/runs/demo"
STATE = {"harness_version": "16.0.0", "feature": "demo", "slug": "demo", "status": "in_progress",
         "tier": "full", "scope": "backend", "current_phase": 4, "phases": [], "models": {},
         "goal": {"change": "a and b answer", "check": "run them", "kind": "change"}}
PLAN = "# Plan\nFiles: `src/a.py`, `src/b.py`, `src/c.py`, `src/old.py`, `tests/test_new.py`\n"


def git(root, *args):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    assert r.returncode == 0, f"git {' '.join(args)}: {r.stderr}"
    return r.stdout.strip()


class Proj:
    """A committed project on branch `main` with an open run, and the worktrees of its agents."""

    def __init__(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="gatewt-")).resolve()
        git(self.root, "init", "-q", "-b", "main")
        for key, value in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
            git(self.root, "config", key, value)
        for rel, text in {
                "src/a.py": "A = 1\n", "src/b.py": "B = 1\n", "src/old.py": "OLD = 1\n",
                "tests/test_a.py": "def test_a():\n    assert True\n",
                ".gitignore": "node_modules/\nignored.txt\n",
                "docs/codemap.md": "# Code map\n", f"{RUN}/state.json": json.dumps(STATE),
                f"{RUN}/plan.md": PLAN, f"{RUN}/handoff.md": "# Handoff\n"}.items():
            self.write(rel, text)
        self.commit("init")
        cfg = json.loads((HERE.parent / "config.json").read_text())
        cfg["worktree"] = {"union_globs": ["<run>/**", "docs/codemap.md", "docs/codemap/**"]}
        self.ctx = checks.Ctx(self.root, RUN, cfg)
        self.log = self.ctx.run / "run-log.jsonl"

    def write(self, rel, text, tree=None):
        p = (tree or self.root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def read(self, rel, tree=None):
        return ((tree or self.root) / rel).read_text(encoding="utf-8")

    def commit(self, msg):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", msg)
        return self.head()

    def head(self, tree=None):
        return git(tree or self.root, "rev-parse", "HEAD")

    def worktree(self, aid, start=None):
        wt = self.root / ".claude" / "worktrees" / f"agent-{aid}"
        git(self.root, "worktree", "add", "-q", str(wt), "-b", f"worktree-agent-{aid}", *([start] if start else []))
        return wt

    def out(self, agent, aid=None, note="build it", **more):
        """Dispatch an isolated agent into a worktree of its own: (dispatch event, worktree)."""
        d = runlog.append(self.log, "dispatch", agent=agent, model="opus", phase="4", note=note,
                          isolated=True, head=self.head(), **more)
        return d, (self.worktree(aid) if aid else None)

    def back(self, d, aid=None, status="ok"):
        rel = f".claude/worktrees/agent-{aid}" if aid else None
        return runlog.append(self.log, "return", agent=d["agent"], phase="4", status=status, note="done",
                             dispatch=d["seq"], agent_id=aid, worktree=rel)

    def land(self, d, r, **kw):
        res = worktree.land(self.ctx, self.log, d, r, **kw)
        runlog.append(self.log, "land", **res)
        return res

    def events(self):
        return runlog.events(self.log)

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


class Case(unittest.TestCase):
    def setUp(self):
        self.p = Proj()
        self.addCleanup(self.p.close)


class Where(Case):
    def test_main_root_from_the_checkout_a_subdirectory_and_a_worktree(self):
        p = self.p
        wt = p.worktree("w1")
        self.assertEqual(worktree.main_root(p.root), p.root)
        self.assertEqual(worktree.main_root(p.root / "src"), p.root)
        self.assertEqual(worktree.main_root(wt), p.root)
        self.assertEqual(worktree.main_root(wt / "src"), p.root)

    def test_main_root_outside_git_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(worktree.main_root(d))
            self.assertIsNone(worktree.main_root(pathlib.Path(d) / "missing"))

    def test_path_of(self):
        p = self.p
        wt = p.worktree("w1")
        self.assertEqual(worktree.path_of(p.root, "w1"), wt)
        self.assertIsNone(worktree.path_of(p.root, "w2"))
        self.assertIsNone(worktree.path_of(p.root, None))


class Settings(Case):
    def test_base_setting_reads_project_local_and_home(self):
        p = self.p
        home = pathlib.Path(tempfile.mkdtemp(prefix="gatewt-home-"))
        self.addCleanup(shutil.rmtree, home, True)
        self.assertFalse(worktree.base_setting(p.root, home))
        p.write(".claude/settings.json", json.dumps({"worktree": {"baseRef": "head"}}), tree=home)
        self.assertTrue(worktree.base_setting(p.root, home))
        p.write(".claude/settings.json", json.dumps({"worktree": {"baseRef": "fresh"}}))
        self.assertFalse(worktree.base_setting(p.root, home), "the project's setting overrides the user's")
        p.write(".claude/settings.local.json", json.dumps({"worktree": {"baseRef": "head"}}))
        self.assertTrue(worktree.base_setting(p.root, home))
        p.write(".claude/settings.local.json", "not json")
        self.assertFalse(worktree.base_setting(p.root, home))

    def test_setup_creates_the_file(self):
        p = self.p
        block = worktree.setup(p.root, ["node_modules"])
        self.assertEqual(block, {"baseRef": "head", "symlinkDirectories": ["node_modules"]})
        self.assertEqual(json.loads(p.read(".claude/settings.json")), {"worktree": block})
        self.assertTrue(worktree.base_setting(p.root, p.root / "no-home"))

    def test_setup_merges_into_an_existing_file(self):
        p = self.p
        had = {"permissions": {"allow": ["Bash(ls:*)"]}, "model": "x",
               "worktree": {"baseRef": "fresh", "symlinkDirectories": [".venv"], "other": 1}}
        p.write(".claude/settings.json", json.dumps(had))
        block = worktree.setup(p.root, ["node_modules/", ".venv"])
        now = json.loads(p.read(".claude/settings.json"))
        self.assertEqual(block, {"baseRef": "head", "symlinkDirectories": [".venv", "node_modules"], "other": 1})
        self.assertEqual(now, {**had, "worktree": block})
        self.assertEqual(worktree.setup(p.root), block, "a second run changes nothing")

    def test_setup_keeps_the_worktrees_out_of_git_status(self):
        p = self.p
        exclude = p.root / ".git" / "info" / "exclude"
        exclude.unlink(missing_ok=True)
        p.worktree("w1")
        self.assertIn(".claude/worktrees/", git(p.root, "status", "--porcelain", "--untracked-files=all"))
        worktree.setup(p.root)
        self.assertEqual(exclude.read_text(), ".claude/worktrees/\n", "created when missing")
        self.assertEqual(git(p.root, "status", "--porcelain", "--untracked-files=all"), "?? .claude/settings.json",
                         "the worktrees are out of sight, and nothing tracked changed")
        exclude.write_text("# the user's own\n*.orig")
        worktree.setup(p.root)
        worktree.setup(p.root)
        self.assertEqual(exclude.read_text(), "# the user's own\n*.orig\n.claude/worktrees/\n", "appended once")
        self.assertEqual([r["state"] for r in worktree.listing(p.ctx, [])], ["landed"], "git still knows the worktree")

    def test_setup_leaves_an_unreadable_file_alone(self):
        p = self.p
        p.write(".claude/settings.json", "{not json")
        with self.assertRaises(ConfigError):
            worktree.setup(p.root, [])
        self.assertEqual(p.read(".claude/settings.json"), "{not json")


class Dirty(Case):
    def test_bookkeeping_is_not_dirt(self):
        p = self.p
        runlog.append(p.log, "mark", role="be-developer")
        p.write(f"{RUN}/gates/snap-be-developer.json", "{}")
        p.write(f"{RUN}/logs/returns/1-be-developer.md", "report")
        p.write(f"{RUN}/stats.md", "# stats")
        p.write("server.log", "volatile")
        p.write(".claude/settings.local.json", "{}")
        p.worktree("w1")
        self.assertEqual(worktree.dirty_ok(p.ctx), [])

    def test_uncommitted_work_is_named(self):
        p = self.p
        p.write("src/a.py", "A = 2\n")
        p.write("src/new.py", "N = 1\n")
        p.write(f"{RUN}/handoff.md", "# Handoff\n- next\n")
        (p.root / "src" / "old.py").unlink()
        self.assertEqual(worktree.dirty_ok(p.ctx), [f"{RUN}/handoff.md", "src/a.py", "src/new.py", "src/old.py"])

    def test_the_run_state_rewritten_by_the_orchestrator_is_not_dirt(self):
        p = self.p
        p.write(f"{RUN}/state.json", json.dumps({**STATE, "current_phase": 5}))
        self.assertIn(f"{RUN}/state.json", git(p.root, "status", "--porcelain"))
        self.assertEqual(worktree.dirty_ok(p.ctx), [])


class Changes(Case):
    def test_committed_uncommitted_untracked_and_deleted(self):
        p = self.p
        wt = p.worktree("w1")
        p.write("src/a.py", "A = 2\n", tree=wt)
        git(wt, "commit", "-qam", "its own commit")
        p.write("src/b.py", "B = 2\nB2 = 3\n", tree=wt)
        p.write("src/c.py", "C = 1\nC2 = 2\n", tree=wt)
        (wt / "src" / "old.py").unlink()
        p.write("ignored.txt", "x", tree=wt)
        p.write("src/__pycache__/a.pyc", "x", tree=wt)   # a cache nobody ignored: no one's work
        p.write("src/build/tool.py", "T = 1\n", tree=wt)  # new source in a directory named like tool output
        p.write("run.log", "volatile", tree=wt)
        p.write(".claude/settings.local.json", "{}", tree=wt)
        ch = worktree.changes(p.ctx, wt)
        self.assertEqual(ch["paths"], ["src/build/tool.py", "src/c.py", "src/a.py", "src/b.py", "src/old.py"])
        self.assertEqual((ch["added"], ch["modified"], ch["deleted"]), (2, 2, 1))
        self.assertEqual(ch["files"], ["src/build/tool.py (+1/-0)", "src/c.py (+2/-0)", "src/a.py (+1/-1)",
                                       "src/b.py (+2/-1)", "src/old.py (+0/-1)"])
        self.assertEqual(worktree.changes(p.ctx, ".claude/worktrees/agent-w1"), ch, "a project-relative path too")

    def test_only_its_own_changes_once_the_run_moved_on(self):
        p = self.p
        wt = p.worktree("w1")
        p.write("src/b.py", "B = 9\n")
        p.commit("the run moved on")
        p.write("src/a.py", "A = 2\n", tree=wt)
        self.assertEqual(worktree.changes(p.ctx, wt)["paths"], ["src/a.py"])

    def test_a_linked_dependency_directory_is_not_a_change(self):
        p = self.p
        p.write("node_modules/dep/index.js", "x")
        wt = p.worktree("w1")
        os.symlink(p.root / "node_modules", wt / "node_modules")  # `node_modules/` does not ignore the link
        self.assertIn("node_modules", git(wt, "status", "--porcelain"))
        os.symlink("a.py", wt / "src" / "alias.py")  # a link inside the tree is its author's work
        self.assertEqual(worktree.changes(p.ctx, wt)["paths"], ["src/alias.py"])


class Land(Case):
    def test_two_writers_out_together_are_both_merged(self):
        p = self.p
        d1, w1 = p.out("be-developer", "w1", note="build a")
        d2, w2 = p.out("be-developer", "w2", note="build b")
        p.write("src/a.py", "A = 2\n", tree=w1)
        p.write("src/c.py", "C = 1\n", tree=w1)
        p.write("src/b.py", "B = 2\n", tree=w2)
        (w2 / "src" / "old.py").unlink()
        r1, r2 = p.back(d1, "w1"), p.back(d2, "w2")
        p.write(f"{RUN}/gates/snap-be-tester.json", json.dumps(
            {"role": "be-tester", "time_ns": 1, "snapshot": {"src/a.py": "old", "src/old.py": "old", "src/b.py": "old"}}))
        res1 = p.land(d1, r1)
        self.assertEqual((res1["result"], res1["files"], res1["commit"]), ("merged", 2, p.head()))
        self.assertEqual(git(p.root, "log", "-1", "--format=%s"), "be-developer #1 · step 4 · build a")
        res2 = p.land(d2, r2)
        self.assertEqual((res2["result"], res2["files"], res2["commit"]), ("merged", 2, p.head()))
        self.assertEqual([p.read("src/a.py"), p.read("src/b.py"), p.read("src/c.py")], ["A = 2\n", "B = 2\n", "C = 1\n"])
        self.assertFalse((p.root / "src" / "old.py").exists())
        self.assertIn("be-developer #2 · step 4 · build b", git(p.root, "log", "-3", "--format=%s"))
        self.assertEqual(worktree.dirty_ok(p.ctx), [], "the main checkout holds nothing but its bookkeeping")
        self.assertEqual(git(p.root, "symbolic-ref", "--short", "HEAD"), "main")
        mark = json.loads(p.read(f"{RUN}/gates/snap-be-tester.json"))["snapshot"]
        self.assertEqual(mark, {"src/a.py": snap.file_sha(p.root / "src/a.py"),
                                "src/b.py": snap.file_sha(p.root / "src/b.py"),
                                "src/c.py": snap.file_sha(p.root / "src/c.py")},
                         "every landed path is forgiven in the marks kept")
        self.assertEqual(worktree.line(p.events(), res2), f"[land] be-developer #2 · merged {p.head()[:7]} · 2 files")
        self.assertTrue(w1.is_dir() and w2.is_dir(), "the worktrees are kept")
        self.assertEqual(runlog.unlanded(p.events()), [])

    def test_a_code_conflict_is_left_for_its_author_and_lands_once_resolved(self):
        p = self.p
        d1, w1 = p.out("be-developer", "w1", note="build a")
        d2, w2 = p.out("fe-engineer", "w2", note="use a")
        p.write("src/a.py", "A = 2\n", tree=w1)
        p.write("src/a.py", "A = 3\n", tree=w2)
        p.write("src/b.py", "B = 3\n", tree=w2)
        r1, r2 = p.back(d1, "w1"), p.back(d2, "w2")
        self.assertEqual(p.land(d1, r1)["result"], "merged")
        main = p.head()
        res = p.land(d2, r2)
        self.assertEqual(res, {"agent": "fe-engineer", "dispatch": d2["seq"], "result": "conflict",
                               "paths": ["src/a.py"], "owner": "fe-engineer", "note": "met be-developer #1"})
        self.assertEqual(worktree.line(p.events(), res),
                         "[land] fe-engineer #1 · conflict: src/a.py (met be-developer #1)")
        self.assertEqual(p.head(), main, "nothing reached the run's branch")
        self.assertIn("<<<<<<< ", p.read("src/a.py", tree=w2))
        self.assertEqual(worktree.listing(p.ctx, p.events())[1]["state"], "conflict")
        self.assertEqual(p.land(d2, r2)["result"], "conflict", "still unresolved: the same answer")
        self.assertEqual(worktree.changes(p.ctx, w2)["paths"], ["src/a.py", "src/b.py"],
                         "during the merge, its changes are what it adds to the run's branch")
        # the author is continued in its worktree and resolves the file; it runs no git write
        d3 = runlog.append(p.log, "dispatch", agent="fe-engineer", model="opus", phase="4", note="resolve",
                           isolated=True, continued=True, agent_id="w2", worktree=".claude/worktrees/agent-w2",
                           head=p.head())
        worktree.refresh(p.ctx, w2)
        self.assertIn("<<<<<<< ", p.read("src/a.py", tree=w2), "a merge in progress is not refreshed away")
        p.write("src/a.py", "A = 23\n", tree=w2)
        r3 = p.back(d3, "w2")
        res = p.land(d3, r3)
        self.assertEqual((res["result"], res["commit"]), ("merged", p.head()))
        self.assertEqual([p.read("src/a.py"), p.read("src/b.py")], ["A = 23\n", "B = 3\n"])
        self.assertEqual(worktree.line(p.events(), res), f"[land] fe-engineer #1 · merged {p.head()[:7]} · 2 files")

    def test_a_resolved_conflict_lands_after_the_run_moved_again(self):
        p = self.p
        d1, w1 = p.out("be-developer", "w1")
        d2, w2 = p.out("be-developer", "w2")
        d3, w3 = p.out("be-developer", "w3")
        p.write("src/a.py", "A = 2\n", tree=w1)
        p.write("src/a.py", "A = 3\n", tree=w2)
        p.write("src/b.py", "B = 3\n", tree=w3)
        r1, r2, r3 = p.back(d1, "w1"), p.back(d2, "w2"), p.back(d3, "w3")
        self.assertEqual(p.land(d1, r1)["result"], "merged")
        self.assertEqual(p.land(d2, r2)["result"], "conflict")
        self.assertEqual(p.land(d3, r3)["result"], "merged")
        p.write("src/a.py", "A = 23\n", tree=w2)
        self.assertEqual(p.land(d2, r2)["result"], "merged")
        self.assertEqual([p.read("src/a.py"), p.read("src/b.py")], ["A = 23\n", "B = 3\n"])

    def test_the_run_branch_gets_one_commit_per_landing_and_no_merge_commit(self):
        p = self.p
        base = p.head()
        d1, w1 = p.out("be-developer", "w1", note="build a")
        d2, w2 = p.out("be-developer", "w2", note="build b")
        d3, w3 = p.out("be-developer", "w3", note="change a")
        p.write("src/a.py", "A = 2\n", tree=w1)
        p.write("src/b.py", "B = 2\n", tree=w2)
        p.write("src/a.py", "A = 3\n", tree=w3)
        p.write("src/c.py", "C = 3\n", tree=w3)
        r1, r2, r3 = p.back(d1, "w1"), p.back(d2, "w2"), p.back(d3, "w3")
        for d, r, wt in ((d1, r1, w1), (d2, r2, w2)):  # w2 is behind the run's branch when it lands
            res = p.land(d, r)
            self.assertEqual((res["result"], res["commit"], res["files"]), ("merged", p.head(), 1))
            self.assertEqual(p.head(wt), p.head(), "the worktree ends exactly at the run's head")
        res = p.land(d3, r3)
        self.assertEqual((res["result"], res["paths"], res["note"]),
                         ("conflict", ["src/a.py"], "met be-developer #1, be-developer #2"))
        p.write("src/a.py", "A = 23\n", tree=w3)
        res = p.land(d3, r3)
        self.assertEqual((res["result"], res["commit"], res["files"], p.head(w3)), ("merged", p.head(), 2, p.head()))
        self.assertEqual(git(p.root, "rev-list", "--merges", "HEAD"), "", "no merge commit on the run's branch")
        self.assertEqual(git(p.root, "log", "--reverse", "--format=%s", f"{base}..HEAD").split("\n"),
                         ["be-developer #1 · step 4 · build a", "be-developer #2 · step 4 · build b",
                          "be-developer #3 · step 4 · change a"])
        self.assertEqual(git(p.root, "show", "--name-only", "--format=", "HEAD").split("\n"), ["src/a.py", "src/c.py"])
        self.assertEqual([p.read("src/a.py"), p.read("src/b.py"), p.read("src/c.py")], ["A = 23\n", "B = 2\n", "C = 3\n"])
        self.assertEqual([r["state"] for r in worktree.listing(p.ctx, p.events())], ["landed"] * 3)
        # a later continuation in a worktree whose old commits are on no branch any more
        d4 = runlog.append(p.log, "dispatch", agent="be-developer", model="opus", phase="4", note="more b",
                           isolated=True, continued=True, agent_id="w2", worktree=".claude/worktrees/agent-w2",
                           head=p.head())
        worktree.refresh(p.ctx, w2)
        self.assertEqual(p.head(w2), p.head(), "refreshed to the run's head")
        p.write("src/a.py", "A = 24\n", tree=w2)
        res = p.land(d4, p.back(d4, "w2"))
        self.assertEqual((res["result"], res["files"], p.head(w2)), ("merged", 1, p.head()))
        self.assertEqual(git(p.root, "log", "-1", "--format=%s"), "be-developer #2 · step 4 · more b")
        self.assertEqual((git(p.root, "rev-list", "--merges", "HEAD"), git(p.root, "rev-list", "--count", f"{base}..HEAD")),
                         ("", "4"))
        self.assertEqual(len(worktree.clean(p.ctx, p.events())), 3, "every landed worktree and its branch can go")
        self.assertEqual(git(p.root, "branch", "--format=%(refname:short)"), "main")

    def test_a_net_change_the_run_already_holds_is_empty(self):
        p = self.p
        d1, w1 = p.out("be-developer", "w1")
        d2, w2 = p.out("be-developer", "w2")
        p.write("src/a.py", "A = 2\n", tree=w1)
        p.write("src/a.py", "A = 2\n", tree=w2)
        r1, r2 = p.back(d1, "w1"), p.back(d2, "w2")
        self.assertEqual(p.land(d1, r1)["result"], "merged")
        main = p.head()
        self.assertEqual(p.land(d2, r2)["result"], "empty")
        self.assertEqual((p.head(), p.head(w2)), (main, main))
        self.assertEqual(worktree.listing(p.ctx, p.events())[1]["state"], "landed")
        self.assertEqual(runlog.unlanded(p.events()), [])

    def test_documents_several_writers_add_to_keep_both_sides(self):
        p = self.p
        d1, w1 = p.out("be-developer", "w1")
        d2, w2 = p.out("be-developer", "w2")
        for wt, who in ((w1, "one"), (w2, "two")):
            p.write(f"{RUN}/handoff.md", f"# Handoff\n- from {who}\n", tree=wt)
            p.write("docs/codemap.md", f"# Code map\n## {who}\n", tree=wt)
            p.write(f"{RUN}/new.md", f"added by {who}\n", tree=wt)
        r1, r2 = p.back(d1, "w1"), p.back(d2, "w2")
        self.assertEqual(p.land(d1, r1)["result"], "merged")
        self.assertEqual(p.land(d2, r2)["result"], "merged")
        for rel, lines in ((f"{RUN}/handoff.md", ["# Handoff", "- from one", "- from two"]),
                           ("docs/codemap.md", ["# Code map", "## one", "## two"]),
                           (f"{RUN}/new.md", ["added by one", "added by two"])):
            self.assertEqual(sorted(p.read(rel).splitlines()), sorted(lines), rel)

    def test_a_document_outside_union_globs_conflicts(self):
        p = self.p
        p.write("README.md", "# Readme\n")
        p.commit("readme")
        d1, w1 = p.out("be-developer", "w1")
        d2, w2 = p.out("be-developer", "w2")
        p.write("README.md", "# Readme\none\n", tree=w1)
        p.write("README.md", "# Readme\ntwo\n", tree=w2)
        p.write(f"{RUN}/handoff.md", "# Handoff\n- two\n", tree=w2)
        r1, r2 = p.back(d1, "w1"), p.back(d2, "w2")
        p.land(d1, r1)
        res = p.land(d2, r2)
        self.assertEqual((res["result"], res["paths"]), ("conflict", ["README.md"]))

    def test_a_change_outside_the_role_is_refused_and_nothing_is_committed(self):
        p = self.p
        d, wt = p.out("be-tester", "w1")
        p.write("src/a.py", "A = 2\n", tree=wt)
        p.write("tests/test_new.py", "def test_new():\n    assert True\n", tree=wt)
        r = p.back(d, "w1")
        main, own = p.head(), p.head(wt)
        res = p.land(d, r)
        self.assertEqual(res, {"agent": "be-tester", "dispatch": d["seq"], "result": "refused", "paths": ["src/a.py"],
                               "owner": "be-tester", "note": "put these back, or have them planned"})
        self.assertEqual((p.head(), p.head(wt)), (main, own))
        self.assertEqual(git(wt, "diff", "--cached", "--name-only"), "", "nothing was staged")
        self.assertEqual(worktree.line(p.events(), res),
                         "[land] be-tester #1 · refused: src/a.py (put these back, or have them planned)")
        self.assertEqual([x["seq"] for x in runlog.unlanded(p.events())], [d["seq"]])
        p.write("src/a.py", "A = 1\n", tree=wt)  # put back
        res = p.land(d, r)
        self.assertEqual((res["result"], res["files"]), ("merged", 1))
        self.assertTrue((p.root / "tests" / "test_new.py").is_file())

    def test_the_run_books_and_project_config_changed_in_a_worktree_are_refused(self):
        p = self.p
        runlog.append(p.log, "mark", role="be-analyst")
        p.write(".claude/gates.json", "{}")
        p.commit("books")
        d, wt = p.out("be-developer", "w1")
        p.write(f"{RUN}/run-log.jsonl", "", tree=wt)
        p.write(f"{RUN}/gates/p4-latest.json", "{}", tree=wt)
        p.write(".claude/gates.json", '{"confirmed": true}', tree=wt)
        p.write("src/a.py", "A = 2\n", tree=wt)
        res = p.land(d, p.back(d, "w1"))
        self.assertEqual((res["result"], res["paths"]),
                         ("refused", [".claude/gates.json", f"{RUN}/gates/p4-latest.json", f"{RUN}/run-log.jsonl"]))

    def test_the_run_state_changed_in_a_worktree_is_refused_never_union_merged(self):
        p = self.p
        d, wt = p.out("be-developer", "w1")
        p.write(f"{RUN}/state.json", json.dumps({**STATE, "current_phase": 5}), tree=wt)
        p.write("src/a.py", "A = 2\n", tree=wt)
        r = p.back(d, "w1")
        p.write(f"{RUN}/state.json", json.dumps({**STATE, "current_phase": 6}))
        p.commit("the orchestrator's transition")
        main, own = p.head(), p.head(wt)
        res = p.land(d, r)
        self.assertEqual((res["result"], res["paths"], res["owner"]), ("refused", [f"{RUN}/state.json"], "be-developer"))
        self.assertEqual((p.head(), p.head(wt)), (main, own))
        git(wt, "checkout", "--", f"{RUN}/state.json")  # put back
        self.assertEqual(p.land(d, r)["result"], "merged")
        self.assertEqual(json.loads(p.read(f"{RUN}/state.json"))["current_phase"], 6, "the run's own copy, whole")
        self.assertEqual(p.read("src/a.py"), "A = 2\n")

    def test_the_rendered_run_log_is_bookkeeping_in_the_run_tree_and_refused_from_a_worktree(self):
        p = self.p
        p.write(f"{RUN}/run-log.md", "# Run log\n")
        p.commit("a timeline was rendered and committed")
        d, wt = p.out("be-developer", "w1")
        p.write(f"{RUN}/run-log.md", "# Run log\n| 1 | rendered again |\n")  # `gate.py timeline`, uncommitted
        self.assertIn(f"{RUN}/run-log.md", git(p.root, "status", "--porcelain"))
        self.assertEqual(worktree.dirty_ok(p.ctx), [])
        p.write(f"{RUN}/run-log.md", "# Run log\nedited by a writer\n", tree=wt)
        p.write("src/a.py", "A = 2\n", tree=wt)
        main = p.head()
        res = p.land(d, p.back(d, "w1"))
        self.assertEqual((res["result"], res["paths"], res["owner"]), ("refused", [f"{RUN}/run-log.md"], "be-developer"))
        self.assertEqual((p.head(), p.head(wt)), (main, main), "nothing committed, nothing merged")

    def test_a_dirty_main_checkout_blocks_the_fast_forward_only(self):
        p = self.p
        d, wt = p.out("be-developer", "w1")
        p.write("src/a.py", "A = 2\n", tree=wt)
        p.write(f"{RUN}/handoff.md", "# Handoff\n- from the agent\n", tree=wt)
        r = p.back(d, "w1")
        p.write(f"{RUN}/handoff.md", "# Handoff\n- from the orchestrator\n")  # not committed
        main = p.head()
        res = p.land(d, r)
        self.assertEqual(res, {"agent": "be-developer", "dispatch": d["seq"], "result": "refused",
                               "paths": [f"{RUN}/handoff.md"], "owner": "orchestrator",
                               "note": "commit your bookkeeping first"})
        self.assertEqual(p.head(), main)
        self.assertEqual(p.read("src/a.py"), "A = 1\n")
        kept = p.head(wt)
        self.assertNotEqual(kept, main, "the worktree keeps its commit")
        git(p.root, "add", f"{RUN}/handoff.md")
        git(p.root, "commit", "-qm", "handoff")
        res = p.land(d, r)
        self.assertEqual((res["result"], res["commit"]), ("merged", p.head()))
        self.assertEqual((p.head(wt), git(p.root, "rev-list", "--merges", "HEAD")), (p.head(), ""))
        self.assertEqual(p.read("src/a.py"), "A = 2\n")
        self.assertEqual(sorted(p.read(f"{RUN}/handoff.md").splitlines()),
                         ["# Handoff", "- from the agent", "- from the orchestrator"])
        self.assertIn(f"{RUN}/run-log.jsonl", git(p.root, "status", "--porcelain", "--untracked-files=all"),
                      "the uncommitted run log never blocked it")

    def test_a_worktree_that_did_not_start_from_the_run_branch_is_refused(self):
        p = self.p
        old = p.head()
        p.write("src/b.py", "B = 5\n")
        p.commit("the run's earlier work")
        d = runlog.append(p.log, "dispatch", agent="be-developer", model="opus", phase="4", note="x",
                          isolated=True, head=p.head())
        wt = p.worktree("w1", start=old)  # as if started from the remote's default branch
        p.write("src/a.py", "A = 2\n", tree=wt)
        main = p.head()
        res = p.land(d, p.back(d, "w1"))
        self.assertEqual((res["result"], res["owner"], res["note"]), ("refused", "orchestrator", worktree.BASE_NOTE))
        self.assertEqual((p.head(), p.head(wt)), (main, old), "nothing merged, nothing committed")

    def test_a_linked_dependency_directory_is_never_staged(self):
        p = self.p
        p.write("node_modules/dep/index.js", "x")
        d, wt = p.out("be-developer", "w1")
        os.symlink(p.root / "node_modules", wt / "node_modules")
        p.write("src/a.py", "A = 2\n", tree=wt)
        res = p.land(d, p.back(d, "w1"))
        self.assertEqual((res["result"], res["files"]), ("merged", 1))
        self.assertNotIn("node_modules", git(p.root, "ls-files"))
        self.assertTrue((p.root / "node_modules").is_dir() and not (p.root / "node_modules").is_symlink())
        self.assertTrue((wt / "node_modules").is_symlink())

    def test_no_worktree_or_an_unchanged_one_is_empty(self):
        p = self.p
        d1, _ = p.out("be-developer")
        res = p.land(d1, p.back(d1, "gone"))
        self.assertEqual((res["result"], worktree.line(p.events(), res)),
                         ("empty", "[land] be-developer #1 · empty (no worktree: its agent left it unchanged)"))
        d2, _ = p.out("be-developer", "w2")
        main = p.head()
        self.assertEqual(p.land(d2, p.back(d2, "w2"))["result"], "empty")
        self.assertEqual(p.head(), main)
        self.assertEqual(runlog.unlanded(p.events()), [])

    def test_an_in_tree_writer_is_committed_by_path(self):
        p = self.p
        runlog.append(p.log, "mark", role="be-developer")
        d = runlog.append(p.log, "dispatch", agent="be-developer", model="opus", phase="4",
                          note="add  the c module\nand more words than a subject line of seventy-two characters holds")
        p.write("src/a.py", "A = 2\n")
        p.write("src/c.py", "C = 1\n")
        (p.root / "src" / "old.py").unlink()
        p.write("src/b.py", "B = 7\n")          # someone else's: not in tree_paths
        p.write("server.log", "volatile")
        p.write(f"{RUN}/08-implementation-log.md", "# Log\n")
        p.worktree("w9")
        r = runlog.append(p.log, "return", agent="be-developer", phase="4", status="ok", note="done", dispatch=d["seq"])
        res = p.land(d, r, tree_paths=["src/a.py", "src/c.py", "src/old.py", "src/never-existed.py", "server.log",
                                       ".claude/worktrees/agent-w9"])
        self.assertEqual((res["result"], res["commit"], res["files"]), ("committed", p.head(), 5))
        subject = git(p.root, "log", "-1", "--format=%s")
        self.assertTrue(subject.startswith("be-developer #1 · step 4 · add the c module and more words"), subject)
        self.assertLessEqual(len(subject), 72)
        self.assertEqual(sorted(git(p.root, "show", "--name-only", "--format=", "HEAD").split("\n")),
                         [f"{RUN}/08-implementation-log.md", f"{RUN}/run-log.jsonl", "src/a.py", "src/c.py", "src/old.py"])
        self.assertEqual(worktree.dirty_ok(p.ctx), ["src/b.py"], "another writer's file stays uncommitted")
        self.assertEqual(worktree.line(p.events(), res), f"[land] be-developer #1 · committed {p.head()[:7]} · 5 files")
        git(p.root, "add", f"{RUN}/run-log.jsonl")
        git(p.root, "commit", "-qm", "books")
        again = worktree.land(p.ctx, p.log, d, r, tree_paths=["src/a.py"])
        self.assertEqual(again["result"], "empty")

    def test_a_worktree_whose_author_is_out_again_is_not_landed(self):
        p = self.p
        d1, wt = p.out("be-developer", "w1")
        p.write("src/a.py", "A = 2\n", tree=wt)
        r1 = p.back(d1, "w1", status="blocked")
        d2 = runlog.append(p.log, "dispatch", agent="be-developer", model="opus", phase="4", note="the answer",
                           isolated=True, continued=True, agent_id="w1", worktree=".claude/worktrees/agent-w1")
        main = p.head()
        res = p.land(d1, r1)
        self.assertEqual((res["result"], res["owner"], res["note"]),
                         ("refused", "orchestrator", "its agent is out again in this worktree: land after it returns"))
        self.assertEqual((p.head(), p.head(wt)), (main, main))
        p.write("src/b.py", "B = 2\n", tree=wt)
        r2 = p.back(d2, "w1")
        self.assertEqual((p.land(d1, r1)["result"], p.land(d2, r2)["result"]), ("merged", "empty"))
        self.assertEqual([p.read("src/a.py"), p.read("src/b.py")], ["A = 2\n", "B = 2\n"])
        self.assertEqual(runlog.unlanded(p.events()), [])

    def test_a_plain_directory_named_like_a_worktree_never_reaches_the_main_checkout(self):
        p = self.p
        d, _ = p.out("be-developer")
        plain = p.root / ".claude" / "worktrees" / "agent-w1"
        p.write("notes.txt", "left behind", tree=plain)
        p.write("src/a.py", "A = 2\n")  # uncommitted in the main checkout: not this agent's
        main = p.head()
        res = p.land(d, p.back(d, "w1"))
        self.assertEqual((res["result"], res["owner"]), ("refused", "orchestrator"))
        self.assertEqual((p.head(), git(p.root, "diff", "--cached", "--name-only")), (main, ""))
        self.assertEqual(worktree.listing(p.ctx, p.events()), [])
        worktree.refresh(p.ctx, plain)
        with self.assertRaises(ConfigError):
            worktree.changes(p.ctx, plain)

    def test_a_continuation_keeps_its_agents_ordinal(self):
        p = self.p
        d1, _ = p.out("be-developer", "w1")
        d2, _ = p.out("be-developer", "w2")
        p.back(d1, "w1")
        d3 = runlog.append(p.log, "dispatch", agent="be-developer", model="opus", phase="4", note="fix",
                           isolated=True, continued=True, agent_id="w1", worktree=".claude/worktrees/agent-w1")
        self.assertEqual([worktree.ordinal(p.events(), d) for d in (d1, d2, d3)], [1, 2, 1])


class Refresh(Case):
    def test_an_idle_worktree_is_fast_forwarded_after_a_land(self):
        p = self.p
        d1, w1 = p.out("be-developer", "w1")
        d2, w2 = p.out("be-developer", "w2")
        d3, w3 = p.out("be-developer", "w3")
        p.write("src/a.py", "A = 2\n", tree=w1)
        p.write("src/b.py", "B = 2\n", tree=w3)   # uncommitted work of its own
        self.assertEqual(p.land(d1, p.back(d1, "w1"))["result"], "merged")
        before = p.head(w3)
        os.symlink(p.root / "src", w2 / "node_modules")  # a linked directory is not a change
        self.assertIsNone(worktree.refresh(p.ctx, w2))
        worktree.refresh(p.ctx, w3)
        worktree.refresh(p.ctx, p.root / ".claude" / "worktrees" / "agent-gone")
        self.assertEqual(p.head(w2), p.head())
        self.assertEqual(p.read("src/a.py", tree=w2), "A = 2\n")
        self.assertEqual(p.head(w3), before, "a worktree with changes is left as it is")
        self.assertEqual(git(w2, "symbolic-ref", "--short", "HEAD"), "worktree-agent-w2")


class ListAndClean(Case):
    def test_states_and_clean(self):
        p = self.p
        p.write("node_modules/dep/index.js", "x")
        d1, w1 = p.out("be-developer", "landed")
        d2, w2 = p.out("be-developer", "unlanded")
        d3, w3 = p.out("be-tester", "out")
        d4, w4 = p.out("be-developer", "refused")
        git(p.root, "worktree", "lock", str(w3))  # as Claude Code holds it while its agent runs
        p.write("src/a.py", "A = 2\n", tree=w1)
        os.symlink(p.root / "node_modules", w1 / "node_modules")
        p.write("src/b.py", "B = 2\n", tree=w2)
        p.write("src/unplanned.py", "U = 1\n", tree=w4)
        r1, _, r4 = p.back(d1, "landed"), p.back(d2, "unlanded"), p.back(d4, "refused")
        self.assertEqual(p.land(d1, r1)["result"], "merged")
        self.assertEqual(p.land(d4, r4)["result"], "refused")
        stray = p.worktree("stray")  # no dispatch of this run names it
        rows = {r["agent_id"]: r for r in worktree.listing(p.ctx, p.events())}
        self.assertEqual({k: v["state"] for k, v in rows.items()},
                         {"landed": "landed", "unlanded": "unlanded", "out": "out", "refused": "unlanded",
                          "stray": "out"}, "while an isolated agent is out, an unknown worktree may be its own")
        self.assertEqual((rows["landed"]["agent"], rows["landed"]["dispatch"], rows["landed"]["branch"],
                          rows["landed"]["path"], rows["landed"]["locked"]),
                         ("be-developer", d1["seq"], "worktree-agent-landed", ".claude/worktrees/agent-landed", False))
        self.assertTrue(rows["out"]["locked"])
        self.assertIsNone(rows["out"]["agent"], "an agent still out has told no one its id")
        self.assertIsNone(rows["stray"]["agent"])
        self.assertTrue(all(isinstance(r["age"], int) and r["age"] >= 0 for r in rows.values()))
        removed = worktree.clean(p.ctx, p.events())
        self.assertEqual(removed, [".claude/worktrees/agent-landed"])
        self.assertFalse(w1.exists())
        self.assertTrue(w2.is_dir() and w3.is_dir() and w4.is_dir() and stray.is_dir(),
                        "unlanded work, a locked worktree and one that may be an agent's stay")
        self.assertEqual(p.read("node_modules/dep/index.js"), "x", "the linked directory itself is untouched")
        self.assertEqual(p.read("src/b.py", tree=w2), "B = 2\n")
        self.assertEqual(worktree.clean(p.ctx, p.events()), [])
        # its agent returns without a change: both it and the stray one are judged from git alone
        git(p.root, "worktree", "unlock", str(w3))
        p.back(d3, "out")
        rows = {r["agent_id"]: r["state"] for r in worktree.listing(p.ctx, p.events())}
        self.assertEqual(rows, {"unlanded": "unlanded", "out": "landed", "refused": "unlanded", "stray": "landed"})
        self.assertEqual(worktree.clean(p.ctx, p.events()), [".claude/worktrees/agent-out", ".claude/worktrees/agent-stray"])
        branches = git(p.root, "branch", "--format=%(refname:short)").split("\n")
        self.assertEqual(sorted(branches), ["main", "worktree-agent-refused", "worktree-agent-unlanded"])

    def test_a_returned_isolated_agent_not_locked_is_out_only_while_its_dispatch_is_open(self):
        p = self.p
        d1, w1 = p.out("be-developer", "w1")
        r1 = p.back(d1, "w1")
        runlog.append(p.log, "dispatch", agent="be-developer", model="opus", phase="4", note="more",
                      isolated=True, continued=True, agent_id="w1", worktree=".claude/worktrees/agent-w1")
        self.assertEqual(worktree.listing(p.ctx, p.events())[0]["state"], "out")
        self.assertEqual(worktree.clean(p.ctx, p.events()), [])
        self.assertTrue(w1.is_dir())
        self.assertIsNotNone(r1)


if __name__ == "__main__":
    unittest.main()
