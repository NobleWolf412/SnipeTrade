from snipetrade.planner.leverage import (
    estimate_liq_price,
    liq_is_safe,
    recommend_size_adjustment,
)


class DummyCfg:
    LIQ_BUFFER_PCT = 0.8
    LIQ_BUFFER_ATR_MULT = 0.5


def test_estimate_liq_price_moves_with_leverage():
    long_liq_lo = estimate_liq_price(100.0, "LONG", leverage=5, maint_margin_rate=0.005)
    long_liq_hi = estimate_liq_price(100.0, "LONG", leverage=10, maint_margin_rate=0.005)
    assert long_liq_lo < long_liq_hi


def test_liq_is_safe_checks_buffers():
    safe, _ = liq_is_safe(95.0, 94.0, "LONG", 2.0, DummyCfg.LIQ_BUFFER_PCT, DummyCfg.LIQ_BUFFER_ATR_MULT)
    assert safe
    is_safe, reason = liq_is_safe(95.0, 94.8, "LONG", 2.0, DummyCfg.LIQ_BUFFER_PCT, DummyCfg.LIQ_BUFFER_ATR_MULT)
    assert not is_safe
    assert "need" in reason


def test_recommend_size_adjustment():
    factor, reason = recommend_size_adjustment(
        entry=100.0,
        sl=95.0,
        side="LONG",
        leverage=20,
        maint_margin_rate=0.005,
        atr=2.0,
        liq_buffer_pct=DummyCfg.LIQ_BUFFER_PCT,
        liq_buffer_atr_mult=DummyCfg.LIQ_BUFFER_ATR_MULT,
    )
    assert 0 < factor <= 1.0
    assert "reduce" in reason or factor == 1.0
