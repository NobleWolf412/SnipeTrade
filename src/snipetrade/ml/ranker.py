"""Lightweight interpretable ranker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import numpy as np
import pandas as pd


@dataclass
class RankerModel:
    weights: np.ndarray
    bias: float
    feature_names: Tuple[str, ...]

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        matrix = features[list(self.feature_names)].to_numpy()
        logits = matrix @ self.weights + self.bias
        return 1 / (1 + np.exp(-logits))

    def explain(self, features: pd.Series) -> Tuple[str, float]:
        contributions = self.weights * features[list(self.feature_names)].to_numpy()
        top_idx = int(np.argmax(np.abs(contributions)))
        return self.feature_names[top_idx], float(contributions[top_idx])


def train_ranker(features: pd.DataFrame, labels: Iterable[int], *, lr: float = 0.1, epochs: int = 200) -> RankerModel:
    matrix = features.to_numpy()
    labels_arr = np.array(list(labels), dtype=float)
    weights = np.zeros(matrix.shape[1], dtype=float)
    bias = 0.0

    for _ in range(epochs):
        logits = matrix @ weights + bias
        preds = 1 / (1 + np.exp(-logits))
        error = preds - labels_arr
        grad_w = matrix.T @ error / len(matrix)
        grad_b = float(error.mean())
        weights -= lr * grad_w
        bias -= lr * grad_b

    return RankerModel(weights=weights, bias=bias, feature_names=tuple(features.columns))
