import numpy as np
import pandas as pd

from snipetrade.ml.features import build_features
from snipetrade.ml.ranker import train_ranker


def test_ranker_trains_and_predicts():
    index = pd.date_range("2024-01-01", periods=100, freq="1H", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": np.linspace(100, 120, 100),
            "high": np.linspace(101, 121, 100),
            "low": np.linspace(99, 119, 100),
            "close": np.linspace(100, 120, 100),
            "volume": np.linspace(1000, 2000, 100),
        },
        index=index,
    )
    features = build_features(frame).dropna()
    labels = [1 if i % 2 == 0 else 0 for i in range(len(features))]
    model = train_ranker(features, labels, epochs=20)
    preds = model.predict_proba(features.tail(5))
    assert preds.shape[0] == 5
    feature, weight = model.explain(features.iloc[-1])
    assert feature in features.columns
