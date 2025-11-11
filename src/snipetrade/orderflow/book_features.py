"""Order book derived features for execution planning."""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

Side = str


def _top_levels(levels: Iterable[Tuple[float, float]], depth: int) -> List[Tuple[float, float]]:
    return [lvl for i, lvl in enumerate(levels) if i < depth]


def book_imbalance(orderbook: Dict[str, Iterable[Tuple[float, float]]], depth: int = 10) -> float:
    """Return bid/ask volume imbalance in [-1, 1]."""

    bids = _top_levels(orderbook.get("bids", []), depth)
    asks = _top_levels(orderbook.get("asks", []), depth)

    bid_vol = sum(max(float(qty), 0.0) for _, qty in bids)
    ask_vol = sum(max(float(qty), 0.0) for _, qty in asks)
    total = bid_vol + ask_vol
    if total == 0:
        return 0.0
    return (bid_vol - ask_vol) / total


def best_spread_bps(orderbook: Dict[str, Iterable[Tuple[float, float]]]) -> float:
    """Return bid/ask spread in basis points."""

    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])
    if not bids or not asks:
        return float("inf")

    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    if best_ask <= 0 or best_bid <= 0 or best_ask <= best_bid:
        return 0.0 if best_ask == best_bid else float("inf")

    mid = (best_ask + best_bid) / 2.0
    if mid <= 0:
        return float("inf")
    return (best_ask - best_bid) / mid * 10_000


def queue_offset(bid: float, ask: float, ticksz: float, side: Side) -> float:
    """Return a price offset one tick inside the spread without crossing."""

    if ticksz <= 0:
        return 0.0
    spread = max(ask - bid, 0.0)
    if spread < ticksz:
        return 0.0

    # Keep one tick inside the spread, biased by side.
    offset_ticks = min(int(spread / ticksz) - 1, 1)
    if offset_ticks <= 0:
        return 0.0

    if side.upper() == "LONG":
        return offset_ticks * ticksz
    return -offset_ticks * ticksz
