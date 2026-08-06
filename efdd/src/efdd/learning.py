import enum
import os
import warnings
from abc import ABC
from typing import Sequence, Tuple, Any, Optional, List

import pandas as pd
import shap
from joblib import dump, load
from sflkit.analysis.spectra import Line
from sflkit.features.handler import EventHandler
from sflkit.features.value import Feature
from sklearn import tree
from sklearn.exceptions import UndefinedMetricWarning
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from efdd.reduce import FeatureSelection, DefaultSelection

warnings.filterwarnings("ignore", category=UndefinedMetricWarning)


class Label(enum.Enum):
    BUG = 1
    NO_BUG = 0


class DiagnosisGenerator(ABC):
    def __init__(
        self,
        model: Any,
        path: Optional[os.PathLike] = None,
        reducer: FeatureSelection = DefaultSelection(),
        explainer=shap.KernelExplainer,
    ):
        self.all_features: Sequence[Feature] = list()
        self.model = model
        self.path = path
        self.reducer = reducer
        self.explainer = explainer
        self.x_train: pd.DataFrame = None
        self.y_train: pd.DataFrame = None

    def prepare_data(
        self,
        handler: EventHandler,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        data = handler.to_df(self.all_features)
        return data.drop(columns=["test", "failing"]), data["failing"]

    def train(self):
        self.model.fit(
            self.reducer.select(self.x_train).to_numpy(), self.y_train.to_numpy()
        )
        if self.path:
            dump(self.model, str(self.path))

    def fit(
        self,
        all_features: Sequence[Feature],
        handler: EventHandler,
    ):
        self.all_features = all_features
        self.x_train, self.y_train = self.prepare_data(handler)
        self.train()

    def evaluate(
        self,
        handler: EventHandler,
        output_dict: bool = False,
    ) -> Tuple[str | dict, List[List[int]]]:
        x_eval, y_eval = self.prepare_data(handler)
        return (
            self.classification_report(x_eval, y_eval, output_dict=output_dict),
            confusion_matrix(
                y_eval.to_numpy(), self.model.predict(x_eval.to_numpy()), labels=[0, 1]
            ).tolist(),
        )

    def classify(self, x: pd.DataFrame) -> Label:
        return Label[int(self.model.predict(x.to_numpy())[0])]

    def accuracy_score(self, x: pd.DataFrame, y: pd.DataFrame):
        return accuracy_score(y.to_numpy(), self.model.predict(x.to_numpy()))

    def classification_report(
        self, x: pd.DataFrame, y: pd.DataFrame, output_dict: bool = False
    ) -> str | dict:
        return classification_report(
            y.to_numpy(), self.model.predict(x.to_numpy()), output_dict=output_dict
        )

    def explain(self, x: Optional[pd.DataFrame] = None):
        x = x or self.x_train
        return self.explainer(self.model, x)(x)

    def finalize(
        self,
        handler: EventHandler,
    ):
        x_train, y_train = self.prepare_data(handler)
        self.x_train = pd.concat((self.x_train, x_train))
        self.y_train = pd.concat((self.y_train, y_train))
        self.train()

    def get_information(self) -> dict[str, Any]:
        return dict()


class DecisionTreeDiagnosis(DiagnosisGenerator):
    def __init__(
        self,
        path: Optional[os.PathLike] = None,
        reducer: FeatureSelection = DefaultSelection(),
        random_state: int = 42,
        criterion: str = "log_loss",
    ):
        # criterion: gini or log_loss
        if path is None or not os.path.exists(path):
            model = tree.DecisionTreeClassifier(
                random_state=random_state, criterion=criterion
            )
        else:
            model = load(str(path))
        super().__init__(
            model=model, path=path, reducer=reducer, explainer=shap.TreeExplainer
        )

    def get_information(self) -> dict[str, Any]:
        depth = self.model.get_depth()
        n_leaves = self.model.get_n_leaves()
        indices = [i for i, x in enumerate(self.model.feature_importances_) if x > 0]
        features = [self.all_features[i] for i in indices]
        return dict(
            depth=depth,
            n_leaves=int(n_leaves),
            complex_features=any(not isinstance(f, Line) for f in features),
            features=[f.analysis.analysis_type().value for f in features],
        )
