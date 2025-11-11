"""Unit tests for JSON formatter"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from snipetrade.output.json_formatter import JSONFormatter
from snipetrade.models import TradeSetup, ScanResult, TradeDirection


class TestJSONFormatter:
    """Test cases for JSONFormatter"""

    def test_init_no_dir(self):
        """Test initialization without output directory"""
        formatter = JSONFormatter()
        assert formatter.output_dir is None

    def test_init_with_dir(self, tmp_path):
        """Test initialization with output directory"""
        formatter = JSONFormatter(output_dir=tmp_path)
        assert formatter.output_dir == tmp_path
        assert tmp_path.exists()

    def test_format_setup(self):
        """Test formatting a trade setup"""
        setup = TradeSetup(
            symbol='BTC/USDT',
            exchange='binance',
            direction=TradeDirection.LONG,
            score=75.0,
            confidence=0.8,
            entry_price=50000.0,
            reasons=['Test reason']
        )
        
        formatter = JSONFormatter()
        formatted = formatter.format_setup(setup)
        
        assert formatted['symbol'] == 'BTC/USDT'
        assert formatted['exchange'] == 'binance'
        assert formatted['direction'] == 'LONG'
        assert formatted['score'] == 75.0
        assert formatted['confidence'] == 0.8

    def test_format_scan_result(self):
        """Test formatting a scan result"""
        scan_result = ScanResult(
            scan_id='test-123',
            exchange='binance',
            total_pairs_scanned=50,
            total_setups_found=5,
            top_setups=[]
        )
        
        formatter = JSONFormatter()
        formatted = formatter.format_scan_result(scan_result)
        
        assert formatted['scan_id'] == 'test-123'
        assert formatted['exchange'] == 'binance'
        assert formatted['total_pairs_scanned'] == 50
        assert formatted['total_setups_found'] == 5

    def test_save_setup(self, tmp_path):
        """Test saving setup to file"""
        setup = TradeSetup(
            symbol='BTC/USDT',
            exchange='binance',
            direction=TradeDirection.LONG,
            score=75.0,
            confidence=0.8,
            entry_price=50000.0
        )
        
        formatter = JSONFormatter(output_dir=tmp_path)
        filepath = formatter.save_setup(setup)
        
        assert Path(filepath).exists()
        
        # Verify content
        with open(filepath, 'r') as f:
            data = json.load(f)
            assert data['symbol'] == 'BTC/USDT'

    def test_save_scan_result(self, tmp_path):
        """Test saving scan result to file"""
        scan_result = ScanResult(
            scan_id='test-123',
            exchange='binance',
            total_pairs_scanned=50,
            total_setups_found=5,
            top_setups=[]
        )
        
        formatter = JSONFormatter(output_dir=tmp_path)
        filepath = formatter.save_scan_result(scan_result)
        
        assert Path(filepath).exists()
        
        # Verify content
        with open(filepath, 'r') as f:
            data = json.load(f)
            assert data['scan_id'] == 'test-123'

    def test_to_json_string_pretty(self):
        """Test converting to pretty JSON string"""
        setup = TradeSetup(
            symbol='BTC/USDT',
            exchange='binance',
            direction=TradeDirection.LONG,
            score=75.0,
            confidence=0.8,
            entry_price=50000.0
        )
        
        formatter = JSONFormatter()
        json_str = formatter.to_json_string(setup, pretty=True)
        
        assert 'BTC/USDT' in json_str
        assert '\n' in json_str  # Pretty print should have newlines

    def test_to_json_string_compact(self):
        """Test converting to compact JSON string"""
        setup = TradeSetup(
            symbol='BTC/USDT',
            exchange='binance',
            direction=TradeDirection.LONG,
            score=75.0,
            confidence=0.8,
            entry_price=50000.0
        )
        
        formatter = JSONFormatter()
        json_str = formatter.to_json_string(setup, pretty=False)
        
        assert 'BTC/USDT' in json_str
        # Compact format should be on one line (no pretty formatting)
        data = json.loads(json_str)
        assert data['symbol'] == 'BTC/USDT'
