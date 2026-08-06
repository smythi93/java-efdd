import json
import os

import tests4py.api as t4p
from sflkit import Analyzer
from sflkit.analysis.analysis_type import AnalysisType
from sflkit.analysis.predicate import Predicate
from sflkit.analysis.spectra import Spectrum
from sflkit.evaluation import Rank, Scenario, Average
from sflkit.language.language import Language
from tests4py.projects import TestStatus

from utils.analyze import get_analysis
from utils.constants import (
    METRICS,
    SUSPICIOUSNESS,
    LOCALIZATION,
    BEST,
    MEAN,
    MEDIAN,
    WORST,
    TOP1,
    TOP5,
    TOP10,
    TOP200,
    EXAM,
    WASTED_EFFORT,
    RESULTS_DIR,
    ANALYSIS_DIR,
    UNIFIED_MAX,
    UNIFIED_AVG,
    CORRELATION,
    TRUE,
    TOTAL,
)


def get_results_for_type(
    type_,
    analyzer,
    project,
    report,
    faulty_lines,
    eval_metric=max,
    include_correlation=True,
):
    type_results = dict()
    type_results[SUSPICIOUSNESS] = dict()
    if include_correlation:
        type_results[CORRELATION] = {
            TRUE: [],
            TOTAL: [],
        }
    type_results[LOCALIZATION] = dict()
    if type_:
        analysis = analyzer.get_analysis_by_type(type_)
    else:
        analysis = analyzer.get_analysis()
    if include_correlation:
        for object_ in analysis:
            if isinstance(object_, Spectrum):
                type_results[CORRELATION][TRUE].append(object_.failed_observed)
                type_results[CORRELATION][TOTAL].append(
                    object_.failed_observed + object_.passed_observed
                )
            elif isinstance(object_, Predicate):
                type_results[CORRELATION][TRUE].append(object_.true_relevant)
                type_results[CORRELATION][TOTAL].append(
                    object_.true_relevant + object_.true_irrelevant
                )
    for metric in METRICS:
        suggestions = analyzer.get_sorted_suggestions_from_analysis(
            report.location, analysis, metric
        )
        if suggestions:
            type_results[SUSPICIOUSNESS][metric.__name__] = {
                BEST: analyzer.max_suspiciousness,
                MEAN: analyzer.mean_suspiciousness,
                MEDIAN: analyzer.median_suspiciousness,
                WORST: analyzer.min_suspiciousness,
            }
        else:
            type_results[SUSPICIOUSNESS][metric.__name__] = {
                BEST: 0,
                MEAN: 0,
                MEDIAN: 0,
                WORST: 0,
            }
        rank = Rank(
            suggestions, total_number_of_locations=project.loc, metric=eval_metric
        )
        type_results[LOCALIZATION][metric.__name__] = dict()
        for scenario in Scenario:
            type_results[LOCALIZATION][metric.__name__][scenario.value] = {
                TOP1: rank.top_n(faulty_lines, 1, scenario),
                TOP5: rank.top_n(faulty_lines, 5, scenario),
                TOP10: rank.top_n(faulty_lines, 10, scenario),
                TOP200: rank.top_n(faulty_lines, 200, scenario),
                EXAM: rank.exam(faulty_lines, scenario),
                WASTED_EFFORT: rank.wasted_effort(faulty_lines, scenario),
            }
    return type_results


def evaluate(project_name, bug_id, start: int = None, end: int = None):
    Language.PYTHON.setup()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    for project in t4p.get_projects(project_name, bug_id):
        if start is not None and project.bug_id < start:
            continue
        if end is not None and project.bug_id > end:
            continue
        results_file = RESULTS_DIR / f"{project.get_identifier()}.json"
        if results_file.exists():
            continue
        if project.project_name == "youtubedl" and project.bug_id == 24:
            project.loc = 87341
        results = dict()
        print(project)
        if (
            project.test_status_buggy != TestStatus.FAILING
            or project.test_status_fixed != TestStatus.PASSING
        ):
            continue
        project.buggy = True
        analysis_file = ANALYSIS_DIR / f"{project}.json"
        if analysis_file.exists():
            analyzer = Analyzer.load(analysis_file)
        else:
            analyzer = get_analysis(project, analysis_file)
        report = t4p.checkout(project)
        if not report.successful:
            raise report.raised
        subject_results = dict()
        faulty_lines = set(t4p.get_faulty_lines(project))
        for type_ in AnalysisType:
            subject_results[type_.name] = get_results_for_type(
                type_, analyzer, project, report, faulty_lines
            )
        subject_results[UNIFIED_MAX] = get_results_for_type(
            None, analyzer, project, report, faulty_lines, include_correlation=False
        )
        subject_results[UNIFIED_AVG] = get_results_for_type(
            None,
            analyzer,
            project,
            report,
            faulty_lines,
            eval_metric=Average().average,
            include_correlation=False,
        )
        results[project.get_identifier()] = subject_results
        with open(results_file, "w") as f:
            json.dump(results, f, indent=1)
