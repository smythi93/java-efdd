import json
import sys
from pathlib import Path
from typing import Tuple, List

import matplotlib.pyplot as plt

from confusion import (
    Confusion,
    get_confusion,
    EVAL,
    CONFUSION,
    Metrics,
    get_metrics,
)

RESULTS = Path("results")

COOKIECUTTER_2 = RESULTS / "cookiecutter_2.json"
COOKIECUTTER_3 = RESULTS / "cookiecutter_3.json"
COOKIECUTTER_4 = RESULTS / "cookiecutter_4.json"
FASTAPI_1 = RESULTS / "fastapi_1.json"
PYSNOOPER_2 = RESULTS / "pysnooper_2.json"
PYSNOOPER_3 = RESULTS / "pysnooper_3.json"


def get_results(path: Path) -> Confusion:
    result = Confusion(total=0)
    metrics = Metrics()
    if path.exists():
        t4p_results = json.loads(path.read_text("utf8"))
        for name in t4p_results:
            result += get_confusion(t4p_results[name], name=name)
            metrics += get_metrics(t4p_results[name], name=name)
    return result, metrics


def main():
    results = Confusion(total=0)
    metrics = Metrics()
    for path in [
        PYSNOOPER_2,
        PYSNOOPER_3,
        FASTAPI_1,
        COOKIECUTTER_2,
        COOKIECUTTER_3,
        COOKIECUTTER_4,
    ]:
        r, m = get_results(path)
        results += r
        metrics += m
    results.print()
    metrics.print()


if __name__ == "__main__":
    main()
