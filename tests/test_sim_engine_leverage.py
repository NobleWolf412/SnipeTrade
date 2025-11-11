from snipetrade.sim.engine import SimulationEngine


def test_sim_engine_maker_fill():
    engine = SimulationEngine(maker_fee_bps=1.0, taker_fee_bps=7.5, slippage_bps=2.0)
    plan = {
        "side": "LONG",
        "qty": 1.0,
        "entries": {"near": {"type": "limit", "price": 100.0}},
        "execution": {
            "near_plan": {"valid_until_ms": 90_000},
            "fallback": {"activate_after_ms": 90_000, "type": "stop", "price": 101.0},
        },
        "stop": 98.0,
        "tps": [102.0],
    }
    prices = [{"ts": 0, "price": 100.0}, {"ts": 30_000, "price": 99.8}, {"ts": 60_000, "price": 102.0}]
    result = engine.run(plan, prices)
    assert result["filled"]
    assert result["fill_type"] == "maker"
    assert result["fees"] == pytest.approx(100.0 * 0.0001)


def test_sim_engine_fallback_trigger():
    engine = SimulationEngine(maker_fee_bps=1.0, taker_fee_bps=7.5, slippage_bps=2.0)
    plan = {
        "side": "LONG",
        "qty": 1.0,
        "entries": {"near": {"type": "limit", "price": 100.0}},
        "execution": {
            "near_plan": {"valid_until_ms": 90_000},
            "fallback": {"activate_after_ms": 30_000, "type": "stop", "price": 101.0},
        },
        "stop": 98.0,
        "tps": [104.0],
    }
    prices = [
        {"ts": 0, "price": 102.0},
        {"ts": 30_000, "price": 101.5},
        {"ts": 60_000, "price": 104.0},
    ]
    result = engine.run(plan, prices)
    assert result["filled"]
    assert result["fill_type"] == "fallback"
    assert result["fees"] == pytest.approx(101.0 * 0.00075, rel=1e-3)

import pytest
