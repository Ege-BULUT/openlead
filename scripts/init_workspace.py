#!/usr/bin/env python3
"""init_workspace.py: scaffold a new OpenLead workspace, a fully local homepage, roadmap,
task board, and agent-memory system for a project, driven entirely by JSON + a Python CLI
per page (no server, no build step, no framework).

  python3 init_workspace.py /path/to/target --name "My Project" \\
      [--tagline "One-line description shown on the homepage"] \\
      [--pitch "One paragraph shown below the nav cards"]

Idempotent-ish: refuses to overwrite an existing target directory unless --force is passed
(existing data/*.json is never touched by --force either, only the HTML/scripts get
re-copied, so a re-run can't destroy real project data. If you actually want fresh data too,
delete the target directory yourself first).

After running, cd into the target directory and open index.html. Or better, start with:
  python3 scripts/roadmap_cli.py add --name "..." --status next
  python3 scripts/tasks_cli.py add --title "..."
  python3 scripts/memory_cli.py create --name "..." --owner "..."
"""
import argparse
import importlib.util
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
TEMPLATES = os.path.join(REPO_ROOT, "templates")

PAGES = ("index.html", "roadmap.html", "tasks.html", "memory.html")
DATA_FILES = ("project.json", "roadmap.json", "tasks.json", "memory.json")
SCRIPTS = ("project_cli.py", "roadmap_cli.py", "tasks_cli.py", "memory_cli.py")


def _load_module_from_target(target, script_name):
    """Load a CLI module from its just-copied location in the target workspace (not from
    this repo), so its DATA_PATH/HTML_PATH resolve against that workspace, not this one."""
    path = os.path.join(target, "scripts", script_name)
    spec = importlib.util.spec_from_file_location(script_name[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render_from_target(target, script_name):
    """Re-render the page a CLI owns from whatever is actually in that workspace's data/
    directory right now. Needed because copying the HTML template on a --force re-run
    resets the page's embedded data block to the template's empty default, even though the
    real data file next to it is untouched."""
    module = _load_module_from_target(target, script_name)
    module.render(module.load())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="directory to create the workspace in (will be created)")
    ap.add_argument("--name", required=True, help="project name, shown as the homepage H1 and sidebar title")
    ap.add_argument("--tagline", default="", help="one-line description shown under the H1")
    ap.add_argument("--pitch", default="", help="one paragraph shown below the nav cards on the homepage")
    ap.add_argument("--force", action="store_true", help="proceed even if target already has an index.html")
    args = ap.parse_args()

    target = os.path.abspath(args.target)
    if os.path.exists(target) and os.path.samefile(target, REPO_ROOT):
        sys.exit(f"{target} is this skill's own directory. Point init_workspace.py at the "
                 f"project you want a workspace inside, not at the skill's install location.")
    os.makedirs(target, exist_ok=True)
    os.makedirs(os.path.join(target, "data"), exist_ok=True)
    os.makedirs(os.path.join(target, "scripts"), exist_ok=True)

    existing_index = os.path.join(target, "index.html")
    if os.path.exists(existing_index) and not args.force:
        sys.exit(f"{existing_index} already exists. Pass --force to re-copy the HTML/scripts "
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

    # The HTML pages we just copied in have the template's empty data baked in. On a fresh
    # scaffold that's correct (there's nothing to show yet); on a --force re-run it would
    # otherwise blank out whatever was already rendered, even though the real data files
    # right next to them were never touched. Re-render each page from its own data now so
    # both cases end up correct.
    for script in ("roadmap_cli.py", "tasks_cli.py", "memory_cli.py"):
        _render_from_target(target, script)

    # project.json/index.html go through project_cli.py's own load/save/render, the same
    # thing running `project_cli.py update` by hand would do, instead of a second copy of
    # that logic living here too.
    project_cli = _load_module_from_target(target, "project_cli.py")
    project = project_cli.load()
    project["name"] = args.name
    if args.tagline:
        project["tagline"] = args.tagline
    if args.pitch:
        project["pitch"] = args.pitch
    project_cli.save(project)
    project_cli.render(project)

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
