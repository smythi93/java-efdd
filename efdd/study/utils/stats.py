import json
from pathlib import Path

import tqdm

from utils.constants import RESULTS_DIR, SUBJECTS, FEATURES, CORRELATION, TOTAL
import tests4py.api as t4p

from utils.interpret import tex_translation


def stats():
    if not RESULTS_DIR.exists():
        return
    locs_to_features = []
    all_features = {t: [] for t in FEATURES}
    for subject in tqdm.tqdm(SUBJECTS):
        for i in range(100):
            subject_results = RESULTS_DIR / f"{subject}_{i}.json"
            if not subject_results.exists():
                continue
            with subject_results.open() as f:
                subject_data = json.load(f)
            for s in subject_data:
                total = 0
                for t in FEATURES:
                    feature = sum(subject_data[s][t][CORRELATION][TOTAL])
                    all_features[t].append(feature)
                    total += feature
                locs_to_features.append((t4p.get_projects(subject, i)[0].loc, total))
    with open("stats.json", "w") as f:
        json.dump(
            {"all_features": all_features, "locs_to_features": locs_to_features},
            f,
            indent=1,
        )


def get_avg_features():
    with open("stats.json", "r") as f:
        data = json.load(f)
    all_features = data["all_features"]
    avg_features = {t: sum(all_features[t]) / len(all_features[t]) for t in FEATURES}
    print("Average features per type:")
    for t in FEATURES:
        print(f"{t}: {avg_features[t]:.2f}")
    print(f"Overall average: {sum(avg_features.values()) / len(avg_features):.2f}")
    tex_string = f"\\begin{{tabular}}{{l{'r' * len(FEATURES)}}}\n\\toprule\n"
    tex_string += (
        " & "
        + " & ".join(
            [
                "\\multicolumn{1}{c}{\\shortstack{"
                + tex_translation[f].replace(" ", " \\\\ ")
                + "}}"
                for f in FEATURES
            ]
        )
        + " \\\\\\midrule\n"
    )
    tex_string += (
        "Average Features per Subject & "
        + " & ".join(f"{avg_features[t] / 1000:.2f}K" for t in FEATURES)
        + " \\\\\n"
    )
    tex_string += "\\bottomrule\n\\end{tabular}\n"
    with open(Path("tex") / "avg-features.tex", "w") as f:
        f.write(tex_string)


def locs_to_features():
    with open("stats.json", "r") as f:
        data = json.load(f)
    locs_to_features = data["locs_to_features"]
    locs_to_features.sort()
    # generate plot but ignore outliers
    import matplotlib.pyplot as plt
    import numpy as np

    locs = [x[0] for x in locs_to_features if x[0] < 200000 and x[1] < 2 * 1e7]
    features = [x[1] for x in locs_to_features if x[0] < 200000 and x[1] < 2 * 1e7]

    plt.scatter(locs, features, alpha=0.5)
    plt.xlabel("Lines of Code")
    plt.ylabel("Number of Features")
    plt.title("Lines of Code vs Number of Features")
    # add trend line
    z = np.polyfit(locs, features, 1)
    p = np.poly1d(z)
    plt.plot(locs, p(locs), "r--")
    plt.savefig("locs-to-features.pdf")
    plt.show()
