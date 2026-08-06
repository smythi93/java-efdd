import numpy as np
from sflkit.analysis.analysis_type import AnalysisType
from sklearn.metrics import auc


class Confusion:
    def __init__(
        self,
        tp: int = 0,
        fn: int = 0,
        fp: int = 0,
        tn: int = 0,
        perfect: int = 0,
        total: int = 1,
        time: float = 0,
        times: list[float] = None,
        baseline: list[float] = None,
        final: bool = False,
    ):
        self.tp = tp
        self.fp = fp
        self.fn = fn
        self.tn = tn
        self.perfect = perfect
        self.total = total
        self.time = time
        self.times = times or []
        self.baseline = baseline or []
        self.all_confusions = [self] if final else []

    def __add__(self, other):
        assert isinstance(other, Confusion)
        all_confusions = self.all_confusions + other.all_confusions
        confusion = Confusion(
            tp=self.tp + other.tp,
            fn=self.fn + other.fn,
            fp=self.fp + other.fp,
            tn=self.tn + other.tn,
            perfect=self.perfect + other.perfect,
            total=self.total + other.total,
            times=self.times + other.times,
            baseline=self.baseline + other.baseline,
            time=self.time + other.time,
        )
        confusion.all_confusions = all_confusions
        return confusion

    def precision_bug(self) -> float:
        return self.tn / max(self.tn + self.fn, 1)

    def precision_no_bug(self) -> float:
        return self.tp / max(self.tp + self.fp, 1)

    def recall_bug(self) -> float:
        return self.tn / max(self.tn + self.fp, 1)

    def recall_no_bug(self) -> float:
        return self.tp / max(self.tp + self.fn, 1)

    def accuracy(self) -> float:
        return (self.tp + self.tn) / max(self.total_labels(), 1) * 100

    def perfect_score(self) -> float:
        return self.perfect / max(self.total, 1) * 100

    def f1_bug(self) -> float:
        return 2 * self.tn / max(2 * self.tn + self.fn + self.fp, 1)

    def f1_no_bug(self) -> float:
        return 2 * self.tp / max(2 * self.tp + self.fp + self.fn, 1)

    def macro_precision(self):
        return (self.precision_bug() + self.precision_no_bug()) / 2

    def macro_recall(self):
        return (self.recall_bug() + self.recall_no_bug()) / 2

    def macro_f1(self):
        return (self.f1_bug() + self.f1_no_bug()) / 2

    def auc_bug(self):
        return auc(self.tn / (self.tn + self.fp), self.fn / (self.fn + self.tp))

    def auc_no_bug(self):
        return auc(self.tp / (self.tp + self.fn), self.fp / (self.fp + self.tn))

    def macro_auc(self):
        return (self.auc_bug() + self.auc_no_bug()) / 2

    def bugs(self):
        return self.tn + self.fp

    def no_bugs(self):
        return self.tp + self.fn

    def total_labels(self):
        return self.bugs() + self.no_bugs()

    def avg_time(self):
        return np.mean(self.times) if self.times else 0

    def avg_overhead(self):
        overheads = []
        for t, b in zip(self.times, self.baseline):
            if b > 0:
                overheads.append((t - b) / b)
        if overheads:
            return np.mean(overheads)
        return 0

    def avg_baseline(self):
        return np.mean(self.baseline) if self.baseline else 0

    def print(self):
        print(f"tp  : {self.tp}")
        print(f"fn  : {self.fn}")
        print(f"fp  : {self.fp}")
        print(f"tn  : {self.tn}")
        print(f"p   : {self.perfect}")
        print(f"t   : {self.total}")
        print(f"ac  : {self.accuracy():.2f}")
        print(f"pb  : {self.precision_bug():.4f}")
        print(f"pn  : {self.precision_no_bug():.4f}")
        print(f"rb  : {self.recall_bug():.4f}")
        print(f"rn  : {self.recall_no_bug():.4f}")
        print(f"f1b : {self.f1_bug():.4f}")
        print(f"f1n : {self.f1_no_bug():.4f}")
        print(f"mp  : {self.macro_precision():.4f}")
        print(f"mr  : {self.macro_recall():.4f}")
        print(f"mf1 : {self.macro_f1():.4f}")
        print(f"ps  : {self.perfect_score():.2f}")
        print(f"time: {self.avg_time():.2f}")
        print(f"baseline: {self.avg_baseline():.2f}")
        print(f"overhead: {self.avg_overhead():.2f}")


EVAL = "eval"
TIME_EXECUTION = "time_execution"
TIME_DIAGNOSIS = "time_diagnosis"
BUG = "1"
NO_BUG = "0"
CONFUSION = "confusion"


def get_confusion(dictionary: dict, name="", exclude_no_eval=True) -> Confusion:
    result = Confusion(total=0)
    if CONFUSION not in dictionary:
        print(f"skip {name}: no {CONFUSION}")
        return result
    if EVAL not in dictionary:
        print(f"skip {name}: no {EVAL}")
        return result
    if TIME_EXECUTION not in dictionary:
        print(f"skip {name}: no {TIME_EXECUTION}")
        return result
    if TIME_DIAGNOSIS not in dictionary:
        print(f"skip {name}: no {TIME_DIAGNOSIS}")
        return result
    cm = dictionary[CONFUSION]
    if len(cm) == 1:
        if exclude_no_eval:
            return result
        if len(cm[0]) != 1:
            print(f"skip {name}: {CONFUSION} not correct format")
            return result
        if BUG in dictionary[EVAL]:
            result = Confusion(tn=cm[0][0], perfect=1, final=True)
        else:
            result = Confusion(tp=cm[0][0], perfect=1, final=True)
    else:
        tp = cm[0][0]
        fp = cm[0][1]
        fn = cm[1][0]
        tn = cm[1][1]
        result = Confusion(
            tp=tp, fp=fp, fn=fn, tn=tn, perfect=fp == 0 and fn == 0, final=True
        )
    baseline = dictionary[TIME_EXECUTION]
    time = baseline + dictionary[TIME_DIAGNOSIS]
    result.time = time
    result.times = [time]
    result.baseline = [baseline]
    return result


class Metrics:
    def __init__(
        self,
        depths=None,
        leaves=None,
        complex_features=0,
        total=0,
        features=None,
        used=None,
    ):
        self.depths = depths or []
        self.leaves = leaves or []
        self.complex = complex_features
        self.total = total
        self.features = features or {}
        self.used = used or []

    def __add__(self, other):
        assert isinstance(other, Metrics)
        features = {}
        for key in set(self.features.keys()).union(other.features.keys()):
            features[key] = self.features.get(key, 0) + other.features.get(key, 0)
        return Metrics(
            depths=self.depths + other.depths,
            leaves=self.leaves + other.leaves,
            complex_features=self.complex + other.complex,
            total=self.total + other.total,
            features=features,
            used=self.used + other.used,
        )

    def mean_depth(self):
        return np.mean(self.depths) if self.depths else 0

    def mean_leaves(self):
        return np.mean(self.leaves) if self.leaves else 0

    def median_depth(self):
        return np.median(self.depths) if self.depths else 0

    def median_leaves(self):
        return np.median(self.leaves) if self.leaves else 0

    def complex_features_ratio(self):
        return self.complex / max(self.total, 1) if self.total > 0 else 0

    def ranked_features(self):
        feature_ids = sorted(
            self.features.keys(), key=lambda x: self.features[x], reverse=True
        )
        return [
            (AnalysisType(feature_id).name, self.features[feature_id])
            for feature_id in feature_ids
        ]

    def n_simple(self):
        return len([d for d in self.depths if d <= 1])

    def n_moderate(self):
        return len([d for d in self.depths if d == 2])

    def n_complex(self):
        return len([d for d in self.depths if d == 3])

    def n_very_complex(self):
        return len([d for d in self.depths if d > 3])

    def n_binary_decision(self):
        return len([l for l in self.leaves if l <= 2])

    def n_additional_branch(self):
        return len([l for l in self.leaves if l == 3])

    def n_balanced(self):
        return len([l for l in self.leaves if l == 4])

    def n_complex_decision(self):
        return len([l for l in self.leaves if l > 4])

    def avg_used_features(self):
        return np.mean(self.used) if self.used else 0

    def print(self):
        print(f"total: {self.total}")
        print(f"complex: {self.complex_features_ratio():.2f}")
        print(f"mean depth: {self.mean_depth():.2f}")
        print(f"mean leaves: {self.mean_leaves():.2f}")
        print(f"median depth: {self.median_depth():.2f}")
        print(f"median leaves: {self.median_leaves():.2f}")
        print(f"n simple: {self.n_simple()}")
        print(f"n moderate: {self.n_moderate()}")
        print(f"n complex: {self.n_complex()}")
        print(f"n very complex: {self.n_very_complex()}")
        print(f"n binary decision: {self.n_binary_decision()}")
        print(f"n additional branch: {self.n_additional_branch()}")
        print(f"n balanced: {self.n_balanced()}")
        print(f"n complex decision: {self.n_complex_decision()}")
        print(f"avg used features: {self.avg_used_features():.2f}")
        print("features:")
        for feature, count in self.ranked_features():
            print(f"  {feature}: {count}")


DATA = "data"
DEPTH = "depth"
LEAVES = "n_leaves"
COMPLEX = "complex_features"
FEATURES = "features"


def get_metrics(dictionary: dict, name="") -> Metrics:
    if "data" not in dictionary:
        print(f"skip {name}: no metrics")
        return Metrics()
    data = dictionary[DATA]
    if DEPTH not in data or LEAVES not in data:
        print(f"skip {name}: no depth or leaves")
        return Metrics()
    if COMPLEX not in data:
        print(f"skip {name}: no complex features")
        return Metrics()
    if FEATURES not in data:
        print(f"skip {name}: no features")
        return Metrics()
    features = {}
    for feature in data[FEATURES]:
        if feature not in features:
            features[feature] = 0
        features[feature] += 1
    return Metrics(
        depths=[data[DEPTH]],
        leaves=[data[LEAVES]],
        complex_features=int(data[COMPLEX]),
        total=1,
        features=features,
        used=[len(set(data[FEATURES]))],
    )
