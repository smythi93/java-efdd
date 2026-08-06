import json
import warnings
from math import isnan

from scipy.stats import spearmanr

from utils.constants import (
    RESULTS_DIR,
    AGGREGATES,
    METRICS,
    AVG,
    ALL,
    FEATURES,
    UNIFIED,
    SUSPICIOUSNESS,
    LOCALIZATION,
    LOCALIZATIONS,
    SCENARIOS,
    SUBJECTS,
    SUMMARY,
    CORRELATION,
    TRUE,
    FALSE,
    TOTAL,
    BEST,
    MEAN,
    MEDIAN,
    P_VALUE,
)

warnings.filterwarnings("ignore")


def spearman(x, y):
    rho, p = spearmanr(x, y)
    if isnan(rho):
        rho = 0
    if isnan(p):
        p = 1
    return rho, p


def summarize():
    if not RESULTS_DIR.exists():
        return
    results = {
        CORRELATION: {
            type_: {
                TRUE: {ALL: list(), **{a: (0, 0) for a in AGGREGATES}},
                ALL: {
                    TRUE: (0, 0),
                },
            }
            for type_ in FEATURES + UNIFIED
        },
        SUSPICIOUSNESS: {
            type_: {
                metric.__name__: {m: {AVG: 0.0, ALL: list()} for m in AGGREGATES}
                for metric in METRICS
            }
            for type_ in FEATURES + UNIFIED
        },
        LOCALIZATION: {
            type_: {
                metric.__name__: {
                    scenario: {m: {AVG: 0.0, ALL: list()} for m in LOCALIZATIONS}
                    for scenario in SCENARIOS
                }
                for metric in METRICS
            }
            for type_ in FEATURES + UNIFIED
        },
    }
    number_of_subjects = 0

    all_corr = {
        type_: {
            TRUE: [],
            FALSE: [],
            TOTAL: [],
        }
        for type_ in FEATURES + UNIFIED
    }
    for subject in SUBJECTS:
        for i in range(200):
            subject_results = RESULTS_DIR / f"{subject}_{i}.json"
            if not subject_results.exists():
                continue
            with subject_results.open() as f:
                subject_data = json.load(f)
            for s in subject_data:
                number_of_subjects += 1
                for t in FEATURES + UNIFIED:
                    if t in FEATURES:
                        all_corr[t][TRUE].extend(subject_data[s][t][CORRELATION][TRUE])
                        all_corr[t][TOTAL].extend(
                            subject_data[s][t][CORRELATION][TOTAL]
                        )
                        results[CORRELATION][t][TRUE][ALL].append(
                            spearman(
                                subject_data[s][t][CORRELATION][TRUE],
                                subject_data[s][t][CORRELATION][TOTAL],
                            )
                        )
                    for m in METRICS:
                        m = m.__name__
                        for c in AGGREGATES:
                            results[SUSPICIOUSNESS][t][m][c][ALL].append(
                                subject_data[s][t][SUSPICIOUSNESS][m][c]
                            )
                        for sce in SCENARIOS:
                            for loc in LOCALIZATIONS:
                                results[LOCALIZATION][t][m][sce][loc][ALL].append(
                                    subject_data[s][t][LOCALIZATION][m][sce][loc]
                                )

    for t in FEATURES + UNIFIED:
        if t in FEATURES:
            results[CORRELATION][t][ALL][TRUE] = spearman(
                all_corr[t][TRUE], all_corr[t][TOTAL]
            )
            for a in AGGREGATES:
                if a == BEST:
                    r, p = 0, 1
                    for r_, p_ in results[CORRELATION][t][TRUE][ALL]:
                        if p < P_VALUE <= p_:
                            continue
                        if abs(r) < abs(r_):
                            r = r_
                            p = p_
                        elif abs(r) == abs(r_):
                            p = min(p, p_)
                elif a == MEAN:
                    mean = lambda cors: sum(cors) / len(cors)
                    r = mean([x for x, _ in results[CORRELATION][t][TRUE][ALL]])
                    p = mean([y for _, y in results[CORRELATION][t][TRUE][ALL]])
                elif a == MEDIAN:
                    median = lambda cors: sorted(cors)[len(cors) // 2]
                    r = median([x for x, _ in results[CORRELATION][t][TRUE][ALL]])
                    p = median([y for _, y in results[CORRELATION][t][TRUE][ALL]])
                else:
                    r, p = 1, 1
                    for r_, p_ in results[CORRELATION][t][TRUE][ALL]:
                        if p < P_VALUE <= p_:
                            continue
                        if abs(r) > abs(r_):
                            r = r_
                            p = p_
                        elif abs(r) == abs(r_):
                            p = min(p, p_)
                results[CORRELATION][t][TRUE][a] = (r, p)
        for m in METRICS:
            m = m.__name__
            for c in AGGREGATES:
                results[SUSPICIOUSNESS][t][m][c][AVG] = (
                    sum(results[SUSPICIOUSNESS][t][m][c][ALL]) / number_of_subjects
                )
            for sce in SCENARIOS:
                for loc in LOCALIZATIONS:
                    results[LOCALIZATION][t][m][sce][loc][AVG] = (
                        sum(results[LOCALIZATION][t][m][sce][loc][ALL])
                        / number_of_subjects
                    )
    with open(SUMMARY, "w") as f:
        json.dump(results, f, indent=1)
