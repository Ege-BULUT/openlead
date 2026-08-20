#!/usr/bin/env python3
"""End-to-end check of the OpenLead CLIs against a scaffolded workspace.

  python3 tests/test_clis.py

Scaffolds throwaway workspaces in a temp directory with init_workspace.py, then drives the
four CLIs the way an agent would and asserts on the JSON and the rendered pages. Stdlib
only, same as the tool itself, so there is nothing to install and no test framework to
learn. Exits non-zero if anything fails.

The roadmap diagram is laid out in JavaScript, so that part is checked by tests/test_diagram.js
(run from here automatically, skipped with a notice if node isn't on PATH).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(HERE)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("  PASS  " if cond else "  FAIL  ") + name + (("   " + detail) if detail and not cond else ""))


def run(ws, script, *args, expect_ok=True):
    p = subprocess.run([sys.executable, os.path.join("scripts", script)] + list(args),
                       cwd=ws, capture_output=True, text=True)
    if expect_ok and p.returncode != 0:
        raise AssertionError(f"{script} {' '.join(args)} exited {p.returncode}: {p.stderr.strip()}")
    return p


def data(ws, name):
    with open(os.path.join(ws, "data", name), encoding="utf-8") as fh:
        return json.load(fh)


def embedded(ws, page, block_id):
    html = open(os.path.join(ws, page), encoding="utf-8").read()
    m = re.search(r'<script id="%s" type="application/json">(.*?)</script>' % block_id, html, re.S)
    assert m, f"no {block_id} block in {page}"
    return json.loads(m.group(1))


def task(ws, tid):
    return next(t for t in data(ws, "tasks.json")["tasks"] if t["id"] == tid)


def diagram_check(tmp):
    """The milestone diagram is laid out by roadmap.html's own JavaScript, so the only
    honest way to check it is to run that JavaScript. tests/test_diagram.js does exactly
    that against a stub DOM; all this does is build the workspaces to point it at. Node
    isn't a dependency of the tool, so a missing one is a skip, not a failure."""
    if not shutil.which("node"):
        print("  SKIP  diagram layout (node not on PATH)")
        return
    pages = []
    for n in (1, 3, 6):
        ws = os.path.join(tmp, f"diagram{n}")
        subprocess.run([sys.executable, os.path.join(REPO, "scripts", "init_workspace.py"),
                        ws, "--name", f"{n} milestones"], capture_output=True, text=True, check=True)
        for i in range(n):
            run(ws, "roadmap_cli.py", "add", "--name", f"Milestone {i + 1}")
        pages.append(os.path.join(ws, "roadmap.html"))
    p = subprocess.run(["node", os.path.join(HERE, "test_diagram.js")] + pages,
                       capture_output=True, text=True)
    print(p.stdout.rstrip())
    check("diagram: legend fits inside the viewBox at every milestone count",
          p.returncode == 0, p.stderr.strip())

    # --- drag-drop: only 4 columns draggable, toast builds a real CLI command --------
    html = open(os.path.join(ws, "tasks.html"), encoding="utf-8").read()
    check("drag-drop: tasks.html wires onDragStart", "function onDragStart" in html)
    check("drag-drop: tasks.html wires onDrop", "function onDrop" in html)
    check("drag-drop: DRAGGABLE_COLS lists the 4 manual-verify columns",
          "'ready_for_review', 'testing', 'accepted', 'rejected'" in html)
    # backlog must not appear in the DRAGGABLE_COLS array — drag-drop there would let
    # humans bypass the agent claim/release flow, which is the whole reason these
    # columns are click-only.
    draggable_block = html.split("DRAGGABLE_COLS")[1].split("]")[0]
    check("drag-drop: backlog is intentionally NOT in the draggable set",
          "'backlog'" not in draggable_block)
    check("drag-drop: drag-target CSS exists", ".col.drag-target .col-cards" in html)
    check("drag-drop: toast CSS exists", ".dd-toast" in html)
    check("drag-drop: toast builder emits an `update` command",
          "showMoveToast" in html and "scripts/tasks_cli.py update" in html)
    # JS only shows the toast — the actual write goes through the CLI we already
    # exercise. Verify the equivalent CLI move works and produces a log entry.
    p = run(ws, "tasks_cli.py", "add", "--title", "drag target")
    drag_id = p.stdout.strip().split()[-1]  # "created T-9001"
    run(ws, "tasks_cli.py", "update", drag_id, "--status", "ready_for_review",
        "--actor", "drag-drop-test")
    check("drag-drop: CLI accepts a status move the toast would build",
          task(ws, drag_id)["status"] == "ready_for_review",
          task(ws, drag_id)["status"])
    check("drag-drop: that CLI move writes a log entry on the task",
          any("status: backlog -> ready_for_review" in l["detail"]
              for l in task(ws, drag_id)["log"]))


def main():
    tmp = tempfile.mkdtemp(prefix="openlead-test-")
    ws = os.path.join(tmp, "ws")
    try:
        p = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "init_workspace.py"),
                            ws, "--name", "Test Project", "--tagline", "tagline here"],
                           capture_output=True, text=True)
        check("init_workspace scaffolds a workspace", p.returncode == 0, p.stderr.strip())
        for f in ("index.html", "roadmap.html", "tasks.html", "memory.html"):
            check(f"  {f} created", os.path.exists(os.path.join(ws, f)))

        # --- fix 1: milestone ids start at M1 -------------------------------------------
        run(ws, "roadmap_cli.py", "add", "--name", "First", "--status", "next")
        run(ws, "roadmap_cli.py", "add", "--name", "Second")
        ids = [m["id"] for m in data(ws, "roadmap.json")["milestones"]]
        check("fix 1: first milestone id is M1, not M0", ids == ["M1", "M2"], f"got {ids}")

        # --- fix 2: `add --related-to` writes both sides ---------------------------------
        run(ws, "tasks_cli.py", "add", "--title", "A")
        run(ws, "tasks_cli.py", "add", "--title", "B", "--related-to", "T-0001", "--actor", "tester")
        check("fix 2: add --related-to writes the backlink",
              task(ws, "T-0001")["relatedTo"] == ["T-0002"], str(task(ws, "T-0001")["relatedTo"]))
        check("fix 2: and the forward link", task(ws, "T-0002")["relatedTo"] == ["T-0001"])
        check("fix 2: backlink is logged on the other task",
              any("relatedTo += T-0002" in l["detail"] for l in task(ws, "T-0001")["log"]))
        run(ws, "tasks_cli.py", "add", "--title", "C", "--blocked-by", "T-0001")
        check("blockedBy stays one-directional (not symmetric)",
              task(ws, "T-0001")["blockedBy"] == [] and task(ws, "T-0003")["blockedBy"] == ["T-0001"])

        # --- fix 4: warning wording on the update path -----------------------------------
        p = run(ws, "tasks_cli.py", "update", "T-0001", "--milestone", "M9")
        check("fix 4: unknown-milestone warning does not say 'created' on update",
              "still be saved" in p.stderr and "still be created" not in p.stderr, p.stderr.strip())
        p = run(ws, "tasks_cli.py", "update", "T-0001", "--milestone", "M1")
        check("known milestone produces no warning", p.stderr.strip() == "", p.stderr.strip())

        # --- fix 5a: no-op update changes nothing ----------------------------------------
        before = task(ws, "T-0001")
        n_log, updated_at = len(before["log"]), before["updatedAt"]
        p = run(ws, "tasks_cli.py", "update", "T-0001", "--status", "backlog", "--urgency", "medium")
        after = task(ws, "T-0001")
        check("fix 5a: no-op update reports 'no changes'", "no changes" in p.stdout, p.stdout.strip())
        check("fix 5a: no-op update adds no log entry", len(after["log"]) == n_log)
        check("fix 5a: no-op update leaves updatedAt alone", after["updatedAt"] == updated_at)
        p = run(ws, "tasks_cli.py", "update", "T-0001", "--status", "development", "--actor", "tester")
        after = task(ws, "T-0001")
        check("real update still logs exactly one entry", len(after["log"]) == n_log + 1)
        check("real update records the transition",
              after["log"][-1]["detail"] == "status: backlog -> development", after["log"][-1]["detail"])
        check("real update records the actor", after["log"][-1]["actor"] == "tester")

        # --- fix 5b: repeat link changes nothing -----------------------------------------
        n_log = len(task(ws, "T-0002")["log"])
        p = run(ws, "tasks_cli.py", "link", "T-0002", "--related-to", "T-0001")
        check("fix 5b: repeat link reports 'nothing to link'", "nothing to link" in p.stdout, p.stdout.strip())
        check("fix 5b: repeat link adds no log entry", len(task(ws, "T-0002")["log"]) == n_log)
        run(ws, "tasks_cli.py", "link", "T-0003", "--related-to", "T-0001")
        check("a genuinely new link still works",
              "T-0003" in task(ws, "T-0001")["relatedTo"] and "T-0001" in task(ws, "T-0003")["relatedTo"])
        p = run(ws, "tasks_cli.py", "link", "T-0001", "--related-to", "T-0001", expect_ok=False)
        check("self-link still refused", p.returncode != 0 and "itself" in p.stderr, p.stderr.strip())

        # --- fix 6: list validates --status ----------------------------------------------
        p = run(ws, "tasks_cli.py", "list", "--status", "doing", expect_ok=False)
        check("fix 6: bogus --status exits non-zero", p.returncode != 0, str(p.returncode))
        check("fix 6: bogus --status names the valid set", "invalid status" in p.stderr, p.stderr.strip())
        p = run(ws, "tasks_cli.py", "list", "--status", "development")
        check("valid --status still filters", "T-0001" in p.stdout and "T-0002" not in p.stdout, p.stdout.strip())
        p = run(ws, "tasks_cli.py", "list", "--status", "testing")
        check("empty-but-valid column still says so", "(no matching tasks)" in p.stdout, p.stdout.strip())

        # --- fix 7: atomic HTML render ----------------------------------------------------
        for page, block in (("tasks.html", "board-data"), ("roadmap.html", "roadmap-data"),
                            ("memory.html", "journal-data"), ("index.html", "project-data")):
            embedded(ws, page, block)
        check("fix 7: all four pages' embedded JSON parses", True)
        leftovers = [f for f in os.listdir(ws) if f.endswith(".tmp")] + \
                    [f for f in os.listdir(os.path.join(ws, "data")) if f.endswith(".tmp") or f.endswith(".lock")]
        check("fix 7: no .tmp/.lock files left behind", not leftovers, str(leftovers))
        check("fix 7: rendered board matches tasks.json",
              embedded(ws, "tasks.html", "board-data") == data(ws, "tasks.json"))

        # --- regressions around the changed code -------------------------------------------
        run(ws, "tasks_cli.py", "add", "--title", "</script><img src=x>", "--desc", "çğüöşı & <b>")
        board = embedded(ws, "tasks.html", "board-data")
        raw = open(os.path.join(ws, "tasks.html"), encoding="utf-8").read()
        check("script-closing title cannot break out of the data block",
              "</script><img" not in raw and any(t["title"] == "</script><img src=x>" for t in board["tasks"]))
        check("non-ASCII survives the JSON round trip",
              any(t["description"] == "çğüöşı & <b>" for t in board["tasks"]))

        run(ws, "tasks_cli.py", "delete", "T-0001", "--actor", "tester")
        check("deleting a task drops it from other tasks' relatedTo",
              task(ws, "T-0002")["relatedTo"] == [] and task(ws, "T-0003")["relatedTo"] == [])
        check("deleting a task drops it from other tasks' blockedBy",
              task(ws, "T-0003")["blockedBy"] == [])

        p = run(ws, "tasks_cli.py", "session", "T-0002", "--agent", "code-reviewer",
                "--duration-sec", "12.5", "--tokens", "900", "--summary", "reviewed")
        s = task(ws, "T-0002")["sessions"][-1]
        check("session ledger records agent/duration/tokens",
              s["agent"] == "code-reviewer" and s["durationSec"] == 12.5 and s["tokens"] == 900)

        run(ws, "tasks_cli.py", "comment", "T-0002", "--author", "me", "--text", "hi", "--role", "reviewer")
        check("comment lands with its role", task(ws, "T-0002")["comments"][-1]["role"] == "reviewer")
        p = run(ws, "tasks_cli.py", "comment", "T-0002", "--author", "me", "--text", "x",
                "--role", "wizard", expect_ok=False)
        check("bogus comment role refused", p.returncode != 0, p.stderr.strip())

        # roadmap
        run(ws, "roadmap_cli.py", "move", "M1", "--position", "1")
        check("roadmap move reorders", [m["id"] for m in data(ws, "roadmap.json")["milestones"]] == ["M2", "M1"])
        p = run(ws, "roadmap_cli.py", "delete", "M2")
        check("roadmap delete is quiet when nothing points at the milestone",
              p.stdout.strip() == "deleted M2", p.stdout.strip())
        run(ws, "tasks_cli.py", "update", "T-0002", "--milestone", "M1")
        p = run(ws, "roadmap_cli.py", "delete", "M1")
        check("roadmap delete warns about tasks still pointing at it",
              "still have this as" in p.stdout and "T-0002" in p.stdout, p.stdout.strip())
        p = run(ws, "roadmap_cli.py", "add", "--name", "Third", "--status", "bogus", expect_ok=False)
        check("bogus milestone status refused", p.returncode != 0, p.stderr.strip())

        # memory
        note = os.path.join(tmp, "note.txt")
        open(note, "w", encoding="utf-8").write("first note\n")
        run(ws, "memory_cli.py", "create", "--name", "Journal", "--owner", "agent-a", "--content-file", note)
        entries = data(ws, "memory.json")["entries"]
        check("memory create makes M-0001", entries[0]["id"] == "M-0001", entries[0]["id"])
        open(note, "w", encoding="utf-8").write("second note\n")
        run(ws, "memory_cli.py", "append", "M-0001", "--content-file", note, "--author", "agent-b")
        e = data(ws, "memory.json")["entries"][0]
        check("memory append keeps the earlier content",
              "first note" in e["content"] and "second note" in e["content"])
        check("memory append adds the author as a contributor", "agent-b" in e["contributors"])

        # project
        run(ws, "project_cli.py", "update", "--name", "Renamed", "--pitch", "the pitch")
        check("project update reaches index.html",
              embedded(ws, "index.html", "project-data")["name"] == "Renamed")

        # --- concurrency: the lock must not let a parallel add vanish ----------------------
        errs = []

        def add(i):
            r = run(ws, "tasks_cli.py", "add", "--title", f"parallel {i}", expect_ok=False)
            if r.returncode != 0:
                errs.append(r.stderr.strip())

        threads = [threading.Thread(target=add, args=(i,)) for i in range(5)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        titles = [t["title"] for t in data(ws, "tasks.json")["tasks"]]
        got = sum(1 for t in titles if t.startswith("parallel "))
        check("5 concurrent adds all land", got == 5 and not errs, f"landed {got}, errors {errs}")
        ids = [t["id"] for t in data(ws, "tasks.json")["tasks"]]
        check("no duplicate task ids after concurrent adds", len(ids) == len(set(ids)), str(ids))

        # --- init --force keeps data and re-renders ----------------------------------------
        p = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "init_workspace.py"),
                            ws, "--name", "Renamed"], capture_output=True, text=True)
        check("re-init without --force refuses", p.returncode != 0, p.stdout.strip())
        n_tasks = len(data(ws, "tasks.json")["tasks"])
        p = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "init_workspace.py"),
                            ws, "--name", "Renamed", "--force"], capture_output=True, text=True)
        check("re-init --force succeeds", p.returncode == 0, p.stderr.strip())
        check("re-init --force keeps existing tasks", len(data(ws, "tasks.json")["tasks"]) == n_tasks)
        check("re-init --force re-renders the board from real data",
              len(embedded(ws, "tasks.html", "board-data")["tasks"]) == n_tasks)
        check("re-init --force keeps milestone seq (no id reuse)",
              data(ws, "roadmap.json")["_meta"]["nextMilestoneSeq"] == 3,
              str(data(ws, "roadmap.json")["_meta"]["nextMilestoneSeq"]))

        # --- the diagram's own layout, checked in JS where it actually runs -------------
        diagram_check(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("\nFAILURES:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
