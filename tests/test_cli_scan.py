from types import SimpleNamespace

from snipetrade.cli.scan import BatchScanContext, run_scan_cmd, scan_once


def _sample_cfg():
    return {
        "BATCH_LIMIT": 10,
        "BATCH_MIN_SCORE": 60,
        "BATCH_LEVERAGE": 5,
        "BATCH_RISK_USD": 50.0,
        "BATCH_OUTPUT_FORMATS": ["json"],
        "BATCH_OUTPUT_DIR": "out",
        "TELEGRAM_ENABLED": False,
    }


def test_scan_once_respects_limit_and_min_score(stub_exchange, stub_scorer):
    cfg = _sample_cfg()
    meta, results = scan_once(
        symbols=["BTC/USDT", "ETH/USDT"],
        timeframes=["15m", "1h"],
        cfg=cfg,
        limit=5,
        min_score=65,
        leverage=cfg["BATCH_LEVERAGE"],
        risk_usd=cfg["BATCH_RISK_USD"],
        exchange=stub_exchange,
        scorer=stub_scorer,
    )

    assert meta["stats"]["returned"] == len(results)
    assert len(results) <= 5
    assert all(result["score"] >= 65 for result in results)
    assert meta["filters"]["symbols"] == ["BTC/USDT", "ETH/USDT"]


def test_run_scan_cmd_writes_outputs(tmp_path, stub_exchange, stub_scorer, monkeypatch):
    args = SimpleNamespace(
        symbols="BTC/USDT,ETH/USDT",
        timeframes="15m",
        limit=3,
        min_score=60,
        leverage=5,
        risk_usd=40.0,
        telegram=0,
        formats="json",
        out=str(tmp_path),
    )

    monkeypatch.setattr("snipetrade.cli.scan._make_exchange", lambda cfg, override=None: stub_exchange)
    monkeypatch.setattr(
        "snipetrade.cli.scan._build_context",
        lambda cfg_dict, tfs, *, exchange=None, scorer=None: BatchScanContext(
            exchange=stub_exchange,
            scorer=scorer or stub_scorer,
        ),
    )

    result = run_scan_cmd(args, _sample_cfg())

    assert "meta" in result and "results" in result
    generated = list(tmp_path.iterdir())
    assert generated, "Expected JSON output file to be created"
    assert generated[0].suffix == ".json"
