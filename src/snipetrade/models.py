"""Data models for the trade scanner"""

from typing import Dict, List, Optional, Any, NamedTuple
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from enum import Enum


class TradeDirection(str, Enum):
    """Trade direction enum"""
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


class Timeframe(str, Enum):
    """Supported timeframes"""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class OHLCVTuple(NamedTuple):
    """Typed OHLCV tuple used across the scanner."""

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketData(BaseModel):
    """Market data for a trading pair"""
    symbol: str
    exchange: str
    timeframe: str
    timestamp: datetime
    ohlcv: OHLCVTuple
    open: float
    high: float
    low: float
    close: float
    volume: float

    @model_validator(mode='before')
    @classmethod
    def _ensure_ohlcv(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(values)
        ohlcv = data.get('ohlcv')
        timestamp = data.get('timestamp')

        def _to_float(name: str) -> float:
            value = data.get(name)
            return float(value) if value is not None else 0.0

        if ohlcv is None:
            if isinstance(timestamp, datetime):
                ts = int(timestamp.timestamp() * 1000)
            else:
                ts = int(datetime.utcnow().timestamp() * 1000)
            data['ohlcv'] = OHLCVTuple(
                timestamp=ts,
                open=_to_float('open'),
                high=_to_float('high'),
                low=_to_float('low'),
                close=_to_float('close'),
                volume=_to_float('volume'),
            )
        else:
            if not isinstance(ohlcv, OHLCVTuple):
                ohlcv_tuple = OHLCVTuple(*ohlcv)
                data['ohlcv'] = ohlcv_tuple
            else:
                ohlcv_tuple = ohlcv

            if timestamp is None:
                data['timestamp'] = datetime.fromtimestamp(ohlcv_tuple.timestamp / 1000)

            for attr in ('open', 'high', 'low', 'close', 'volume'):
                if data.get(attr) is None:
                    data[attr] = getattr(ohlcv_tuple, attr)

        return data


class IndicatorSignal(BaseModel):
    """Individual indicator signal"""
    name: str
    value: float
    signal: TradeDirection
    strength: float = Field(ge=0.0, le=1.0)  # 0 to 1
    timeframe: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LiquidationData(BaseModel):
    """Liquidation heatmap data"""
    symbol: str
    price_level: float
    liquidation_amount: float
    direction: TradeDirection
    significance: float = Field(ge=0.0, le=1.0)


class TradeSetup(BaseModel):
    """Complete trade setup with scoring"""
    symbol: str
    exchange: str
    direction: TradeDirection
    score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    entry_price: float
    suggested_stop_loss: Optional[float] = None
    suggested_take_profit: Optional[float] = None
    timeframe_confluence: Dict[str, TradeDirection] = Field(default_factory=dict)
    indicator_signals: List[IndicatorSignal] = Field(default_factory=list)
    liquidation_zones: List[LiquidationData] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ScanResult(BaseModel):
    """Complete scan result"""
    scan_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    exchange: str
    total_pairs_scanned: int
    total_setups_found: int
    top_setups: List[TradeSetup] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
