"""Formatting helpers for batch scan outputs."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

OUTPUT_SUFFIX = "%Y%m%dT%H%M%S"


def _ensure_dir(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)


def _generate_filename(prefix: str, scan_meta: Dict[str, Any], extension: str) -> str:
    timestamp = datetime.utcnow().strftime(OUTPUT_SUFFIX)
    scan_id = scan_meta.get("scan_id", "scan")
    return f"{prefix}_{scan_id}_{timestamp}.{extension}"


def _flatten_setup(setup: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {
        "symbol": setup["symbol"],
        "timeframe": setup["timeframe"],
        "direction": setup["direction"],
        "score": setup["score"],
        "rr": setup.get("rr"),
        "leverage": setup.get("leverage"),
        "qty": setup.get("qty"),
        "notional": setup.get("notional"),
        "liq_price": setup.get("liq_price"),
        "liq_safe": setup.get("liq_safe"),
        "distance_pct": setup.get("distance_pct"),
        "atr_pct": setup.get("atr_pct"),
        "spread_bps": setup.get("spread_bps"),
        "vol_usd_24h": setup.get("vol_usd_24h"),
    }

    entry = setup.get("entry", {})
    near = entry.get("near", {})
    far = entry.get("far", {})
    tps = list(setup.get("tps") or [])
    while len(tps) < 3:
        tps.append(None)

    flat.update(
        {
            "entry_near_price": near.get("price"),
            "entry_far_price": far.get("price"),
            "stop": setup.get("stop"),
            "tp1": tps[0],
            "tp2": tps[1],
            "tp3": tps[2],
            "reasons": "; ".join(setup.get("reasons", [])),
        }
    )

    return flat


def to_json(scan_meta: Dict[str, Any], results: List[Dict[str, Any]], directory: Path) -> Path:
    _ensure_dir(directory)
    filename = _generate_filename("scan", scan_meta, "json")
    path = directory / filename
    payload = {"meta": scan_meta, "results": results}
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return path


def to_csv(results: List[Dict[str, Any]], directory: Path, scan_meta: Dict[str, Any]) -> Path:
    _ensure_dir(directory)
    filename = _generate_filename("scan", scan_meta, "csv")
    path = directory / filename
    rows = [_flatten_setup(item) for item in results]
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def to_md(results: List[Dict[str, Any]], directory: Path, scan_meta: Dict[str, Any]) -> Path:
    _ensure_dir(directory)
    filename = _generate_filename("scan", scan_meta, "md")
    path = directory / filename
    header = "| # | Symbol | TF | Dir | Score | RR | Liq Safe | TP1 | TP2 | TP3 |\n"
    separator = "|---|---|---|---|---|---|---|---|---|---|\n"
    lines = [header, separator]
    for idx, setup in enumerate(results, 1):
        tps = list(setup.get("tps") or [])
        while len(tps) < 3:
            tps.append(None)
        line = (
            f"| {idx} | {setup['symbol']} | {setup['timeframe']} | {setup['direction']} | "
            f"{setup['score']} | {setup.get('rr', '')} | {'✅' if setup.get('liq_safe') else '⚠️'} | "
            f"{tps[0]} | {tps[1]} | {tps[2]} |\n"
        )
        lines.append(line)
    with path.open("w", encoding="utf-8") as fh:
        fh.writelines(lines)
    return path


def _escape_markdown(value: str) -> str:
    return re.sub(r"([_\*\[\]()~`>#+\-=|{}.!])", r"\\\1", value)


def to_telegram_summary(results: List[Dict[str, Any]]) -> str:
    if not results:
        return "No qualifying setups found."
    lines = ["📡 Top Setups", ""]
    for idx, setup in enumerate(results, 1):
        direction_emoji = "🟢" if setup.get("direction") == "LONG" else "🔴"
        content = (
            f"{idx}. {direction_emoji} {setup['symbol']} {setup['timeframe']}"
            f" — score {setup['score']:.1f}"
        )
        lines.append(content)
    return "\n".join(lines)


def _format_price(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return str(value)


def to_telegram_detail(setup: Dict[str, Any]) -> str:
    near = setup.get("entry", {}).get("near", {})
    far = setup.get("entry", {}).get("far", {})
    tp_values = setup.get("tps", [None, None, None])
    reasons = setup.get("reasons", [])
    structure = setup.get("structure", {})
    flow = setup.get("flow", {})

    near_post = " post-only" if near.get("post_only") else ""
    far_post = " post-only" if far.get("post_only") else ""

    lines = [
        f"{setup['symbol']} {setup['direction']} ({setup['timeframe']}) — Score {setup['score']:.1f}",
        (
            "Entry: "
            f"{_format_price(near.get('price'))} {near.get('type', '').upper()}{near_post}"
            " | Far: "
            f"{_format_price(far.get('price'))} {far.get('type', '').upper()}{far_post}"
        ),
        (
            f"SL: {_format_price(setup.get('stop'))} | TP1: {_format_price(tp_values[0])} "
            f"| RR: {setup.get('rr', 0):.2f}"
        ),
        (
            f"Leverage: {setup.get('leverage')}× | Qty: {setup.get('qty')} | "
            f"Notional: ${_format_price(setup.get('notional'))}"
        ),
        (
            f"Liq: {_format_price(setup.get('liq_price'))}  "
            f"{'✅ Safe' if setup.get('liq_safe') else '⚠️ Risk'}  "
            f"({setup.get('liq_reason')})"
        ),
        (
            f"Distance: {setup.get('distance_pct'):.2f}% | ATR: {setup.get('atr_pct'):.2f}% "
            f"| Spread: {setup.get('spread_bps'):.1f} bps"
        ),
        f"Vol24h: ${_format_price(setup.get('vol_usd_24h'))}",
        (
            "Structure: "
            f"OBmid {_format_price(structure.get('ob_mid'))} / "
            f"OBlow {_format_price(structure.get('ob_low'))} | "
            f"FVGmid {_format_price(structure.get('fvg_mid'))}"
        ),
        (
            "Flow: "
            f"OBI {flow.get('obi', 0):.2f} | "
            f"CVD {flow.get('cvd')} | "
            f"{flow.get('liq_cluster_note')}"
        ),
        "Reasons: " + "; ".join(reasons),
        (
            "Exec: "
            f"{setup.get('execution', {}).get('near')} | Far: "
            f"{setup.get('execution', {}).get('far')}"
        ),
        f"TV: {setup.get('links', {}).get('tv')}",
        f"Phemex: {setup.get('links', {}).get('phemex_preview')}",
    ]

    escaped_lines = [_escape_markdown(str(line)) for line in lines]
    return "\n".join(escaped_lines)


def _format_reasons(reasons: List[str]) -> str:
    filtered = [r for r in reasons if r]
    return " | ".join(filtered[:5]) if filtered else "n/a"


def format_telegram_alert(payload: Dict) -> str:
    """Return a compact Telegram alert string."""

    symbol = payload.get("symbol", "UNKNOWN")
    timeframe = payload.get("timeframe", "?")
    direction = payload.get("direction", "?")
    score = payload.get("score", 0)

    entry_near = payload.get("entry_near")
    entry_far = payload.get("entry_far")
    stop = payload.get("stop")
    tp1 = payload.get("tp1")

    leverage = payload.get("leverage")
    qty = payload.get("qty")
    liq = payload.get("liq")
    liq_buffer = payload.get("liq_buffer")

    exec_hint = payload.get("execution", {})

    parts = [
        f"{symbol} {timeframe} {direction}",
        f"Score {score}",
        f"Entry N/F: {entry_near} / {entry_far}",
        f"SL {stop} | TP1 {tp1}",
        f"Lev {leverage}x | Qty {qty} | Liq {liq} ({liq_buffer})",
        f"RR {payload.get('rr')} | Dist {payload.get('distance_pct')}%",
        f"Spread {payload.get('spread_bps')}bps | Vol {payload.get('volume_usd_24h')}",
    ]

    reasons = _format_reasons(payload.get("reasons", []))
    parts.append(f"Reasons: {reasons}")

    if exec_hint:
        near = exec_hint.get("near_plan")
        fallback = exec_hint.get("fallback")
        plan_msg = []
        if near:
            mode = "LIMIT" if near.get("type") == "limit" else "STOP"
            post = " post-only" if near.get("post_only") else ""
            plan_msg.append(f"near: {mode}{post} @{near.get('price')}")
        if fallback:
            plan_msg.append(f"fallback → {fallback.get('type').upper()} @{fallback.get('price')} ({fallback.get('reason')})")
        far = exec_hint.get("far_plan")
        if far:
            mode = "LIMIT" if far.get("type") == "limit" else "STOP"
            plan_msg.append(f"far: {mode} @{far.get('price')}")
        if plan_msg:
            parts.append("Execution: " + "; ".join(plan_msg))

    links = payload.get("links", [])
    if links:
        parts.append("Links: " + " | ".join(links))

    return "\n".join(parts)


def format_and_write(
    scan_meta: Dict[str, Any],
    results: List[Dict[str, Any]],
    output_dir: str,
    formats: Iterable[str],
) -> Dict[str, Path]:
    directory = Path(output_dir)
    _ensure_dir(directory)
    produced: Dict[str, Path] = {}
    normalized_formats = {fmt.lower() for fmt in formats}
    if "json" in normalized_formats:
        produced["json"] = to_json(scan_meta, results, directory)
    if "csv" in normalized_formats:
        produced["csv"] = to_csv(results, directory, scan_meta)
    if "md" in normalized_formats:
        produced["md"] = to_md(results, directory, scan_meta)
    return produced
