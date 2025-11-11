"""JSON-based audit module for tracking scanner operations"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from snipetrade.models import ScanResult, TradeSetup


class AuditLogger:
    """JSON-based audit logger for scanner operations"""

    def __init__(self, audit_dir: Path = None):
        """Initialize audit logger
        
        Args:
            audit_dir: Directory to store audit logs
        """
        self.audit_dir = audit_dir or Path("./audit_logs")
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        
        # Current audit file
        date_str = datetime.utcnow().strftime("%Y%m%d")
        self.current_file = self.audit_dir / f"audit_{date_str}.jsonl"

    def log_event(self, event_type: str, data: Dict[str, Any], 
                   level: str = "INFO") -> None:
        """Log an audit event
        
        Args:
            event_type: Type of event (e.g., 'scan_started', 'setup_found')
            data: Event data
            level: Log level (INFO, WARNING, ERROR)
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "level": level,
            "data": data
        }
        
        with open(self.current_file, 'a') as f:
            f.write(json.dumps(event) + '\n')

    def log_scan_started(self, exchange: str, num_pairs: int, 
                          config: Dict[str, Any]) -> None:
        """Log scan start event
        
        Args:
            exchange: Exchange being scanned
            num_pairs: Number of pairs to scan
            config: Scanner configuration
        """
        self.log_event("scan_started", {
            "exchange": exchange,
            "num_pairs": num_pairs,
            "config": config
        })

    def log_scan_completed(self, scan_result: ScanResult) -> None:
        """Log scan completion event
        
        Args:
            scan_result: Complete scan result
        """
        self.log_event("scan_completed", {
            "scan_id": scan_result.scan_id,
            "exchange": scan_result.exchange,
            "total_pairs_scanned": scan_result.total_pairs_scanned,
            "total_setups_found": scan_result.total_setups_found,
            "top_setup_count": len(scan_result.top_setups)
        })

    def log_setup_found(self, setup: TradeSetup) -> None:
        """Log trade setup found event
        
        Args:
            setup: Trade setup that was found
        """
        self.log_event("setup_found", {
            "symbol": setup.symbol,
            "exchange": setup.exchange,
            "direction": setup.direction.value,
            "score": setup.score,
            "confidence": setup.confidence
        })

    def log_alert_sent(self, setup: TradeSetup, channel: str, 
                        success: bool) -> None:
        """Log alert sent event
        
        Args:
            setup: Trade setup that was alerted
            channel: Alert channel (e.g., 'telegram', 'discord')
            success: Whether alert was sent successfully
        """
        level = "INFO" if success else "WARNING"
        self.log_event("alert_sent", {
            "symbol": setup.symbol,
            "direction": setup.direction.value,
            "score": setup.score,
            "channel": channel,
            "success": success
        }, level=level)

    def log_error(self, error_type: str, error_message: str, 
                   context: Optional[Dict[str, Any]] = None) -> None:
        """Log error event
        
        Args:
            error_type: Type of error
            error_message: Error message
            context: Additional context
        """
        self.log_event("error", {
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {}
        }, level="ERROR")

    def read_audit_log(self, date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Read audit log for a specific date
        
        Args:
            date: Date to read (default: today)
            
        Returns:
            List of audit events
        """
        if date is None:
            date = datetime.utcnow()
        
        date_str = date.strftime("%Y%m%d")
        log_file = self.audit_dir / f"audit_{date_str}.jsonl"
        
        if not log_file.exists():
            return []
        
        events = []
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    events.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        
        return events

    def get_scan_statistics(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get statistics from audit logs
        
        Args:
            date: Date to analyze (default: today)
            
        Returns:
            Statistics dictionary
        """
        events = self.read_audit_log(date)
        
        stats = {
            "total_scans": 0,
            "total_setups_found": 0,
            "total_alerts_sent": 0,
            "total_errors": 0,
            "exchanges": set(),
            "event_counts": {}
        }
        
        for event in events:
            event_type = event.get("event_type")
            
            # Count event types
            stats["event_counts"][event_type] = stats["event_counts"].get(event_type, 0) + 1
            
            # Specific event processing
            if event_type == "scan_completed":
                stats["total_scans"] += 1
                stats["total_setups_found"] += event["data"].get("total_setups_found", 0)
                stats["exchanges"].add(event["data"].get("exchange", "unknown"))
            
            elif event_type == "alert_sent" and event["data"].get("success"):
                stats["total_alerts_sent"] += 1
            
            elif event_type == "error":
                stats["total_errors"] += 1
        
        stats["exchanges"] = list(stats["exchanges"])
        
        return stats
