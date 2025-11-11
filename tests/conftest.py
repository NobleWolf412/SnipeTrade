import sys
from pathlib import Path
from typing import List

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from snipetrade.cli.scan import BatchScanContext, _generate_synthetic_ohlcv  # noqa: E402
from snipetrade.models import TradeSetup  # noqa: E402


class StubExchange:
    exchange_id = "phemex"

    def __init__(self) -> None:
        symbols = [
            "BTC/USDT",
            "ETH/USDT",
            "SOL/USDT",
            "XRP/USDT",
            "ADA/USDT",
        ]
        self._markets = {symbol: {"symbol": symbol, "active": True} for symbol in symbols}

    def fetch_markets(self, *, force_refresh: bool = False):
        return self._markets

    def fetch_ohlcv(self, symbol: str, timeframe: str, *, limit: int = 100):
        return _generate_synthetic_ohlcv(symbol, timeframe, limit)

    def get_top_pairs(self, *, limit: int = 50, quote_currency: str = "USDT") -> List[str]:
        return list(self._markets.keys())[:limit]

    def get_current_price(self, symbol: str) -> float:
        candles = self.fetch_ohlcv(symbol, "15m", limit=1)
        return float(candles[-1][4])


class StubScorer:
    def __init__(self, timeframes):
        self.timeframes = list(timeframes)

    def score_setup(self, symbol, exchange, timeframe_data, current_price):
        direction = "LONG" if hash(symbol + next(iter(timeframe_data))) % 2 == 0 else "SHORT"
        base_price = float(current_price)
        if direction == "LONG":
            entry = base_price * 0.995
            stop = entry * 0.98
            take_profits = [entry * 1.02, entry * 1.04]
        else:
            entry = base_price * 1.005
            stop = entry * 1.02
            take_profits = [entry * 0.98, entry * 0.96]

        reasons = [f"{direction} bias detected"]
        timeframe_key = next(iter(timeframe_data.keys()))

        return TradeSetup(
            symbol=symbol,
            exchange=exchange,
            direction=direction,
            score=78.0,
            confidence=0.72,
            entry_plan=[entry],
            stop_loss=stop,
            take_profits=take_profits,
            rr=2.6,
            reasons=reasons,
            timeframe_confluence={tf: direction for tf in timeframe_data.keys()},
            indicator_summaries=[
                {
                    "name": "RSI",
                    "signal": direction,
                    "strength": 0.72,
                    "timeframe": timeframe_key,
                    "value": 55.0,
                }
            ],
            liquidation_zones=[
                {
                    "price_level": entry * (0.99 if direction == "LONG" else 1.01),
                    "liquidation_amount": 1_000_000.0,
                    "direction": direction,
                    "significance": 0.8,
                }
            ],
            metadata={
                "indicator_score": 70.0,
                "confluence_score": 65.0,
                "liquidation_score": 60.0,
                "trend_score": 68.0,
                "aligned_timeframes": len(timeframe_data),
                "signal_count": 6,
            },
        )


@pytest.fixture
def stub_exchange():
    return StubExchange()


@pytest.fixture
def stub_scorer():
    return StubScorer(["15m", "1h", "4h"])


@pytest.fixture
def stub_context(stub_exchange, stub_scorer):
    return BatchScanContext(exchange=stub_exchange, scorer=stub_scorer)
