from types import SimpleNamespace

import pytest

from snipetrade.cli.scan import scan_once
from snipetrade.outputs import telegram


class FakeBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, parse_mode="MarkdownV2"):
        self.messages.append(SimpleNamespace(chat_id=chat_id, text=text, parse_mode=parse_mode))


def _sample_cfg():
    return {
        "TELEGRAM_ENABLED": True,
        "TELEGRAM_BATCH_SUMMARY": True,
        "TELEGRAM_MAX_MSGS": 5,
        "TELEGRAM_RATE_MS": 0,
        "TELEGRAM_CHAT_ID": "chat123",
        "TELEGRAM_BOT_TOKEN": "token",
    }


@pytest.fixture
def sample_results(stub_exchange, stub_scorer):
    return scan_once(
        ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        ["15m"],
        _sample_cfg(),
        limit=3,
        min_score=60,
        leverage=5,
        risk_usd=40.0,
        exchange=stub_exchange,
        scorer=stub_scorer,
    )


def test_send_batch_respects_limits(sample_results, monkeypatch):
    meta, results = sample_results
    bot = FakeBot()

    monkeypatch.setattr(telegram.time, "sleep", lambda *_: None)

    sent = telegram.send_batch_top_setups(meta, results, _sample_cfg(), bot=bot)

    assert len(bot.messages) <= _sample_cfg()["TELEGRAM_MAX_MSGS"]
    assert sent
    assert any("Top Setups" in msg.text for msg in bot.messages)
    escaped_id = meta["scan_id"].replace("-", "\\-")
    assert any(escaped_id in msg.text for msg in bot.messages)
    assert all(msg.parse_mode == "MarkdownV2" for msg in bot.messages)


def test_send_setup_detail_chunks_long_messages(sample_results, monkeypatch):
    meta, results = sample_results
    setup = results[0]
    setup["reasons"] = ["reason" + str(i) for i in range(100)]

    bot = FakeBot()
    monkeypatch.setattr(telegram.time, "sleep", lambda *_: None)

    chunks = telegram.send_setup_detail(bot, "chat123", setup)

    assert chunks
    assert all(len(chunk) <= telegram.MAX_MESSAGE_LENGTH for chunk in chunks)
