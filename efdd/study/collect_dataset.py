"""Collect the full Defects4J event dataset for the Java replication study.

Round-robins across the validated projects (so coverage stays broad even if the
run is interrupted), collecting every relevant test (failing + passing) for each
bug into the study layout.  Resumable: any bug already recorded in the report is
skipped.  Each checkout workdir is removed after the bug to bound disk use.
"""
import json
import logging
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, ".")
logging.basicConfig(level=logging.ERROR)

from sflkit.runners.defects4j import Defects4J, Defects4JRunner
from sflkitlib.events import EventType
from utils.constants import EVENTS_DIR, MAPPINGS_DIR
from utils.defects4j import JLIB_JAR

PROJECTS = [
    "Lang", "Math", "Chart", "Cli", "Codec", "Collections", "Compress",
    "Csv", "Gson", "JxPath", "Time", "Jsoup", "Mockito",
]
WORK = Path("/tmp/d4j/dataset_work")
REPORT = Path("dataset_report.json")
EVENTS = list(EventType.events())

d4j = Defects4J()


def bids(project):
    result = d4j._run("bids", "-p", project)
    return [int(b) for b in result.stdout.split() if b.strip().isdigit()]


per = {p: bids(p) for p in PROJECTS}
order = []
i = 0
while any(i < len(per[p]) for p in PROJECTS):
    for p in PROJECTS:
        if i < len(per[p]):
            order.append((p, per[p][i]))
    i += 1

report = json.loads(REPORT.read_text()) if REPORT.exists() else {}
MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
print(f"dataset: {len(order)} bugs across {len(PROJECTS)} projects", flush=True)

for project, bug in order:
    key = f"{project}-{bug}"
    if key in report:  # resumable: never re-run a recorded bug
        continue
    out = EVENTS_DIR / project / str(bug) / "bug"
    mapping = MAPPINGS_DIR / f"{project}_{bug}.json"
    wd = WORK / key
    shutil.rmtree(out, ignore_errors=True)
    shutil.rmtree(wd, ignore_errors=True)
    start = time.time()
    try:
        runner = Defects4JRunner(
            jlib_jar=str(JLIB_JAR), events=EVENTS,
            thread_support=True, defects4j=d4j, timeout=180,
        )
        runner.collect(project, bug, output=out, workdir=wd, mapping_path=mapping)
        f = len(os.listdir(out / "failing")) if (out / "failing").exists() else 0
        p = len(os.listdir(out / "passing")) if (out / "passing").exists() else 0
        report[key] = {
            "status": "ok" if (f and p) else "incomplete",
            "failing": f, "passing": p, "time": round(time.time() - start),
        }
    except Exception as error:  # noqa: BLE001
        report[key] = {
            "status": "error",
            "error": "".join(
                traceback.format_exception_only(type(error), error)
            ).strip()[:200],
            "time": round(time.time() - start),
        }
    finally:
        shutil.rmtree(wd, ignore_errors=True)
    REPORT.write_text(json.dumps(report, indent=2))
    r = report[key]
    print(
        f"{key}: {r['status']} f={r.get('failing','-')} p={r.get('passing','-')} "
        f"[{r['time']}s]",
        flush=True,
    )

done = sum(1 for v in report.values() if v.get("status") == "ok")
print(f"COMPLETE: {done}/{len(report)} ok of {len(order)} total", flush=True)
