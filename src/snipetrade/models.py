"""Data models for the trade scanner"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
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


class MarketData(BaseModel):
    """Market data for a trading pair"""
    symbol: str
    exchange: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


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
