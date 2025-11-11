import pandas as pd

from snipetrade.sim.engine import BacktestEngine, TradeSpec
from snipetrade.tune.grid import build_grid, run_grid
from snipetrade.tune.bayes import optimise, parse_bounds


class CountingProfile:
    def __init__(self):
        self.train_called = 0
        self.test_windows = []

    def prepare(self, train: pd.DataFrame):
        self.train_called += 1
        return train.index[0]

    def generate(self, test: pd.DataFrame, context):
        self.test_windows.append(test.index[0])
        for ts, row in test.iterrows():
            yield TradeSpec(
                symbol="SIM",
                direction="long",
                entry=row["close"],
                stop=row["close"] * 0.9,
                targets=[row["close"] * 1.1],
                timestamp=ts,
            )


def make_frame():
    index = pd.date_range("2024-01-01", periods=120, freq="1H", tz="UTC")
    close = pd.Series(range(120), index=index) + 100
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1}, index=index)


def evaluate(params):
    frame = make_frame()
    profile = CountingProfile()
    engine = BacktestEngine()
    engine.run_walk_forward(frame, profile, train="5d", test="2d", steps=2)
    return params["a"]


def test_grid_search_runs():
    grid = build_grid({"a": "1..3x3"})
    results = run_grid(lambda p: p["a"], grid, budget=3)
    assert results[0].score == 3


def test_bayesian_bounds():
    bounds = {"a": parse_bounds("[0,1]")}
    result = optimise(lambda p: p["a"], bounds, trials=5, warmup=2)
    assert len(result.trials) == 5
