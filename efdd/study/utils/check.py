import json
import os
import re

from utils.logger import LOGGER
from utils.constants import EVENT_REPORT_DIR

PATTERN = re.compile(r"report_(?P<name>[^.]*)\.json")


def check(directory=None):
    if directory is None:
        directory = EVENT_REPORT_DIR
    skipped = list()
    functions = list()
    errors = list()
    check_failed = list()
    missing_bug = list()
    empty_passing = list()
    missing_fixed = list()
    for file in os.listdir(directory):
        match = PATTERN.match(file)
        if match:
            file = os.path.join(directory, file)
            with open(file, "r") as f:
                report = json.load(f)
            for identifier in report:
                if (
                    "status" in report[identifier]
                    and report[identifier]["status"] == "skipped"
                ):
                    skipped.append(identifier)
                if (
                    "check" in report[identifier]
                    and report[identifier]["check"] == "successful"
                ):
                    functions.append(identifier)
                if "error" in report[identifier]:
                    errors.append((identifier, report[identifier]["error"]))
                if (
                    "check" in report[identifier]
                    and report[identifier]["check"] == "failed"
                ):
                    check_failed.append(identifier)
                    buggy = list()
                    empty = False
                    for key, value in report[identifier].items():
                        if value == "empty":
                            empty = True
                        if value == "not_found":
                            if key.startswith("bug:"):
                                buggy.append(key[4:])
                    if empty:
                        empty_passing.append(identifier)
                    if buggy:
                        missing_bug.append((identifier, buggy))
    need_investigation = {
        "errors": errors,
        "missing_bug": missing_bug,
        "empty_passing": empty_passing,
    }
    total = len(skipped) + len(functions) + len(check_failed) + len(errors)
    subjects = len(functions) + len(check_failed) + len(errors)
    LOGGER.info(f"Total: {total}")
    LOGGER.info(f"Skipped: {len(skipped)}")
    LOGGER.info(f"Investigate: {subjects}")
    LOGGER.info(f"Errors: {len(errors)}")
    LOGGER.info(f"Check failed: {len(check_failed)}")
    LOGGER.info(f"Functional: {len(functions)}")
    with open("need_investigation.json", "w") as f:
        json.dump(need_investigation, f, indent=2)
