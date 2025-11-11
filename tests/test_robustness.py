import pandas as pd

from snipetrade.sim.engine import TradeResult, TradeSpec
from snipetrade.sim.robust import monte_carlo, parameter_jitter, slippage_shock


def make_trades():
    spec = TradeSpec(
        symbol="SIM",
        direction="long",
        entry=100,
        stop=95,
        targets=[110],
        timestamp=pd.Timestamp("2024-01-01", tz="UTC"),
    )
    return [
        TradeResult(
            spec=spec,
            filled=True,
            entry_time=pd.Timestamp("2024-01-01", tz="UTC"),
            exit_time=pd.Timestamp("2024-01-02", tz="UTC"),
            avg_entry=100,
            avg_exit=110,
            pnl=10,
            fee=-0.1,
            funding=0,
            partial=1,
        ),
        TradeResult(
            spec=spec,
            filled=True,
            entry_time=pd.Timestamp("2024-01-03", tz="UTC"),
            exit_time=pd.Timestamp("2024-01-04", tz="UTC"),
            avg_entry=100,
            avg_exit=90,
            pnl=-10,
            fee=-0.1,
            funding=0,
            partial=1,
        ),
        TradeResult(
            spec=spec,
            filled=True,
            entry_time=pd.Timestamp("2024-01-05", tz="UTC"),
            exit_time=pd.Timestamp("2024-01-06", tz="UTC"),
            avg_entry=100,
            avg_exit=105,
            pnl=5,
            fee=-0.1,
            funding=0,
            partial=1,
        ),
    ]


def test_monte_carlo_distribution():
    trades = make_trades()
    result = monte_carlo(trades, runs=20)
    assert result.mean != 0


def test_parameter_jitter_returns_samples():
    result = parameter_jitter({"a": 1.0}, lambda params: params["a"])
    assert "baseline" in result
    assert result["samples"]


def test_slippage_shock_expectancy():
    trades = make_trades()
    outcomes = slippage_shock(trades, shocks=[0.0])
    assert outcomes[0].expectancy != 0
