import pandas as pd

from snipetrade.sim.engine import BacktestEngine, TradeSpec
from snipetrade.sim.datasets import walk_forward_windows


class DummyProfile:
    def prepare(self, train: pd.DataFrame):
        return {"mean": train["close"].mean()}

    def generate(self, test: pd.DataFrame, context):
        for ts, row in test.iterrows():
            yield TradeSpec(
                symbol="SIM",
                direction="long",
                entry=row["close"],
                stop=row["close"] * 0.95,
                targets=[row["close"] * 1.05],
                timestamp=ts,
            )


def make_frame():
    index = pd.date_range("2024-01-01", periods=200, freq="1H", tz="UTC")
    close = pd.Series(range(200), index=index) + 100
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": 1,
        },
        index=index,
    )
    return frame


def test_walk_forward_determinism():
    frame = make_frame()
    engine = BacktestEngine(seed=42)
    profile = DummyProfile()

    result_a = engine.run_walk_forward(frame, profile, train="10d", test="5d", steps=3)
    result_b = engine.run_walk_forward(frame, profile, train="10d", test="5d", steps=3)

    assert result_a.combined_metrics == result_b.combined_metrics


def test_partial_fill_and_breakeven():
    frame = make_frame()
    engine = BacktestEngine()
    profile = DummyProfile()
    result = engine.run_walk_forward(frame, profile, train="5d", test="2d", steps=1)
    assert result.iterations[0].metrics["filled_trades"] > 0
