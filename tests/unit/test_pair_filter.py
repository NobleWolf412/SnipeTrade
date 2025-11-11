"""Unit tests for pair filtering module"""

import pytest
from snipetrade.filters.pair_filter import PairFilter, STABLECOINS


class TestPairFilter:
    """Test cases for PairFilter"""

    def test_init_default(self):
        """Test default initialization"""
        filter = PairFilter()
        assert filter.exclude_stables is True
        assert len(filter.excluded_symbols) == len(STABLECOINS)

    def test_init_no_exclude_stables(self):
        """Test initialization without stablecoin exclusion"""
        filter = PairFilter(exclude_stables=False)
        assert filter.exclude_stables is False
        assert len(filter.excluded_symbols) == 0

    def test_init_custom_exclude(self):
        """Test initialization with custom exclusions"""
        custom = {'BNB', 'FTM'}
        filter = PairFilter(custom_exclude=custom)
        assert custom.issubset(filter.excluded_symbols)

    def test_is_stablecoin_pair(self):
        """Test stablecoin pair detection"""
        filter = PairFilter()
        
        # Stablecoin pairs
        assert filter.is_stablecoin_pair('USDT/USDC') is True
        assert filter.is_stablecoin_pair('DAI/USDT') is True
        assert filter.is_stablecoin_pair('BUSD/USDC') is True
        
        # Non-stablecoin pairs
        assert filter.is_stablecoin_pair('BTC/USDT') is False
        assert filter.is_stablecoin_pair('ETH/USDT') is False
        assert filter.is_stablecoin_pair('BTC/ETH') is False

    def test_should_exclude(self):
        """Test exclusion logic"""
        custom = {'BNB'}
        filter = PairFilter(custom_exclude=custom)
        
        # Should exclude stablecoin pairs
        assert filter.should_exclude('USDT/USDC') is True
        
        # Should exclude custom
        assert filter.should_exclude('BNB/USDT') is True
        
        # Should not exclude regular pairs
        assert filter.should_exclude('BTC/USDT') is False
        assert filter.should_exclude('ETH/USDT') is False

    def test_filter_pairs(self):
        """Test pair filtering"""
        pairs = [
            'BTC/USDT',
            'ETH/USDT',
            'USDT/USDC',
            'BNB/USDT',
            'SOL/USDT',
            'DAI/BUSD'
        ]
        
        filter = PairFilter(custom_exclude={'BNB'})
        filtered = filter.filter_pairs(pairs)
        
        assert 'BTC/USDT' in filtered
        assert 'ETH/USDT' in filtered
        assert 'SOL/USDT' in filtered
        assert 'USDT/USDC' not in filtered
        assert 'BNB/USDT' not in filtered
        assert 'DAI/BUSD' not in filtered

    def test_get_top_pairs(self):
        """Test getting top N pairs"""
        pairs = [f'COIN{i}/USDT' for i in range(100)]
        pairs.insert(5, 'USDT/USDC')  # Add stablecoin pair
        
        filter = PairFilter()
        top_pairs = filter.get_top_pairs(pairs, limit=10)
        
        assert len(top_pairs) == 10
        assert 'USDT/USDC' not in top_pairs

    def test_get_top_pairs_insufficient(self):
        """Test getting top pairs when fewer available"""
        pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        
        filter = PairFilter()
        top_pairs = filter.get_top_pairs(pairs, limit=10)
        
        assert len(top_pairs) == 3
