---
name: openlead
description: Scaffold and operate a fully local, portable project-management workspace for AI coding agents — a homepage, a milestone roadmap (with an auto-generated diagram), a Kanban task board, and per-agent memory journals, all driven by JSON and edited only through the bundled Python CLIs. Use when the user asks to set up a project roadmap, task board, or kanban for a project; when they want agents to track their own work with timestamps/token/duration logs; when they mention wanting a "team lead" view over agent work; or when working inside an existing OpenLead workspace (a directory containing index.html, roadmap.html, tasks.html, memory.html and a data/ + scripts/ pair).
license: MIT
compatibility: claude-code, opencode
metadata:
  audience: coding-agents
---

# OpenLead

A local project-management substrate for a codebase: a homepage, a milestone roadmap, a Kanban
task board, and agent memory journals — four static HTML pages, each rendered from a JSON file
in `data/`, mutated only through a matching Python CLI in `scripts/`. No server, no build step,
no framework, no network call anywhere. Nothing pushes to a remote on its own.

## When to use this

- The user asks you to set up a roadmap, task board, kanban, or "project HQ" for their project.
- The user wants agents to track their own work with a timestamped audit trail and effort log
  (duration, tokens, which agent did what).
- You're already inside a directory that has `index.html`, `roadmap.html`, `tasks.html`,
  `memory.html` and `data/`/`scripts/` siblings — that's an existing OpenLead workspace; read
  this file before hand-editing anything in it.

## Golden rule

**Never hand-edit `data/*.json`.** Every page is a rendered VIEW of its JSON file; the CLI is
the only writer, because it also keeps ids consistent, timestamps honest, and the HTML in sync.
If you edit the JSON directly, run the matching `... render` command before anyone opens the
page again — but prefer just using the CLI verb that does what you want.

## Set up a new workspace

```bash
python3 scripts/init_workspace.py /path/to/project/openlead-workspace \
  --name "My Project" \
  --tagline "One-line description shown on the homepage" \
  --pitch "One paragraph shown below the nav cards (optional)"
```

This copies the four HTML pages, the four CLIs, and empty `data/*.json` into the target
directory. Re-running with `--force` re-copies the HTML/scripts (safe to do — it never
touches existing `data/*.json`, so an upgrade can't destroy real project data).

## The four CLIs

Run `python3 scripts/<name>.py --help` (and `<subcommand> --help`) for the full flag list —
this section is the shape, not the reference.

### `project_cli.py` — the project's name, tagline and pitch

```bash
python3 scripts/project_cli.py update --tagline "New one-line description"
python3 scripts/project_cli.py show
```

This is what drives the homepage. `init_workspace.py` sets it once from `--name`/`--tagline`/
`--pitch` when the workspace is first scaffolded; use this CLI for any change after that,
rather than re-running `init_workspace.py --force` just to rename something.

### `roadmap_cli.py` — milestones

```bash
python3 scripts/roadmap_cli.py add --name "Duplicate cleanup" --status next \
  --description "Collapse every place the same rule lives twice into one source of truth." \
  --why "Lowest risk, and it's the drift that makes every later milestone harder to verify." \
  --chip "9 tasks" --chip "Effort: small"
python3 scripts/roadmap_cli.py example M1 --tag P0 --text "Two config files disagree"
python3 scripts/roadmap_cli.py update M1 --status done
python3 scripts/roadmap_cli.py move M1 --position 2       # milestone order = display order
python3 scripts/roadmap_cli.py note --text "A caveat shown below every milestone card"
python3 scripts/roadmap_cli.py list
```

- `status` is one of `done` / `next` / `planned`. Exactly one milestone should normally be
  `next` — that's the diagram's one focal/highlighted node — but this is a convention the CLI
  doesn't enforce.
- Keep `name` to 2-4 words — the diagram renders it inline next to its neighbors. Put the real
  detail in `--description` / `--why`, which only show in the cards below the diagram.
- The diagram (an SVG, auto-laid-out for however many milestones exist) and the detail cards
  are BOTH generated from the same `roadmap.json` by `roadmap.html`'s own JS — one `render`
  updates both.
- Every milestone card gets an automatic "Tasks →" link to `tasks.html?milestone=<id>` for
  free; you don't need to add that as a chip.

### `tasks_cli.py` — the Kanban board

```bash
python3 scripts/tasks_cli.py add --title "Fix the duplicate config" \
  --milestone M1 --tag backend --urgency high \
  --desc "Two files disagree on the source of truth." --ref "design-doc#3"
python3 scripts/tasks_cli.py update T-0001 --status development --actor "your-agent-name"
python3 scripts/tasks_cli.py comment T-0001 --author "tester-agent" --role tester \
  --text "Verified this in isolation; the fix looks correct."
python3 scripts/tasks_cli.py link T-0001 --blocked-by T-0002
python3 scripts/tasks_cli.py list --status backlog
```

Columns (fixed): `backlog → analyze → planning → development → ready_for_review → testing →
accepted (Done) / rejected`. `milestone` ties a task back to a roadmap entry; `tag` is a
freeform category (a subsystem, a component, whatever fits your project); `refs` is a freeform
list of external identifiers a task traces back to (a finding id, a ticket, a doc anchor).

**Every mutating command auto-logs.** `add`/`update`/`comment`/`link`/`session` all append a
timestamped entry to the task's own `log[]` — who changed what, and when — with zero extra
effort from you. Pass `--actor "your-name-or-agent-type"` on `update`/`link` (and `--author` on
`comment`) so the log actually says who did it; if you skip it, it's logged as `unspecified`.

### Logging agent work sessions (time + tokens + who)

If the user wants to know how much time/tokens an agent spent on a task, call `session` right
after you (or a subagent you dispatched) finish a piece of work on it:

```bash
python3 scripts/tasks_cli.py session T-0001 --agent "code-reviewer" \
  --duration-sec 340 --tokens 12845 --summary "Reviewed the fix, requested one change"
```

If you dispatched a subagent (Claude Code's Agent tool, or an equivalent in your own harness)
and its completion result reports elapsed time and token usage, that's exactly what
`--duration-sec` / `--tokens` are for — convert milliseconds to seconds and pass the token
count straight through. `--agent` is a freeform string: the subagent's name/type (e.g.
`code-reviewer`, `general-purpose`, or whatever your harness calls it).

### `memory_cli.py` — agent journals

```bash
python3 scripts/memory_cli.py create --name "Investigating the flaky test" --owner "your-agent-name" \
  --content-file /path/to/notes.txt
python3 scripts/memory_cli.py append M-0001 --content-file /path/to/more-notes.txt --author "your-agent-name"
python3 scripts/memory_cli.py list
```

Content is always passed via `--content-file` (write your notes to a file first, then point
the CLI at it) — this avoids fragile shell-escaping of long, multi-paragraph text. `append`
adds a timestamped section to an existing journal (the normal case — journals are logs, not
documents you overwrite); `update --content-file` replaces the whole body when you actually
mean to correct it.

**Read before you write.** Before doing analysis on a project that has an OpenLead workspace,
run `python3 scripts/memory_cli.py list` and skim anything relevant — someone (possibly you, in
an earlier session) may have already worked through it.

## Design notes for agents extending this workspace

- Every page's data lives in exactly one `<script id="...-data" type="application/json">`
  block. Every CLI's `render()` function replaces ONLY that block via a regex substitution —
  it never touches page chrome (CSS, layout, JS). This means you (or the project owner) can
  freely hand-edit a page's HTML/CSS/JS and it survives every future `render()` call, as long
  as you don't rename or remove that one `<script id="...">` tag.
- All four CLIs follow the same shape: `load()` → mutate → `save()` → `render()`. If you add a
  new page, follow this pattern rather than inventing a new persistence mechanism — it's what
  keeps the whole system predictable across pages.
- Nothing here calls out to a network. If you're tempted to add a "sync to a real project
  tracker" feature, make it an explicit, separate, clearly-labeled export step — never a
  silent side effect of a normal CLI command.
- See `ROADMAP.md` for where this tool itself is headed (multi-project overview, a docs/wiki
  layer, a skills manager) — useful context if you're extending OpenLead itself rather than
  just using it inside a project.
