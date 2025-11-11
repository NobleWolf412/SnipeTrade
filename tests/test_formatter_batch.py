import json

import pytest

from snipetrade.cli.scan import scan_once
from snipetrade.outputs import formatter


_DEF_CFG = {
    "BATCH_LIMIT": 10,
    "BATCH_MIN_SCORE": 60,
    "BATCH_LEVERAGE": 5,
    "BATCH_RISK_USD": 50.0,
    "TELEGRAM_ENABLED": False,
}


@pytest.fixture
def sample_scan(stub_exchange, stub_scorer):
    return scan_once(
        ["BTC/USDT", "ETH/USDT"],
        ["15m", "1h"],
        _DEF_CFG,
        limit=3,
        min_score=60,
        leverage=5,
        risk_usd=50.0,
        exchange=stub_exchange,
        scorer=stub_scorer,
    )


def test_formatters_create_files(tmp_path, sample_scan):
    meta, results = sample_scan
    produced = formatter.format_and_write(meta, results, tmp_path, ["json", "csv", "md"])
    assert set(produced.keys()) == {"json", "csv", "md"}

    json_path = produced["json"]
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "meta" in payload and "results" in payload
    assert payload["results"], "Expected results to be serialized"

    csv_content = produced["csv"].read_text(encoding="utf-8")
    assert "symbol" in csv_content.splitlines()[0]

    md_content = produced["md"].read_text(encoding="utf-8")
    assert "| # |" in md_content


def test_telegram_payloads_are_populated(sample_scan):
    meta, results = sample_scan
    summary = formatter.to_telegram_summary(results)
    assert "Top Setups" in summary

    detail = formatter.to_telegram_detail(results[0])
    assert "Reasons" in detail
    assert "None" not in detail
