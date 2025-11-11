"""Configuration loader for SnipeTrade"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Cache configuration defaults exposed at module level for easy reuse
DEFAULT_OHLCV_CACHE_DIR = Path(".cache") / "ohlcv"
OHLCV_CACHE_DIR = Path(os.getenv("OHLCV_CACHE_DIR", str(DEFAULT_OHLCV_CACHE_DIR)))
OHLCV_CACHE_TTL_MS = int(os.getenv("OHLCV_CACHE_TTL_MS", "300000"))
OHLCV_CACHE_FORMAT = os.getenv("OHLCV_CACHE_FORMAT", "parquet").lower()


DEFAULT_EXCHANGE = "phemex"
DEFAULT_TIMEFRAMES = ["15m", "1h", "4h"]
MARKETS_TTL_MS = 5 * 60 * 1000  # 5 minutes
OHLCV_CACHE_TTL_MS = 2 * 60 * 1000  # 2 minutes
FAST_TF_TTL = 15 * 60 * 1000  # 15 minutes
SLOW_TF_TTL = 60 * 60 * 1000  # 1 hour

# --- Autotrade master switch ---
AUTOTRADE_ENABLED = False            # default OFF
AUTOTRADE_MODE = "paper"             # "paper" | "live25" | "live50" | "live100"

# --- Policy / brakes ---
MAX_CONCURRENT_TRADES = 3
DAILY_RISK_USD_LIMIT = 300           # stop if daily realized loss exceeds
PER_TRADE_RISK_USD = 50              # overrides batch if needed
PER_SYMBOL_EXPOSURE_USD_MAX = 1500
TOTAL_EXPOSURE_USD_MAX = 4000
ALLOWLIST_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
TRADING_WINDOWS_UTC = ["07:00-20:00"]    # only place during these windows
BLOCKLIST_DAYS = []                      # e.g. ["2025-12-25"]

# --- Execution behavior ---
POST_ONLY_DEFAULT = True
MAKER_TIMEOUT_SEC = 90                  # switch to stop-entry after
AMEND_ON_DRIFT_BPS = 8                  # reprice maker if best changes by N bps
CANCEL_ON_TIMEOUT_SEC = 600             # hard cancel stale orders
RETRY_BACKOFF_MS = [400, 800, 1600]     # transient failures

# --- Compliance / audit ---
IDEMPOTENCY_PREFIX = "snp_v1_"
LOG_REDACT_KEYS = True


class Config:
    """Configuration manager for SnipeTrade
    
    Loads configuration from:
    1. Environment variables (.env file)
    2. JSON configuration file
    3. Default values
    """

    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration
        
        Args:
            config_file: Optional path to JSON config file
        """
        # Load environment variables
        load_dotenv()
        
        # Load JSON config if provided
        self.json_config = {}
        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                self.json_config = json.load(f)
        
        # Build complete config
        self.config = self._build_config()

    def _build_config(self) -> Dict[str, Any]:
        """Build configuration from all sources
        
        Priority: ENV vars > JSON config > Defaults
        """
        markets_ttl_ms = self._get_int('MARKETS_TTL_MS', MARKETS_TTL_MS)
        ohlcv_cache_ttl_ms = self._get_int('OHLCV_CACHE_TTL_MS', OHLCV_CACHE_TTL_MS)
        fast_timeframe_ttl_ms = self._get_int('FAST_TF_TTL', FAST_TF_TTL)
        slow_timeframe_ttl_ms = self._get_int('SLOW_TF_TTL', SLOW_TF_TTL)

        config = {
            # Exchange settings
            'exchange': self._get('EXCHANGE', DEFAULT_EXCHANGE),
            'exchange_config': self._get_exchange_config(
                markets_ttl_ms=markets_ttl_ms,
                ohlcv_cache_ttl_ms=ohlcv_cache_ttl_ms,
                fast_timeframe_ttl_ms=fast_timeframe_ttl_ms,
                slow_timeframe_ttl_ms=slow_timeframe_ttl_ms,
            ),
            'markets_ttl_ms': markets_ttl_ms,
            'ohlcv_cache_ttl_ms': ohlcv_cache_ttl_ms,
            'fast_timeframe_ttl_ms': fast_timeframe_ttl_ms,
            'slow_timeframe_ttl_ms': slow_timeframe_ttl_ms,

            # Scanning settings
            'exclude_stablecoins': self._get_bool('EXCLUDE_STABLECOINS', True),
            'custom_exclude': self._get_list('CUSTOM_EXCLUDE', []),
            'timeframes': self._get_list('TIMEFRAMES', DEFAULT_TIMEFRAMES),
            'min_score': self._get_float('MIN_SCORE_THRESHOLD', 50.0),
            'max_pairs': self._get_int('MAX_PAIRS', 50),
            'max_workers': self._get_int('MAX_WORKERS', 5),
            'top_setups_limit': self._get_int('TOP_SETUPS_LIMIT', 10),
            
            # Output settings
            'json_output_dir': self._get('JSON_OUTPUT_DIR', './output'),
            'enable_audit': self._get_bool('ENABLE_AUDIT', True),
            'audit_dir': self._get('AUDIT_DIR', './audit_logs'),
            
            # Telegram settings
            'telegram_bot_token': self._get('TELEGRAM_BOT_TOKEN'),
            'telegram_chat_id': self._get('TELEGRAM_CHAT_ID'),
            'enable_notifications': self._get_bool('ENABLE_NOTIFICATIONS', True),

            # Trading settings (for future use)
            'enable_trading': self._get_bool('ENABLE_TRADING', False),
            'trading_mode': self._get('TRADING_MODE', 'paper'),  # paper or live
            'max_position_size_usd': self._get_float('MAX_POSITION_SIZE_USD', 1000.0),
            'max_open_positions': self._get_int('MAX_OPEN_POSITIONS', 3),
            'risk_per_trade_percent': self._get_float('RISK_PER_TRADE_PERCENT', 2.0),

            # Data caching
            'ohlcv_cache_dir': self._get('OHLCV_CACHE_DIR', str(OHLCV_CACHE_DIR)),
            'ohlcv_cache_ttl_ms': self._get_int('OHLCV_CACHE_TTL_MS', OHLCV_CACHE_TTL_MS),
            'ohlcv_cache_format': self._get('OHLCV_CACHE_FORMAT', OHLCV_CACHE_FORMAT),
        }

        return config

    def _get_exchange_config(
        self,
        *,
        markets_ttl_ms: int,
        ohlcv_cache_ttl_ms: int,
        fast_timeframe_ttl_ms: int,
        slow_timeframe_ttl_ms: int,
    ) -> Dict[str, Any]:
        """Get exchange-specific configuration including API keys"""
        exchange = self._get('EXCHANGE', DEFAULT_EXCHANGE).lower()

        exchange_config = {
            'enableRateLimit': True,
        }

        # TTL controls for adapters that implement caching
        exchange_config.setdefault('markets_ttl_ms', markets_ttl_ms)
        exchange_config.setdefault('ohlcv_cache_ttl_ms', ohlcv_cache_ttl_ms)
        exchange_config.setdefault('fast_timeframe_ttl_ms', fast_timeframe_ttl_ms)
        exchange_config.setdefault('slow_timeframe_ttl_ms', slow_timeframe_ttl_ms)

        # Add API credentials if available
        if exchange == 'binance':
            api_key = self._get('BINANCE_API_KEY')
            api_secret = self._get('BINANCE_API_SECRET')
            if api_key and api_secret:
                exchange_config['apiKey'] = api_key
                exchange_config['secret'] = api_secret

        elif exchange == 'bybit':
            api_key = self._get('BYBIT_API_KEY')
            api_secret = self._get('BYBIT_API_SECRET')
            if api_key and api_secret:
                exchange_config['apiKey'] = api_key
                exchange_config['secret'] = api_secret

        elif exchange == 'phemex':
            api_key = self._get('PHEMEX_API_KEY')
            api_secret = self._get('PHEMEX_API_SECRET')
            if api_key and api_secret:
                exchange_config['apiKey'] = api_key
                exchange_config['secret'] = api_secret

        # Merge with JSON config if present
        json_exchange_config = self.json_config.get('exchange_config', {})
        exchange_config.update(json_exchange_config)

        return exchange_config

    def _get(self, key: str, default: Any = None) -> Any:
        """Get configuration value
        
        Priority: ENV var > JSON config > default
        """
        # Check environment variable
        env_value = os.getenv(key)
        if env_value is not None:
            return env_value
        
        # Check JSON config (lowercase key)
        json_key = key.lower()
        if json_key in self.json_config:
            return self.json_config[json_key]
        
        return default

    def _get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value"""
        value = self._get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value"""
        value = self._get(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value"""
        value = self._get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return default

    def _get_list(self, key: str, default: list = None) -> list:
        """Get list configuration value"""
        value = self._get(key, default or [])
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Parse comma-separated string
            return [item.strip() for item in value.split(',') if item.strip()]
        return default or []

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        return self.config.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary"""
        return self.config.copy()

    def is_trading_enabled(self) -> bool:
        """Check if trading is enabled"""
        return self.config.get('enable_trading', False)

    def is_live_trading(self) -> bool:
        """Check if live trading mode is enabled"""
        return (
            self.config.get('enable_trading', False) and
            self.config.get('trading_mode', 'paper') == 'live'
        )

    def has_telegram_configured(self) -> bool:
        """Check if Telegram is properly configured"""
        return bool(
            self.config.get('telegram_bot_token') and
            self.config.get('telegram_chat_id')
        )

    def validate(self) -> list:
        """Validate configuration and return list of issues
        
        Returns:
            List of validation error messages (empty if valid)
        """
        issues = []
        
        # Check Telegram config if notifications enabled
        if self.config.get('enable_notifications'):
            if not self.has_telegram_configured():
                issues.append(
                    "Telegram notifications enabled but bot_token or chat_id missing"
                )
        
        # Check trading configuration
        if self.is_trading_enabled():
            exchange_config = self.config.get('exchange_config', {})
            if not exchange_config.get('apiKey') or not exchange_config.get('secret'):
                issues.append(
                    "Trading enabled but exchange API credentials not configured"
                )
            
            if self.is_live_trading():
                issues.append(
                    "WARNING: Live trading mode enabled! This will execute real trades."
                )
        
        # Validate numeric ranges
        if self.config.get('min_score', 0) < 0 or self.config.get('min_score', 0) > 100:
            issues.append("min_score must be between 0 and 100")
        
        if self.config.get('max_pairs', 0) < 1:
            issues.append("max_pairs must be at least 1")
        
        return issues
