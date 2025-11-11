"""Pair filtering module to exclude stablecoins and select top pairs"""

from typing import List, Set, Optional


# Common stablecoin symbols
STABLECOINS = {
    'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDP', 'USDD', 
    'GUSD', 'FRAX', 'LUSD', 'USDK', 'USDJ', 'HUSD', 'CUSD',
    'UST', 'USTC', 'SUSD', 'DUSD', 'OUSD', 'MUSD', 'RSV'
}


class PairFilter:
    """Filter trading pairs based on various criteria"""

    def __init__(self, exclude_stables: bool = True, custom_exclude: Optional[Set[str]] = None):
        """Initialize pair filter
        
        Args:
            exclude_stables: Whether to exclude stablecoin pairs
            custom_exclude: Custom set of symbols to exclude
        """
        self.exclude_stables = exclude_stables
        self.custom_exclude = custom_exclude or set()
        self.excluded_symbols = STABLECOINS.union(self.custom_exclude) if exclude_stables else self.custom_exclude

    def is_stablecoin_pair(self, symbol: str) -> bool:
        """Check if a pair involves stablecoins on both sides
        
        Args:
            symbol: Trading pair symbol (e.g., 'USDT/USDC')
            
        Returns:
            True if both base and quote are stablecoins
        """
        parts = symbol.replace('/', '').split(':')
        base_quote = parts[0]
        
        # Try to split into base and quote
        for stable in STABLECOINS:
            if base_quote.endswith(stable):
                base = base_quote[:-len(stable)]
                quote = stable
                return base in STABLECOINS and quote in STABLECOINS
        
        return False

    def should_exclude(self, symbol: str) -> bool:
        """Check if a symbol should be excluded
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if symbol should be excluded
        """
        # Exclude stablecoin-to-stablecoin pairs
        if self.is_stablecoin_pair(symbol):
            return True
        
        # Check custom exclusions
        for excluded in self.custom_exclude:
            if excluded in symbol:
                return True
        
        return False

    def filter_pairs(self, pairs: List[str]) -> List[str]:
        """Filter a list of trading pairs
        
        Args:
            pairs: List of trading pair symbols
            
        Returns:
            Filtered list of trading pairs
        """
        return [pair for pair in pairs if not self.should_exclude(pair)]

    def get_top_pairs(self, pairs: List[str], limit: int = 50) -> List[str]:
        """Get top N pairs after filtering
        
        Args:
            pairs: List of trading pairs (assumed to be pre-sorted by volume)
            limit: Number of pairs to return
            
        Returns:
            Top N filtered pairs
        """
        filtered = self.filter_pairs(pairs)
        return filtered[:limit]
