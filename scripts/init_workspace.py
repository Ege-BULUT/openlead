#!/usr/bin/env python3
"""init_workspace.py — scaffold a new OpenLead workspace: a fully local homepage, roadmap,
task board, and agent-memory system for a project, driven entirely by JSON + a Python CLI
per page (no server, no build step, no framework).

  python3 init_workspace.py /path/to/target --name "My Project" \\
      [--tagline "One-line description shown on the homepage"] \\
      [--pitch "One paragraph shown below the nav cards"]

Idempotent-ish: refuses to overwrite an existing target directory unless --force is passed
(existing data/*.json is never touched by --force either — only the HTML/scripts are
re-copied, so a re-run can't destroy real project data. If you actually want fresh data too,
delete the target directory yourself first).

After running, cd into the target directory and open index.html — or better, start with:
  python3 scripts/roadmap_cli.py add --name "..." --status next
  python3 scripts/tasks_cli.py add --title "..."
  python3 scripts/memory_cli.py create --name "..." --owner "..."
"""
import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
TEMPLATES = os.path.join(REPO_ROOT, "templates")

PAGES = ("index.html", "roadmap.html", "tasks.html", "memory.html")
DATA_FILES = ("project.json", "roadmap.json", "tasks.json", "memory.json")
SCRIPTS = ("roadmap_cli.py", "tasks_cli.py", "memory_cli.py")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="directory to create the workspace in (will be created)")
    ap.add_argument("--name", required=True, help="project name, shown as the homepage H1 and sidebar title")
    ap.add_argument("--tagline", default="", help="one-line description shown under the H1")
    ap.add_argument("--pitch", default="", help="one paragraph shown below the nav cards on the homepage")
    ap.add_argument("--force", action="store_true", help="proceed even if target already has an index.html")
    args = ap.parse_args()

    target = os.path.abspath(args.target)
    os.makedirs(target, exist_ok=True)
    os.makedirs(os.path.join(target, "data"), exist_ok=True)
    os.makedirs(os.path.join(target, "scripts"), exist_ok=True)

    existing_index = os.path.join(target, "index.html")
    if os.path.exists(existing_index) and not args.force:
        sys.exit(f"{existing_index} already exists — pass --force to re-copy the HTML/scripts "
                 f"(existing data/*.json is never touched, so this is safe for an upgrade).")

    for page in PAGES:
        shutil.copy2(os.path.join(TEMPLATES, page), os.path.join(target, page))
    for script in SCRIPTS:
        shutil.copy2(os.path.join(HERE, script), os.path.join(target, "scripts", script))

    for data_file in DATA_FILES:
        dst = os.path.join(target, "data", data_file)
        if os.path.exists(dst):
            continue  # never clobber real project data on a re-run
        shutil.copy2(os.path.join(TEMPLATES, "data", data_file), dst)

    project_path = os.path.join(target, "data", "project.json")
    project = json.load(open(project_path, encoding="utf-8"))
    project["name"] = args.name
    if args.tagline:
        project["tagline"] = args.tagline
    if args.pitch:
        project["pitch"] = args.pitch
    with open(project_path, "w", encoding="utf-8") as fh:
        json.dump(project, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # index.html's project-data script block starts as the template default — sync it now so
    # the homepage reflects --name/--tagline/--pitch immediately, without a separate render step.
    index_path = os.path.join(target, "index.html")
    html = open(index_path, encoding="utf-8").read()
    import re
    # See the matching comment in each CLI's render() for why: json.dumps() doesn't escape
    # "<", so a name/tagline/pitch containing "</script>" would otherwise corrupt the page.
    payload = json.dumps(project, indent=2, ensure_ascii=False).replace("<", "\\u003c")
    html, n = re.subn(
        r'(<script id="project-data" type="application/json">)(.*?)(</script>)',
        lambda m: m.group(1) + "\n" + payload + "\n" + m.group(3),
        html, count=1, flags=re.S)
    if n:
        open(index_path, "w", encoding="utf-8").write(html)

    print(f"Created OpenLead workspace at {target}")
    print(f"  {len(PAGES)} pages, {len(SCRIPTS)} CLI scripts, {len(DATA_FILES)} data files")
    print()
    print("Next:")
    print(f"  cd {target}")
    print('  python3 scripts/roadmap_cli.py add --name "Milestone 1" --status next')
    print('  python3 scripts/tasks_cli.py add --title "First task"')
    print('  python3 scripts/memory_cli.py create --name "Bootstrap" --owner "you"')
    print("  open index.html   (or just double-click it)")


if __name__ == "__main__":
    main()
