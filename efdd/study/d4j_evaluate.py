"""Defects4J counterpart of ``utils/evaluate.py`` (which is tests4py/Python only).

It consumes the already-collected Java artifacts

    mappings/<Project>_<bug>.json
    sflkit_events/<Project>/<bug>/bug/{failing,passing,undefined}/<test>

builds an :class:`sflkit.Analyzer` over them, sources the ground truth from
Defects4J (faulty lines from the reference patch, LOC from the buggy checkout),
and writes the same per-feature result shape the downstream ``stats``/
``interpret`` steps expect:

    results/<Project>_<bug>.json

Run from the ``efdd/study`` directory (same as ``study.py``)::

    python d4j_evaluate.py -p Csv            # one project
    python d4j_evaluate.py -p Csv -i 1       # one bug
    python d4j_evaluate.py --all             # every ``ok`` bug in dataset_report.json
"""

import argparse
import json
import logging
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import List, Optional, Set, Tuple

from sflkit import Analyzer
from sflkit.analysis.analysis_type import AnalysisType
from sflkit.analysis.factory import analysis_factory_mapping, CombinationFactory
from sflkit.analysis.predicate import Predicate
from sflkit.analysis.spectra import Spectrum
from sflkit.analysis.suggestion import Location
from sflkit.evaluation import Average, Rank, Scenario
from sflkit.events.event_file import EventFile
from sflkit.events.mapping import EventMapping
from sflkit.language.java import finder as java_finder
from sflkit.language.language import Language
from sflkit.runners.defects4j import Defects4J

from utils.constants import (
    BEST,
    CORRELATION,
    EVENTS_DIR,
    EXAM,
    LOCALIZATION,
    MAPPINGS_DIR,
    MEAN,
    MEDIAN,
    METRICS,
    RESULTS_DIR,
    SUSPICIOUSNESS,
    TOP1,
    TOP5,
    TOP10,
    TOTAL,
    TRUE,
    UNIFIED_AVG,
    UNIFIED_MAX,
    WASTED_EFFORT,
    WORST,
)
from utils.logger import LOGGER

D4J_HOME = Path(os.environ.get("D4J_HOME", Path.home() / "defects4j"))
DATASET_REPORT = Path("dataset_report.json")
TMP_EVAL = Path("tmp_eval")


# --------------------------------------------------------------------------- #
# Event loading (inlined from utils.analyze, which imports tests4py at module  #
# top and cannot be imported in the Java venv).                                #
# --------------------------------------------------------------------------- #
def get_event_files(
    events: os.PathLike, mapping: os.PathLike
) -> Tuple[List[EventFile], List[EventFile], List[EventFile], bool]:
    events = Path(events)
    mapping = EventMapping.load_from_file(Path(mapping), "")
    # The Defects4J events are collected uniformly with thread-id support
    # (collect_dataset.py sets thread_support=True), so they must be read the
    # same way; reading them as non-threaded misframes the stream.
    thread_support = True

    def collect(sub: str, start: int, failing: bool) -> List[EventFile]:
        directory = events / sub
        if not directory.exists():
            return []
        return [
            EventFile(
                directory / name,
                run_id,
                mapping,
                failing=failing,
                thread_support=thread_support,
            )
            for run_id, name in enumerate(sorted(os.listdir(directory)), start=start)
        ]

    failing = collect("failing", 0, True)
    passing = collect("passing", len(failing), False)
    undefined = collect("undefined", len(failing) + len(passing), False)
    return failing, passing, undefined, thread_support


# --------------------------------------------------------------------------- #
# Defects4J ground truth.                                                      #
# --------------------------------------------------------------------------- #
def _relativize(path: str, src_dir: str) -> str:
    """Turn a diff path (``a/src/main/java/pkg/X.java``) into the mapping's
    source-root-relative form (``pkg/X.java``)."""
    if path.startswith(("a/", "b/")):
        path = path[2:]
    src_dir = src_dir.strip("/")
    if src_dir and path.startswith(src_dir + "/"):
        path = path[len(src_dir) + 1 :]
    return path


def parse_faulty_lines(patch_file: Path, src_dir: str) -> Set[Location]:
    """Faulty lines = the ``+`` (buggy-side) hunk lines of the Defects4J
    reference patch. That patch reintroduces the bug into the fixed source, so
    its ``+`` lines are exactly the buggy version's faulty lines (verified on
    Csv-1). Pure ``-`` hunks (the fix only *adds* code, i.e. an omission bug)
    are attributed to the buggy insertion point."""
    faulty: Set[Location] = set()
    current_file: Optional[str] = None
    b_line = 0
    for raw in patch_file.read_text(errors="replace").splitlines():
        if raw.startswith("+++ "):
            current_file = _relativize(raw[4:].split("\t")[0].strip(), src_dir)
        elif raw.startswith("--- "):
            continue
        elif raw.startswith("@@"):
            match = re.search(r"\+(\d+)", raw)
            b_line = int(match.group(1)) if match else 0
        elif current_file is None:
            continue
        elif raw.startswith("+"):
            faulty.add(Location(current_file, b_line))
            b_line += 1
        elif raw.startswith("-"):
            faulty.add(Location(current_file, b_line))  # omission: insertion point
        else:
            b_line += 1
    return faulty


def count_loc(src_root: Path) -> int:
    """Total physical lines across all ``.java`` files under the buggy source
    root; the denominator for EXAM / wasted-effort (mirrors ``project.loc``)."""
    total = 0
    for path in src_root.rglob("*.java"):
        try:
            with path.open("r", errors="replace") as handle:
                total += sum(1 for _ in handle)
        except OSError:
            pass
    return total


# --------------------------------------------------------------------------- #
# Per-feature results (mirrors utils.evaluate.get_results_for_type).           #
# --------------------------------------------------------------------------- #
def get_results_for_type(
    type_,
    analyzer: Analyzer,
    base_dir: str,
    faulty_lines: Set[Location],
    loc: int,
    eval_metric=max,
    include_correlation: bool = True,
) -> dict:
    results: dict = {SUSPICIOUSNESS: {}, LOCALIZATION: {}}
    if include_correlation:
        results[CORRELATION] = {TRUE: [], TOTAL: []}
    analysis = analyzer.get_analysis_by_type(type_) if type_ else analyzer.get_analysis()
    if include_correlation:
        for object_ in analysis:
            if isinstance(object_, Spectrum):
                results[CORRELATION][TRUE].append(object_.failed_observed)
                results[CORRELATION][TOTAL].append(
                    object_.failed_observed + object_.passed_observed
                )
            elif isinstance(object_, Predicate):
                results[CORRELATION][TRUE].append(object_.true_relevant)
                results[CORRELATION][TOTAL].append(
                    object_.true_relevant + object_.true_irrelevant
                )
    for metric in METRICS:
        suggestions = analyzer.get_sorted_suggestions_from_analysis(
            base_dir, analysis, metric
        )
        if suggestions:
            results[SUSPICIOUSNESS][metric.__name__] = {
                BEST: analyzer.max_suspiciousness,
                MEAN: analyzer.mean_suspiciousness,
                MEDIAN: analyzer.median_suspiciousness,
                WORST: analyzer.min_suspiciousness,
            }
        else:
            results[SUSPICIOUSNESS][metric.__name__] = {
                BEST: 0,
                MEAN: 0,
                MEDIAN: 0,
                WORST: 0,
            }
        rank = Rank(suggestions, total_number_of_locations=loc, metric=eval_metric)
        results[LOCALIZATION][metric.__name__] = {}
        for scenario in Scenario:
            results[LOCALIZATION][metric.__name__][scenario.value] = {
                TOP1: rank.top_n(faulty_lines, 1, scenario),
                TOP5: rank.top_n(faulty_lines, 5, scenario),
                TOP10: rank.top_n(faulty_lines, 10, scenario),
                # TOP200 is computed by the original evaluate but excluded from
                # interpret's LOCALIZATIONS; skip its costly repeat=1000 sampling.
                EXAM: rank.exam(faulty_lines, scenario),
                WASTED_EFFORT: rank.wasted_effort(faulty_lines, scenario),
            }
    return results


def evaluate_bug(project_name: str, bug_id: int, d4j: Defects4J) -> str:
    results_file = RESULTS_DIR / f"{project_name}_{bug_id}.json"
    if results_file.exists():
        return "skip"

    events = EVENTS_DIR / project_name / str(bug_id) / "bug"
    mapping = MAPPINGS_DIR / f"{project_name}_{bug_id}.json"
    if not events.exists() or not mapping.exists():
        LOGGER.warning("Missing events/mapping for %s-%s", project_name, bug_id)
        return "missing"

    failing, passing, _, thread_support = get_event_files(events, mapping)
    if not failing:
        LOGGER.warning("No failing traces for %s-%s", project_name, bug_id)
        return "no-failing"
    LOGGER.info(
        "%s-%s: %d failing, %d passing (thread_support=%s)",
        project_name,
        bug_id,
        len(failing),
        len(passing),
        thread_support,
    )

    analyzer = Analyzer(
        failing,
        passing,
        CombinationFactory([factory() for factory in analysis_factory_mapping.values()]),
    )
    analyzer.analyze()

    work = TMP_EVAL / f"{project_name}_{bug_id}b"
    shutil.rmtree(work, ignore_errors=True)
    d4j.checkout(project_name, bug_id, work, buggy=True)
    src_dir = d4j.export("dir.src.classes", work).strip()
    src_root = work / src_dir
    faulty_lines = parse_faulty_lines(
        D4J_HOME / "framework" / "projects" / project_name / "patches" / f"{bug_id}.src.patch",
        src_dir,
    )
    loc = count_loc(src_root)

    subject: dict = {}
    for type_ in AnalysisType:
        subject[type_.name] = _safe_results(
            type_, analyzer, str(src_root), faulty_lines, loc
        )
    subject[UNIFIED_MAX] = _safe_results(
        None, analyzer, str(src_root), faulty_lines, loc, include_correlation=False
    )
    subject[UNIFIED_AVG] = _safe_results(
        None,
        analyzer,
        str(src_root),
        faulty_lines,
        loc,
        include_correlation=False,
        eval_metric=Average().average,
    )

    subject["_meta"] = {
        "faulty_lines": sorted(f"{loc_.file}:{loc_.line}" for loc_ in faulty_lines),
        "loc": loc,
        "failing": len(failing),
        "passing": len(passing),
        "thread_support": thread_support,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    with open(results_file, "w") as handle:
        json.dump({f"{project_name}_{bug_id}": subject}, handle, indent=1)
    shutil.rmtree(work, ignore_errors=True)
    java_finder._TREE_CACHE.clear()  # trees are keyed by this bug's workdir path
    return "ok"


def _safe_results(type_, analyzer, base_dir, faulty_lines, loc, **kwargs) -> dict:
    """Wrap one feature type so a jast parse failure on a single source file
    (needed by the line finder) degrades that type to empty instead of losing
    the whole bug."""
    try:
        return get_results_for_type(
            type_, analyzer, base_dir, faulty_lines, loc, **kwargs
        )
    except Exception as error:  # noqa: BLE001 - want to survive per-type failures
        name = type_.name if type_ else "UNIFIED"
        LOGGER.warning("Feature %s failed: %s", name, error)
        return {"error": repr(error)}


# --------------------------------------------------------------------------- #
# Driver.                                                                      #
# --------------------------------------------------------------------------- #
def select_bugs(
    project: Optional[str], bug_id: Optional[int], only_ok: bool
) -> List[Tuple[str, int]]:
    report = json.loads(DATASET_REPORT.read_text())
    bugs: List[Tuple[str, int]] = []
    for key, meta in report.items():
        name, number = key.rsplit("-", 1)
        number = int(number)
        if only_ok and meta.get("status") != "ok":
            continue
        if project is not None and name != project:
            continue
        if bug_id is not None and number != bug_id:
            continue
        bugs.append((name, number))
    bugs.sort(key=lambda pb: (pb[0], pb[1]))
    return bugs


def _add_log_handler() -> None:
    if not LOGGER.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        LOGGER.addHandler(handler)


def _worker_init() -> None:
    """Each ProcessPool worker re-imports the module, so wire up logging and the
    Java analysis finders once per worker."""
    _add_log_handler()
    Language.JAVA.setup()


def _evaluate_one(task: Tuple[str, int]) -> Tuple[str, int, str, float]:
    name, number = task
    d4j = Defects4J()
    bug_start = time.time()
    try:
        status = evaluate_bug(name, number, d4j)
    except Exception:  # noqa: BLE001 - one bad bug must not abort the batch
        status = "error"
        LOGGER.error("Failed %s-%s\n%s", name, number, traceback.format_exc())
    return name, number, status, time.time() - bug_start


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-p", dest="project", default=None, help="project name")
    parser.add_argument("-i", dest="bug_id", type=int, default=None, help="bug id")
    parser.add_argument(
        "--all", action="store_true", help="evaluate every ok bug in the dataset"
    )
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help="also evaluate bugs whose collection status is not 'ok'",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="number of bugs to evaluate in parallel (default 1). Big bugs are "
        "RAM-heavy, so keep this modest.",
    )
    parser.add_argument(
        "--projects",
        default=None,
        help="comma-separated subset of projects to evaluate (shard by subject "
        "across machines), e.g. --projects Chart,Cli,Codec",
    )
    parser.add_argument(
        "--shard",
        default=None,
        help="process only shard k of n of the selected+sorted bugs, e.g. 0/3, to "
        "split a heavy project (Jsoup/Compress) across machines",
    )
    args = parser.parse_args(argv)

    if not args.all and args.project is None and args.projects is None:
        parser.error("provide -p <project>, --projects <list>, or --all")

    _add_log_handler()

    bugs = select_bugs(args.project, args.bug_id, only_ok=not args.include_incomplete)
    if args.projects:
        keep = {p.strip() for p in args.projects.split(",") if p.strip()}
        bugs = [pb for pb in bugs if pb[0] in keep]
    # Shard on the stable (project, bug_id) order from select_bugs so every machine
    # computes the SAME disjoint split (independent of collection/report state).
    if args.shard:
        k, n = (int(x) for x in args.shard.split("/"))
        bugs = bugs[k::n]
    # Then, for local execution only, order by on-disk trace SIZE (bytes), smallest
    # first: fast early progress and the RAM/CPU-heavy giants (big Jsoup ~3GB, Math
    # ~7GB) last. Trace COUNT under-predicts cost (a ~400-trace Jsoup bug takes ~107min
    # because its traces are large), so bytes is the right cost proxy. Already-done
    # bugs sort first (key -1) so workers skip them instantly and reach real work.
    def _cost_key(pb: Tuple[str, int]) -> float:
        if (RESULTS_DIR / f"{pb[0]}_{pb[1]}.json").exists():
            return -1.0
        events = EVENTS_DIR / pb[0] / str(pb[1])
        try:
            return float(
                sum(f.stat().st_size for f in events.rglob("*") if f.is_file())
            )
        except OSError:
            return 0.0

    bugs.sort(key=_cost_key)
    total = len(bugs)
    LOGGER.info("Evaluating %d bug(s) with %d worker(s)", total, args.workers)

    counts: dict = {}
    start = time.time()
    done = 0

    def record(name: str, number: int, status: str, elapsed: float) -> None:
        nonlocal done
        done += 1
        counts[status] = counts.get(status, 0) + 1
        LOGGER.info(
            "[%d/%d] %s-%s -> %s (%.1fs)", done, total, name, number, status, elapsed
        )

    if args.workers > 1:
        with ProcessPoolExecutor(
            max_workers=args.workers, initializer=_worker_init
        ) as executor:
            futures = [executor.submit(_evaluate_one, task) for task in bugs]
            for future in as_completed(futures):
                record(*future.result())
    else:
        Language.JAVA.setup()
        d4j = Defects4J()
        for name, number in bugs:
            bug_start = time.time()
            try:
                status = evaluate_bug(name, number, d4j)
            except Exception:  # noqa: BLE001 - one bad bug must not abort the batch
                status = "error"
                LOGGER.error("Failed %s-%s\n%s", name, number, traceback.format_exc())
            record(name, number, status, time.time() - bug_start)

    LOGGER.info(
        "Done in %.1fs: %s", time.time() - start, json.dumps(counts, sort_keys=True)
    )


if __name__ == "__main__":
    # Resolve mappings/, sflkit_events/, results/ relative to this file, so the
    # command can be launched from the repo base dir.
    os.chdir(Path(__file__).parent)
    main()
