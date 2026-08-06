import os
from pathlib import Path
from typing import List, Tuple

import tests4py.api as t4p
from sflkit import Analyzer
from sflkit.analysis.factory import analysis_factory_mapping, CombinationFactory
from sflkit.events.event_file import EventFile
from sflkit.events.mapping import EventMapping
from tests4py.projects import TestStatus, Project

from utils.constants import ANALYSIS_DIR, EVENTS_DIR, MAPPINGS_DIR
from utils.logger import LOGGER


def get_event_files(
    events: os.PathLike, mapping: os.PathLike | EventMapping
) -> Tuple[List[EventFile], List[EventFile], List[EventFile]]:
    events = Path(events)
    if isinstance(mapping, EventMapping):
        mapping = mapping
    else:
        mapping = EventMapping.load_from_file(Path(mapping), "")
    if (events / "failing").exists():
        failing = [
            EventFile(
                events / "failing" / path,
                run_id,
                mapping,
                failing=True,
            )
            for run_id, path in enumerate(os.listdir(events / "failing"), start=0)
        ]
    else:
        failing = []
    if (events / "passing").exists():
        passing = [
            EventFile(events / "passing" / path, run_id, mapping, failing=False)
            for run_id, path in enumerate(
                os.listdir(events / "passing"),
                start=len(failing),
            )
        ]
    else:
        passing = []
    if (events / "undefined").exists():
        undefined = [
            EventFile(events / "undefined" / path, run_id, mapping, failing=False)
            for run_id, path in enumerate(
                os.listdir(events / "undefined"),
                start=len(failing) + len(passing),
            )
        ]
    else:
        undefined = []
    return failing, passing, undefined


def analyze_project(project: Project, analysis_file: os.PathLike) -> Analyzer:
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    events = Path(EVENTS_DIR, project.project_name, str(project.bug_id), "bug")
    mapping_file = Path(MAPPINGS_DIR, f"{project}.json")
    if not events.exists():
        raise FileNotFoundError(f"Events not found for {project}")
    if not mapping_file.exists():
        raise FileNotFoundError(f"Mapping not found for {project}")
    failing, passing, undefined = get_event_files(events, mapping_file)
    analyzer = Analyzer(
        failing,
        passing,
        CombinationFactory(list(map(lambda f: f(), analysis_factory_mapping.values()))),
    )
    analyzer.analyze()
    analyzer.dump(analysis_file, indent=1)
    return analyzer


def get_analysis(project_name, bug_id, start: int = None, end: int = None):
    for project in t4p.get_projects(project_name, bug_id):
        if start is not None and project.bug_id < start:
            continue
        if end is not None and project.bug_id > end:
            continue
        LOGGER.info(project)
        if (
            project.test_status_buggy != TestStatus.FAILING
            or project.test_status_fixed != TestStatus.PASSING
        ):
            continue
        project.buggy = True
        analysis_file = ANALYSIS_DIR / f"{project}.json"
        if analysis_file.exists():
            continue
        analyze_project(project, analysis_file)
