# Execution-Feature-Driven Debugging

## Abstract

Fault localization is a fundamental aspect of debugging, aiming to identify code regions likely responsible for 
failures. 
Traditional techniques primarily correlate statement execution with failures, yet program behavior is influenced by 
diverse execution features—such as variable values, branch conditions, and definition-use pairs—that can provide richer 
diagnostic insights.

In an empirical study of 310 bugs across 20 projects, we analyzed 17 execution features and assessed their correlation 
with failure outcomes. Our findings suggest that fault localization benefits from a broader range of execution features:
(1) _Scalar pairs_ exhibit the strongest correlation with failures;
(2) Beyond line executions, _def-use pairs_ and _functions executed_ are key indicators for fault localization; and
(3) Combining _multiple features_ enhances effectiveness compared to relying solely on individual features.

Building on these insights, we introduce a debugging approach to diagnose failure circumstances. 
The approach extracts fine-grained execution features and trains a decision tree to differentiate passing and failing 
runs.
From this model, we derive a diagnosis that pinpoints faulty locations and explains the underlying causes of the 
failure. 

Our evaluation demonstrates that the generated diagnoses achieve high predictive accuracy, reinforcing their 
reliability. 
These interpretable diagnoses empower developers to efficiently debug software by providing deeper insights into 
failure causes.

## Study

### Setup

We leverage SFLKit to collect the event data for the subjects. 
SFLKit is a tool that instruments the subject programs to collect the event data. 
The event data is a sequence of events that occur during the execution of the subject.

As subjects of our empirical study, we leverage [Tests4Py](https://github.com/smythi93/Tests4Py).

The study is located in the `study` directory.
Additionally, we have implemented a script, `study.py,` to run the experiments and analyze the results.

### Installing Requirements

To install the requirements, run the following command inside the `study` directory:

```bash
python -m pip install -r requirements.txt
```

We recommend using a virtual environment to install the requirements. To create a virtual environment, run the following command:

```bash
python -m venv .venv
```

and to activate the virtual environment, run the following command:
```bash
. .venv/bin/activate
```
or
```bash
source .venv/bin/activate
```

### Getting the Data Set

To get the data set, please download the data set from [here](https://doi.org/10.5281/zenodo.14909966) and extract it to
the `study` directory.

You can also reproduce the data by following the next section.

### Reproducing the Data Set

#### Collecting The Event Data

To collect the event data, run the following command:

```bash
python study.py event -p <project_name> [-i <bug_id>]
```

For instance, to collect the event data for bug 1 of the project `black`, run the following command:

```bash
python3 get_events.py -p black -i 1
```

The collected event data will be stored in the `sflkit_events` directory.
Additionally, this script maps all possible events for the subjects and stores them in 
`mappings/<project_name>_<bug_id>.json`.

So the collected events and mapping of the `black` project and bug 1 will be stored in `sflkit_events/black/1/bug` for 
the buggy version, `sflkit_events/black/1/fix` for the fixed version, and `mappings/black_1.json` for the mapping.

Remove the `report_<project_name>.json` file if you want to collect the event data from scratch.

#### Evaluating the Correlation and Fault Localization

To evaluate the correlation and fault localization, run the following command:

```bash
python study.py evaluate -p <project_name> [-i <bug_id>]
```

This script will evaluate the correlation of the execution features with the failure and the fault localization.
This script generates the features and their values in the `analysis` directory as an intermediate step.
The following command can explicitly run this step:

```bash
python study.py analyze -p <project_name> [-i <bug_id>]
```

The results of the correlation and fault localization will be stored in the `results` directory for each subject 
individually as a JSON file with the name `<project_name>_<bug_id>.json`.

If you want to evaluate the correlation and fault localization from scratch, you need to remove the corresponding 
files in the `results` directory.

To summarize the results of all subjects, run the following command:

```bash
python study.py summarize
```

The summarized results will be stored in a file called `summary.json`.

## Execution-Feature-Driven Debugging

### Installation

To install __E__xecution-__F__eature-__D__riven __D__ebugging (_EFDD_), run the following command:

```bash
python -m pip install .
```

### Usage

For _EFDD_, you need to instrument your subject.
```python
from efdd.events import instrument

instrument("middle.py", "tmp.py", "mapping.json")
```
Next, you need some tests to execute and collect their event traces. 
We provide two collectors, one for unit tests and one for input to the program.
However, implementing another collector by inheriting the base class `EventCollector` and implementing its `collect()` method is an option.
To employ the collector, use it like this:
```python
from efdd.events import SystemtestEventCollector

collector = SystemtestEventCollector(os.getcwd(), "middle.py", "tmp.py", mapping_path="mapping.json")
events = collector.get_events((passing, failing))
```
In this example, we leverage the input event collector. 
`passing` and `failing` are lists of passing and failing inputs.

Next, you can utilize the event handler to extract and build feature vectors from the event traces.
```python
from sflkit.features.handler import EventHandler

handler = EventHandler()
handler.handle_files(events)
```

Now, we can leverage _EFDD_ learning to infer a failure diagnosis.
```python
from efdd.learning import DecisionTreeDiagnosis

debugger = DecisionTreeDiagnosis()
debugger.fit(
    handler.builder.get_all_features(),
    handler,
)
```

Now, we can leverage the underlying model of the debugger as a diagnosis that pinpoints faulty locations and explains 
the underlying causes of the failure.

We provide an example of this walk-through in `evaluation/example.ipynb`.

# License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.