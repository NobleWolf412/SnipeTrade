# API Documentation for GUI/Mobile Integration

This document describes the SnipeTrade API for building GUI applications or mobile apps.

## Table of Contents

1. [Core Classes](#core-classes)
2. [Scanner API](#scanner-api)
3. [Configuration API](#configuration-api)
4. [Data Models](#data-models)
5. [Output Modules](#output-modules)
6. [Example Integrations](#example-integrations)

## Core Classes

### TradeScanner

Main scanner class that orchestrates all scanning operations.

```python
from snipetrade.scanner import TradeScanner
from snipetrade.config import Config

# Initialize with Config object
config = Config(config_file='config/my_config.json')
scanner = TradeScanner(config)

# Or with dict
config_dict = {
    'exchange': 'binance',
    'max_pairs': 50,
    'min_score': 60.0
}
scanner = TradeScanner(config_dict)

# Run scan with progress callback
def on_progress(current, total, symbol):
    print(f"Scanning {symbol} ({current}/{total})")

result = scanner.scan(progress_callback=on_progress)

# Or use convenience method
result = scanner.run()  # Includes output
```

**Methods:**

- `scan(progress_callback=None) -> ScanResult`: Execute market scan
- `run() -> ScanResult`: Execute scan and output results
- `output_results(scan_result: ScanResult) -> None`: Output results to configured channels

### Config

Configuration management class with environment variable support.

```python
from snipetrade.config import Config

# Load from .env and JSON
config = Config(config_file='config/production.json')

# Access values
exchange = config.get('exchange')
max_pairs = config.get('max_pairs', default=50)

# Check features
if config.has_telegram_configured():
    print("Telegram is configured")

if config.is_trading_enabled():
    print("Trading is enabled")

# Validate configuration
issues = config.validate()
if issues:
    for issue in issues:
        print(f"Config issue: {issue}")

# Export as dict
config_dict = config.to_dict()
```

**Methods:**

- `get(key, default=None) -> Any`: Get configuration value
- `to_dict() -> Dict`: Export configuration as dictionary
- `has_telegram_configured() -> bool`: Check if Telegram is configured
- `is_trading_enabled() -> bool`: Check if trading is enabled
- `validate() -> List[str]`: Validate configuration and return issues

## Scanner API

### Scanning Flow

```python
from snipetrade.scanner import TradeScanner
from snipetrade.models import ScanResult, TradeSetup

# 1. Initialize scanner
scanner = TradeScanner(config)

# 2. Run scan
result: ScanResult = scanner.scan()

# 3. Access results
print(f"Found {result.total_setups_found} setups")

for setup in result.setups:
    print(f"{setup.symbol}: {setup.score:.1f}")
```

### Progress Monitoring

For UI applications, implement a progress callback:

```python
class ScanProgressTracker:
    def __init__(self, ui_updater):
        self.ui_updater = ui_updater
    
    def on_progress(self, current, total, symbol):
        progress_pct = (current / total) * 100
        self.ui_updater.update_progress(progress_pct, symbol)

tracker = ScanProgressTracker(my_ui)
result = scanner.scan(progress_callback=tracker.on_progress)
```

## Configuration API

### Configuration Structure

```python
{
    # Exchange settings
    "exchange": "phemex",  # or "binance"/"bybit"
    "exchange_config": {
        "apiKey": "...",
        "secret": "...",
        "enableRateLimit": true
    },
    
    # Scanning parameters
    "exclude_stablecoins": true,
    "custom_exclude": ["BNB", "FTM"],
    "timeframes": ["15m", "1h", "4h"],
    "min_score": 50.0,
    "max_pairs": 50,
    "max_workers": 5,
    "top_setups_limit": 10,
    
    # Output settings
    "json_output_dir": "./output",
    "enable_audit": true,
    "audit_dir": "./audit_logs",

    # Market data caching
    "markets_ttl_ms": 300000,
    "ohlcv_cache_ttl_ms": 120000,
    "fast_timeframe_ttl_ms": 900000,
    "slow_timeframe_ttl_ms": 3600000,
    
    # Telegram
    "telegram_bot_token": "...",
    "telegram_chat_id": "...",
    "enable_notifications": true,
    
    # Trading (future)
    "enable_trading": false,
    "trading_mode": "paper",
    "max_position_size_usd": 1000.0,
    "max_open_positions": 3,
    "risk_per_trade_percent": 2.0
}
```

### Environment Variables

All config values can be set via environment variables:

```bash
# Exchange
EXCHANGE=phemex
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
BYBIT_API_KEY=...
BYBIT_API_SECRET=...
PHEMEX_API_KEY=...
PHEMEX_API_SECRET=...

# Scanning
MAX_PAIRS=50
MIN_SCORE_THRESHOLD=60.0

# Market data caching
MARKETS_TTL_MS=300000
OHLCV_CACHE_TTL_MS=120000
FAST_TF_TTL=900000
SLOW_TF_TTL=3600000

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
ENABLE_NOTIFICATIONS=true

# Trading
ENABLE_TRADING=false
TRADING_MODE=paper
```

## Data Models

All models use Pydantic for validation and serialization.

### TradeSetup

Represents a complete trade setup with analysis.

```python
from snipetrade.models import TradeSetup

setup = TradeSetup(
    symbol='BTC/USDT',
    exchange='binance',
    direction='LONG',
    score=75.5,
    confidence=0.82,
    entry_plan=[50000.0, 49750.0],
    stop_loss=48500.0,
    take_profits=[51000.0, 52000.0],
    rr=2.0,
    timeframe_confluence={'15m': 'LONG', '1h': 'LONG'},
    indicator_summaries=[...],
    liquidation_zones=[...],
    reasons=['RSI oversold', 'Timeframe confluence'],
    metadata={'custom': 'data'}
)

# Serialize to JSON
json_dict = setup.model_dump(mode='json')

# Access fields
print(setup.symbol)
print(setup.direction)  # "LONG" or "SHORT"
print(setup.score)
```

**Key Fields:**

- `symbol`: Trading pair (e.g., "BTC/USDT")
- `exchange`: Exchange name
- `direction`: "LONG" or "SHORT"
- `score`: Overall score (0-100)
- `confidence`: Confidence level (0.0-1.0)
- `entry_plan`: List of entry price levels
- `stop_loss`: Protective stop price
- `take_profits`: List of take-profit targets
- `rr`: Risk-to-reward ratio
- `timeframe_confluence`: Dict of timeframe alignments
- `indicator_summaries`: List of summarized indicator readings
- `reasons`: List of human-readable reasons

### ScanResult

Complete scan results.

```python
from snipetrade.models import ScanResult

result = ScanResult(
    scan_id='uuid-here',
    exchange='binance',
    total_pairs_scanned=50,
    total_setups_found=5,
    setups=[setup1, setup2, ...],
    metadata={'config': {...}}
)

# Access results
print(f"Scanned {result.total_pairs_scanned} pairs")
print(f"Found {result.total_setups_found} setups")

for setup in result.setups:
    print(f"{setup.symbol}: {setup.score}")
```

### IndicatorSignal

Individual technical indicator signal.

```python
from snipetrade.models import IndicatorSignal, TradeDirection

signal = IndicatorSignal(
    name='RSI',
    value=28.5,
    signal=TradeDirection.LONG,
    strength=0.8,  # 0.0 to 1.0
    timeframe='1h',
    metadata={'period': 14}
)
```

## Output Modules

### JSON Formatter

```python
from snipetrade.output.json_formatter import JSONFormatter
from pathlib import Path

formatter = JSONFormatter(output_dir=Path('./output'))

# Format setup
json_dict = formatter.format_setup(setup)

# Save to file
filepath = formatter.save_setup(setup)
filepath = formatter.save_scan_result(result)

# Get JSON string
json_str = formatter.to_json_string(setup, pretty=True)
```

### Telegram Notifier

```python
from snipetrade.output.telegram import TelegramNotifier

notifier = TelegramNotifier(
    bot_token='YOUR_BOT_TOKEN',
    chat_id='YOUR_CHAT_ID'
)

# Send setup alert
success = notifier.send_setup_alert_sync(setup)

# Send scan summary
success = notifier.send_scan_summary_sync(result)

# Send multiple
count = await notifier.send_multiple_alerts(setups, max_alerts=5)
```

### Audit Logger

```python
from snipetrade.output.audit import AuditLogger
from pathlib import Path

logger = AuditLogger(audit_dir=Path('./audit_logs'))

# Log events
logger.log_scan_started('binance', 50, config)
logger.log_setup_found(setup)
logger.log_scan_completed(result)

# Read logs
events = logger.read_audit_log()
stats = logger.get_scan_statistics()

print(f"Total scans: {stats['total_scans']}")
print(f"Total setups: {stats['total_setups_found']}")
```

## Example Integrations

### Simple Python GUI (Tkinter)

```python
import tkinter as tk
from tkinter import ttk
from snipetrade.scanner import TradeScanner
from snipetrade.config import Config

class ScannerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SnipeTrade Scanner")
        
        # Progress bar
        self.progress = ttk.Progressbar(root, length=300)
        self.progress.pack(pady=10)
        
        # Status label
        self.status = tk.Label(root, text="Ready")
        self.status.pack(pady=5)
        
        # Start button
        self.btn = tk.Button(root, text="Start Scan", command=self.start_scan)
        self.btn.pack(pady=10)
        
        # Results
        self.results_text = tk.Text(root, width=60, height=20)
        self.results_text.pack(pady=10)
    
    def update_progress(self, current, total, symbol):
        progress_pct = (current / total) * 100
        self.progress['value'] = progress_pct
        self.status['text'] = f"Scanning {symbol} ({current}/{total})"
        self.root.update()
    
    def start_scan(self):
        self.btn['state'] = 'disabled'
        self.results_text.delete(1.0, tk.END)
        
        # Run scan
        config = Config()
        scanner = TradeScanner(config)
        result = scanner.scan(progress_callback=self.update_progress)
        
        # Display results
        self.results_text.insert(tk.END, f"Found {result.total_setups_found} setups\n\n")
        for setup in result.setups:
            entries = ', '.join(f"${price:.2f}" for price in setup.entry_plan)
            targets = ', '.join(f"${tp:.2f}" for tp in setup.take_profits)
            self.results_text.insert(tk.END,
                f"{setup.symbol} - {setup.direction}\n"
                f"  Score: {setup.score:.1f}\n"
                f"  Entries: {entries}\n"
                f"  Stop: ${setup.stop_loss:.2f} | Targets: {targets}\n\n"
            )
        
        self.btn['state'] = 'normal'
        self.status['text'] = "Complete!"

# Run
root = tk.ROOT()
app = ScannerGUI(root)
root.mainloop()
```

### React Native Integration

```javascript
// Scanner API wrapper for React Native
import { NativeModules } from 'react-native';

class SnipeTradeAPI {
  async runScan(config) {
    const result = await NativeModules.SnipeTrade.runScan(config);
    return result;
  }
  
  async getStatus() {
    return await NativeModules.SnipeTrade.getStatus();
  }
}

// Usage in component
const ScannerScreen = () => {
  const [scanning, setScanning] = useState(false);
  const [results, setResults] = useState(null);
  
  const runScan = async () => {
    setScanning(true);
    const config = {
      exchange: 'binance',
      maxPairs: 30,
      minScore: 60
    };
    
    const result = await api.runScan(config);
    setResults(result);
    setScanning(false);
  };
  
  return (
    <View>
      <Button title="Start Scan" onPress={runScan} disabled={scanning} />
      {results && (
        <FlatList
          data={results.topSetups}
          renderItem={({item}) => <TradeSetupCard setup={item} />}
        />
      )}
    </View>
  );
};
```

### Web Dashboard (Flask + JavaScript)

```python
# Backend API endpoint
from flask import Flask, jsonify
from snipetrade.scanner import TradeScanner
from snipetrade.config import Config

app = Flask(__name__)

@app.route('/api/scan', methods=['POST'])
def start_scan():
    config = Config()
    scanner = TradeScanner(config)
    result = scanner.scan()
    
    return jsonify({
        'scan_id': result.scan_id,
        'total_found': result.total_setups_found,
        'setups': [s.model_dump(mode='json') for s in result.setups]
    })

@app.route('/api/status')
def get_status():
    # Return scanner status
    return jsonify({'status': 'ready'})
```

```javascript
// Frontend
async function startScan() {
  const response = await fetch('/api/scan', {method: 'POST'});
  const data = await response.json();
  
  // Display results
  displayResults(data.setups);
}
```

## Best Practices

1. **Always validate configuration** before running scans
2. **Use progress callbacks** for better UX in GUI applications
3. **Handle exceptions** gracefully
4. **Cache results** when appropriate
5. **Respect API rate limits** when scanning
6. **Use audit logging** for production deployments
7. **Secure credentials** - never hardcode API keys

## Future Features

- WebSocket support for real-time updates
- Trading execution API
- Backtesting API
- Portfolio management
- Risk management hooks
- Custom indicator plugins
