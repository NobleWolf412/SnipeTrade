# SnipeTrade

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Modular Crypto Trade Scanner** with multi-timeframe confluence analysis, technical indicators, and liquidation heatmap integration.

## Features

- 🔍 **Multi-Exchange Support**: Binance, Bybit, and extensible architecture for more exchanges
- 📊 **Multi-Timeframe Analysis**: Confluence scoring across multiple timeframes (15m, 1h, 4h, etc.)
- 📈 **Technical Indicators**: RSI, MACD, EMA, Bollinger Bands, and more
- 🔥 **Liquidation Heatmap Integration**: Identify key liquidation zones
- 🎯 **Smart Scoring System**: Weighted scoring based on indicator alignment, timeframe confluence, and liquidation support
- 💬 **Telegram Alerts**: Real-time trade setup notifications
- 📝 **JSON Output**: Structured output with detailed reasoning for each trade setup
- 🔒 **Audit Logging**: Complete JSON-based audit trail of all scanner operations
- 🧪 **Comprehensive Tests**: Unit tests for all core modules
- 🏗️ **Modular Architecture**: Clean, scalable design ready for GUI/mobile integration

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/NobleWolf412/SnipeTrade.git
cd SnipeTrade
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install the package:
```bash
pip install -e .
```

## Quick Start

### 1. Initialize Configuration

Generate a default configuration file:

```bash
snipetrade init --output config/my_config.json
```

### 2. Configure Settings

Edit the configuration file to set your preferences:

```json
{
  "exchange": "binance",
  "exclude_stablecoins": true,
  "timeframes": ["15m", "1h", "4h"],
  "min_score": 50.0,
  "max_pairs": 50,
  "telegram_bot_token": "YOUR_BOT_TOKEN",
  "telegram_chat_id": "YOUR_CHAT_ID"
}
```

### 3. Run Scanner

```bash
# Run with default settings
snipetrade scan

# Run with custom config
snipetrade scan --config config/my_config.json

# Run with CLI overrides
snipetrade scan --exchange bybit --max-pairs 30 --min-score 60
```

### 4. Offline Backtest Harness

Run the lightweight harness that replays the bundled OHLCV cache and emits
Telegram-formatted notifications without requiring network access:

```bash
python tools/snp_backtest.py
```

This command leverages the cached Phemex data under `data/ohlcv_cache/` to
score sample symbols across the 15m/1h/4h timeframes and prints JSON-formatted
setups alongside the notification payload that would be delivered to Telegram.

## Configuration

### Basic Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `exchange` | string | "binance" | Exchange to scan (binance, bybit) |
| `exclude_stablecoins` | boolean | true | Exclude stablecoin-to-stablecoin pairs |
| `custom_exclude` | array | [] | Custom symbols to exclude |
| `timeframes` | array | ["15m", "1h", "4h"] | Timeframes for analysis |
| `min_score` | float | 50.0 | Minimum score threshold (0-100) |
| `max_pairs` | integer | 50 | Maximum pairs to scan |
| `max_workers` | integer | 5 | Parallel workers for scanning |
| `top_setups_limit` | integer | 10 | Number of top setups to return |

### Output Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `json_output_dir` | string | "./output" | Directory for JSON output files |
| `enable_audit` | boolean | true | Enable audit logging |
| `audit_dir` | string | "./audit_logs" | Directory for audit logs |

### Telegram Configuration

To receive trade alerts via Telegram:

1. **Get Telegram credentials** (see [docs/TELEGRAM_SETUP.md](docs/TELEGRAM_SETUP.md)):
   - Bot token from @BotFather
   - Your Chat ID

2. **Configure using .env file** (recommended):
   ```bash
   cp .env.example .env
   # Edit .env and add:
   TELEGRAM_BOT_TOKEN=your_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   ENABLE_NOTIFICATIONS=true
   ```

3. **Or use JSON config**:
   ```json
   {
     "telegram_bot_token": "123456789:ABC...",
     "telegram_chat_id": "123456789",
     "enable_notifications": true
   }
   ```

See [Telegram Setup Guide](docs/TELEGRAM_SETUP.md) for detailed instructions.

### Trading Configuration (Future Use)

The scanner is designed to support automated trading in the future. Configure these settings in preparation:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_trading` | boolean | false | Enable automated trading (not yet implemented) |
| `trading_mode` | string | "paper" | Trading mode: "paper" or "live" |
| `max_position_size_usd` | float | 1000.0 | Maximum position size in USD |
| `max_open_positions` | integer | 3 | Maximum concurrent positions |
| `risk_per_trade_percent` | float | 2.0 | Risk per trade as % of capital |

## Output Format

### JSON Output Structure

Each scan produces a JSON file with the following structure:

```json
{
  "scan_id": "uuid-here",
  "timestamp": "2024-01-01T00:00:00",
  "exchange": "binance",
  "total_pairs_scanned": 50,
  "total_setups_found": 5,
  "top_setups": [
    {
      "symbol": "BTC/USDT",
      "direction": "LONG",
      "score": 75.5,
      "confidence": 0.82,
      "entry_price": 50000.0,
      "timeframe_confluence": {
        "15m": "LONG",
        "1h": "LONG",
        "4h": "LONG"
      },
      "indicator_signals": [...],
      "liquidation_zones": [...],
      "reasons": [
        "RSI shows LONG signal (strength: 0.80) on 1h",
        "Multi-timeframe confluence across 15m, 1h, 4h",
        "Strong setup with high confidence score (75.5/100)"
      ]
    }
  ]
}
```

## Architecture

### Module Structure

```
src/snipetrade/
├── models.py              # Data models (Pydantic)
├── scanner.py             # Main scanner orchestrator
├── cli.py                 # Command-line interface
├── exchanges/
│   └── base.py           # Exchange connectors (CCXT)
├── filters/
│   └── pair_filter.py    # Pair filtering logic
├── indicators/
│   ├── calculator.py     # Technical indicators
│   └── liquidation.py    # Liquidation heatmap
├── scoring/
│   └── confluence.py     # Multi-timeframe scoring
└── output/
    ├── json_formatter.py # JSON output
    ├── telegram.py       # Telegram alerts
    └── audit.py          # Audit logging
```

### Extensibility

The modular design allows easy extension:

- **Add Exchange**: Extend `BaseExchange` class
- **Add Indicator**: Add method to `IndicatorCalculator`
- **Add Output Channel**: Create new module in `output/`
- **Custom Scoring**: Modify weights in `ConfluenceScorer`

## API for GUI/Mobile Integration

### Core Classes

```python
from snipetrade.scanner import TradeScanner
from snipetrade.models import ScanResult

# Initialize scanner
config = {
    "exchange": "binance",
    "max_pairs": 50,
    "min_score": 60.0
}
scanner = TradeScanner(config)

# Run scan
result: ScanResult = scanner.scan()

# Access results
for setup in result.top_setups:
    print(f"{setup.symbol}: {setup.score}")
```

### Key Classes for Integration

- `TradeScanner`: Main scanner orchestrator
- `ScanResult`: Complete scan results
- `TradeSetup`: Individual trade setup
- `JSONFormatter`: JSON serialization
- `AuditLogger`: Operation logging

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=snipetrade --cov-report=html

# Run specific test file
pytest tests/unit/test_scoring.py
```

## Development

### Project Structure

```
SnipeTrade/
├── src/snipetrade/        # Source code
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── config/               # Configuration examples
├── docs/                 # Documentation
├── requirements.txt      # Dependencies
└── setup.py             # Package setup
```

### Adding Features

1. Create feature branch
2. Implement in appropriate module
3. Add unit tests
4. Update documentation
5. Submit pull request

## Roadmap

- [ ] Additional exchanges (Kraken, Coinbase, etc.)
- [ ] Real liquidation heatmap API integration
- [ ] Volume profile analysis
- [ ] Order book depth analysis
- [ ] Machine learning signal enhancement
- [ ] Web dashboard GUI
- [ ] Mobile app (React Native)
- [ ] Backtesting framework
- [ ] Paper trading mode

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Disclaimer

This software is for educational purposes only. Trading cryptocurrencies carries risk. Always do your own research and never invest more than you can afford to lose.

## Support

- Issues: [GitHub Issues](https://github.com/NobleWolf412/SnipeTrade/issues)
- Discussions: [GitHub Discussions](https://github.com/NobleWolf412/SnipeTrade/discussions)
