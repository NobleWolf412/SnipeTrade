"""Implementation of the quality gates described in QUALITY_GATES_DESIGN."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from snipetrade.models import TradeDirection


DEFAULT_WEIGHTS: Dict[str, int] = {
    "tf_align": 25,
    "ob_quality": 15,
    "fvg_presence": 10,
    "bos_choch": 15,
    "freshness": 10,
    "rr_strength": 10,
    "atr_sweetspot": 10,
    "regime_bias": 5,
}


@dataclass(frozen=True)
class QualityGatesConfig:
    """Runtime configuration for the quality gates."""

    min_rr: float = 2.0
    entry_distance_pct: Tuple[float, float] = (0.5, 5.0)
    freshness_half_life_min: float = 30.0
    max_setup_age_min: float = 90.0
    min_volume_usd: float = 100_000.0
    max_spread_bps: float = 20.0
    min_confluence: int = 3
    min_score: float = 60.0
    max_setups: int = 5
    confluence_weights: Dict[str, int] = field(default_factory=lambda: DEFAULT_WEIGHTS.copy())


@dataclass
class SetupCandidate:
    """Normalized candidate structure consumed by the quality gates."""

    symbol: str
    timeframe: str
    direction: TradeDirection
    price_current: float
    orderbook_bid: float
    orderbook_ask: float
    volume_usd_24h: float
    atr_pct: float
    minutes_old: float
    entry_near: float
    entry_stop: float
    entry_tp1: float
    structure_flags: Dict[str, bool]
    phemex_listed: bool
    regime: str
    touched_tfs: Iterable[str] = field(default_factory=list)
    ob_quality: Optional[float] = None
    metadata: Dict[str, float] = field(default_factory=dict)

    def confluence_count(self) -> int:
        """Return the number of True structure flags."""

        return sum(1 for value in self.structure_flags.values() if value)


@dataclass
class GateDecision:
    """Outcome from the quality gates for an approved setup."""

    candidate: SetupCandidate
    rr: float
    entry_distance_pct: float
    spread_bps: float
    freshness_weight: float
    confluence: int
    score: float
    reasons: List[str]
    touched_tfs: List[str]


class QualityGates:
    """Evaluate trade setup candidates against hard and soft gates."""

    def __init__(self, config: Optional[QualityGatesConfig] = None, exchange: Optional[str] = None):
        self.config = config or QualityGatesConfig()
        self.exchange = exchange

    # ------------------------------------------------------------------
    # Hard gate helpers
    # ------------------------------------------------------------------
    def compute_rr(self, entry: float, stop: float, tp1: float, direction: TradeDirection) -> float:
        """Calculate risk-to-reward ratio according to direction."""

        risk = 0.0
        reward = 0.0

        if direction == TradeDirection.LONG:
            risk = entry - stop
            reward = tp1 - entry
        elif direction == TradeDirection.SHORT:
            risk = stop - entry
            reward = entry - tp1

        if risk <= 0 or reward <= 0:
            return 0.0

        return reward / risk

    def compute_entry_distance_pct(self, price: float, entry: float) -> float:
        """Return the percentage distance between current price and entry."""

        if price <= 0:
            return float("inf")
        return abs(entry - price) / price * 100.0

    def compute_spread_bps(self, bid: float, ask: float) -> float:
        """Return bid/ask spread expressed in basis points."""

        if bid <= 0 or ask <= 0 or ask <= bid:
            return float("inf")
        mid = (ask + bid) / 2.0
        return (ask - bid) / mid * 10_000.0

    def compute_freshness_weight(self, minutes_old: float) -> float:
        """Return freshness weight and enforce max age."""

        if minutes_old < 0:
            minutes_old = 0.0
        return 0.5 ** (minutes_old / self.config.freshness_half_life_min)

    # ------------------------------------------------------------------
    # Soft scoring helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _clip(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    def _f_bool(self, flag: bool) -> float:
        return 1.0 if flag else 0.0

    def _f_rr(self, rr: float) -> float:
        if rr <= 0:
            return 0.0
        return min(rr / 3.0, 1.0)

    def _f_tf_align(self, htf_trend_agrees: bool) -> float:
        return 1.0 if htf_trend_agrees else 0.0

    def _f_atr_band(self, atr_pct: float, regime: str) -> float:
        if atr_pct <= 0:
            return 0.0

        regime = (regime or "").upper()
        if regime == "TRENDING":
            sweet_low, sweet_high = 1.0, 3.0
        elif regime == "RANGING":
            sweet_low, sweet_high = 0.5, 1.5
        elif regime == "VOLATILE":
            sweet_low, sweet_high = 2.0, 5.0
        else:
            sweet_low, sweet_high = 1.0, 3.0

        if atr_pct < sweet_low or atr_pct > sweet_high:
            # Triangular fall-off
            span = sweet_high - sweet_low
            if atr_pct < sweet_low:
                return self._clip(1 - (sweet_low - atr_pct) / span, 0.0, 1.0)
            return self._clip(1 - (atr_pct - sweet_high) / span, 0.0, 1.0)

        # Inside the sweet spot
        mid = (sweet_low + sweet_high) / 2.0
        if atr_pct == mid:
            return 1.0
        # Provide mild tapering within the band so that edges score slightly lower
        distance = abs(atr_pct - mid)
        half_span = (sweet_high - sweet_low) / 2.0
        return self._clip(1 - distance / half_span, 0.0, 1.0)

    def _f_regime(self, regime: str) -> float:
        mapping = {
            "TRENDING": 1.0,
            "RANGING": 0.6,
            "VOLATILE": 0.8,
        }
        return mapping.get((regime or "").upper(), 0.6)

    def _calc_score(self, candidate: SetupCandidate, rr: float, w_fresh: float) -> float:
        weights = self.config.confluence_weights
        flags = candidate.structure_flags

        score = (
            weights.get("tf_align", 0) * self._f_tf_align(flags.get("htf_trend_agrees", False))
            + weights.get("ob_quality", 0) * (candidate.ob_quality or 0.0)
            + weights.get("fvg_presence", 0) * self._f_bool(flags.get("has_fvg", False))
            + weights.get("bos_choch", 0) * self._f_bool(flags.get("bos_in_favor", False))
            + weights.get("freshness", 0) * w_fresh
            + weights.get("rr_strength", 0) * self._f_rr(rr)
            + weights.get("atr_sweetspot", 0) * self._f_atr_band(candidate.atr_pct, candidate.regime)
            + weights.get("regime_bias", 0) * self._f_regime(candidate.regime)
        )

        return self._clip(score, 0.0, 100.0)

    # ------------------------------------------------------------------
    # Reasons
    # ------------------------------------------------------------------
    def _build_reasons(
        self,
        candidate: SetupCandidate,
        rr: float,
        entry_distance_pct: float,
        w_fresh: float,
        spread_bps: float,
    ) -> List[str]:
        reasons: List[str] = []

        flags = candidate.structure_flags
        if flags.get("htf_trend_agrees"):
            reasons.append("HTF trend agrees")
        if flags.get("bos_in_favor"):
            reasons.append("BOS in favor")
        if flags.get("has_ob") and candidate.ob_quality is not None:
            reasons.append(f"OB quality={candidate.ob_quality * 100:.0f}")
        elif flags.get("has_ob"):
            reasons.append("Order block in play")
        if flags.get("has_fvg"):
            reasons.append("FVG aligned")

        reasons.append(f"RR={rr:.2f} (entry {entry_distance_pct:.1f}% away)")
        reasons.append(f"fresh {w_fresh:.2f} (age {candidate.minutes_old:.0f}m)")
        reasons.append(f"spread {spread_bps:.0f} bps, vol ${candidate.volume_usd_24h/1_000_000:.2f}M")

        return reasons[:5]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def evaluate(self, candidates: Iterable[SetupCandidate]) -> List[GateDecision]:
        """Evaluate candidates and return approved setups sorted by score."""

        approved: List[GateDecision] = []

        for candidate in candidates:
            # Only check phemex_listed if exchange is Phemex
            if self.exchange and self.exchange.lower() == "phemex":
                if not candidate.phemex_listed:
                    continue

            rr = self.compute_rr(candidate.entry_near, candidate.entry_stop, candidate.entry_tp1, candidate.direction)
            if rr < self.config.min_rr:
                continue

            entry_distance_pct = self.compute_entry_distance_pct(candidate.price_current, candidate.entry_near)
            low, high = self.config.entry_distance_pct
            if entry_distance_pct < low or entry_distance_pct > high:
                continue

            if candidate.minutes_old > self.config.max_setup_age_min:
                continue

            if candidate.volume_usd_24h < self.config.min_volume_usd:
                continue

            spread_bps = self.compute_spread_bps(candidate.orderbook_bid, candidate.orderbook_ask)
            if spread_bps > self.config.max_spread_bps:
                continue

            confluence = candidate.confluence_count()
            if confluence < self.config.min_confluence:
                continue

            w_fresh = self.compute_freshness_weight(candidate.minutes_old)
            score = self._calc_score(candidate, rr, w_fresh)
            if score < self.config.min_score:
                continue

            reasons = self._build_reasons(candidate, rr, entry_distance_pct, w_fresh, spread_bps)
            decision = GateDecision(
                candidate=candidate,
                rr=rr,
                entry_distance_pct=entry_distance_pct,
                spread_bps=spread_bps,
                freshness_weight=w_fresh,
                confluence=confluence,
                score=score,
                reasons=reasons,
                touched_tfs=list(candidate.touched_tfs),
            )
            approved.append(decision)

        approved.sort(key=lambda d: d.score, reverse=True)
        return approved[: self.config.max_setups]
