"""JSON output formatter for trade setups"""

import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from snipetrade.models import TradeSetup, ScanResult


class JSONFormatter:
    """Format and output trade setups as JSON"""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize JSON formatter
        
        Args:
            output_dir: Directory to save JSON files (optional)
        """
        self.output_dir = output_dir
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)

    def format_setup(self, setup: TradeSetup) -> Dict[str, Any]:
        """Format a single trade setup as JSON-serializable dict
        
        Args:
            setup: TradeSetup to format
            
        Returns:
            JSON-serializable dictionary
        """
        return setup.model_dump(mode='json')

    def format_scan_result(self, scan_result: ScanResult) -> Dict[str, Any]:
        """Format scan result as JSON-serializable dict
        
        Args:
            scan_result: ScanResult to format
            
        Returns:
            JSON-serializable dictionary
        """
        return scan_result.model_dump(mode='json')

    def save_setup(self, setup: TradeSetup, filename: Optional[str] = None) -> str:
        """Save trade setup to JSON file
        
        Args:
            setup: TradeSetup to save
            filename: Optional custom filename
            
        Returns:
            Path to saved file
        """
        if not self.output_dir:
            raise ValueError("Output directory not configured")
        
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"setup_{setup.symbol.replace('/', '_')}_{timestamp}.json"
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.format_setup(setup), f, indent=2)
        
        return str(filepath)

    def save_scan_result(self, scan_result: ScanResult, filename: Optional[str] = None) -> str:
        """Save scan result to JSON file
        
        Args:
            scan_result: ScanResult to save
            filename: Optional custom filename
            
        Returns:
            Path to saved file
        """
        if not self.output_dir:
            raise ValueError("Output directory not configured")
        
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"scan_{scan_result.scan_id}_{timestamp}.json"
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.format_scan_result(scan_result), f, indent=2)
        
        return str(filepath)

    def to_json_string(self, data: Any, pretty: bool = True) -> str:
        """Convert data to JSON string
        
        Args:
            data: Data to convert (TradeSetup, ScanResult, or dict)
            pretty: Whether to pretty-print with indentation
            
        Returns:
            JSON string
        """
        if isinstance(data, (TradeSetup, ScanResult)):
            data = data.model_dump(mode='json')
        
        if pretty:
            return json.dumps(data, indent=2)
        else:
            return json.dumps(data)
