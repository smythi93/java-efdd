import json
import os
import sys
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from confusion import Confusion, get_confusion, Metrics, get_metrics
from run_on_refactory import QUESTIONS, CODE, FILE_PATTERN


def loc_of_example(
    question: int,
    identifier: int,
) -> int:
    try:
        name = f"wrong_{question}_{identifier:03d}"
        path, eval_path = QUESTIONS[question]
        file: Path = path / CODE / "wrong" / f"{name}.py"
        if file.exists():
            with open(file, "r", encoding="utf8") as fp:
                return len(fp.readlines())
    except Exception:
        pass
    return 0


def locs_of_question(
    question: int,
):
    path, _ = QUESTIONS[question]
    directory: Path = path / CODE / "wrong"
    result = dict()
    if directory.exists():
        for file in tqdm(os.listdir(directory)):
            m = FILE_PATTERN.match(file)
            if m:
                q = int(m.group("q"))
                if q == question:
                    e = int(m.group("e"))
                    result[e] = loc_of_example(question, e)
    return result


def main():
    locs = dict()
    for question in range(1, 6):
        q_locs = locs_of_question(question)
        locs[question] = q_locs
    with open("refactory_locs.json", "w", encoding="utf8") as fp:
        json.dump(locs, fp, indent=2)
    # print overall max, min, average
    all_values = []
    for question in locs:
        all_values.extend(locs[question].values())
        # print max, min, average for each question
        q_locs = locs[question]
        if q_locs:
            values = list(q_locs.values())
            print(
                f"Question {question}: max={max(values)}, min={min(values)}, avg={sum(values)/len(values):.2f}"
            )
    if all_values:
        print(
            f"Overall: max={max(all_values)}, min={min(all_values)}, avg={sum(all_values)/len(all_values):.2f}"
        )


if __name__ == "__main__":
    main()
