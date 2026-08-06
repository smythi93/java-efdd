import json
import os.path
import shutil
import time
import traceback

from sflkit.runners import Runner

import tests4py.api as t4p
from sflkitlib.events import EventType
from tests4py import sfl
from tests4py.projects import TestStatus

from utils.constants import EVENT_REPORT_DIR, MAPPINGS_DIR, TMP, EVENTS_DIR
from utils.logger import LOGGER


def get_events(project_name, bug_id, start: int = None, end: int = None):
    os.makedirs(EVENT_REPORT_DIR, exist_ok=True)
    report_file = EVENT_REPORT_DIR / f"report_{project_name}.json"
    if os.path.exists(report_file):
        with open(report_file, "r") as f:
            report = json.load(f)
    else:
        report = dict()
    os.makedirs(MAPPINGS_DIR, exist_ok=True)
    for project in t4p.get_projects(project_name, bug_id):
        if start is not None and project.bug_id < start:
            continue
        if end is not None and project.bug_id > end:
            continue
        identifier = project.get_identifier()
        LOGGER.info(identifier)
        if (
            identifier in report
            and "check" in report[identifier]
            and report[identifier]["check"] == "successful"
        ):
            continue
        report[identifier] = dict()

        if (
            project.test_status_buggy != TestStatus.FAILING
            or project.test_status_fixed != TestStatus.PASSING
        ):
            report[identifier]["status"] = "skipped"
            continue
        else:
            report[identifier]["status"] = "running"

        report[identifier]["time"] = dict()

        LOGGER.info(f"Checking out project {project}")
        start_time = time.time()
        r = t4p.checkout(project)
        report[identifier]["time"]["checkout"] = time.time() - start_time
        if r.successful:
            report[identifier]["checkout"] = "successful"
        else:
            report[identifier]["checkout"] = "failed"
            report[identifier]["error"] = traceback.format_exception(r.raised)
            LOGGER.error(report[identifier]["error"])
            continue
        original_checkout = r.location

        if project.project_name == "sanic":
            with open(
                os.path.join(original_checkout, "tests4py_requirements.txt"), "r"
            ) as f:
                content = f.read()
            with open(
                os.path.join(original_checkout, "tests4py_requirements.txt"), "w"
            ) as f:
                f.write(
                    content.replace(
                        "requests-async==0.4.1", "http3==0.6.*\nrequests==2.*"
                    ).replace("requests-async==0.5.0", "http3==0.6.*\nrequests==2.*")
                )
            if project.bug_id == 4:
                with open(os.path.join(original_checkout, "setup.py"), "r") as f:
                    content = f.read()
                with open(os.path.join(original_checkout, "setup.py"), "w") as f:
                    f.write(
                        content.replace(
                            '\n    "requests-async==0.5.0",',
                            '\n    "http3==0.6.*",\n    "requests==2.*",',
                        )
                    )

        mapping = MAPPINGS_DIR / f"{project}.json"
        sfl_path = TMP / f"sfl_{identifier}"
        LOGGER.info(f"Instrumenting project {project}")
        start_time = time.time()
        r = sfl.sflkit_instrument(
            sfl_path,
            project,
            events=",".join([event.name for event in EventType.events()]),
            mapping=mapping,
        )
        report[identifier]["time"]["instrument"] = time.time() - start_time
        if r.successful:
            report[identifier]["build"] = "successful"
        else:
            report[identifier]["build"] = "failed"
            report[identifier]["error"] = traceback.format_exception(r.raised)
            LOGGER.error(report[identifier]["error"])
            continue

        if project.project_name == "sanic":
            shutil.copytree(
                os.path.join("sanic-libs", "requests_async"),
                os.path.join(
                    sfl_path,
                    "tests4py_venv",
                    "lib",
                    "python3.8",
                    "site-packages",
                    "requests_async",
                ),
            )
            shutil.copytree(
                os.path.join("sanic-libs", "requests_async-0.5.0.dist-info"),
                os.path.join(
                    sfl_path,
                    "tests4py_venv",
                    "lib",
                    "python3.8",
                    "site-packages",
                    "requests_async-0.5.0.dist-info",
                ),
            )

        with open(mapping, "r") as f:
            mapping_content = json.load(f)
        with open(mapping, "w") as f:
            json.dump(mapping_content, f, indent=2)

        events_base = EVENTS_DIR / project.project_name / str(project.bug_id)
        shutil.rmtree(events_base, ignore_errors=True)
        if project.project_name == "ansible":
            """
            When ansible is executed it sometimes loads the original version.
            Even though it is never installed and the virtual environment clearly
            contains the instrumented version.
            This prevents an event collection.
            Removing the original version fixes this problem.
            """
            shutil.rmtree(original_checkout, ignore_errors=True)
        LOGGER.info(f"Running project {project}")
        start_time = time.time()
        r = sfl.sflkit_unittest(
            sfl_path, relevant_tests=True, all_tests=False, include_suffix=True
        )
        report[identifier]["time"]["test"] = time.time() - start_time
        if r.successful:
            report[identifier]["test"] = "successful"
        else:
            report[identifier]["test"] = "failed"
            report[identifier]["error"] = traceback.format_exception(r.raised)
            LOGGER.error(report[identifier]["error"])
            continue

        checks = True
        bug_events = os.path.join(events_base, "bug")
        for failing_test in project.test_cases:
            safe_test = Runner.safe(failing_test)
            if not os.path.exists(os.path.join(bug_events, "failing", safe_test)):
                report[identifier][f"bug:{failing_test}"] = "not_found"
                checks = False
        if not os.listdir(os.path.join(bug_events, "passing")):
            report[identifier]["bug_passing"] = "empty"
            checks = False

        if checks:
            report[identifier]["check"] = "successful"
        else:
            report[identifier]["check"] = "failed"
        LOGGER.info(f"Finished project {project}")
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
