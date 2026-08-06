# Java execution-feature fault localization

This repository is the replication package for a cross-language study of
execution-feature fault localization. It ports the original Python
[Execution-Feature-Driven Debugging](https://doi.org/10.5281/zenodo.14909966)
study to Java, records the same execution features on Defects4J, and repeats the
correlation, single-feature localization, and multi-feature localization
analyses reported in the paper.

The package contains the Java instrumentation tooling, the study drivers, and
the generated data needed to reproduce the paper's tables from either the
included results or the raw execution traces.

## Study at a glance

- **Subject system:** 516 reproducible bugs from 13
  [Defects4J](https://github.com/rjust/defects4j) projects.
- **Trace corpus:** 16,759 failing and 123,655 passing test executions.
- **Features:** the same 17 execution features as the Python EFDD study,
  including lines, branches, functions, def-use pairs, loops, conditions, scalar
  pairs, variable values, returns, null values, string properties, and empty
  bytes.
- **Analyses:** Tarantula, Ochiai, DStar, Naish2, and GP13 suspiciousness;
  Spearman feature-failure correlation; top-1/top-5/top-10, EXAM, and wasted
  effort localization metrics; best-, average-, and worst-case debugging
  scenarios; unified multi-feature rankings.

## Repository layout

| Path | Contents |
| --- | --- |
| `jast/` | ANTLR-based Java parser and instrumentation toolkit used to rewrite Java source code. |
| `sflkit/` | jSFLKit, the Java-capable extension of SFLKit used to record and analyze JVM execution features. |
| `efdd/` | The original EFDD sources plus this Java replication study. |
| `efdd/study/` | Study scripts, raw traces, mappings, per-bug results, aggregate summaries, and generated LaTeX tables. |
| `gen/` | Generated ANTLR lexer/parser artifacts. |

## Data layout

The main artifact data lives in `efdd/study/`.

| Path | Role |
| --- | --- |
| `sflkit_events/<Project>/<bug>/bug/{failing,passing}/` | Raw per-test execution-event traces recorded by jSFLKit. This is the largest part of the package, about 265 GB. |
| `mappings/<Project>_<bug>.json` | Event-id to source-location mappings used to decode traces, about 3.4 GB. |
| `results/<Project>_<bug>.json` | Per-bug suspiciousness, correlation, and localization results, about 2.9 GB. |
| `summary.json` | Aggregated results over all evaluated bugs. |
| `tex/` | Generated LaTeX tables consumed by the paper. |
| `selected_tests/` | Failing and passing test selections used for each bug. |
| `dataset_report.json` | Collection status for every attempted Defects4J bug; bugs with status `ok` are the 516 evaluated subjects. |
| `nonthreaded_bugs.json`, `stats.json` | Study metadata and auxiliary statistics. |

## Requirements

For regenerating the paper tables from the included results, only Python and the
Python dependencies are needed. Re-evaluating traces or recollecting the dataset
also requires Java and Defects4J.

- Python 3.12.
- Java 8 for Defects4J subjects.
- A working Defects4J checkout for Tier 2 and Tier 3 below. Set `D4J_HOME` to
  the checkout root, or leave it unset to use `~/defects4j`. The `defects4j`
  executable must be on `PATH`.
- Enough disk space for the chosen tier. The full raw trace corpus is roughly
  265 GB, before temporary Defects4J checkouts.

Install the bundled packages and study dependencies from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e jast
python -m pip install -e sflkit
python -m pip install -r efdd/study/requirements.txt
```

`d4j_evaluate.py` is intentionally usable in a Java-only study environment: it
does not import `tests4py`. The shared `study.py` commands also support the
original Python EFDD workflow and therefore import `tests4py` through the study
requirements.

## Reproduction workflow

Run the following commands from `efdd/study/` unless noted otherwise:

```bash
cd efdd/study
```

### Tier 1: regenerate the paper tables from included results

Use this tier for the quickest artifact check. It consumes the included
`results/` directory, rebuilds `summary.json`, and regenerates the LaTeX tables
in `tex/`. Defects4J is not required.

```bash
python study.py summarize
python study.py interpret -t
```

The generated files in `tex/` correspond to the tables copied into the paper's
`data/*.tex` files.

### Tier 2: re-run the analysis from included traces

Use this tier to recompute per-bug results from the raw jSFLKit traces and
mappings. This requires Defects4J because the evaluator checks out subjects to
obtain faulty lines from reference patches and source line counts from buggy
versions.

```bash
# Evaluate one project.
python d4j_evaluate.py -p Csv

# Evaluate one bug.
python d4j_evaluate.py -p Csv -i 1

# Evaluate all bugs with status "ok" in dataset_report.json.
python d4j_evaluate.py --all --workers 2
```

Existing files in `results/` are skipped. Delete the corresponding
`results/<Project>_<bug>.json` files before running the command if you want to
force recomputation.

For larger runs, use the built-in splitting options:

```bash
# Restrict the run to selected projects.
python d4j_evaluate.py --projects Chart,Cli,Codec --workers 2

# Process only shard k/n of the selected, sorted bugs.
python d4j_evaluate.py --all --shard 0/3 --workers 1
```

Keep `--workers` modest. Large Defects4J bugs can require several GB of memory
while their traces are analyzed.

After recomputing `results/`, rerun Tier 1 to refresh `summary.json` and `tex/`.

### Tier 3: recollect raw traces from Defects4J

Use this tier only when you need to recreate the raw execution-event dataset.
It checks out each Defects4J bug, instruments the buggy version with jSFLKit,
runs the selected failing and passing tests, writes traces under
`sflkit_events/`, and writes mappings under `mappings/`. This is a multi-day,
high-storage step.

```bash
python collect_dataset.py
```

Collection is resumable through `dataset_report.json`: a bug already recorded in
the report is skipped. Temporary Defects4J work directories are created under
`/tmp/d4j/dataset_work` and removed after each bug.

After recollecting traces, run Tier 2 to rebuild `results/`, then Tier 1 to
rebuild the aggregate tables.

## Subjects

| Project | Bugs | Failing traces | Passing traces |
| --- | ---: | ---: | ---: |
| Chart | 25 | 92 | 5,643 |
| Cli | 37 | 91 | 5,895 |
| Codec | 18 | 526 | 1,235 |
| Collections | 27 | 89 | 2,077 |
| Compress | 47 | 756 | 6,439 |
| Csv | 16 | 24 | 2,097 |
| Gson | 18 | 313 | 12,003 |
| Jsoup | 93 | 903 | 31,111 |
| JxPath | 22 | 2,111 | 3,877 |
| Lang | 58 | 756 | 9,826 |
| Math | 92 | 6,378 | 15,493 |
| Mockito | 38 | 262 | 25,256 |
| Time | 25 | 4,458 | 2,703 |
| **Total** | **516** | **16,759** | **123,655** |

## Useful scripts

| Command | Purpose |
| --- | --- |
| `python study.py summarize` | Aggregate `results/*.json` into `summary.json`. |
| `python study.py interpret -t` | Generate LaTeX tables in `tex/` from `summary.json`. |
| `python d4j_evaluate.py ...` | Evaluate Java traces and write per-bug `results/*.json`. |
| `python collect_dataset.py` | Recollect Defects4J execution traces and mappings. |
| `python test_lists.py record` | Record reproduction/test-list metadata without deleting traces. |
| `python test_lists.py reclaim` | Dry-run trace cleanup for unreproducible or incomplete bugs; add `--apply` to delete. |

## Paper

The accompanying paper evaluates whether the Python EFDD findings transfer to a
statically typed, compiled setting. Its main findings are that value- and
data-level features correlate more strongly with failures than line coverage,
lines remain the strongest single feature for exact localization, and combining
features improves EXAM and wasted effort over any individual feature.

The paper source used while preparing this README is expected next to this
repository at `../../papers/apr2026-java-efdd`.

## Citation

If you use this package, cite the accompanying Java EFDD replication paper and
the original Python EFDD study. The paper's data availability statement points
to this repository:

## License

This replication package is released under the Apache License 2.0; see
`LICENSE`. The vendored original EFDD sources under `efdd/` retain their MIT
license; see `efdd/LICENSE`.
