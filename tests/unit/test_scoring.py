"""Unit tests for scoring engine"""

import pytest
from datetime import datetime, timedelta
from snipetrade.scoring.confluence import ConfluenceScorer
from snipetrade.models import MarketData, TradeDirection, IndicatorSignal


def create_market_data(num_candles: int = 100, base_price: float = 100.0) -> list:
    """Helper to create market data for testing"""
    data = []
    current_time = datetime.utcnow()
    
    for i in range(num_candles):
        price = base_price + (i * 0.5)
        data.append(MarketData(
            symbol='BTC/USDT',
            exchange='binance',
            timeframe='1h',
            timestamp=current_time - timedelta(hours=num_candles - i),
            open=price,
            high=price + 0.5,
            low=price - 0.5,
            close=price,
            volume=1000.0
        ))
    
    return data


class TestConfluenceScorer:
    """Test cases for ConfluenceScorer"""

    def test_init_default(self):
        """Test default initialization"""
        scorer = ConfluenceScorer()
        assert len(scorer.timeframes) == 3
        assert scorer.weights['indicator_alignment'] > 0

    def test_init_custom_timeframes(self):
        """Test initialization with custom timeframes"""
        timeframes = ['5m', '15m', '1h']
        scorer = ConfluenceScorer(timeframes=timeframes)
        assert scorer.timeframes == timeframes

    def test_calculate_indicator_score_aligned(self):
        """Test indicator score with aligned signals"""
        scorer = ConfluenceScorer()
        
        signals = [
            IndicatorSignal(name="RSI", value=25.0, signal=TradeDirection.LONG, 
                           strength=0.8, timeframe="1h"),
            IndicatorSignal(name="MACD", value=1.5, signal=TradeDirection.LONG, 
                           strength=0.7, timeframe="1h"),
            IndicatorSignal(name="EMA", value=100.0, signal=TradeDirection.LONG, 
                           strength=0.6, timeframe="1h"),
        ]
        
        score = scorer.calculate_indicator_score(signals)
        assert score > 50.0  # Should have good alignment

    def test_calculate_indicator_score_mixed(self):
        """Test indicator score with mixed signals"""
        scorer = ConfluenceScorer()
        
        signals = [
            IndicatorSignal(name="RSI", value=25.0, signal=TradeDirection.LONG, 
                           strength=0.8, timeframe="1h"),
            IndicatorSignal(name="MACD", value=-1.5, signal=TradeDirection.SHORT, 
                           strength=0.7, timeframe="1h"),
        ]
        
        score = scorer.calculate_indicator_score(signals)
        assert score >= 0.0 and score <= 100.0

    def test_calculate_indicator_score_empty(self):
        """Test indicator score with no signals"""
        scorer = ConfluenceScorer()
        score = scorer.calculate_indicator_score([])
        assert score == 0.0

    def test_calculate_timeframe_confluence(self):
        """Test timeframe confluence calculation"""
        scorer = ConfluenceScorer()
        
        # All timeframes aligned
        timeframe_signals = {
            '15m': TradeDirection.LONG,
            '1h': TradeDirection.LONG,
            '4h': TradeDirection.LONG,
        }
        score = scorer.calculate_timeframe_confluence(timeframe_signals)
        assert score == 100.0
        
        # Partial alignment
        timeframe_signals = {
            '15m': TradeDirection.LONG,
            '1h': TradeDirection.SHORT,
            '4h': TradeDirection.LONG,
        }
        score = scorer.calculate_timeframe_confluence(timeframe_signals)
        assert score > 0.0 and score < 100.0

    def test_determine_dominant_direction(self):
        """Test determining dominant direction"""
        scorer = ConfluenceScorer()
        
        signals = [
            IndicatorSignal(name="RSI", value=25.0, signal=TradeDirection.LONG, 
                           strength=0.8, timeframe="1h"),
            IndicatorSignal(name="MACD", value=1.5, signal=TradeDirection.LONG, 
                           strength=0.7, timeframe="1h"),
            IndicatorSignal(name="EMA", value=100.0, signal=TradeDirection.SHORT, 
                           strength=0.3, timeframe="1h"),
        ]
        
        direction = scorer.determine_dominant_direction(signals)
        assert direction == TradeDirection.LONG

    def test_calculate_confidence(self):
        """Test confidence calculation"""
        scorer = ConfluenceScorer()
        
        confidence = scorer.calculate_confidence(
            score=80.0,
            num_signals=5,
            timeframe_confluence=3
        )
        
        assert confidence >= 0.0 and confidence <= 1.0
        assert confidence > 0.5  # High score should give good confidence

    def test_score_setup(self):
        """Test complete setup scoring"""
        scorer = ConfluenceScorer()
        
        # Create multi-timeframe data
        timeframe_data = {
            '15m': create_market_data(100, base_price=100.0),
            '1h': create_market_data(100, base_price=100.0),
            '4h': create_market_data(100, base_price=100.0),
        }
        
        setup = scorer.score_setup(
            symbol='BTC/USDT',
            exchange='binance',
            timeframe_data=timeframe_data,
            current_price=150.0
        )
        
        if setup:  # May be None if no clear signal
            assert setup.symbol == 'BTC/USDT'
            assert setup.exchange == 'binance'
            assert setup.direction in [TradeDirection.LONG, TradeDirection.SHORT]
            assert setup.score >= 0.0 and setup.score <= 100.0
            assert setup.confidence >= 0.0 and setup.confidence <= 1.0
            assert len(setup.reasons) > 0

    def test_generate_reasons(self):
        """Test reason generation"""
        scorer = ConfluenceScorer()
        
        from snipetrade.models import TradeSetup, LiquidationData
        
        setup = TradeSetup(
            symbol='BTC/USDT',
            exchange='binance',
            direction=TradeDirection.LONG,
            score=75.0,
            confidence=0.8,
            entry_price=100.0,
            timeframe_confluence={'15m': TradeDirection.LONG, '1h': TradeDirection.LONG},
            indicator_signals=[
                IndicatorSignal(name="RSI", value=25.0, signal=TradeDirection.LONG, 
                               strength=0.8, timeframe="1h"),
            ],
            liquidation_zones=[
                LiquidationData(symbol='BTC/USDT', price_level=95.0, 
                               liquidation_amount=1000000, direction=TradeDirection.LONG,
                               significance=0.8)
            ]
        )
        
        reasons = scorer.generate_reasons(setup)
        assert len(reasons) > 0
        assert any('RSI' in reason for reason in reasons)
