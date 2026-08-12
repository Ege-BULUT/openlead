#!/usr/bin/env python3
"""tasks_cli.py — the read/write interface to this workspace's task board.

Fully local: this touches only files under this workspace's data/ directory. Never call
anything network-facing from here. Agents (and humans) use this instead of hand-editing
tasks.json, so ids, timestamps, and the rendered tasks.html stay consistent.

  tasks_cli.py list [--status STATUS] [--tag TAG] [--owner OWNER]
  tasks_cli.py show T-0001
  tasks_cli.py add --title "..." [--status backlog] [--urgency medium] [--tag frontend]
                   [--desc "..."] [--ref design-doc#3 ...] [--blocked-by T-0002 ...]
                   [--related-to T-0005 ...] [--owner "..."] [--actor "..."]
  tasks_cli.py update T-0001 [--status development] [--urgency high] [--owner "..."]
                   [--title "..."] [--desc "..."] [--actor "..."]
  tasks_cli.py comment T-0001 --author "tester-agent" --text "..." [--role tester|engineer|reviewer|human]
  tasks_cli.py link T-0001 [--blocked-by T-0002] [--related-to T-0005] [--actor "..."]
  tasks_cli.py session T-0001 --agent "code-reviewer" [--duration-sec 340] [--tokens 12345]
                   [--summary "..."] [--started-at ISO] [--ended-at ISO]
      # records one agent's work session on a task: who, how long, how many tokens, what happened.
      # Call this whenever a subagent finishes a piece of work on a task — the Agent tool's
      # completion notification already reports duration_ms/subagent_tokens for exactly this.
  tasks_cli.py render          # regenerate tasks.html's embedded data block from tasks.json

Every mutating command (add/update/comment/link/session) re-renders tasks.html automatically
and appends a timestamped entry to the task's own `log[]` — a full audit trail of what changed,
who changed it, and when — visible in the task's detail view. `render` alone is only needed if
tasks.json was hand-edited.
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_PATH = os.path.join(ROOT, "data", "tasks.json")
HTML_PATH = os.path.join(ROOT, "tasks.html")
VALID_URGENCY = ("low", "medium", "high", "critical")
VALID_ROLES = ("tester", "engineer", "reviewer", "human")


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def load():
    with open(DATA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def save(db):
    with open(DATA_PATH, "w", encoding="utf-8") as fh:
        json.dump(db, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _valid_statuses(db):
    return db["_meta"]["columns"]


def _find(db, task_id):
    for t in db["tasks"]:
        if t["id"] == task_id:
            return t
    sys.exit(f"no such task: {task_id}")


def _new_id(db):
    seq = db["_meta"]["nextTaskSeq"]
    db["_meta"]["nextTaskSeq"] = seq + 1
    return f'{db["_meta"]["taskIdPrefix"]}{seq:04d}'


def _log_event(task, event, detail="", actor="unspecified"):
    """Every mutating command calls this — one line, no agent has to remember to log anything
    separately. `log[]` is the WHAT-changed/WHO/WHEN audit trail; it's distinct from
    `sessions[]` (the effort/cost ledger — see cmd_session), which nothing can auto-measure."""
    task.setdefault("log", []).append({
        "ts": _now(), "actor": actor or "unspecified", "event": event, "detail": detail,
    })


def cmd_list(db, args):
    tasks = db["tasks"]
    if args.status:
        tasks = [t for t in tasks if t["status"] == args.status]
    if args.tag:
        tasks = [t for t in tasks if t.get("tag") == args.tag]
    if args.milestone:
        tasks = [t for t in tasks if t.get("milestone") == args.milestone]
    if args.owner:
        tasks = [t for t in tasks if t.get("owner") == args.owner]
    if not tasks:
        print("(no matching tasks)")
        return
    for t in tasks:
        print(f'{t["id"]}  [{t["status"]:<17}] {t.get("urgency","-"):<8} {t["title"]}')


def cmd_show(db, args):
    t = _find(db, args.task_id)
    print(json.dumps(t, indent=2, ensure_ascii=False))


def cmd_add(db, args):
    status = args.status or db["_meta"]["columns"][0]
    if status not in _valid_statuses(db):
        sys.exit(f"invalid status {status!r} — one of {_valid_statuses(db)}")
    if args.urgency not in VALID_URGENCY:
        sys.exit(f"invalid urgency {args.urgency!r} — one of {VALID_URGENCY}")
    now = _now()
    task = {
        "id": _new_id(db),
        "title": args.title,
        "description": args.desc or "",
        "status": status,
        "urgency": args.urgency,
        "tag": args.tag or None,
        "milestone": args.milestone or None,
        "refs": args.ref or [],
        "blockedBy": args.blocked_by or [],
        "relatedTo": args.related_to or [],
        "owner": args.owner or "",
        "createdAt": now,
        "updatedAt": now,
        "comments": [],
        "log": [],
        "sessions": [],
    }
    _log_event(task, "created", f"status={status}, urgency={args.urgency}", getattr(args, "actor", None))
    db["tasks"].append(task)
    save(db)
    render(db)
    print(f'created {task["id"]}')


def cmd_update(db, args):
    t = _find(db, args.task_id)
    changes = []
    if args.status:
        if args.status not in _valid_statuses(db):
            sys.exit(f"invalid status {args.status!r} — one of {_valid_statuses(db)}")
        if args.status != t["status"]:
            changes.append(f'status: {t["status"]} -> {args.status}')
        t["status"] = args.status
    if args.urgency:
        if args.urgency not in VALID_URGENCY:
            sys.exit(f"invalid urgency {args.urgency!r} — one of {VALID_URGENCY}")
        if args.urgency != t["urgency"]:
            changes.append(f'urgency: {t["urgency"]} -> {args.urgency}')
        t["urgency"] = args.urgency
    if args.title:
        if args.title != t["title"]:
            changes.append("title edited")
        t["title"] = args.title
    if args.desc is not None:
        if args.desc != t["description"]:
            changes.append("description edited")
        t["description"] = args.desc
    if args.owner is not None:
        if args.owner != t["owner"]:
            changes.append(f'owner: {t["owner"] or "(none)"} -> {args.owner or "(none)"}')
        t["owner"] = args.owner
    if args.milestone is not None:
        if args.milestone != t.get("milestone"):
            changes.append(f'milestone: {t.get("milestone") or "(none)"} -> {args.milestone}')
        t["milestone"] = args.milestone
    if changes:
        _log_event(t, "updated", "; ".join(changes), args.actor)
    t["updatedAt"] = _now()
    save(db)
    render(db)
    print(f'updated {t["id"]}')


def cmd_comment(db, args):
    t = _find(db, args.task_id)
    role = args.role or "human"
    if role not in VALID_ROLES:
        sys.exit(f"invalid role {role!r} — one of {VALID_ROLES}")
    t.setdefault("comments", []).append({
        "author": args.author,
        "role": role,
        "date": _now(),
        "text": args.text,
    })
    _log_event(t, "comment", f'{args.text[:80]}{"…" if len(args.text) > 80 else ""}', args.author)
    t["updatedAt"] = _now()
    save(db)
    render(db)
    print(f'commented on {t["id"]}')


def cmd_link(db, args):
    t = _find(db, args.task_id)
    if args.blocked_by:
        _find(db, args.blocked_by)  # must exist
        if args.blocked_by not in t["blockedBy"]:
            t["blockedBy"].append(args.blocked_by)
            _log_event(t, "linked", f"blockedBy += {args.blocked_by}", args.actor)
    if args.related_to:
        other = _find(db, args.related_to)
        if args.related_to not in t["relatedTo"]:
            t["relatedTo"].append(args.related_to)
            _log_event(t, "linked", f"relatedTo += {args.related_to}", args.actor)
        if t["id"] not in other["relatedTo"]:
            other["relatedTo"].append(t["id"])
            _log_event(other, "linked", f"relatedTo += {t['id']}", args.actor)
    t["updatedAt"] = _now()
    save(db)
    render(db)
    print(f'linked {t["id"]}')


def cmd_session(db, args):
    """Log one agent's work session on a task: who, how long, how many tokens, what happened.
    The CLI can't measure this itself — pass it explicitly, typically right after a subagent's
    Agent-tool completion notification reports duration_ms/subagent_tokens for the work it just did."""
    t = _find(db, args.task_id)
    session = {
        "ts": _now(),
        "agent": args.agent,
        "startedAt": args.started_at or "",
        "endedAt": args.ended_at or "",
        "durationSec": args.duration_sec,
        "tokens": args.tokens,
        "summary": args.summary or "",
    }
    t.setdefault("sessions", []).append(session)
    detail = f"agent={args.agent}"
    if args.duration_sec is not None:
        detail += f", {args.duration_sec:.0f}s"
    if args.tokens is not None:
        detail += f", {args.tokens} tokens"
    _log_event(t, "session", detail, args.agent)
    t["updatedAt"] = _now()
    save(db)
    render(db)
    print(f'logged session on {t["id"]}')


def render(db):
    """Regenerate ONLY the embedded <script id="board-data"> JSON block in tasks.html —
    never touches the surrounding page chrome, so hand-edited CSS/layout survives every
    render."""
    if not os.path.exists(HTML_PATH):
        print(f"WARN: {HTML_PATH} not found — skipping render", file=sys.stderr)
        return
    html = open(HTML_PATH, encoding="utf-8").read()
    payload = json.dumps(db, indent=2, ensure_ascii=False)
    pattern = re.compile(
        r'(<script id="board-data" type="application/json">)(.*?)(</script>)',
        re.S,
    )
    new_html, n = pattern.subn(lambda m: m.group(1) + "\n" + payload + "\n" + m.group(3), html, count=1)
    if n == 0:
        sys.exit(f'no <script id="board-data"> block found in {HTML_PATH} — cannot render')
    open(HTML_PATH, "w", encoding="utf-8").write(new_html)


def cmd_render(db, _args):
    render(db)
    print("rendered tasks.html")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list")
    p.add_argument("--status")
    p.add_argument("--tag")
    p.add_argument("--milestone")
    p.add_argument("--owner")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("show")
    p.add_argument("task_id")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("add")
    p.add_argument("--title", required=True)
    p.add_argument("--status")
    p.add_argument("--urgency", default="medium")
    p.add_argument("--tag")
    p.add_argument("--milestone")
    p.add_argument("--desc")
    p.add_argument("--ref", action="append")
    p.add_argument("--blocked-by", action="append")
    p.add_argument("--related-to", action="append")
    p.add_argument("--owner")
    p.add_argument("--actor", help="who/what is creating this (for the log) — defaults to unspecified")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("update")
    p.add_argument("task_id")
    p.add_argument("--status")
    p.add_argument("--urgency")
    p.add_argument("--title")
    p.add_argument("--desc")
    p.add_argument("--owner")
    p.add_argument("--milestone")
    p.add_argument("--actor", help="who/what is making this change (for the log)")
    p.set_defaults(fn=cmd_update)

    p = sub.add_parser("comment")
    p.add_argument("task_id")
    p.add_argument("--author", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--role")
    p.set_defaults(fn=cmd_comment)

    p = sub.add_parser("link")
    p.add_argument("task_id")
    p.add_argument("--blocked-by")
    p.add_argument("--related-to")
    p.add_argument("--actor", help="who/what is making this link (for the log)")
    p.set_defaults(fn=cmd_link)

    p = sub.add_parser("session")
    p.add_argument("task_id")
    p.add_argument("--agent", required=True, help="subagent name/type, e.g. code-reviewer, general-purpose, fork")
    p.add_argument("--duration-sec", type=float, help="wall-clock seconds spent (from the Agent tool's duration_ms/1000)")
    p.add_argument("--tokens", type=int, help="tokens spent (from the Agent tool's subagent_tokens)")
    p.add_argument("--summary", help="one line: what the agent actually did")
    p.add_argument("--started-at", help="ISO timestamp, if known — alternative/addition to --duration-sec")
    p.add_argument("--ended-at", help="ISO timestamp, if known")
    p.set_defaults(fn=cmd_session)

    p = sub.add_parser("render")
    p.set_defaults(fn=cmd_render)

    args = ap.parse_args()
    db = load()
    if args.cmd == "show":
        cmd_show(db, args)
        return
    args.fn(db, args)


if __name__ == "__main__":
    main()
