"""Base exchange connector interface"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import ccxt
import pandas as pd
from datetime import datetime, timedelta
from snipetrade.models import MarketData, OHLCVTuple


class BaseExchange(ABC):
    """Abstract base class for exchange connectors"""

    def __init__(self, exchange_id: str, config: Optional[Dict] = None):
        """Initialize exchange connector
        
        Args:
            exchange_id: CCXT exchange ID (e.g., 'binance', 'bybit')
            config: Optional configuration dict with API keys, etc.
        """
        self.exchange_id = exchange_id
        self.config = config or {}
        self.exchange = self._initialize_exchange()

    def _initialize_exchange(self):
        """Initialize CCXT exchange instance"""
        exchange_class = getattr(ccxt, self.exchange_id)
        return exchange_class(self.config)

    @abstractmethod
    def get_top_pairs(self, limit: int = 50, quote_currency: str = 'USDT') -> List[str]:
        """Get top trading pairs by volume
        
        Args:
            limit: Number of pairs to return
            quote_currency: Quote currency filter
            
        Returns:
            List of trading pair symbols
        """
        pass

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[MarketData]:
        """Fetch OHLCV data for a symbol
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe (e.g., '1h', '4h')
            limit: Number of candles to fetch
            
        Returns:
            List of MarketData objects
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            market_data = []
            
            for candle in ohlcv:
                ohlcv_tuple = OHLCVTuple(
                    timestamp=int(candle[0]),
                    open=float(candle[1]),
                    high=float(candle[2]),
                    low=float(candle[3]),
                    close=float(candle[4]),
                    volume=float(candle[5]),
                )
                market_data.append(MarketData(
                    symbol=symbol,
                    exchange=self.exchange_id,
                    timeframe=timeframe,
                    timestamp=datetime.fromtimestamp(ohlcv_tuple.timestamp / 1000),
                    ohlcv=ohlcv_tuple,
                    open=ohlcv_tuple.open,
                    high=ohlcv_tuple.high,
                    low=ohlcv_tuple.low,
                    close=ohlcv_tuple.close,
                    volume=ohlcv_tuple.volume
                ))
            
            return market_data
        except Exception as e:
            raise Exception(f"Error fetching OHLCV for {symbol}: {str(e)}")

    def get_current_price(self, symbol: str) -> float:
        """Get current market price for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Current price
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            raise Exception(f"Error fetching price for {symbol}: {str(e)}")


class BinanceExchange(BaseExchange):
    """Binance exchange connector"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__('binance', config)

    def get_top_pairs(self, limit: int = 50, quote_currency: str = 'USDT') -> List[str]:
        """Get top Binance pairs by 24h volume"""
        try:
            tickers = self.exchange.fetch_tickers()
            
            # Filter by quote currency and sort by volume
            filtered = []
            for symbol, ticker in tickers.items():
                if quote_currency in symbol and ticker.get('quoteVolume'):
                    filtered.append({
                        'symbol': symbol,
                        'volume': float(ticker['quoteVolume'])
                    })
            
            # Sort by volume and get top N
            sorted_pairs = sorted(filtered, key=lambda x: x['volume'], reverse=True)
            return [p['symbol'] for p in sorted_pairs[:limit]]
        except Exception as e:
            raise Exception(f"Error fetching top pairs: {str(e)}")


class BybitExchange(BaseExchange):
    """Bybit exchange connector"""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__('bybit', config)

    def get_top_pairs(self, limit: int = 50, quote_currency: str = 'USDT') -> List[str]:
        """Get top Bybit pairs by 24h volume"""
        try:
            tickers = self.exchange.fetch_tickers()
            
            # Filter by quote currency and sort by volume
            filtered = []
            for symbol, ticker in tickers.items():
                if quote_currency in symbol and ticker.get('quoteVolume'):
                    filtered.append({
                        'symbol': symbol,
                        'volume': float(ticker['quoteVolume'])
                    })
            
            # Sort by volume and get top N
            sorted_pairs = sorted(filtered, key=lambda x: x['volume'], reverse=True)
            return [p['symbol'] for p in sorted_pairs[:limit]]
        except Exception as e:
            raise Exception(f"Error fetching top pairs: {str(e)}")


def create_exchange(exchange_id: str, config: Optional[Dict] = None) -> BaseExchange:
    """Factory function to create exchange instances
    
    Args:
        exchange_id: Exchange identifier ('binance', 'bybit', etc.)
        config: Optional exchange configuration
        
    Returns:
        Exchange instance
    """
    exchanges = {
        'binance': BinanceExchange,
        'bybit': BybitExchange,
    }
    
    exchange_class = exchanges.get(exchange_id.lower())
    if not exchange_class:
        raise ValueError(f"Unsupported exchange: {exchange_id}")
    
    return exchange_class(config)
