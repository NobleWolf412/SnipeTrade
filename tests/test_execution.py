from snipetrade.planner.execution import decide_execution


class DummyCfg:
    ENTRY_TIMEOUT_SEC = 90


def test_execution_maker_fallback():
    near = {"type": "limit", "price": 100.0, "post_only": True, "reason": "test"}
    far = {"type": "limit", "price": 101.0, "post_only": True, "reason": "far"}
    plan = decide_execution(near, far, now_ts_ms=1_000, cfg=DummyCfg)
    assert plan["near_plan"]["valid_until_ms"] == 1_000 + 90 * 1000
    assert plan["fallback"]["type"] == "stop"
    assert plan["far_plan"]["type"] == "limit"


def test_execution_stop_no_fallback():
    near = {"type": "stop", "price": 102.0, "post_only": False}
    far = {"type": "limit", "price": 103.0, "post_only": True}
    plan = decide_execution(near, far, now_ts_ms=1_000, cfg=DummyCfg)
    assert plan["fallback"] is None
    assert "valid_until_ms" not in plan["far_plan"]
