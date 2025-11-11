"""Scoring engine for trade setups using multi-timeframe confluence"""

from datetime import datetime
from typing import List, Dict, Optional
from snipetrade.models import (
    MarketData, IndicatorSignal, TradeSetup, TradeDirection, 
    LiquidationData, Timeframe
)
from snipetrade.indicators.calculator import IndicatorCalculator
from snipetrade.indicators.liquidation import LiquidationHeatmap


class ConfluenceScorer:
    """Score trade setups based on multi-timeframe confluence and indicators"""

    def __init__(self, timeframes: Optional[List[str]] = None):
        """Initialize confluence scorer
        
        Args:
            timeframes: List of timeframes to analyze (default: 15m, 1h, 4h)
        """
        self.timeframes = timeframes or [Timeframe.M15.value, Timeframe.H1.value, Timeframe.H4.value]
        self.indicator_calculator = IndicatorCalculator()
        self.liquidation_heatmap = LiquidationHeatmap()
        
        # Scoring weights
        self.weights = {
            'indicator_alignment': 0.35,
            'timeframe_confluence': 0.30,
            'liquidation_support': 0.20,
            'trend_strength': 0.15
        }

    def calculate_indicator_score(self, signals: List[IndicatorSignal]) -> float:
        """Calculate score based on indicator alignment
        
        Args:
            signals: List of indicator signals
            
        Returns:
            Indicator alignment score (0-100)
        """
        if not signals:
            return 0.0
        
        # Count signals by direction
        long_signals = [s for s in signals if s.signal == TradeDirection.LONG]
        short_signals = [s for s in signals if s.signal == TradeDirection.SHORT]
        
        # Calculate weighted strength
        long_strength = sum(s.strength for s in long_signals)
        short_strength = sum(s.strength for s in short_signals)
        
        total_strength = long_strength + short_strength
        if total_strength == 0:
            return 0.0
        
        # Score is higher when signals align
        max_strength = max(long_strength, short_strength)
        alignment_ratio = max_strength / total_strength
        
        # Consider number of aligned signals
        max_count = max(len(long_signals), len(short_signals))
        count_bonus = min(1.0, max_count / len(signals))
        
        return (alignment_ratio * 0.7 + count_bonus * 0.3) * 100

    def calculate_timeframe_confluence(self, timeframe_signals: Dict[str, TradeDirection]) -> float:
        """Calculate score based on timeframe confluence
        
        Args:
            timeframe_signals: Dict mapping timeframe to dominant direction
            
        Returns:
            Timeframe confluence score (0-100)
        """
        if not timeframe_signals:
            return 0.0
        
        # Count directions across timeframes
        directions = list(timeframe_signals.values())
        long_count = directions.count(TradeDirection.LONG)
        short_count = directions.count(TradeDirection.SHORT)
        
        total = len(directions)
        max_count = max(long_count, short_count)
        
        # Higher score when more timeframes align
        confluence_ratio = max_count / total
        
        return confluence_ratio * 100

    def calculate_liquidation_score(self, liquidation_zones: List[LiquidationData],
                                      direction: TradeDirection) -> float:
        """Calculate score based on liquidation support
        
        Args:
            liquidation_zones: List of liquidation data
            direction: Trade direction
            
        Returns:
            Liquidation support score (0-100)
        """
        if not liquidation_zones:
            return 50.0  # Neutral score if no data
        
        # Find zones that support the trade direction
        supporting_zones = [
            zone for zone in liquidation_zones
            if zone.direction == direction
        ]
        
        if not supporting_zones:
            return 30.0  # Low score if no support
        
        # Calculate average significance of supporting zones
        avg_significance = sum(z.significance for z in supporting_zones) / len(supporting_zones)
        
        # Bonus for multiple supporting zones
        zone_bonus = min(1.0, len(supporting_zones) / 3)
        
        return (avg_significance * 0.7 + zone_bonus * 0.3) * 100

    def determine_dominant_direction(self, signals: List[IndicatorSignal]) -> TradeDirection:
        """Determine dominant trade direction from signals
        
        Args:
            signals: List of indicator signals
            
        Returns:
            Dominant trade direction
        """
        long_strength = sum(s.strength for s in signals if s.signal == TradeDirection.LONG)
        short_strength = sum(s.strength for s in signals if s.signal == TradeDirection.SHORT)
        
        if long_strength > short_strength:
            return TradeDirection.LONG
        elif short_strength > long_strength:
            return TradeDirection.SHORT
        else:
            return TradeDirection.NEUTRAL

    def calculate_confidence(self, score: float, num_signals: int, 
                              timeframe_confluence: int) -> float:
        """Calculate confidence level for a trade setup
        
        Args:
            score: Overall trade score
            num_signals: Number of indicator signals
            timeframe_confluence: Number of aligned timeframes
            
        Returns:
            Confidence level (0-1)
        """
        # Base confidence from score
        score_confidence = score / 100
        
        # Bonus for multiple signals
        signal_bonus = min(0.2, num_signals / 20)
        
        # Bonus for timeframe alignment
        timeframe_bonus = min(0.2, timeframe_confluence / 10)
        
        confidence = min(1.0, score_confidence + signal_bonus + timeframe_bonus)
        return confidence

    def generate_reasons(
        self,
        score: float,
        direction: TradeDirection,
        indicator_signals: List[IndicatorSignal],
        timeframe_confluence: Dict[str, TradeDirection],
        liquidation_zones: List[LiquidationData],
    ) -> List[str]:
        """Generate human-readable reasons for a trade setup"""

        reasons: List[str] = []

        strong_signals = [s for s in indicator_signals if s.strength > 0.6]
        for signal in strong_signals[:3]:
            reasons.append(
                f"{signal.name} favours {signal.signal.value} on {signal.timeframe}"
                f" (strength {signal.strength:.2f})"
            )

        aligned_timeframes = [
            tf for tf, tf_direction in timeframe_confluence.items()
            if tf_direction == direction
        ]
        if len(aligned_timeframes) >= 2:
            reasons.append(
                f"Multi-timeframe alignment: {', '.join(aligned_timeframes[:4])}"
            )

        significant_zones = [z for z in liquidation_zones if z.significance > 0.6]
        if significant_zones:
            reasons.append(
                f"{len(significant_zones)} supportive liquidation zone(s)"
            )

        if score >= 70:
            reasons.append(f"High composite score {score:.1f}/100")
        elif score >= 50:
            reasons.append(f"Moderate composite score {score:.1f}/100")

        return reasons

    def score_setup(self, symbol: str, exchange: str,
                     timeframe_data: Dict[str, List[MarketData]],
                     current_price: float) -> Optional[TradeSetup]:
        """Score a complete trade setup.

        Args:
            symbol: Trading pair symbol
            exchange: Exchange name
            timeframe_data: Dict mapping timeframe to market data
            current_price: Current market price

        Returns:
            Scored TradeSetup or None if insufficient data
        """
        all_signals: List[IndicatorSignal] = []
        timeframe_directions: Dict[str, TradeDirection] = {}

        for timeframe, market_data in timeframe_data.items():
            if len(market_data) < 50:
                continue

            signals = self.indicator_calculator.calculate_all_indicators(market_data)
            for signal in signals:
                signal.timeframe = timeframe

            all_signals.extend(signals)

            if signals:
                timeframe_directions[timeframe] = self.determine_dominant_direction(signals)

        if not all_signals:
            return None

        overall_direction = self.determine_dominant_direction(all_signals)
        if overall_direction == TradeDirection.NEUTRAL:
            return None

        liquidation_zones = self.liquidation_heatmap.get_liquidation_levels(
            symbol, current_price
        )

        indicator_score = self.calculate_indicator_score(all_signals)
        confluence_score = self.calculate_timeframe_confluence(timeframe_directions)
        liquidation_score = self.calculate_liquidation_score(liquidation_zones, overall_direction)

        avg_strength = sum(s.strength for s in all_signals) / len(all_signals)
        trend_score = avg_strength * 100

        total_score = (
            indicator_score * self.weights['indicator_alignment'] +
            confluence_score * self.weights['timeframe_confluence'] +
            liquidation_score * self.weights['liquidation_support'] +
            trend_score * self.weights['trend_strength']
        )

        num_aligned_timeframes = len([
            d for d in timeframe_directions.values() if d == overall_direction
        ])
        confidence = self.calculate_confidence(
            total_score, len(all_signals), num_aligned_timeframes
        )

        if overall_direction == TradeDirection.LONG:
            stop_loss = current_price * 0.98
            take_profits = [current_price * 1.02, current_price * 1.04]
            risk = current_price - stop_loss
            reward = take_profits[0] - current_price
        else:
            stop_loss = current_price * 1.02
            take_profits = [current_price * 0.98, current_price * 0.96]
            risk = stop_loss - current_price
            reward = current_price - take_profits[0]

        rr = reward / risk if risk > 0 else 0.0

        reasons = self.generate_reasons(
            score=total_score,
            direction=overall_direction,
            indicator_signals=all_signals,
            timeframe_confluence=timeframe_directions,
            liquidation_zones=liquidation_zones,
        )

        if not reasons:
            reasons = [
                f"{overall_direction.value} setup detected at {datetime.utcnow().isoformat()}"
            ]

        timeframe_summary = {
            tf: tf_direction.value for tf, tf_direction in timeframe_directions.items()
        }

        indicator_summary = [
            {
                'name': signal.name,
                'signal': signal.signal.value,
                'strength': signal.strength,
                'timeframe': signal.timeframe,
                'value': signal.value,
            }
            for signal in all_signals
        ]

        liquidation_summary = [
            {
                'price_level': zone.price_level,
                'liquidation_amount': zone.liquidation_amount,
                'direction': zone.direction.value,
                'significance': zone.significance,
            }
            for zone in liquidation_zones
        ]

        return TradeSetup(
            symbol=symbol,
            exchange=exchange,
            direction=overall_direction.value,
            score=total_score,
            confidence=confidence,
            entry_plan=[current_price],
            stop_loss=stop_loss,
            take_profits=take_profits,
            rr=rr if rr > 0 else 0.01,
            reasons=reasons,
            timeframe_confluence=timeframe_summary,
            indicator_summaries=indicator_summary,
            liquidation_zones=liquidation_summary,
            metadata={
                'indicator_score': indicator_score,
                'confluence_score': confluence_score,
                'liquidation_score': liquidation_score,
                'trend_score': trend_score,
                'aligned_timeframes': num_aligned_timeframes,
                'signal_count': len(all_signals),
            },
        )
