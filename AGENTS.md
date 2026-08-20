# OpenLead — Agent guide

How AI coding agents (Claude Code, OpenCode, Codex, GLM, others) use the OpenLead board to work as a real coder/reviewer team.

## Mental model

```
   PM (you)
     │
     ▼
  tasks_cli.py add       ──►  backlog → development → ready_for_review
     │                              ▲                     │
     │                              │                     ▼
     │                          (coder agent)         (reviewer agent)
     │                              │                     │
     └──────────► memory_cli ◄──────┴─────────────────────┘
                  (notes that survive context compaction)
```

The board is the source of truth. Status changes, claims, reviews, and effort (tokens + duration) all live there. No transcript, no chat scrollback.

## Setup (one-time)

```bash
git clone https://github.com/Ege-BULUT/openlead
python3 openlead/scripts/init_workspace.py ~/projects/my-project/pm \
  --name "My Project" --tagline "One-line description"
```

OpenLead ships as a Claude Code Agent Skill at `SKILL.md`. Symlink or copy to your harness's skill dir (see provider matrix below).

## Subagent protocol (mandatory)

Every coding subagent **must** do all four steps. Skip one and the audit trail breaks.

### 1. Claim before coding

```bash
python3 scripts/tasks_cli.py claim T-XXXX --actor "<your-name>"
```

- Fails if the task already has an `assignee` — prevents two agents picking the same work.
- Sets status to `development`.
- Records a claim event in `log[]`.

If the claim fails, stop and pick another task, or ask the PM.

### 2. Do the work

Edit code. Run tests. The board doesn't see file changes — `git status` is yours, not the board's.

### 3. Mark done with session telemetry

The Agent tool reports `duration_ms` and `subagent_tokens` in its completion notification. Pass those through:

```bash
python3 scripts/tasks_cli.py update T-XXXX \
  --status ready_for_review \
  --actor "<your-name>" \
  --duration-sec <ms/1000> \
  --tokens <n> \
  --summary "one-line: what you actually did"
```

One call updates status **and** appends a session entry. Reviewer can see exactly what was spent.

### 4. Reviewer agent: structured verdict

```bash
python3 scripts/tasks_cli.py review T-XXXX \
  --verdict approve | request_changes | reject \
  --reviewer "<your-name>" \
  --notes "..." \
  --duration-sec <ms/1000> \
  --tokens <n>
```

`review` records verdict + reviewer + telemetry in one entry. Kanban can color-code by verdict.

## Coder prompt template

```
You are the coder for [T-XXXX].
1. Read: `python3 scripts/tasks_cli.py show T-XXXX`
2. Claim: `python3 scripts/tasks_cli.py claim T-XXXX --actor "<your-name>"`
3. Implement. Test. Commit locally.
4. When done:
   python3 scripts/tasks_cli.py update T-XXXX \
     --status ready_for_review --actor "<your-name>" \
     --duration-sec <Agent.tool.duration_ms / 1000> \
     --tokens <Agent.tool.subagent_tokens> \
     --summary "one-line summary"
Never edit data/*.json directly. CLI is the only writer.
```

## Reviewer prompt template

```
You are the reviewer for [T-XXXX].
1. Read: `python3 scripts/tasks_cli.py show T-XXXX`
2. Read the code diff (`git diff main...HEAD` or similar).
3. Verdict:
   python3 scripts/tasks_cli.py review T-XXXX \
     --verdict approve | request_changes | reject \
     --reviewer "<your-name>" --notes "..." \
     --duration-sec <ms/1000> --tokens <n>
If requesting changes, the coder picks the task back up — status stays at development.
If approving, PM moves to accepted.
Never edit data/*.json directly.
```

## Parallel-team rules

- **Independent tasks → spawn in one message.** When the PM sees multiple tasks with empty `blockedBy`, fire all coder subagents in a single message (multiple Agent tool calls). Wall-clock = slowest, not sum.
- **Blocked tasks → sequence.** Check `blockedBy` is empty before claiming.
- **Two agents on the same epic → use `relatedTo`, not duplicate code.** Epics hold sub-tasks via `relatedTo`. Coder for one sub-task reads the epic's description but doesn't touch siblings.
- **Long I/O → dedicated agent.** Big asset downloads, vendor file fetches, and asset pipelines deserve their own subagent — they block the main thread otherwise.
- **Memory journals outlive context.** `memory_cli.py create --name "..." --owner "<name>" --content-file notes.md` then `append` as work progresses. Survives compaction, available to the next session.

## CLI reference (quick)

```bash
# list / inspect
tasks_cli.py list [--status STATUS] [--tag TAG] [--owner OWNER]
tasks_cli.py show T-XXXX

# mutate (every mutating command auto-logs + re-renders tasks.html)
tasks_cli.py add --title "..." [--status backlog] [--urgency medium]
                 [--milestone M1] [--tag backend] [--desc "..."]
                 [--ref abc1234] [--blocked-by T-YYYY] [--related-to T-ZZZZ]
                 [--owner "..."] [--actor "..."]
tasks_cli.py claim T-XXXX --actor "<name>"        # atomic claim; sets assignee + moves to development
tasks_cli.py release T-XXXX --actor "<name>"      # drop claim (--force to override)
tasks_cli.py update T-XXXX --status development
                 [--urgency high] [--owner "..."] [--milestone M1]
                 [--ref sha] [--title "..."] [--desc "..."]
                 [--actor "..."]
                 [--duration-sec N] [--tokens N] [--summary "..."]  # inline session telemetry
tasks_cli.py review T-XXXX --verdict approve|request_changes|reject
                 --reviewer "<name>" --notes "..." [--duration-sec N] [--tokens N]
tasks_cli.py comment T-XXXX --author "<name>" --text "..." [--role tester|engineer|reviewer|human]
tasks_cli.py link T-XXXX --blocked-by T-YYYY --related-to T-ZZZZ --actor "..."
tasks_cli.py unlink T-XXXX --blocked-by T-YYYY --actor "..."
tasks_cli.py delete T-XXXX --actor "..."     # also drops id from every other task's links
tasks_cli.py session T-XXXX --agent "<name>" [--duration-sec N] [--tokens N] [--summary "..."]
tasks_cli.py render    # regenerate tasks.html from tasks.json (only needed after hand-edit)
```

A file lock (`data/tasks.json.lock`) already serializes concurrent CLI calls. Spawning multiple `tasks_cli.py` from parallel subagents is safe.

## Provider portability matrix

`SKILL.md` is plain Markdown — drop it into any harness's skill dir.

| Harness       | Skill path                              | Notes |
|---------------|-----------------------------------------|-------|
| Claude Code   | `.claude/skills/openlead/SKILL.md`      | Native — auto-loaded. |
| OpenCode      | `.claude/skills/openlead/SKILL.md`      | Same path; OpenCode reads Claude's skill dir. |
| Codex CLI     | `.codex/skills/openlead/SKILL.md`       | Copy or `ln -s`. |
| GLM Code      | Consult their skill-dir docs; copy `SKILL.md` verbatim. | |
| Other CLIs    | Consult their skill-dir convention; copy `SKILL.md` verbatim. | |

The board itself (`data/*.json`, `*.html`, `scripts/*.py`) is harness-agnostic — Python stdlib only, no framework. A team using Claude Code for coding and Codex for review can share the same board via `git`.

## Why this beats a chat transcript

- **Survives context compaction.** Board state is on disk, not in the model's context window.
- **Auditable.** `log[]` = what changed; `sessions[]` = who, how long, how many tokens; `comments[]` = reviewer notes; `verdict` = structured decision.
- **Provider-portable.** Same board works across Claude, OpenCode, Codex, GLM.
- **Local.** No account, no sync, no leak.
- **Cost-visible.** Sum `sessions[].tokens` per task to see where budget goes.

## When NOT to use the board

- One-line typo fix or 5-minute tweak — overkill, just edit and commit.
- Throwaway exploration — `memory_cli.py` is enough.
- External PR description — board is internal; PR text still goes in the commit body / PR template.
