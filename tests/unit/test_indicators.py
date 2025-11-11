"""Unit tests for indicator calculator"""

import pytest
from datetime import datetime, timedelta
from snipetrade.indicators.calculator import IndicatorCalculator
from snipetrade.models import MarketData, TradeDirection


def create_market_data(num_candles: int = 100, base_price: float = 100.0,
                        trend: str = 'up') -> list:
    """Helper to create market data for testing"""
    data = []
    current_time = datetime.utcnow()
    
    for i in range(num_candles):
        if trend == 'up':
            price = base_price + (i * 0.5)
        elif trend == 'down':
            price = base_price - (i * 0.5)
        else:  # sideways
            price = base_price + (i % 10 - 5) * 0.2
        
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


class TestIndicatorCalculator:
    """Test cases for IndicatorCalculator"""

    def test_calculate_rsi_oversold(self):
        """Test RSI calculation in oversold condition"""
        # Create downtrending data
        market_data = create_market_data(100, base_price=100.0, trend='down')
        
        calculator = IndicatorCalculator()
        signal = calculator.calculate_rsi(market_data)
        
        assert signal.name == "RSI"
        assert signal.signal in [TradeDirection.LONG, TradeDirection.NEUTRAL]
        assert 0 <= signal.strength <= 1.0
        assert signal.timeframe == '1h'

    def test_calculate_rsi_overbought(self):
        """Test RSI calculation in overbought condition"""
        # Create uptrending data
        market_data = create_market_data(100, base_price=100.0, trend='up')
        
        calculator = IndicatorCalculator()
        signal = calculator.calculate_rsi(market_data)
        
        assert signal.name == "RSI"
        assert signal.signal in [TradeDirection.SHORT, TradeDirection.NEUTRAL]
        assert 0 <= signal.strength <= 1.0

    def test_calculate_macd(self):
        """Test MACD calculation"""
        market_data = create_market_data(100, base_price=100.0, trend='up')
        
        calculator = IndicatorCalculator()
        signal = calculator.calculate_macd(market_data)
        
        assert signal.name == "MACD"
        assert signal.signal in [TradeDirection.LONG, TradeDirection.SHORT, TradeDirection.NEUTRAL]
        assert 0 <= signal.strength <= 1.0
        assert 'macd_line' in signal.metadata
        assert 'signal_line' in signal.metadata

    def test_calculate_ema(self):
        """Test EMA calculation"""
        market_data = create_market_data(250, base_price=100.0, trend='up')
        
        calculator = IndicatorCalculator()
        signal = calculator.calculate_ema(market_data, periods=[20, 50, 200])
        
        assert signal.name == "EMA"
        assert signal.signal in [TradeDirection.LONG, TradeDirection.SHORT, TradeDirection.NEUTRAL]
        assert 0 <= signal.strength <= 1.0
        assert 'emas' in signal.metadata
        assert len(signal.metadata['emas']) == 3

    def test_calculate_bollinger_bands(self):
        """Test Bollinger Bands calculation"""
        market_data = create_market_data(100, base_price=100.0, trend='sideways')
        
        calculator = IndicatorCalculator()
        signal = calculator.calculate_bollinger_bands(market_data)
        
        assert signal.name == "BollingerBands"
        assert signal.signal in [TradeDirection.LONG, TradeDirection.SHORT, TradeDirection.NEUTRAL]
        assert 0 <= signal.strength <= 1.0
        assert 'upper_band' in signal.metadata
        assert 'middle_band' in signal.metadata
        assert 'lower_band' in signal.metadata

    def test_calculate_all_indicators(self):
        """Test calculation of all indicators"""
        market_data = create_market_data(250, base_price=100.0, trend='up')
        
        calculator = IndicatorCalculator()
        signals = calculator.calculate_all_indicators(market_data)
        
        assert len(signals) > 0
        assert all(s.strength >= 0 and s.strength <= 1.0 for s in signals)
        
        # Check that we have various indicators
        indicator_names = {s.name for s in signals}
        assert 'RSI' in indicator_names
        assert 'MACD' in indicator_names

    def test_calculate_all_indicators_insufficient_data(self):
        """Test with insufficient data"""
        market_data = create_market_data(20, base_price=100.0)
        
        calculator = IndicatorCalculator()
        signals = calculator.calculate_all_indicators(market_data)
        
        assert signals == []
