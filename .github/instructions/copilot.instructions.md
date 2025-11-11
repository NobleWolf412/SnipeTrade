# SnipeTrade — Copilot Instructions (Global)

Act as a senior trading-systems engineer. Optimize for **correctness**, **modularity**, and **performance**. Favor clarity over cleverness.

## Operating Principles
- **Architecture:** Keep code layered as `data/`, `indicators/`, `structure/`, `signals/`, `quality/`, `scoring/`, `alerts/`, `core/`.
- **Trading fundamentals:** Structure → confluence → liquidity → risk/reward → regime awareness. Penalize stale setups.
- **Modularity:** One module = one responsibility, with clean, typed interfaces.
- **Reuse first:** Extend existing helpers instead of duplicating logic.

## Python Rules
- Python 3.x, **type hints everywhere**, docstrings on public functions, absolute imports from the `snipe/` package.
- Use `pathlib.Path`, `logging` (no prints), and explicit exceptions (no silent excepts).
- Pure functions when possible; avoid hidden globals.

## Async & Realtime
- WebSockets use `async with`, timeouts, exponential backoff, and `finally: close()`.
- Use `asyncio.gather(..., return_exceptions=True)` for concurrency.
- Never block the event loop with heavy CPU work—batch or offload.

## Data & Indicators
- Inputs: timezone-aware, monotonic OHLCV DataFrames.
- Outputs: deterministic Series/DataFrames; avoid unnecessary copies.
- Provide RSI/MACD/ATR/VWAP/StochRSI/Bollinger via `snipe/indicators/`.
- Cache indicators (fast TF TTL ≈ 60s, slow TF TTL ≈ 300s).

## Market Structure & Signals
- Detect BOS/CHoCH, order blocks, FVGs, sweeps in `snipe/structure/`.
- Build candidate setups in `snipe/signals/` (SCALP/SWING).
- Apply regime filters, volume/liquidity gates, ATR distance, min RR≥2:1 in `snipe/quality/`.
- Score in `snipe/scoring/` with explainable reasons.

## Alerts & Outputs
- `snipe/alerts/` formats JSON + Telegram messages (no credentials in code).
- Preserve stable JSON schema; include entry/SL/TP and reasoning.

## Testing Discipline
- Pytest for unit/integration; **no live exchange calls in CI** (mock IO).
- Deterministic tests (fixed seeds/fixtures). Keep a quick `tests/smoke_test.py`.
- When refactoring, keep behavior parity or add tests that prove the change.

## Performance Targets
- 100+ symbols × multi-TF in ~2 minutes.
- Batch API calls, cache indicators, vectorize Pandas ops, profile before “optimizing.”

## Code Style (enforced mindset)
- Small, intention-revealing functions.
- Early returns over nested conditionals.
- Clear names: `risk_to_reward`, `structure_break`, not `rr`, `sb`.
- One concern per PR; update docs/tests alongside code.

## Guardrails
- Respect existing CLI flags and JSON outputs.
- Never hardcode secrets; read from env/config.
- Don’t duplicate utilities—search `snipe/` first.

**North Star:** Fewer, higher-quality trades with full auditability. Write code future-you can trust at 3 a.m.
