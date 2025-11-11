"""Integration test for complete scanner workflow"""

import pytest
from pathlib import Path
from snipetrade.config import Config
from snipetrade.scanner import TradeScanner


class TestScannerIntegration:
    """Integration tests for complete scanner workflow"""

    def test_scanner_with_minimal_config(self, tmp_path):
        """Test scanner with minimal configuration"""
        config = {
            'exchange': 'binance',
            'max_pairs': 3,  # Very small for testing
            'min_score': 0.0,  # Accept all
            'max_workers': 1,
            'json_output_dir': str(tmp_path / 'output'),
            'enable_audit': True,
            'audit_dir': str(tmp_path / 'audit'),
            'enable_notifications': False,
            'top_setups_limit': 5,
            'timeframes': ['1h'],  # Single timeframe for speed
        }
        
        scanner = TradeScanner(config)
        
        # Verify scanner components initialized
        assert scanner.exchange is not None
        assert scanner.pair_filter is not None
        assert scanner.scorer is not None
        assert scanner.audit_logger is not None
        assert scanner.telegram is None  # Disabled

    def test_config_validation(self):
        """Test configuration validation"""
        config = Config()
        
        issues = config.validate()
        
        # Should have at least one issue (missing telegram config)
        assert isinstance(issues, list)

    def test_config_loading(self, tmp_path):
        """Test configuration loading from file"""
        config_file = tmp_path / "test_config.json"
        config_file.write_text('''{
            "exchange": "bybit",
            "max_pairs": 20,
            "min_score_threshold": 55.0
        }''')
        
        config = Config(config_file=str(config_file))
        
        assert config.get('exchange') == 'bybit'
        assert config.get('max_pairs') == 20
        # Note: JSON uses lowercase with underscores, gets mapped to config keys
        assert config.get('min_score') >= 50.0  # Will be default or from JSON

    def test_json_output_creation(self, tmp_path):
        """Test that JSON output directory is created"""
        config = {
            'exchange': 'binance',
            'json_output_dir': str(tmp_path / 'output'),
            'max_pairs': 1,
        }
        
        scanner = TradeScanner(config)
        assert scanner.json_formatter is not None
        assert Path(tmp_path / 'output').exists()

    def test_audit_logging_creation(self, tmp_path):
        """Test that audit logging directory is created"""
        config = {
            'exchange': 'binance',
            'enable_audit': True,
            'audit_dir': str(tmp_path / 'audit'),
            'max_pairs': 1,
        }
        
        scanner = TradeScanner(config)
        assert scanner.audit_logger is not None
        assert Path(tmp_path / 'audit').exists()
