from pathlib import Path

from sflkit.analysis.analysis_type import AnalysisType
from sflkit.analysis.spectra import Spectrum
from sflkit.evaluation import Scenario

EVENT_REPORT_DIR = Path("events")
ANALYSIS_DIR = Path("analysis")
RESULTS_DIR = Path("results")
EVENTS_DIR = Path("sflkit_events")
MAPPINGS_DIR = Path("mappings")

TMP = Path("tmp")

METRICS = [
    Spectrum.Tarantula,
    Spectrum.Ochiai,
    Spectrum.DStar,
    Spectrum.Naish2,
    Spectrum.GP13,
]

SUSPICIOUSNESS = "suspiciousness"
CORRELATION = "correlation"
LOCALIZATION = "localization"
BEST = "best"
MEAN = "mean"
MEDIAN = "median"
WORST = "worst"

TOP1 = "top-1"
TOP5 = "top-5"
TOP10 = "top-10"
TOP200 = "top-200"
EXAM = "exam"
WASTED_EFFORT = "wasted-effort"

UNIFIED_MAX = "unified-max"
UNIFIED_AVG = "unified-avg"

FEATURES = [
    AnalysisType.LINE.name,
    AnalysisType.BRANCH.name,
    AnalysisType.FUNCTION.name,
    AnalysisType.FUNCTION_ERROR.name,
    AnalysisType.DEF_USE.name,
    AnalysisType.LOOP.name,
    AnalysisType.CONDITION.name,
    AnalysisType.SCALAR_PAIR.name,
    AnalysisType.VARIABLE.name,
    AnalysisType.RETURN.name,
    AnalysisType.NONE.name,
    AnalysisType.LENGTH.name,
    AnalysisType.EMPTY_STRING.name,
    AnalysisType.ASCII_STRING.name,
    AnalysisType.DIGIT_STRING.name,
    AnalysisType.SPECIAL_STRING.name,
    AnalysisType.EMPTY_BYTES.name,
]

UNIFIED = [
    UNIFIED_MAX,
    UNIFIED_AVG,
]

SCENARIOS = [
    Scenario.BEST_CASE.value,
    Scenario.AVG_CASE.value,
    Scenario.WORST_CASE.value,
]

LOCALIZATIONS = [
    TOP1,
    TOP5,
    TOP10,
    # TOP200,
    EXAM,
    WASTED_EFFORT,
]

LOCALIZATION_COMP = [
    True,
    True,
    True,
    # True,
    False,
    False,
]

AGGREGATES = [BEST, MEAN, MEDIAN, WORST]

SUBJECTS = [
    "Chart",
    "Cli",
    "Codec",
    "Collections",
    "Compress",
    "Csv",
    "Gson",
    "Jsoup",
    "JxPath",
    "Lang",
    "Math",
    "Mockito",
    "Time",
]

AVG = "avg"
ALL = "all"

SUMMARY = Path("summary.json")

TRUE = "true"
FALSE = "false"
TOTAL = "total"

P_VALUE = 0.05
