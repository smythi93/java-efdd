"""Reproduction records + disk reclaim for the Defects4J event traces.

The traces are ~265 GB. Once ``results/`` is computed we don't need to keep
them: each bug's tests are fully determined by Defects4J's ``trigger_tests``
(the failing tests) + ``relevant_tests`` (the passing-relevant test classes),
which ``collect_dataset.py`` re-runs deterministically. This script records
those lists (plus the exact trace filenames that were collected) so any bug can
be regenerated, and then optionally deletes the traces.

    python test_lists.py record            # write selected_tests/<P>_<b>.json (safe)
    python test_lists.py reclaim           # DRY-RUN: show what deleting would free
    python test_lists.py reclaim --apply   # actually delete traces (only bugs that
                                           # already have results/ AND a test list)
"""

import argparse
import json
import os
import shutil
from pathlib import Path

D4J_HOME = Path(os.environ.get("D4J_HOME", Path.home() / "defects4j"))
PROJECTS = D4J_HOME / "framework" / "projects"
SELECTED = Path("selected_tests")
EVENTS = Path("sflkit_events")
RESULTS = Path("results")
REPORT = Path("dataset_report.json")


def trigger_tests(project: str, bug: int):
    path = PROJECTS / project / "trigger_tests" / str(bug)
    if not path.exists():
        return []
    return [
        line[4:].strip()
        for line in path.read_text(errors="replace").splitlines()
        if line.startswith("--- ")
    ]


def relevant_test_classes(project: str, bug: int):
    path = PROJECTS / project / "relevant_tests" / str(bug)
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def _listdir(path: Path):
    return sorted(os.listdir(path)) if path.is_dir() else []


def ok_bugs():
    report = json.loads(REPORT.read_text())
    for key, meta in report.items():
        if meta.get("status") == "ok":
            project, bug = key.rsplit("-", 1)
            yield project, int(bug)


def record():
    SELECTED.mkdir(exist_ok=True)
    count = 0
    for project, bug in ok_bugs():
        bug_dir = EVENTS / project / str(bug) / "bug"
        record = {
            "project": project,
            "bug": bug,
            "trigger_tests": trigger_tests(project, bug),
            "relevant_test_classes": relevant_test_classes(project, bug),
            "collected": {
                "failing": _listdir(bug_dir / "failing"),
                "passing": _listdir(bug_dir / "passing"),
            },
        }
        (SELECTED / f"{project}_{bug}.json").write_text(json.dumps(record, indent=1))
        count += 1
    print(f"wrote {count} reproduction records to {SELECTED}/")


def reclaim(apply: bool):
    freed = 0
    deletable = 0
    for project, bug in ok_bugs():
        events = EVENTS / project / str(bug)
        has_result = (RESULTS / f"{project}_{bug}.json").exists()
        has_list = (SELECTED / f"{project}_{bug}.json").exists()
        if not events.exists():
            continue
        # Only reclaim once a bug is both evaluated and reproducible.
        if not (has_result and has_list):
            continue
        size = sum(f.stat().st_size for f in events.rglob("*") if f.is_file())
        freed += size
        deletable += 1
        if apply:
            shutil.rmtree(events, ignore_errors=True)
    verb = "deleted" if apply else "would delete"
    print(f"{verb} traces for {deletable} bugs, {'freed' if apply else 'reclaimable'} {freed / 1e9:.1f} GB")
    if not apply and deletable:
        print("re-run with --apply to delete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("record", help="write reproduction records (non-destructive)")
    reclaim_parser = sub.add_parser("reclaim", help="delete traces (dry-run by default)")
    reclaim_parser.add_argument(
        "--apply", action="store_true", help="actually delete (default is dry-run)"
    )
    args = parser.parse_args()
    if args.command == "record":
        record()
    elif args.command == "reclaim":
        reclaim(args.apply)


if __name__ == "__main__":
    os.chdir(Path(__file__).parent)  # resolve paths relative to this file
    main()
