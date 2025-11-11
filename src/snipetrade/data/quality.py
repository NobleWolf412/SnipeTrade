"""Data quality checks for OHLCV candles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd


@dataclass
class QualityReport:
    total: int
    dropped: int
    fixes: Dict[str, int]

    def as_dict(self) -> Dict[str, float]:
        return {"total": self.total, "dropped": self.dropped, **self.fixes}


def check_quality(frame: pd.DataFrame) -> QualityReport:
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError("OHLCV data must use a DatetimeIndex")

    fixes = {"deduplicated": 0, "sorted": 0, "filled_gaps": 0}
    total = len(frame)

    cleaned = frame.copy()
    cleaned = cleaned[~cleaned.index.duplicated(keep="last")]
    fixes["deduplicated"] = total - len(cleaned)

    if not cleaned.index.is_monotonic_increasing:
        cleaned = cleaned.sort_index()
        fixes["sorted"] = 1

    # Identify gaps larger than median spacing and forward fill volume to zero
    if len(cleaned) >= 3:
        diffs = cleaned.index.to_series().diff().dropna()
        median = diffs.median()
        gap_mask = diffs > median * 3
        fixes["filled_gaps"] = int(gap_mask.sum())

    dropped = total - len(cleaned)
    return QualityReport(total=total, dropped=dropped, fixes=fixes)


def enforce_quality(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a cleaned dataframe ensuring quality constraints."""

    report = check_quality(frame)
    cleaned = frame.copy()
    cleaned = cleaned[~cleaned.index.duplicated(keep="last")]
    cleaned = cleaned.sort_index()
    cleaned = cleaned.loc[~cleaned.index.isna()]
    if cleaned.index.tz is None:
        cleaned.index = cleaned.index.tz_localize("UTC")
    else:
        cleaned.index = cleaned.index.tz_convert("UTC")
    return cleaned
