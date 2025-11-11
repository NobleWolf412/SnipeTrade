# SnipeTrade Quick Start Guide

Get started with SnipeTrade crypto scanner in 5 minutes!

## Installation

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/NobleWolf412/SnipeTrade.git
cd SnipeTrade

# Install dependencies
pip install -r requirements.txt

# Install package
pip install -e .
```

### 2. Quick Test

```bash
# Test the CLI
snipetrade --help

# Generate default configuration
snipetrade init

# View configuration
cat config/default.json
```

## Basic Usage

### Scan Without Telegram (Demo Mode)

```bash
# Run a basic scan (no telegram alerts)
snipetrade scan --max-pairs 10 --min-score 40

# Scan specific exchange
snipetrade scan --exchange bybit --max-pairs 20

# Save output to custom directory
snipetrade scan --output ./my_results
```

### Configuration File

Create `config/my_config.json`:

```json
{
  "exchange": "binance",
  "max_pairs": 50,
  "min_score": 55.0,
  "timeframes": ["15m", "1h", "4h"],
  "json_output_dir": "./output"
}
```

Run with config:

```bash
snipetrade scan --config config/my_config.json
```

## Telegram Setup (Recommended)

### 1. Get Telegram Credentials

1. Open Telegram and find **@BotFather**
2. Create a bot: `/newbot`
3. Save your bot token (looks like: `123456:ABC...xyz`)
4. Get your chat ID from **@userinfobot**

See [docs/TELEGRAM_SETUP.md](docs/TELEGRAM_SETUP.md) for detailed instructions.

### 2. Configure Telegram

**Option A: Environment Variables (Recommended)**

```bash
# Copy example
cp .env.example .env

# Edit .env and add:
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
ENABLE_NOTIFICATIONS=true
```

**Option B: Command Line**

```bash
snipetrade scan \
  --telegram-token "your_bot_token" \
  --telegram-chat-id "your_chat_id"
```

**Option C: Configuration File**

```json
{
  "telegram_bot_token": "your_token",
  "telegram_chat_id": "your_chat_id",
  "enable_notifications": true
}
```

### 3. Test Telegram

```bash
# Run scan with telegram alerts
snipetrade scan --max-pairs 10
```

You should receive:
- A scan summary message
- Individual alerts for top setups

## Output

### JSON Output

Results are saved to `./output/` directory:

```bash
ls output/
# scan_<id>_<timestamp>.json

cat output/scan_*.json | jq '.setups[0]'
```

### Audit Logs

All scanner operations are logged to `./audit_logs/`:

```bash
ls audit_logs/
# audit_<date>.jsonl

# View today's audit log
cat audit_logs/audit_$(date +%Y%m%d).jsonl | jq '.'
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=snipetrade --cov-report=html

# Run specific test category
pytest tests/unit/
pytest tests/integration/
```

## Python API Usage

```python
from snipetrade.scanner import TradeScanner
from snipetrade.config import Config

# Load configuration
config = Config()

# Create scanner
scanner = TradeScanner(config)

# Run scan
result = scanner.scan()

# Access results
print(f"Found {result.total_setups_found} setups")
for setup in result.setups:
    print(f"{setup.symbol}: Score {setup.score:.1f}")
```

## Demo Script

```bash
# Run interactive demo
python demo.py
```

The demo shows:
- Configuration system
- Output formats (JSON, Telegram)
- Live scan example

## Common Issues

### "Module not found" Error

```bash
# Make sure package is installed
pip install -e .
```

### CCXT Connection Issues

```bash
# Install/update ccxt
pip install --upgrade ccxt
```

### Telegram "Unauthorized" Error

- Check bot token is correct
- Ensure no extra spaces in token
- Verify you've messaged the bot first

### No Setups Found

- Lower `min_score` threshold
- Increase `max_pairs`
- Try different timeframes
- Check exchange connectivity

## Next Steps

1. **Configure Telegram** - Get real-time alerts
2. **Customize Scoring** - Adjust weights in `src/snipetrade/scoring/confluence.py`
3. **Add Exchanges** - Extend `BaseExchange` class
4. **Build GUI** - See `docs/API_DOCUMENTATION.md`
5. **Integrate Trading** - Structure is ready for automated trading

## Configuration Reference

### Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `exchange` | binance | Exchange to scan |
| `max_pairs` | 50 | Number of pairs to scan |
| `min_score` | 50.0 | Minimum score (0-100) |
| `timeframes` | [15m,1h,4h] | Analysis timeframes |
| `max_workers` | 5 | Parallel workers |
| `top_setups_limit` | 10 | Top results to return |

### Environment Variables

```bash
# Exchange
EXCHANGE=binance
MAX_PAIRS=50
MIN_SCORE_THRESHOLD=55.0

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
ENABLE_NOTIFICATIONS=true

# Output
JSON_OUTPUT_DIR=./output
ENABLE_AUDIT=true
```

## Support

- **Issues**: [GitHub Issues](https://github.com/NobleWolf412/SnipeTrade/issues)
- **Docs**: See `docs/` directory
- **API**: See `docs/API_DOCUMENTATION.md`
- **Tests**: `pytest -v`

## Safety Reminder

⚠️ This is a **scanning tool** only. It does not execute trades.

For future trading integration:
- Always test with paper trading first
- Start with small position sizes
- Never risk more than you can afford to lose
- Do your own research

---

**Happy Scanning! 🚀**
