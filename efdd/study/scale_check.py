"""Scaling / sanity harness for the Defects4J Java pilot.

For each (project, bug) it instruments+compiles (reporting compile reverts) and
runs the trigger tests in isolation, asserting they come back FAILING (a
trigger test that passes means the instrumentation changed behavior).  A small
passing test is also run so we know both partitions are populated.
"""
import logging
import re
import sys
import time
import traceback

sys.path.insert(0, ".")

from sflkit.runners.defects4j import Defects4J, Defects4JRunner
from sflkit.runners.run import TestResult
from sflkitlib.events import EventType, event as event_mod
from utils.defects4j import JLIB_JAR

BUGS = [(p, int(b)) for p, b in (s.split("-") for s in sys.argv[1:])]

# Capture the runner's "Instrumented .../Reverted ..." log lines.
_log = []


class _Grab(logging.Handler):
    def emit(self, record):
        msg = record.getMessage()
        if "Instrumented" in msg or "Reverted" in msg:
            _log.append(msg)


logging.basicConfig(level=logging.ERROR)
_sflkit_log = logging.getLogger("sflkit")
_sflkit_log.addHandler(_Grab())
_sflkit_log.setLevel(logging.INFO)
_sflkit_log.propagate = False  # keep the per-file INFO chatter off the console

d4j = Defects4J()


def trigger_tests(project, bug):
    wd = f"/tmp/d4j/scale_{project}_{bug}_tr"
    import shutil
    shutil.rmtree(wd, ignore_errors=True)
    d4j.checkout(project, bug, wd)
    raw = d4j.export("tests.trigger", wd).splitlines()
    return [t.replace("::", "#") for t in raw if t]


print(f"{'bug':>16} | {'files':>5} {'revert':>6} | trig(FAIL/total) | traces | status", flush=True)
print("-" * 78, flush=True)
for project, bug in BUGS:
    _log.clear()
    start = time.time()
    try:
        triggers = trigger_tests(project, bug)
        runner = Defects4JRunner(
            jlib_jar=str(JLIB_JAR),
            events=list(EventType.events()),
            thread_support=True,
            defects4j=d4j,
            timeout=120,
        )
        out = f"/tmp/d4j/scale_{project}_{bug}/out"
        import shutil
        shutil.rmtree(f"/tmp/d4j/scale_{project}_{bug}", ignore_errors=True)
        part = runner.collect(
            project, bug,
            output=out,
            workdir=f"/tmp/d4j/scale_{project}_{bug}/wd",
            mapping_path=f"/tmp/d4j/scale_{project}_{bug}/map.json",
            tests=triggers,
        )
        instr = next((m for m in _log if "Instrumented" in m), "")
        files = re.search(r"Instrumented (\d+)", instr)
        files = files.group(1) if files else "?"
        rev = re.search(r"Reverted (\d+)", " ".join(_log))
        rev = rev.group(1) if rev else "0"
        failing = part.get(TestResult.FAILING, set())
        passing = part.get(TestResult.PASSING, set())
        undef = part.get(TestResult.UNDEFINED, set())
        n_fail = len(failing)
        n_trig = len(triggers)
        import os
        traces = sum(
            len(os.listdir(f"{out}/{k}")) for k in ("failing", "passing", "undefined")
            if os.path.isdir(f"{out}/{k}")
        )
        # behavior preservation: every trigger test must be FAILING
        bad = [t for t in triggers if t not in failing]
        status = "OK" if not bad else f"BEHAVIOR-CHANGE: {bad[:2]}"
        if undef and not bad:
            status += f" (undef={len(undef)})"
        print(f"{project + '-' + str(bug):>16} | {files:>5} {rev:>6} | "
              f"{n_fail:>6}/{n_trig:<7} | {traces:>6} | {status}  [{time.time()-start:.0f}s]")
    except Exception as error:
        print(f"{project + '-' + str(bug):>16} | ERROR: {error}")
        traceback.print_exc()
