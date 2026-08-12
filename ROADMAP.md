# OpenLead roadmap

Where the tool itself is headed — not to be confused with the `roadmap.html` a project gets
when it adopts OpenLead. This is the plan for OpenLead's own future; see `README.md` for the
short version.

Current state (v0): a single-project workspace — homepage, milestone roadmap, Kanban board,
agent memory — scaffolded by `scripts/init_workspace.py`, each page rendered from its own
`data/*.json` by a matching CLI. Fully local, single project, no docs layer beyond agent memory.

## Next

### Docs / wiki integration

Agent memory (`memory.html`) already gives agents a place to leave working notes, but it's a
flat list of journals, not a structured knowledge base — there's no hierarchy, no cross-linking
between pages, no distinction between "a note I made while debugging" and "the durable design
doc for this subsystem." The next step is a `docs/` (or `wiki/`) page, in the same
JSON-driven-CLI-editable shape as everything else here, where agents write up findings and
decisions in a structured, linkable form as they go — closer to how a team uses Confluence or
Notion, minus the server and the account. The open question is whether this absorbs agent
memory (one system, two views: "journal" vs. "wiki") or stays separate; leaning toward
absorbing it, since the failure mode of two note-taking surfaces is agents not knowing which
one to check.

### Multi-project support

Right now one OpenLead workspace = one project. Most people running multiple agent-assisted
projects will end up with multiple separate workspaces and no shared view. The natural fix is
a workspace that can register several projects (each still its own `data/` + `scripts/` +
pages) and a way to move between them without re-navigating by hand.

### Overview across all projects

Follows directly from multi-project support: a single top-level page that shows, per project,
milestone status, open task counts by column, and recent agent activity — the "team lead" view
of everything at once, rather than having to open each project's homepage to check on it.

### Skills manager

A page (and CLI) to show, add, edit, delete, and favorite the skills available across a
person's agent setup — useful once OpenLead itself is one skill among several a user has
installed, and they want one place to see what's there instead of grepping `.claude/skills/`.

## Non-goals (for now)

- **No server, ever, for the core tool.** Multi-project and the overview page can both be done
  as more static HTML + JSON + CLI, same as everything else here. If a real server ever makes
  sense (e.g. real-time multi-user sync), that's a different, clearly-labeled add-on — not a
  silent architecture change to the base tool.
- **No auto-push to any remote.** Whatever gets built, "commit and push this workspace" stays
  an explicit, user-initiated action, never something a CLI command does as a side effect.

## Contributing

This is early and the shape of the next few features isn't fully settled — if you want to work
on one of the above, opening an issue first to align on approach is more useful than a large
unsolicited PR.
