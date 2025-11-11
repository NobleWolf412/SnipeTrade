import pytest

from snipetrade.planner.entries_adv import propose_entries_adv


class DummyCfg:
    VWAP_K_STD = 0.35
    OBI_MAKER_THRESHOLD = 0.2
    MAKER_SPREAD_MAX_BPS = 10
    STOP_ENTRY_TICKS = 1
    QUEUE_OFFSET_TICKS = 1
    ENTRY_ATR_MIN_FRAC = 0.2
    SESSION_BIAS = {"london_ny_tighter": True}


@pytest.fixture
def base_setup():
    return {
        "direction": "LONG",
        "atr": 2.0,
        "stop": 95.0,
    }


@pytest.fixture
def price_ctx():
    return {"price": 100.5, "tick_size": 0.1, "session": "london"}


@pytest.fixture
def structure_ctx():
    return {
        "ob_mid": 99.8,
        "ob_low": 99.5,
        "ob_high": 100.2,
        "fvg_mid": 101.0,
        "fvg_lo": 99.2,
        "fvg_hi": 101.4,
        "anchor_idx": 3,
    }


@pytest.fixture
def vwap_ctx():
    return {"vwap": 100.2, "std": 1.0}


@pytest.fixture
def orderflow_ctx():
    return {"obi": 0.35, "spread_bps": 8.0, "cvd": 10.0, "liq_in_zone": False}


def test_entries_limit_when_orderflow_supports(base_setup, price_ctx, orderflow_ctx, structure_ctx, vwap_ctx):
    entries = propose_entries_adv(base_setup, price_ctx, orderflow_ctx, structure_ctx, vwap_ctx, DummyCfg)
    near = entries["near"]
    far = entries["far"]
    assert near["type"] == "limit"
    assert near["post_only"]
    assert far["type"] == "limit"
    assert far["price"] <= near["price"]


def test_entries_stop_when_liq_cluster(base_setup, price_ctx, structure_ctx, vwap_ctx):
    orderflow_ctx = {"obi": 0.05, "spread_bps": 12.0, "cvd": -5.0, "liq_in_zone": True}
    entries = propose_entries_adv(base_setup, price_ctx, orderflow_ctx, structure_ctx, vwap_ctx, DummyCfg)
    assert entries["near"]["type"] == "stop"
    assert entries["far"]["type"] == "stop"


def test_entries_atr_guard(price_ctx, structure_ctx, vwap_ctx):
    cfg = DummyCfg
    setup = {"direction": "LONG", "atr": 2.0, "stop": 98.8}
    orderflow_ctx = {"obi": 0.3, "spread_bps": 4.0, "cvd": 5.0, "liq_in_zone": False}
    with pytest.raises(ValueError):
        propose_entries_adv(setup, price_ctx, orderflow_ctx, structure_ctx, vwap_ctx, cfg)
