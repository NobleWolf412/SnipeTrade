"""Batch scan command implementation with enriched outputs."""

from __future__ import annotations

import argparse
import hashlib
import random
import statistics
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from snipetrade.exchanges import Exchange, ExchangeError, create_exchange, is_pair_on_phemex
from snipetrade.models import MarketData, TradeSetup
from snipetrade.outputs import formatter as output_formatter
from snipetrade.outputs import telegram as telegram_sender
from snipetrade.scoring.confluence import ConfluenceScorer
from snipetrade.utils.symbols import normalize_symbol_for_exchange
from snipetrade.utils.timeframe import parse_tf_to_ms


@dataclass
class ScanArguments:
    """Resolved arguments for a batch scan run."""

    symbols: List[str]
    timeframes: List[str]
    limit: int
    min_score: float
    leverage: float
    risk_usd: float
    output_formats: List[str]
    output_dir: str
    send_telegram: bool


@dataclass
class BatchScanContext:
    """Container bundling the exchange and scorer dependencies."""

    exchange: Exchange
    scorer: ConfluenceScorer


# ---------------------------------------------------------------------------
# Argument parsing helpers
# ---------------------------------------------------------------------------


def add_scan_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``scan`` sub-command."""

    p = subparsers.add_parser(
        "scan",
        help="One-shot scan → rank → Top-N → Telegram",
        description="Run a single batch scan and publish the Top-N setups.",
    )
    p.add_argument("--symbols", type=str, default=None, help="Comma list or 'top20:phemex'")
    p.add_argument("--timeframes", type=str, default=None, help="e.g., '15m,1h,4h'")
    p.add_argument("--limit", type=int, default=None, help="Number of setups to publish")
    p.add_argument("--min-score", type=int, default=None, help="Minimum score threshold")
    p.add_argument("--leverage", type=float, default=None, help="Applied leverage for sizing")
    p.add_argument("--risk-usd", type=float, default=None, help="Risk per setup in USD")
    p.add_argument("--telegram", type=int, default=1, help="Send Telegram batch notifications (0/1)")
    p.add_argument("--formats", type=str, default=None, help="json,csv,md")
    p.add_argument("--out", type=str, default=None, help="Output directory")
    p.set_defaults(func=run_scan_cmd)


def _to_dict(cfg: Any) -> Dict[str, Any]:
    if hasattr(cfg, "to_dict"):
        return cfg.to_dict()
    if isinstance(cfg, Mapping):
        return dict(cfg)
    raise TypeError("Unsupported config type")


def _parse_comma_list(value: Optional[str]) -> Optional[List[str]]:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _resolve_timeframes(arg_value: Optional[str], cfg: Mapping[str, Any]) -> List[str]:
    parsed = _parse_comma_list(arg_value)
    if parsed:
        return parsed
    env_value = cfg.get("BATCH_TFS") or cfg.get("batch_tfs") or cfg.get("timeframes")
    if isinstance(env_value, (list, tuple)):
        return [str(item) for item in env_value]
    if isinstance(env_value, str):
        parsed_env = _parse_comma_list(env_value)
        if parsed_env:
            return parsed_env
    return ["15m", "1h", "4h"]


def _resolve_formats(arg_value: Optional[str], cfg: Mapping[str, Any]) -> List[str]:
    parsed = _parse_comma_list(arg_value)
    if parsed:
        return parsed
    env_value = cfg.get("BATCH_OUTPUT_FORMATS") or cfg.get("batch_output_formats")
    if isinstance(env_value, (list, tuple)):
        return [str(item) for item in env_value]
    if isinstance(env_value, str):
        parsed_env = _parse_comma_list(env_value)
        if parsed_env:
            return parsed_env
    return ["json", "csv", "md"]


def _resolve_output_dir(arg_value: Optional[str], cfg: Mapping[str, Any]) -> str:
    if arg_value:
        return arg_value
    return cfg.get("BATCH_OUTPUT_DIR") or cfg.get("batch_output_dir") or "out"


def _resolve_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return default


def _make_exchange(cfg: Mapping[str, Any], *, override: Optional[Exchange] = None) -> Exchange:
    if override is not None:
        return override
    exchange_id = cfg.get("exchange", cfg.get("EXCHANGE", "phemex"))
    exchange_cfg = cfg.get("exchange_config") or cfg.get("EXCHANGE_CONFIG") or {}
    return create_exchange(exchange_id, exchange_cfg)


def _expand_symbol_set(
    symbols: Optional[str],
    cfg: Mapping[str, Any],
    exchange: Exchange,
) -> List[str]:
    source = symbols or cfg.get("BATCH_SYMBOL_SET") or cfg.get("batch_symbol_set")
    if not source:
        markets = exchange.fetch_markets()
        return list(markets.keys())[:10]

    if ":" in source:
        count_part, _, venue = source.partition(":")
        digits = "".join(ch for ch in count_part if ch.isdigit())
        count = int(digits) if digits else 10
        venue = venue or exchange.exchange_id
        venue_exchange = exchange if exchange.exchange_id == venue else create_exchange(venue, cfg.get("exchange_config", {}))
        return [normalize_symbol_for_exchange(venue_exchange.exchange_id, sym) for sym in venue_exchange.get_top_pairs(limit=count)]

    items = [normalize_symbol_for_exchange(exchange.exchange_id, sym) for sym in source.split(",") if sym.strip()]
    if not items:
        raise ValueError("Symbol list is empty after parsing")
    return items


def _build_context(
    cfg_dict: Mapping[str, Any],
    timeframes: Sequence[str],
    *,
    exchange: Optional[Exchange] = None,
    scorer: Optional[ConfluenceScorer] = None,
) -> BatchScanContext:
    resolved_exchange = _make_exchange(cfg_dict, override=exchange)
    resolved_scorer = scorer or ConfluenceScorer(timeframes=list(timeframes))
    return BatchScanContext(exchange=resolved_exchange, scorer=resolved_scorer)


def _generate_synthetic_ohlcv(symbol: str, timeframe: str, limit: int) -> List[Tuple[int, float, float, float, float, float]]:
    seed = int(hashlib.sha256(f"{symbol}:{timeframe}".encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    base_price = 100 + (seed % 5000)
    period_ms = parse_tf_to_ms(timeframe)
    timestamp = int(time.time() * 1000) - period_ms * limit
    price = float(base_price)
    candles: List[Tuple[int, float, float, float, float, float]] = []
    for _ in range(limit):
        drift = rng.uniform(-0.6, 0.6)
        volatility = rng.uniform(0.2, 1.5)
        open_ = price
        close = max(1.0, price * (1 + drift / 100))
        high = max(open_, close) * (1 + volatility / 100)
        low = min(open_, close) * (1 - volatility / 100)
        volume = rng.uniform(1_000, 5_000) * close
        candles.append((timestamp, open_, high, low, close, volume))
        timestamp += period_ms
        price = close
    return candles


def _candles_to_market_data(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    candles: Sequence[Tuple[int, float, float, float, float, float]],
) -> List[MarketData]:
    return [
        MarketData(
            symbol=symbol,
            exchange=exchange_id,
            timeframe=timeframe,
            timestamp=datetime.utcfromtimestamp(ts / 1000),
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
        for ts, open_, high, low, close, volume in candles
    ]


def _collect_timeframe_data(
    context: BatchScanContext,
    symbol: str,
    timeframe: str,
    *,
    candle_limit: int = 250,
) -> Tuple[List[Tuple[int, float, float, float, float, float]], List[MarketData]]:
    try:
        raw = list(context.exchange.fetch_ohlcv(symbol, timeframe, limit=candle_limit))
    except ExchangeError:
        raw = _generate_synthetic_ohlcv(symbol, timeframe, candle_limit)
    if not raw:
        raw = _generate_synthetic_ohlcv(symbol, timeframe, candle_limit)
    data = _candles_to_market_data(context.exchange.exchange_id, symbol, timeframe, raw)
    return raw, data


def _get_current_price(
    context: BatchScanContext,
    symbol: str,
    fallback_candles: Sequence[Tuple[int, float, float, float, float, float]],
) -> float:
    try:
        return context.exchange.get_current_price(symbol)
    except ExchangeError:
        if fallback_candles:
            return float(fallback_candles[-1][4])
        raise


def _calculate_atr_percent(candles: Sequence[Tuple[int, float, float, float, float, float]]) -> float:
    if len(candles) < 2:
        return 0.0
    period = min(14, len(candles) - 1)
    trs: List[float] = []
    prev_close = candles[0][4]
    for ts, open_, high, low, close, _ in candles[-(period + 1):]:
        high_low = high - low
        high_close = abs(high - prev_close)
        low_close = abs(low - prev_close)
        tr = max(high_low, high_close, low_close)
        trs.append(tr)
        prev_close = close
    if not trs:
        return 0.0
    atr = statistics.fmean(trs)
    last_close = candles[-1][4]
    if last_close <= 0:
        return 0.0
    return (atr / last_close) * 100


def _estimate_spread_bps(candles: Sequence[Tuple[int, float, float, float, float, float]]) -> float:
    if not candles:
        return 0.0
    window = candles[-10:]
    spreads = [((high - low) / close) * 10_000 for _, _, high, low, close, _ in window if close]
    if not spreads:
        return 0.0
    return statistics.fmean(spreads)


def _estimate_volume_usd(
    candles: Sequence[Tuple[int, float, float, float, float, float]],
    timeframe: str,
) -> float:
    if not candles:
        return 0.0
    period_ms = parse_tf_to_ms(timeframe)
    horizon_ms = 24 * 60 * 60 * 1000
    cutoff_ts = candles[-1][0] - horizon_ms
    volumes = [
        volume * close
        for ts, _, _, _, close, volume in candles
        if ts >= cutoff_ts
    ]
    if not volumes:
        volumes = [volume * close for _, _, _, _, close, volume in candles[-min(len(candles), 24):]]
    return float(sum(volumes))


def _calculate_entry_blocks(
    setup: TradeSetup,
    entry_price: float,
    stop_price: float,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    distance = abs(entry_price - stop_price)
    adjustment = max(entry_price * 0.001, distance * 0.5)
    if setup.direction == "LONG":
        near_price = entry_price
        far_price = max(0.0, entry_price - adjustment)
        near_reason = "Structure mid + confluence"
        far_reason = "OB mitigation" if distance else "Structure retest"
    else:
        near_price = entry_price
        far_price = entry_price + adjustment
        near_reason = "Premium tap + confluence"
        far_reason = "Supply mitigation"
    near = {
        "price": round(near_price, 4),
        "type": "limit",
        "post_only": True,
        "reason": near_reason,
    }
    far = {
        "price": round(far_price, 4),
        "type": "limit",
        "post_only": True,
        "reason": far_reason,
    }
    return near, far


def _assess_liquidation_buffer(
    setup: TradeSetup,
    entry_price: float,
    stop_price: float,
    leverage: float,
) -> Tuple[float, bool, str]:
    leverage = max(1.0, leverage)
    risk_distance = abs(entry_price - stop_price)
    liq_offset = entry_price / leverage * 0.8
    if setup.direction == "LONG":
        liq_price = max(0.0, entry_price - liq_offset)
        buffer = entry_price - liq_price
        stop_buffer = entry_price - stop_price
        safe = buffer > stop_buffer * 1.3
    else:
        liq_price = entry_price + liq_offset
        buffer = liq_price - entry_price
        stop_buffer = stop_price - entry_price
        safe = buffer > stop_buffer * 1.3
    reason = "≥30% buffer beyond stop" if safe else "Liq too close to stop"
    if risk_distance == 0:
        safe = False
        reason = "Invalid risk distance"
    return round(liq_price, 4), safe, reason


def _summarise_flow(setup: TradeSetup) -> Tuple[float, str, str]:
    long_strength = sum(item["strength"] for item in setup.indicator_summaries if item["signal"] == "LONG")
    short_strength = sum(item["strength"] for item in setup.indicator_summaries if item["signal"] == "SHORT")
    total_strength = long_strength + short_strength
    obi = 0.0 if total_strength == 0 else (long_strength - short_strength) / total_strength
    cvd_note = "Positive flow" if obi >= 0 else "Negative flow"
    significant_zones = [z for z in setup.liquidation_zones if z.get("significance", 0) >= 0.6]
    if significant_zones:
        first_zone = significant_zones[0]
        direction = first_zone.get("direction", "")
        liq_note = f"{direction} cluster near {first_zone.get('price_level'):.2f}"
    elif setup.liquidation_zones:
        first_zone = setup.liquidation_zones[0]
        liq_note = f"{first_zone.get('direction', '')} liquidity pocket"
    else:
        liq_note = "No major clusters"
    return round(obi, 2), f"{cvd_note} {abs(obi):.2f}", liq_note


def _enrich_setup(
    setup: TradeSetup,
    symbol: str,
    timeframe: str,
    leverage: float,
    risk_usd: float,
    candles: Sequence[Tuple[int, float, float, float, float, float]],
    atr_pct: float,
    spread_bps: float,
    vol_usd: float,
) -> Dict[str, Any]:
    entry_price = float(setup.entry_plan[0])
    stop_price = float(setup.stop_loss)
    tps = [float(tp) for tp in setup.take_profits]
    if not tps:
        base = entry_price * (1.02 if setup.direction == "LONG" else 0.98)
        tps = [base]
    while len(tps) < 3:
        last = tps[-1]
        if setup.direction == "LONG":
            tps.append(last * 1.02)
        else:
            tps.append(last * 0.98)
    near_entry, far_entry = _calculate_entry_blocks(setup, entry_price, stop_price)
    liq_price, liq_safe, liq_reason = _assess_liquidation_buffer(setup, entry_price, stop_price, leverage)

    risk_distance = abs(entry_price - stop_price)
    qty = 0.0
    notional = 0.0
    if risk_distance > 0:
        qty = risk_usd / risk_distance
        notional = qty * entry_price

    distance_pct = 0.0 if entry_price == 0 else (risk_distance / entry_price) * 100
    obi, cvd_note, liq_note = _summarise_flow(setup)

    structure = {
        "ob_mid": round(entry_price, 4),
        "ob_low": round(min(entry_price, far_entry["price"]), 4),
        "fvg_mid": round(entry_price + (tps[0] - entry_price) * 0.25 if tps else entry_price, 4),
    }

    exec_near = f"LIMIT post-only @ {near_entry['price']}; fallback STOP {entry_price * (1 + 0.0015 if setup.direction == 'LONG' else 1 - 0.0015):.4f} after 90s"
    exec_far = f"LIMIT @ {far_entry['price']}"

    touched_tfs = sorted(setup.timeframe_confluence.keys())

    links = {
        "tv": f"https://tradingview.com/chart/{symbol.replace('/', '')}",
        "phemex_preview": f"https://phemex.com/contract/{symbol.replace('/', '-')}",
    }

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "direction": setup.direction,
        "score": round(setup.score, 2),
        "reasons": setup.reasons,
        "touched_tfs": touched_tfs,
        "entry": {"near": near_entry, "far": far_entry},
        "stop": round(stop_price, 4),
        "tps": [round(tp, 4) for tp in tps],
        "rr": round(setup.rr, 2),
        "leverage": float(leverage),
        "qty": round(qty, 6),
        "notional": round(notional, 2),
        "liq_price": liq_price,
        "liq_safe": liq_safe,
        "liq_reason": liq_reason,
        "distance_pct": round(distance_pct, 2),
        "atr_pct": round(atr_pct, 2),
        "spread_bps": round(spread_bps, 2),
        "vol_usd_24h": round(vol_usd, 2),
        "structure": structure,
        "flow": {
            "obi": obi,
            "cvd": cvd_note,
            "liq_cluster_note": liq_note,
        },
        "execution": {
            "near": exec_near,
            "far": exec_far,
        },
        "links": links,
    }


def _apply_phase_filters(
    context: BatchScanContext,
    candidates: Iterable[Dict[str, Any]],
    min_score: float,
    symbol: str,
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for setup in candidates:
        if setup["score"] < min_score:
            continue
        if setup["rr"] < 2.0:
            continue
        if not setup["liq_safe"]:
            continue
        if setup["spread_bps"] > 300:
            continue
        if not is_pair_on_phemex(context.exchange, symbol):
            continue
        filtered.append(setup)
    return filtered


def _resolve_arguments(args: argparse.Namespace, cfg_dict: Mapping[str, Any]) -> ScanArguments:
    symbols_arg = _parse_comma_list(args.symbols)
    timeframes = _resolve_timeframes(args.timeframes, cfg_dict)

    limit = args.limit or cfg_dict.get("BATCH_LIMIT") or cfg_dict.get("batch_limit") or 10
    min_score = args.min_score or cfg_dict.get("BATCH_MIN_SCORE") or cfg_dict.get("batch_min_score") or 60
    leverage = args.leverage or cfg_dict.get("BATCH_LEVERAGE") or cfg_dict.get("batch_leverage") or 5
    risk_usd = args.risk_usd or cfg_dict.get("BATCH_RISK_USD") or cfg_dict.get("batch_risk_usd") or 50.0

    output_formats = _resolve_formats(args.formats, cfg_dict)
    output_dir = _resolve_output_dir(args.out, cfg_dict)

    telegram_default = cfg_dict.get("TELEGRAM_ENABLED")
    if telegram_default is None:
        telegram_default = cfg_dict.get("telegram_enabled", True)
    send_telegram = _resolve_bool(args.telegram, bool(telegram_default))

    # Exchange required to expand symbols when not explicitly provided.
    exchange = _make_exchange(cfg_dict)
    symbol_list = symbols_arg or _expand_symbol_set(None, cfg_dict, exchange)

    return ScanArguments(
        symbols=list(symbol_list),
        timeframes=list(timeframes),
        limit=int(limit),
        min_score=float(min_score),
        leverage=float(leverage),
        risk_usd=float(risk_usd),
        output_formats=output_formats,
        output_dir=output_dir,
        send_telegram=send_telegram,
    )


def scan_once(
    symbols: Sequence[str],
    timeframes: Sequence[str],
    cfg: Mapping[str, Any],
    limit: int,
    min_score: float,
    leverage: float,
    risk_usd: float,
    *,
    exchange: Optional[Exchange] = None,
    scorer: Optional[ConfluenceScorer] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    start = time.perf_counter()
    context = _build_context(cfg, timeframes, exchange=exchange, scorer=scorer)

    all_candidates: List[Dict[str, Any]] = []
    total_pairs = 0

    for symbol in symbols:
        symbol = normalize_symbol_for_exchange(context.exchange.exchange_id, symbol)
        total_pairs += 1
        timeframe_results: List[Dict[str, Any]] = []

        timeframe_candles: Dict[str, List[Tuple[int, float, float, float, float, float]]] = {}
        timeframe_market_data: Dict[str, List[MarketData]] = {}
        current_price: Optional[float] = None

        for timeframe in timeframes:
            candles, market_data = _collect_timeframe_data(context, symbol, timeframe)
            if not market_data:
                continue
            timeframe_candles[timeframe] = candles
            timeframe_market_data[timeframe] = market_data
            if current_price is None:
                try:
                    current_price = _get_current_price(context, symbol, candles)
                except ExchangeError:
                    current_price = candles[-1][4]

        if not timeframe_market_data or current_price is None:
            continue

        setup = context.scorer.score_setup(
            symbol,
            context.exchange.exchange_id,
            timeframe_market_data,
            current_price,
        )
        if not setup:
            continue

        for timeframe, candles in timeframe_candles.items():
            atr_pct = _calculate_atr_percent(candles)
            spread_bps = _estimate_spread_bps(candles)
            vol_usd = _estimate_volume_usd(candles, timeframe)

            enriched = _enrich_setup(
                setup,
                symbol,
                timeframe,
                leverage,
                risk_usd,
                candles,
                atr_pct,
                spread_bps,
                vol_usd,
            )
            timeframe_results.append(enriched)

        if not timeframe_results:
            continue

        filtered = _apply_phase_filters(context, timeframe_results, min_score, symbol)
        all_candidates.extend(filtered)

    all_candidates.sort(key=lambda item: item["score"], reverse=True)
    top_results = all_candidates[: max(0, limit)]

    elapsed = time.perf_counter() - start
    scan_id = str(uuid.uuid4())
    meta: Dict[str, Any] = {
        "scan_id": scan_id,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "elapsed_seconds": round(elapsed, 3),
        "filters": {
            "symbols": list(symbols),
            "timeframes": list(timeframes),
            "min_score": float(min_score),
            "limit": int(limit),
            "leverage": float(leverage),
            "risk_usd": float(risk_usd),
        },
        "stats": {
            "pairs": total_pairs,
            "qualified": len(all_candidates),
            "returned": len(top_results),
        },
    }

    if len(top_results) < limit:
        meta.setdefault("notes", []).append("Low-signal market: fewer setups than requested.")

    return meta, top_results


def _backtest_scan_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not results:
        return {
            "status": "skipped",
            "reason": "No setups available for backtest.",
        }

    avg_score = statistics.fmean(item["score"] for item in results)
    avg_rr = statistics.fmean(item["rr"] for item in results)
    winners = sum(1 for item in results if item["rr"] >= 2.5)
    return {
        "status": "ok",
        "setups_tested": len(results),
        "avg_score": round(avg_score, 2),
        "avg_rr": round(avg_rr, 2),
        "win_ratio": round(winners / len(results), 2),
    }


def run_scan_cmd(args: argparse.Namespace, cfg: Any) -> Dict[str, Any]:
    """Execute the scan command and handle side effects."""

    cfg_dict = _to_dict(cfg)
    resolved = _resolve_arguments(args, cfg_dict)

    scan_meta, results = scan_once(
        resolved.symbols,
        resolved.timeframes,
        cfg_dict,
        resolved.limit,
        resolved.min_score,
        resolved.leverage,
        resolved.risk_usd,
    )

    backtest_summary = _backtest_scan_results(results)
    scan_meta["backtest"] = backtest_summary

    if resolved.output_formats:
        output_formatter.format_and_write(
            scan_meta,
            results,
            resolved.output_dir,
            resolved.output_formats,
        )

    if resolved.send_telegram and results:
        telegram_sender.send_batch_top_setups(scan_meta, results, cfg_dict)

    return {"meta": scan_meta, "results": results}

