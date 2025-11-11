"""Command-line interface for SnipeTrade scanner"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any
from snipetrade.scanner import TradeScanner
from snipetrade.config import (
    Config,
    DEFAULT_EXCHANGE,
    DEFAULT_TIMEFRAMES,
    MARKETS_TTL_MS,
    OHLCV_CACHE_TTL_MS,
    FAST_TF_TTL,
    SLOW_TF_TTL,
)
from snipetrade import __version__


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        return json.load(f)


def create_default_config() -> Dict[str, Any]:
    """Create default configuration
    
    Returns:
        Default configuration dictionary
    """
    return {
        "exchange": DEFAULT_EXCHANGE,
        "exchange_config": {},
        "exclude_stablecoins": True,
        "custom_exclude": [],
        "timeframes": DEFAULT_TIMEFRAMES,
        "min_score": 50.0,
        "max_pairs": 50,
        "max_workers": 5,
        "top_setups_limit": 10,
        "json_output_dir": "./output",
        "enable_audit": True,
        "audit_dir": "./audit_logs",
        "markets_ttl_ms": MARKETS_TTL_MS,
        "ohlcv_cache_ttl_ms": OHLCV_CACHE_TTL_MS,
        "fast_timeframe_ttl_ms": FAST_TF_TTL,
        "slow_timeframe_ttl_ms": SLOW_TF_TTL,
        "adapter_cache_ttl": {
            "markets": 3600,
            "tickers": 30,
            "ohlcv": 60,
        },
        "timeframe_cache_ttl": 300,
    }


def save_default_config(output_path: str) -> None:
    """Save default configuration to file
    
    Args:
        output_path: Path to save configuration
    """
    config = create_default_config()
    config_file = Path(output_path)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Default configuration saved to: {output_path}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="SnipeTrade - Modular Crypto Trade Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run scan with default config
  snipetrade scan
  
  # Run scan with custom config
  snipetrade scan --config config/my_config.json
  
  # Generate default config file
  snipetrade init --output config/default.json
  
  # Scan specific exchange
  snipetrade scan --exchange bybit --max-pairs 30
        """
    )
    
    parser.add_argument('--version', action='version', version=f'SnipeTrade {__version__}')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Run trade scanner')
    scan_parser.add_argument('--config', '-c', type=str, help='Path to configuration file')
    scan_parser.add_argument('--exchange', '-e', type=str, help='Exchange to scan (phemex, binance, bybit)')
    scan_parser.add_argument('--max-pairs', '-n', type=int, help='Maximum number of pairs to scan')
    scan_parser.add_argument('--min-score', '-s', type=float, help='Minimum score threshold')
    scan_parser.add_argument('--output', '-o', type=str, help='Output directory for results')
    scan_parser.add_argument('--telegram-token', type=str, help='Telegram bot token')
    scan_parser.add_argument('--telegram-chat-id', type=str, help='Telegram chat ID')
    scan_parser.add_argument('--adapter-ttl-markets', type=int, help='Override adapter market TTL (seconds)')
    scan_parser.add_argument('--adapter-ttl-tickers', type=int, help='Override adapter ticker TTL (seconds)')
    scan_parser.add_argument('--adapter-ttl-ohlcv', type=int, help='Override adapter OHLCV TTL (seconds)')
    scan_parser.add_argument('--timeframe-cache-ttl', type=int, help='Override timeframe data cache TTL (seconds)')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize default configuration')
    init_parser.add_argument('--output', '-o', type=str, default='config/default.json',
                              help='Output path for configuration file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # Handle commands
    if args.command == 'init':
        save_default_config(args.output)
        
    elif args.command == 'scan':
        # Load configuration using Config class
        config_obj = Config(config_file=args.config)
        
        # Override with CLI arguments
        config_dict = config_obj.to_dict()
        if args.exchange:
            config_dict['exchange'] = args.exchange
        if args.max_pairs:
            config_dict['max_pairs'] = args.max_pairs
        if args.min_score:
            config_dict['min_score'] = args.min_score
        if args.output:
            config_dict['json_output_dir'] = args.output
        if args.telegram_token:
            config_dict['telegram_bot_token'] = args.telegram_token
        if args.telegram_chat_id:
            config_dict['telegram_chat_id'] = args.telegram_chat_id
        if args.adapter_ttl_markets is not None:
            config_dict.setdefault('adapter_cache_ttl', {})['markets'] = args.adapter_ttl_markets
        if args.adapter_ttl_tickers is not None:
            config_dict.setdefault('adapter_cache_ttl', {})['tickers'] = args.adapter_ttl_tickers
        if args.adapter_ttl_ohlcv is not None:
            config_dict.setdefault('adapter_cache_ttl', {})['ohlcv'] = args.adapter_ttl_ohlcv
        if args.timeframe_cache_ttl is not None:
            config_dict['timeframe_cache_ttl'] = args.timeframe_cache_ttl

        # Rebuild config with overrides
        if args.config or any([
            args.exchange,
            args.max_pairs,
            args.min_score,
            args.output,
            args.telegram_token,
            args.telegram_chat_id,
            args.adapter_ttl_markets,
            args.adapter_ttl_tickers,
            args.adapter_ttl_ohlcv,
            args.timeframe_cache_ttl,
        ]):
            # Create temp JSON for override handling
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(config_dict, f)
                temp_config_path = f.name
            config_obj = Config(config_file=temp_config_path)
            Path(temp_config_path).unlink()
        
        # Validate configuration
        issues = config_obj.validate()
        if issues:
            print("⚠️  Configuration Issues:")
            for issue in issues:
                if "WARNING" in issue:
                    print(f"   ⚠️  {issue}")
                else:
                    print(f"   ❌ {issue}")
            
            # Exit on errors (not warnings)
            has_errors = any("WARNING" not in issue for issue in issues)
            if has_errors:
                print("\n❌ Please fix configuration errors before running.")
                sys.exit(1)
            else:
                print("\n⚠️  Continuing with warnings...\n")
        
        # Show Telegram configuration status
        if config_obj.has_telegram_configured():
            print(f"✓ Telegram notifications enabled")
            print(f"  Bot token: {config_obj.get('telegram_bot_token')[:20]}...")
            print(f"  Chat ID: {config_obj.get('telegram_chat_id')}")
        else:
            print("ℹ️  Telegram notifications disabled (no credentials configured)")
            print(f"  See docs/TELEGRAM_SETUP.md for setup instructions\n")
        
        # Create and run scanner
        try:
            print(f"Starting SnipeTrade Scanner v{__version__}")
            print(f"Exchange: {config_obj.get('exchange')}")
            print(f"Max Pairs: {config_obj.get('max_pairs')}")
            print(f"Min Score: {config_obj.get('min_score')}")
            print("-" * 60)
            
            scanner = TradeScanner(config_obj)
            result = scanner.run()
            
            print(f"\n{'='*60}")
            print("✓ Scan completed successfully!")
            print(f"{'='*60}")
            
        except KeyboardInterrupt:
            print("\nScan interrupted by user")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
