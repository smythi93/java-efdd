"""Defects4J event collection, the Java counterpart of ``utils.events``.

Instead of tests4py, it drives sflkit's ``Defects4JRunner`` to produce the same
on-disk layout the downstream study steps consume:

    mappings/<project>_<bug>.json
    sflkit_events/<project>/<bug>/bug/{failing,passing,undefined}/<safe_test>
"""

import json
import os
import shutil
import time
import traceback
from pathlib import Path
from typing import List, Optional

from sflkit.runners.defects4j import Defects4J, Defects4JRunner
from sflkitlib.events import EventType

from utils.constants import EVENT_REPORT_DIR, EVENTS_DIR, MAPPINGS_DIR
from utils.logger import LOGGER

# the runtime logging library built from the vendored sflkit
import sflkit as _sflkit

# Resolve the runtime jar from the active sflkit package (``.../sflkit/src/
# sflkit/__init__.py`` -> ``.../sflkit/jsflkit/jsflkit.jar``) so the jar used to
# compile and run the instrumented code always matches the instrumenter.
JLIB_JAR = (
    Path(_sflkit.__file__).resolve().parents[2] / "jsflkit" / "jsflkit.jar"
)


def collect_defects4j_events(
    project_name: str,
    bug_id: int,
    jlib_jar: Optional[os.PathLike] = None,
    events: Optional[List[EventType]] = None,
    tests: Optional[List[str]] = None,
    thread_support: bool = False,
    defects4j: Optional[Defects4J] = None,
):
    """Collect event traces for one Defects4J bug into the study layout."""
    os.makedirs(MAPPINGS_DIR, exist_ok=True)
    events = events or list(EventType.events())
    runner = Defects4JRunner(
        jlib_jar=str(jlib_jar or JLIB_JAR),
        defects4j=defects4j,
        events=events,
        thread_support=thread_support,
    )
    output = EVENTS_DIR / project_name / str(bug_id) / "bug"
    shutil.rmtree(output, ignore_errors=True)
    mapping_path = MAPPINGS_DIR / f"{project_name}_{bug_id}.json"
    runner.collect(
        project_name, bug_id, output=output, mapping_path=mapping_path, tests=tests
    )
    return runner.tests


def get_defects4j_events(
    project_name: str,
    bug_ids: List[int],
    jlib_jar: Optional[os.PathLike] = None,
    tests: Optional[List[str]] = None,
):
    """Collect events for a list of bugs, recording status in a report file."""
    os.makedirs(EVENT_REPORT_DIR, exist_ok=True)
    report_file = EVENT_REPORT_DIR / f"report_{project_name}.json"
    report = json.loads(report_file.read_text()) if report_file.exists() else {}
    defects4j = Defects4J()
    for bug_id in bug_ids:
        identifier = f"{project_name}_{bug_id}"
        LOGGER.info(identifier)
        if report.get(identifier, {}).get("check") == "successful":
            continue
        entry = report[identifier] = {"time": {}}
        start = time.time()
        try:
            partition = collect_defects4j_events(
                project_name, bug_id, jlib_jar=jlib_jar, tests=tests,
                defects4j=defects4j,
            )
            entry["time"]["collect"] = time.time() - start
            entry["failing"] = len(partition[next(iter(partition))]) if partition else 0
            base = EVENTS_DIR / project_name / str(bug_id) / "bug"
            failing = list((base / "failing").iterdir()) if (base / "failing").exists() else []
            passing = list((base / "passing").iterdir()) if (base / "passing").exists() else []
            entry["failing_traces"] = len(failing)
            entry["passing_traces"] = len(passing)
            entry["check"] = "successful" if failing and passing else "failed"
        except Exception as error:  # noqa: BLE001
            entry["check"] = "failed"
            entry["error"] = traceback.format_exception(error)
            LOGGER.error(entry["error"])
        report_file.write_text(json.dumps(report, indent=2))
    return report
