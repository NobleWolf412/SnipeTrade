"""Anchored VWAP utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass
class AnchoredVWAP:
    vwap: float
    std: float


def anchored_vwap(df: pd.DataFrame, anchor_idx: int) -> Dict[str, float]:
    """Return VWAP anchored at the given index."""

    if df.empty:
        raise ValueError("DataFrame must contain price data")
    if anchor_idx < 0 or anchor_idx >= len(df):
        raise IndexError("anchor_idx outside of dataframe")

    required = {"high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        missing = ", ".join(sorted(required - set(df.columns)))
        raise KeyError(f"Missing columns: {missing}")

    anchored = df.iloc[anchor_idx:]
    typical = (anchored["high"] + anchored["low"] + anchored["close"]) / 3.0
    volume = anchored["volume"].astype(float)
    if (volume <= 0).all():
        return {"vwap": float(typical.iloc[-1]), "std": 0.0}

    pv = typical * volume
    cum_volume = volume.sum()
    if cum_volume <= 0:
        return {"vwap": float(typical.iloc[-1]), "std": 0.0}

    vwap_value = float(pv.sum() / cum_volume)
    variance = float(np.average((typical - vwap_value) ** 2, weights=volume))
    std = float(np.sqrt(max(variance, 0.0)))
    return {"vwap": vwap_value, "std": std}
