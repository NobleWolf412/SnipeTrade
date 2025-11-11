from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from snipetrade.sim.engine import StrategyProfile, TradeSpec


def _load_simple_yaml(path: Path) -> Dict[str, float]:
    data: Dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split(":", 1)
        data[key.strip()] = float(value.strip())
    return data


class ThresholdProfile(StrategyProfile):
    def __init__(self, params: Dict[str, float]):
        self.params = params

    def prepare(self, train: pd.DataFrame) -> Dict[str, float]:
        momentum_series = train["close"].pct_change(periods=4, fill_method=None).fillna(0.0)
        momentum = float(momentum_series.mean())
        atr_series = (train["high"] - train["low"]).rolling(14).mean().bfill()
        atr = float(atr_series.iloc[-1]) if not atr_series.empty else 0.0
        return {"momentum": momentum, "atr": atr}

    def generate(self, test: pd.DataFrame, context: Dict[str, float]):
        atr_band = float(self.params.get("atr_band", 1.0))
        rr_min = float(self.params.get("rr_min", 2.0))
        min_score = float(self.params.get("min_score", 50))
        stop_multiplier = atr_band
        for ts, row in test.iterrows():
            momentum = float(row["close"] / max(row["open"], 1e-9) - 1)
            base_momentum = context.get("momentum", 0.0)
            score = (momentum + base_momentum) * 10000
            if abs(score) < min_score:
                continue
            direction = "long" if momentum >= 0 else "short"
            entry = row["close"]
            atr = float((row["high"] - row["low"]) or context.get("atr", 0.0) or 1.0)
            stop = entry - atr * stop_multiplier if direction == "long" else entry + atr * stop_multiplier
            target = entry + (entry - stop) * rr_min if direction == "long" else entry - (stop - entry) * rr_min
            yield TradeSpec(
                symbol=row.get("symbol", "SYMBOL"),
                direction=direction,
                entry=entry,
                stop=stop,
                targets=[target],
                timestamp=ts,
                metadata={"score": score},
            )


def load_data(path: Path | None, length: int = 500) -> pd.DataFrame:
    if path is None:
        index = pd.date_range("2024-01-01", periods=length, freq="1h", tz="UTC")
        base = pd.Series(range(length), dtype=float).rolling(5, min_periods=1).mean().to_numpy()
        close = pd.Series(100 + base, index=index)
        frame = pd.DataFrame(
            {
                "open": close.shift(1).bfill(),
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1000,
                "symbol": "SIM",
            },
            index=index,
        )
        return frame
    frame = pd.read_csv(path, parse_dates=[0], index_col=0)
    if "symbol" not in frame.columns:
        frame["symbol"] = "CSV"
    return frame


def load_profile(path: Path) -> ThresholdProfile:
    params = _load_simple_yaml(path)
    return ThresholdProfile(params)
