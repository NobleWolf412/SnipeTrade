"""Technical indicator calculations using TA library"""

from typing import List, Dict, Optional
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
from snipetrade.models import MarketData, IndicatorSignal, TradeDirection


class IndicatorCalculator:
    """Calculate technical indicators from market data"""

    @staticmethod
    def _to_dataframe(market_data: List[MarketData]) -> pd.DataFrame:
        """Convert MarketData list to pandas DataFrame"""
        data = {
            'timestamp': [md.timestamp for md in market_data],
            'open': [md.open for md in market_data],
            'high': [md.high for md in market_data],
            'low': [md.low for md in market_data],
            'close': [md.close for md in market_data],
            'volume': [md.volume for md in market_data],
        }
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

    def calculate_rsi(self, market_data: List[MarketData], period: int = 14) -> IndicatorSignal:
        """Calculate RSI indicator
        
        Args:
            market_data: List of market data
            period: RSI period
            
        Returns:
            IndicatorSignal with RSI value and signal
        """
        df = self._to_dataframe(market_data)
        rsi = RSIIndicator(close=df['close'], window=period)
        rsi_value = rsi.rsi().iloc[-1]
        
        # Determine signal
        if rsi_value < 30:
            signal = TradeDirection.LONG
            strength = (30 - rsi_value) / 30  # Stronger as it goes lower
        elif rsi_value > 70:
            signal = TradeDirection.SHORT
            strength = (rsi_value - 70) / 30  # Stronger as it goes higher
        else:
            signal = TradeDirection.NEUTRAL
            strength = 0.0
        
        strength = min(1.0, max(0.0, strength))
        
        return IndicatorSignal(
            name="RSI",
            value=float(rsi_value),
            signal=signal,
            strength=strength,
            timeframe=market_data[0].timeframe if market_data else "unknown",
            metadata={"period": period}
        )

    def calculate_macd(self, market_data: List[MarketData], 
                       fast: int = 12, slow: int = 26, signal_period: int = 9) -> IndicatorSignal:
        """Calculate MACD indicator
        
        Args:
            market_data: List of market data
            fast: Fast EMA period
            slow: Slow EMA period
            signal_period: Signal line period
            
        Returns:
            IndicatorSignal with MACD signal
        """
        df = self._to_dataframe(market_data)
        macd = MACD(close=df['close'], window_fast=fast, window_slow=slow, window_sign=signal_period)
        
        macd_line = macd.macd().iloc[-1]
        signal_line = macd.macd_signal().iloc[-1]
        macd_diff = macd.macd_diff().iloc[-1]
        
        # Determine signal based on MACD crossover
        if macd_diff > 0:
            signal = TradeDirection.LONG
            strength = min(1.0, abs(macd_diff) / abs(macd_line) if macd_line != 0 else 0.5)
        elif macd_diff < 0:
            signal = TradeDirection.SHORT
            strength = min(1.0, abs(macd_diff) / abs(macd_line) if macd_line != 0 else 0.5)
        else:
            signal = TradeDirection.NEUTRAL
            strength = 0.0
        
        return IndicatorSignal(
            name="MACD",
            value=float(macd_diff),
            signal=signal,
            strength=strength,
            timeframe=market_data[0].timeframe if market_data else "unknown",
            metadata={
                "macd_line": float(macd_line),
                "signal_line": float(signal_line)
            }
        )

    def calculate_ema(self, market_data: List[MarketData], periods: List[int] = [20, 50, 200]) -> IndicatorSignal:
        """Calculate EMA crossover signals
        
        Args:
            market_data: List of market data
            periods: List of EMA periods to calculate
            
        Returns:
            IndicatorSignal based on EMA alignment
        """
        df = self._to_dataframe(market_data)
        current_price = df['close'].iloc[-1]
        
        emas = {}
        for period in sorted(periods):
            ema = EMAIndicator(close=df['close'], window=period)
            emas[period] = ema.ema_indicator().iloc[-1]
        
        # Check if price is above/below all EMAs
        above_all = all(current_price > ema for ema in emas.values())
        below_all = all(current_price < ema for ema in emas.values())
        
        if above_all:
            signal = TradeDirection.LONG
            # Calculate strength based on distance from highest EMA
            highest_ema = max(emas.values())
            strength = min(1.0, (current_price - highest_ema) / highest_ema * 10)
        elif below_all:
            signal = TradeDirection.SHORT
            # Calculate strength based on distance from lowest EMA
            lowest_ema = min(emas.values())
            strength = min(1.0, (lowest_ema - current_price) / lowest_ema * 10)
        else:
            signal = TradeDirection.NEUTRAL
            strength = 0.0
        
        return IndicatorSignal(
            name="EMA",
            value=float(current_price),
            signal=signal,
            strength=strength,
            timeframe=market_data[0].timeframe if market_data else "unknown",
            metadata={"emas": {str(k): float(v) for k, v in emas.items()}}
        )

    def calculate_bollinger_bands(self, market_data: List[MarketData], 
                                   period: int = 20, std_dev: int = 2) -> IndicatorSignal:
        """Calculate Bollinger Bands signals
        
        Args:
            market_data: List of market data
            period: Moving average period
            std_dev: Standard deviation multiplier
            
        Returns:
            IndicatorSignal based on BB position
        """
        df = self._to_dataframe(market_data)
        bb = BollingerBands(close=df['close'], window=period, window_dev=std_dev)
        
        current_price = df['close'].iloc[-1]
        upper_band = bb.bollinger_hband().iloc[-1]
        lower_band = bb.bollinger_lband().iloc[-1]
        middle_band = bb.bollinger_mavg().iloc[-1]
        
        # Calculate position within bands
        band_width = upper_band - lower_band
        
        if current_price < lower_band:
            signal = TradeDirection.LONG
            strength = min(1.0, (lower_band - current_price) / band_width * 2)
        elif current_price > upper_band:
            signal = TradeDirection.SHORT
            strength = min(1.0, (current_price - upper_band) / band_width * 2)
        else:
            signal = TradeDirection.NEUTRAL
            strength = 0.0
        
        return IndicatorSignal(
            name="BollingerBands",
            value=float(current_price),
            signal=signal,
            strength=strength,
            timeframe=market_data[0].timeframe if market_data else "unknown",
            metadata={
                "upper_band": float(upper_band),
                "middle_band": float(middle_band),
                "lower_band": float(lower_band)
            }
        )

    def calculate_all_indicators(self, market_data: List[MarketData]) -> List[IndicatorSignal]:
        """Calculate all available indicators
        
        Args:
            market_data: List of market data
            
        Returns:
            List of all indicator signals
        """
        if not market_data or len(market_data) < 50:
            return []
        
        signals = []
        
        try:
            signals.append(self.calculate_rsi(market_data))
        except Exception:
            pass
        
        try:
            signals.append(self.calculate_macd(market_data))
        except Exception:
            pass
        
        try:
            signals.append(self.calculate_ema(market_data))
        except Exception:
            pass
        
        try:
            signals.append(self.calculate_bollinger_bands(market_data))
        except Exception:
            pass
        
        return signals
