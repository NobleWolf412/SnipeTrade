from snipetrade.planner.sizing import position_size_leverage


class DummyCfg:
    RISK_USD = 50.0
    LOT_SIZE = 0.001
    MIN_NOTIONAL = 5.0
    MAINT_MARGIN_RATE = 0.005
    LIQ_BUFFER_PCT = 0.8
    LIQ_BUFFER_ATR_MULT = 0.5
    REDUCE_SIZE_IF_LIQ_TOO_CLOSE = True
    SKIP_IF_AFTER_REDUCE_STILL_UNSAFE = True


def test_position_size_basic():
    cfg = DummyCfg
    result = position_size_leverage(
        entry=100.0,
        stop=95.0,
        side="LONG",
        leverage=10,
        price=100.0,
        risk_usd=cfg.RISK_USD,
        lot_size=cfg.LOT_SIZE,
        min_notional=cfg.MIN_NOTIONAL,
        maint_margin_rate=cfg.MAINT_MARGIN_RATE,
        atr=2.0,
        cfg=cfg,
    )
    assert result["qty"] > 0
    assert result["liq"] < 95.0


def test_position_size_reduction():
    class TightCfg(DummyCfg):
        LIQ_BUFFER_PCT = 5.0
        LIQ_BUFFER_ATR_MULT = 1.0

    result = position_size_leverage(
        entry=100.0,
        stop=98.5,
        side="LONG",
        leverage=50,
        price=100.0,
        risk_usd=TightCfg.RISK_USD,
        lot_size=TightCfg.LOT_SIZE,
        min_notional=TightCfg.MIN_NOTIONAL,
        maint_margin_rate=TightCfg.MAINT_MARGIN_RATE,
        atr=1.0,
        cfg=TightCfg,
    )
    assert result["qty"] >= 0
    assert result["reduced"] or result["qty"] == 0
