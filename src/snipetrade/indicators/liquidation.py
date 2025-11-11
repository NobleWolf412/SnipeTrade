"""Liquidation heatmap data provider (mock implementation)"""

from typing import List, Dict, Optional
import random
from snipetrade.models import LiquidationData, TradeDirection


class LiquidationHeatmap:
    """Provides liquidation heatmap data
    
    Note: This is a mock implementation. In production, this would integrate
    with real liquidation data providers like Coinglass, Hyblock, etc.
    """

    def __init__(self, data_source: Optional[str] = None):
        """Initialize liquidation heatmap provider
        
        Args:
            data_source: Optional data source identifier
        """
        self.data_source = data_source or "mock"

    def get_liquidation_levels(self, symbol: str, current_price: float, 
                                range_percent: float = 5.0) -> List[LiquidationData]:
        """Get liquidation levels for a symbol
        
        Args:
            symbol: Trading pair symbol
            current_price: Current market price
            range_percent: Price range to search (percentage)
            
        Returns:
            List of liquidation data points
        """
        # Mock implementation - generates synthetic liquidation levels
        # In production, this would fetch real data from liquidation heatmap APIs
        
        liquidation_levels = []
        
        # Generate mock liquidation clusters
        num_levels = random.randint(3, 7)
        
        for i in range(num_levels):
            # Random price level within range
            offset = random.uniform(-range_percent / 100, range_percent / 100)
            price_level = current_price * (1 + offset)
            
            # Random liquidation amount
            liquidation_amount = random.uniform(100000, 5000000)
            
            # Direction (longs or shorts being liquidated)
            direction = random.choice([TradeDirection.LONG, TradeDirection.SHORT])
            
            # Significance based on amount
            significance = min(1.0, liquidation_amount / 5000000)
            
            liquidation_levels.append(LiquidationData(
                symbol=symbol,
                price_level=price_level,
                liquidation_amount=liquidation_amount,
                direction=direction,
                significance=significance
            ))
        
        # Sort by price level
        liquidation_levels.sort(key=lambda x: x.price_level)
        
        return liquidation_levels

    def get_nearest_liquidation_zone(self, symbol: str, current_price: float, 
                                      direction: TradeDirection) -> Optional[LiquidationData]:
        """Get nearest significant liquidation zone
        
        Args:
            symbol: Trading pair symbol
            current_price: Current market price
            direction: Trade direction to check for
            
        Returns:
            Nearest significant liquidation zone or None
        """
        levels = self.get_liquidation_levels(symbol, current_price)
        
        # Filter by direction and find nearest
        relevant_levels = [
            level for level in levels 
            if level.direction == direction and level.significance > 0.5
        ]
        
        if not relevant_levels:
            return None
        
        # Find nearest to current price
        nearest = min(relevant_levels, key=lambda x: abs(x.price_level - current_price))
        return nearest

    def has_significant_liquidation_support(self, symbol: str, current_price: float,
                                             direction: TradeDirection, 
                                             threshold: float = 0.6) -> bool:
        """Check if there's significant liquidation support for a direction
        
        Args:
            symbol: Trading pair symbol
            current_price: Current market price
            direction: Trade direction
            threshold: Significance threshold
            
        Returns:
            True if significant liquidation support exists
        """
        levels = self.get_liquidation_levels(symbol, current_price)
        
        # Check for significant levels in the direction
        significant = [
            level for level in levels
            if level.direction == direction and level.significance >= threshold
        ]
        
        return len(significant) > 0
