"""Unit tests for audit logger"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from snipetrade.output.audit import AuditLogger
from snipetrade.models import ScanResult, TradeSetup


class TestAuditLogger:
    """Test cases for AuditLogger"""

    def test_init(self, tmp_path):
        """Test initialization"""
        logger = AuditLogger(audit_dir=tmp_path)
        assert logger.audit_dir == tmp_path
        assert logger.audit_dir.exists()
        assert logger.current_file.name.startswith('audit_')

    def test_log_event(self, tmp_path):
        """Test logging an event"""
        logger = AuditLogger(audit_dir=tmp_path)
        logger.log_event('test_event', {'key': 'value'}, level='INFO')
        
        assert logger.current_file.exists()
        
        # Read and verify
        with open(logger.current_file, 'r') as f:
            line = f.readline()
            event = json.loads(line)
            assert event['event_type'] == 'test_event'
            assert event['level'] == 'INFO'
            assert event['data']['key'] == 'value'

    def test_log_scan_started(self, tmp_path):
        """Test logging scan start"""
        logger = AuditLogger(audit_dir=tmp_path)
        logger.log_scan_started('binance', 50, {'min_score': 50.0})
        
        events = logger.read_audit_log()
        assert len(events) == 1
        assert events[0]['event_type'] == 'scan_started'
        assert events[0]['data']['exchange'] == 'binance'

    def test_log_scan_completed(self, tmp_path):
        """Test logging scan completion"""
        scan_result = ScanResult(
            scan_id='test-123',
            exchange='binance',
            total_pairs_scanned=50,
            total_setups_found=5,
            setups=[]
        )
        
        logger = AuditLogger(audit_dir=tmp_path)
        logger.log_scan_completed(scan_result)
        
        events = logger.read_audit_log()
        assert len(events) == 1
        assert events[0]['event_type'] == 'scan_completed'
        assert events[0]['data']['scan_id'] == 'test-123'

    def test_log_setup_found(self, tmp_path):
        """Test logging setup found"""
        setup = TradeSetup(
            symbol='BTC/USDT',
            exchange='binance',
            direction='LONG',
            score=75.0,
            confidence=0.8,
            entry_plan=[50000.0],
            stop_loss=48000.0,
            take_profits=[52000.0],
            rr=2.5,
            reasons=['Auto reason']
        )
        
        logger = AuditLogger(audit_dir=tmp_path)
        logger.log_setup_found(setup)
        
        events = logger.read_audit_log()
        assert len(events) == 1
        assert events[0]['event_type'] == 'setup_found'
        assert events[0]['data']['symbol'] == 'BTC/USDT'

    def test_log_alert_sent(self, tmp_path):
        """Test logging alert sent"""
        setup = TradeSetup(
            symbol='BTC/USDT',
            exchange='binance',
            direction='LONG',
            score=75.0,
            confidence=0.8,
            entry_plan=[50000.0],
            stop_loss=48000.0,
            take_profits=[52000.0],
            rr=2.5,
            reasons=['Auto reason']
        )
        
        logger = AuditLogger(audit_dir=tmp_path)
        logger.log_alert_sent(setup, 'telegram', True)
        
        events = logger.read_audit_log()
        assert len(events) == 1
        assert events[0]['event_type'] == 'alert_sent'
        assert events[0]['data']['channel'] == 'telegram'
        assert events[0]['data']['success'] is True

    def test_log_error(self, tmp_path):
        """Test logging error"""
        logger = AuditLogger(audit_dir=tmp_path)
        logger.log_error('test_error', 'Error message', {'context': 'test'})
        
        events = logger.read_audit_log()
        assert len(events) == 1
        assert events[0]['event_type'] == 'error'
        assert events[0]['level'] == 'ERROR'
        assert events[0]['data']['error_type'] == 'test_error'

    def test_read_audit_log_empty(self, tmp_path):
        """Test reading non-existent audit log"""
        logger = AuditLogger(audit_dir=tmp_path)
        
        # Read a different date
        past_date = datetime(2020, 1, 1)
        events = logger.read_audit_log(date=past_date)
        assert events == []

    def test_get_scan_statistics(self, tmp_path):
        """Test getting scan statistics"""
        logger = AuditLogger(audit_dir=tmp_path)
        
        # Log multiple events
        logger.log_scan_started('binance', 50, {})
        logger.log_scan_completed(ScanResult(
            scan_id='test-1',
            exchange='binance',
            total_pairs_scanned=50,
            total_setups_found=3,
            setups=[]
        ))
        logger.log_error('test_error', 'Error message')
        
        stats = logger.get_scan_statistics()
        
        assert stats['total_scans'] == 1
        assert stats['total_setups_found'] == 3
        assert stats['total_errors'] == 1
        assert 'binance' in stats['exchanges']

    def test_multiple_events(self, tmp_path):
        """Test logging multiple events"""
        logger = AuditLogger(audit_dir=tmp_path)
        
        for i in range(5):
            logger.log_event(f'event_{i}', {'index': i})
        
        events = logger.read_audit_log()
        assert len(events) == 5
