#!/usr/bin/env python3
"""roadmap_cli.py — the read/write interface to this workspace's roadmap.

Fully local: this touches only files under this workspace's data/ directory. Agents (and
humans) use this instead of hand-editing roadmap.json, so ids and the rendered roadmap.html
(both the milestone cards AND the auto-generated diagram) stay consistent.

  roadmap_cli.py list
  roadmap_cli.py show M1
  roadmap_cli.py add --name "Duplicate cleanup" [--status planned] [--description "..."]
                     [--why "..."] [--chip "9 tasks"] [--chip "Effort: small"]
  roadmap_cli.py update M1 [--name "..."] [--status done|next|planned] [--description "..."]
                          [--why "..."]
  roadmap_cli.py example M1 --tag P0 --text "Two config files disagree on the source of truth"
      # adds one bullet to a milestone's illustrative example list
  roadmap_cli.py chip M1 --text "Effort: small"
      # adds one small plain-text badge/chip to a milestone's footer (effort, risk, a count —
      # whatever's useful). Every milestone card also gets an automatic "Tasks →" link to
      # tasks.html?milestone=<id> for free — you don't need a chip for that.
  roadmap_cli.py move M1 --position 2
      # milestone order is display order; 0-based position, moves M1 to index 2
  roadmap_cli.py note --text "A provenance caveat shown below all milestone cards"
  roadmap_cli.py intro --text "One-paragraph subtitle shown under the Roadmap H1"
  roadmap_cli.py render          # regenerate roadmap.html's embedded data block from roadmap.json

Status is exactly one of: done, next, planned. Exactly one milestone should normally be "next"
(what the diagram highlights as the focal, up-next node) — this CLI doesn't enforce that, it's
a convention, not a constraint, because a brief moment with zero or two "next" milestones during
a transition isn't actually invalid.

Every mutating command re-renders roadmap.html automatically. `render` alone is only needed if
roadmap.json was hand-edited.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_PATH = os.path.join(ROOT, "data", "roadmap.json")
HTML_PATH = os.path.join(ROOT, "roadmap.html")
VALID_STATUS = ("done", "next", "planned")


def load():
    with open(DATA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def save(db):
    with open(DATA_PATH, "w", encoding="utf-8") as fh:
        json.dump(db, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _find(db, milestone_id):
    for m in db["milestones"]:
        if m["id"] == milestone_id:
            return m
    sys.exit(f"no such milestone: {milestone_id}")


def _new_id(db):
    seq = db["_meta"]["nextMilestoneSeq"]
    db["_meta"]["nextMilestoneSeq"] = seq + 1
    return f'{db["_meta"]["milestoneIdPrefix"]}{seq}'


def cmd_list(db, _args):
    if not db["milestones"]:
        print("(no milestones yet)")
        return
    for m in db["milestones"]:
        print(f'{m["id"]:<4} [{m["status"]:<7}] {m["name"]}')


def cmd_show(db, args):
    print(json.dumps(_find(db, args.milestone_id), indent=2, ensure_ascii=False))


def cmd_add(db, args):
    status = args.status or "planned"
    if status not in VALID_STATUS:
        sys.exit(f"invalid status {status!r} — one of {VALID_STATUS}")
    m = {
        "id": _new_id(db),
        "name": args.name,
        "status": status,
        "description": args.description or "",
        "why": args.why or "",
        "examples": [],
        "chips": list(args.chip or []),
    }
    db["milestones"].append(m)
    save(db)
    render(db)
    print(f'created {m["id"]}')


def cmd_update(db, args):
    m = _find(db, args.milestone_id)
    if args.status:
        if args.status not in VALID_STATUS:
            sys.exit(f"invalid status {args.status!r} — one of {VALID_STATUS}")
        m["status"] = args.status
    if args.name:
        m["name"] = args.name
    if args.description is not None:
        m["description"] = args.description
    if args.why is not None:
        m["why"] = args.why
    save(db)
    render(db)
    print(f'updated {m["id"]}')


def cmd_example(db, args):
    m = _find(db, args.milestone_id)
    m.setdefault("examples", []).append({"tag": args.tag or "", "text": args.text})
    save(db)
    render(db)
    print(f'added example to {m["id"]}')


def cmd_chip(db, args):
    m = _find(db, args.milestone_id)
    m.setdefault("chips", []).append(args.text)
    save(db)
    render(db)
    print(f'added chip to {m["id"]}')


def cmd_move(db, args):
    m = _find(db, args.milestone_id)
    db["milestones"].remove(m)
    pos = max(0, min(args.position, len(db["milestones"])))
    db["milestones"].insert(pos, m)
    save(db)
    render(db)
    print(f'moved {m["id"]} to position {pos}')


def cmd_note(db, args):
    db.setdefault("notes", []).append(args.text)
    save(db)
    render(db)
    print("added note")


def cmd_intro(db, args):
    db["intro"] = args.text
    save(db)
    render(db)
    print("updated intro")


def render(db):
    """Regenerate ONLY the embedded <script id="roadmap-data"> JSON block in roadmap.html —
    never touches the surrounding page chrome. roadmap.html's own JS draws the milestone-track
    diagram AND the detail cards from this same data, so one edit updates both."""
    if not os.path.exists(HTML_PATH):
        print(f"WARN: {HTML_PATH} not found — skipping render", file=sys.stderr)
        return
    html = open(HTML_PATH, encoding="utf-8").read()
    # json.dumps() doesn't escape "<", so a name/description/note containing "</script>" would
    # otherwise close the data block early and corrupt the page. < is valid JSON, decodes
    # back to "<" transparently in JSON.parse(), and can never be read as a tag by the
    # browser's HTML tokenizer, so this covers "</script>" and the "<!--<script" case too.
    payload = json.dumps(db, indent=2, ensure_ascii=False).replace("<", "\\u003c")
    pattern = re.compile(
        r'(<script id="roadmap-data" type="application/json">)(.*?)(</script>)',
        re.S,
    )
    new_html, n = pattern.subn(lambda m: m.group(1) + "\n" + payload + "\n" + m.group(3), html, count=1)
    if n == 0:
        sys.exit(f'no <script id="roadmap-data"> block found in {HTML_PATH} — cannot render')
    open(HTML_PATH, "w", encoding="utf-8").write(new_html)


def cmd_render(db, _args):
    render(db)
    print("rendered roadmap.html")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list"); p.set_defaults(fn=cmd_list)

    p = sub.add_parser("show")
    p.add_argument("milestone_id")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("add")
    p.add_argument("--name", required=True)
    p.add_argument("--status")
    p.add_argument("--description")
    p.add_argument("--why")
    p.add_argument("--chip", action="append")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("update")
    p.add_argument("milestone_id")
    p.add_argument("--name")
    p.add_argument("--status")
    p.add_argument("--description")
    p.add_argument("--why")
    p.set_defaults(fn=cmd_update)

    p = sub.add_parser("example")
    p.add_argument("milestone_id")
    p.add_argument("--tag")
    p.add_argument("--text", required=True)
    p.set_defaults(fn=cmd_example)

    p = sub.add_parser("chip")
    p.add_argument("milestone_id")
    p.add_argument("--text", required=True)
    p.set_defaults(fn=cmd_chip)

    p = sub.add_parser("move")
    p.add_argument("milestone_id")
    p.add_argument("--position", type=int, required=True)
    p.set_defaults(fn=cmd_move)

    p = sub.add_parser("note")
    p.add_argument("--text", required=True)
    p.set_defaults(fn=cmd_note)

    p = sub.add_parser("intro")
    p.add_argument("--text", required=True)
    p.set_defaults(fn=cmd_intro)

    p = sub.add_parser("render"); p.set_defaults(fn=cmd_render)

    args = ap.parse_args()
    db = load()
    if args.cmd in ("show", "list"):
        args.fn(db, args)
        return
    args.fn(db, args)


if __name__ == "__main__":
    main()
