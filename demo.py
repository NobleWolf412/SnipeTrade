"""Demo script showing SnipeTrade scanner capabilities"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from snipetrade.config import Config
from snipetrade.scanner import TradeScanner
from snipetrade.output.json_formatter import JSONFormatter


def demo_basic_scan():
    """Demo: Basic scanner usage with minimal configuration"""
    print("=" * 70)
    print("DEMO: Basic SnipeTrade Scanner")
    print("=" * 70)
    
    # Create simple configuration
    config = {
        'exchange': 'binance',
        'max_pairs': 10,  # Small number for demo
        'min_score': 40.0,  # Lower threshold for demo
        'max_workers': 3,
        'json_output_dir': '/tmp/snipetrade_output',
        'enable_audit': True,
        'audit_dir': '/tmp/snipetrade_audit',
        'enable_notifications': False,  # Disabled for demo
        'top_setups_limit': 5
    }
    
    print("\nConfiguration:")
    print(f"  Exchange: {config['exchange']}")
    print(f"  Max Pairs: {config['max_pairs']}")
    print(f"  Min Score: {config['min_score']}")
    print(f"  Telegram: Disabled (demo mode)")
    
    print("\nStarting scan...\n")
    
    try:
        # Create scanner
        scanner = TradeScanner(config)
        
        # Run scan
        result = scanner.run()
        
        # Display results
        print("\n" + "=" * 70)
        print("SCAN RESULTS")
        print("=" * 70)
        print(f"Scan ID: {result.scan_id}")
        print(f"Exchange: {result.exchange}")
        print(f"Pairs Scanned: {result.total_pairs_scanned}")
        print(f"Setups Found: {result.total_setups_found}")
        
        if result.top_setups:
            print(f"\nTop {len(result.top_setups)} Trade Setups:")
            print("-" * 70)
            
            for i, setup in enumerate(result.top_setups, 1):
                print(f"\n{i}. {setup.symbol} - {setup.direction.value}")
                print(f"   Score: {setup.score:.1f}/100")
                print(f"   Confidence: {setup.confidence:.1%}")
                print(f"   Entry Price: ${setup.entry_price:.2f}")
                
                if setup.timeframe_confluence:
                    aligned = [tf for tf, d in setup.timeframe_confluence.items() 
                              if d == setup.direction]
                    if aligned:
                        print(f"   Timeframe Alignment: {', '.join(aligned)}")
                
                if setup.reasons:
                    print(f"   Top Reason: {setup.reasons[0][:80]}...")
        else:
            print("\nNo setups found matching criteria.")
            print("Try lowering min_score or increasing max_pairs.")
        
        print("\n" + "=" * 70)
        print("Demo completed successfully!")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\nError during demo: {e}")
        import traceback
        traceback.print_exc()


def demo_config_system():
    """Demo: Configuration system with environment variables"""
    print("\n" + "=" * 70)
    print("DEMO: Configuration System")
    print("=" * 70)
    
    # Create config from dict
    config = Config()
    
    print("\nConfiguration loaded from environment and defaults:")
    print(f"  Exchange: {config.get('exchange')}")
    print(f"  Max Pairs: {config.get('max_pairs')}")
    print(f"  Min Score: {config.get('min_score')}")
    print(f"  Timeframes: {config.get('timeframes')}")
    print(f"  Telegram Configured: {config.has_telegram_configured()}")
    print(f"  Trading Enabled: {config.is_trading_enabled()}")
    
    # Validate config
    print("\nValidating configuration...")
    issues = config.validate()
    
    if issues:
        print("  Issues found:")
        for issue in issues:
            print(f"    - {issue}")
    else:
        print("  ✓ Configuration is valid!")


def demo_output_formats():
    """Demo: Different output formats"""
    print("\n" + "=" * 70)
    print("DEMO: Output Formats")
    print("=" * 70)
    
    from snipetrade.models import TradeSetup, TradeDirection, IndicatorSignal
    
    # Create sample trade setup
    setup = TradeSetup(
        symbol='BTC/USDT',
        exchange='binance',
        direction=TradeDirection.LONG,
        score=75.5,
        confidence=0.82,
        entry_price=50000.0,
        timeframe_confluence={'15m': TradeDirection.LONG, '1h': TradeDirection.LONG},
        indicator_signals=[
            IndicatorSignal(
                name='RSI',
                value=28.5,
                signal=TradeDirection.LONG,
                strength=0.8,
                timeframe='1h'
            )
        ],
        reasons=['RSI shows strong LONG signal', 'Multi-timeframe confluence']
    )
    
    # JSON Output
    print("\n1. JSON Output:")
    print("-" * 70)
    formatter = JSONFormatter()
    json_str = formatter.to_json_string(setup, pretty=True)
    print(json_str[:500] + "...")
    
    # Telegram Format (text)
    print("\n2. Telegram Message Format:")
    print("-" * 70)
    from snipetrade.output.telegram import TelegramNotifier
    notifier = TelegramNotifier()  # Without credentials
    message = notifier.format_setup_message(setup)
    print(message)


if __name__ == '__main__':
    print("\n\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "SnipeTrade Scanner Demo" + " " * 25 + "║")
    print("╚" + "═" * 68 + "╝")
    
    # Run demos
    demo_config_system()
    demo_output_formats()
    
    print("\n\nReady to run live scan demo? (This will connect to Binance)")
    response = input("Press Enter to continue or Ctrl+C to exit: ")
    
    demo_basic_scan()
    
    print("\n\n✓ All demos completed!")
    print("\nNext steps:")
    print("  1. Configure Telegram: See docs/TELEGRAM_SETUP.md")
    print("  2. Run: snipetrade scan --max-pairs 20")
    print("  3. Check output in ./output/ and ./audit_logs/")
