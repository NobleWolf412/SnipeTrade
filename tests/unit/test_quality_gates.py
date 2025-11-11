"""Unit tests for quality gates implementation."""

from __future__ import annotations

from copy import deepcopy

import pytest

from snipetrade.models import TradeDirection
from snipetrade.quality import QualityGates, QualityGatesConfig, SetupCandidate


def make_candidate(**overrides):
    """Create a baseline candidate with sensible defaults for tests."""

    base = dict(
        symbol="BTC/USDT",
        timeframe="15m",
        direction=TradeDirection.LONG,
        price_current=100.0,
        orderbook_bid=99.9,
        orderbook_ask=100.1,
        volume_usd_24h=2_000_000.0,
        atr_pct=2.0,
        minutes_old=10.0,
        entry_near=101.0,
        entry_stop=99.0,
        entry_tp1=105.0,
        structure_flags={
            "has_ob": True,
            "has_fvg": True,
            "bos_in_favor": True,
            "htf_trend_agrees": True,
        },
        phemex_listed=True,
        regime="TRENDING",
        touched_tfs=["15m", "1h"],
        ob_quality=0.75,
    )

    base.update(overrides)
    return SetupCandidate(**base)


class TestQualityGates:
    """Comprehensive table-driven checks covering hard and soft gates."""

    def test_rr_geometry_long_short(self):
        gates = QualityGates()
        long_rr = gates.compute_rr(entry=100, stop=95, tp1=110, direction=TradeDirection.LONG)
        short_rr = gates.compute_rr(entry=100, stop=105, tp1=90, direction=TradeDirection.SHORT)
        assert pytest.approx(long_rr, rel=1e-3) == 2.0
        assert pytest.approx(short_rr, rel=1e-3) == 2.0
        # Invalid geometry should collapse to zero
        assert gates.compute_rr(100, 101, 102, TradeDirection.LONG) == 0.0

    def test_entry_distance_bounds(self):
        gates = QualityGates()
        base = make_candidate()
        # Too close
        close_candidate = deepcopy(base)
        close_candidate.entry_near = 100.2  # 0.2%
        close_candidate.entry_stop = 98.2
        close_candidate.entry_tp1 = 104.2
        assert gates.evaluate([close_candidate]) == []

        # Within bounds
        mid_candidate = deepcopy(base)
        mid_candidate.entry_near = 101.0  # 1%
        mid_candidate.entry_stop = 99.0
        mid_candidate.entry_tp1 = 105.0
        assert gates.evaluate([mid_candidate])

        # Too far
        far_candidate = deepcopy(base)
        far_candidate.entry_near = 107.0  # 7%
        far_candidate.entry_stop = 101.0
        far_candidate.entry_tp1 = 119.0
        assert gates.evaluate([far_candidate]) == []

    def test_freshness_rejects_stale(self):
        gates = QualityGates()
        fresh_weight = gates.compute_freshness_weight(30.0)
        assert pytest.approx(fresh_weight, rel=1e-3) == 0.5

        stale_candidate = make_candidate(minutes_old=95.0)
        assert gates.evaluate([stale_candidate]) == []

    def test_spread_and_volume_gates(self):
        gates = QualityGates()

        bad_spread = make_candidate(orderbook_bid=100.0, orderbook_ask=100.6)
        assert gates.evaluate([bad_spread]) == []

        bad_volume = make_candidate(volume_usd_24h=50_000.0)
        assert gates.evaluate([bad_volume]) == []

        good_candidate = make_candidate()
        decisions = gates.evaluate([good_candidate])
        assert decisions and decisions[0].spread_bps < gates.config.max_spread_bps

    def test_confluence_gate(self):
        gates = QualityGates()
        low_confluence = make_candidate(
            structure_flags={
                "has_ob": True,
                "has_fvg": False,
                "bos_in_favor": False,
                "htf_trend_agrees": False,
            }
        )
        assert gates.evaluate([low_confluence]) == []

    def test_atr_band_scoring(self):
        gates = QualityGates()
        trending_mid = make_candidate(atr_pct=2.0, regime="TRENDING")
        trending_edge = make_candidate(atr_pct=1.0, regime="TRENDING")
        volatile_mid = make_candidate(atr_pct=3.5, regime="VOLATILE")

        base_score = gates.evaluate([trending_mid])[0].score
        edge_score = gates.evaluate([trending_edge])[0].score
        volatile_score = gates.evaluate([volatile_mid])[0].score

        assert base_score > edge_score
        assert volatile_score > 0

    def test_scoring_determinism_and_ranking(self):
        gates = QualityGates()
        c1 = make_candidate(symbol="AAA/USDT", entry_tp1=106.0)
        c2 = make_candidate(symbol="BBB/USDT", entry_tp1=107.0)
        c3 = make_candidate(symbol="CCC/USDT", entry_tp1=110.0)

        decisions_first = gates.evaluate([c1, c2, c3])
        decisions_second = gates.evaluate([c1, c2, c3])

        first_scores = [d.score for d in decisions_first]
        second_scores = [d.score for d in decisions_second]
        assert first_scores == second_scores
        assert all(a >= b for a, b in zip(first_scores, first_scores[1:]))

    def test_reasons_compact(self):
        gates = QualityGates()
        decision = gates.evaluate([make_candidate()])[0]
        assert 0 < len(decision.reasons) <= 5
        assert all(decision.reasons)

    def test_phemex_gate_only_for_phemex_exchange(self):
        """Test that phemex_listed gate only applies when exchange is Phemex."""
        # Candidate not listed on Phemex
        not_listed = make_candidate(phemex_listed=False)
        
        # Without exchange specified, should accept (backwards compatible)
        gates_no_exchange = QualityGates()
        decisions_no_exchange = gates_no_exchange.evaluate([not_listed])
        assert len(decisions_no_exchange) == 1  # Should pass
        
        # With Phemex exchange, should filter out
        gates_phemex = QualityGates(exchange="phemex")
        decisions_phemex = gates_phemex.evaluate([not_listed])
        assert len(decisions_phemex) == 0  # Should be filtered
        
        # With Binance exchange, should accept (phemex_listed check skipped)
        gates_binance = QualityGates(exchange="binance")
        decisions_binance = gates_binance.evaluate([not_listed])
        assert len(decisions_binance) == 1  # Should pass
        
    def test_phemex_listed_true_passes_all_exchanges(self):
        """Test that candidates with phemex_listed=True pass for all exchanges."""
        listed = make_candidate(phemex_listed=True)
        
        for exchange in [None, "phemex", "binance", "bybit"]:
            gates = QualityGates(exchange=exchange)
            decisions = gates.evaluate([listed])
            assert len(decisions) == 1, f"Failed for exchange={exchange}"
