"""Feature engineering for the lightweight ranker."""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute interpretable features used by the ranker."""

    features = pd.DataFrame(index=frame.index)
    range_ = frame["high"] - frame["low"]
    features["atr_pct"] = range_.rolling(14).mean() / frame["close"]
    features["rr_ratio"] = frame["close"].pct_change(periods=4)
    features["vwap_delta"] = frame["close"] - frame["close"].rolling(20).mean()
    volume_mean = frame["volume"].rolling(20).mean()
    volume_std = frame["volume"].rolling(20).std().replace(0, np.nan)
    features["volume_z"] = (frame["volume"] - volume_mean) / volume_std
    features = features.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return features
