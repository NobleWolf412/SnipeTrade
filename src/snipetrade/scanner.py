"""Main scanner engine orchestrating all modules"""

import uuid
from typing import Callable, Dict, List, Optional, Union, TYPE_CHECKING
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from snipetrade.models import ScanResult, TradeSetup, Timeframe, MarketData, OHLCVTuple
from snipetrade.exchanges import CcxtAdapter, DEFAULT_EXCHANGE
from snipetrade.utils.timeframes import normalize_timeframes
from snipetrade.exchanges.phemex_checker import is_pair_on_phemex
from snipetrade.filters.pair_filter import PairFilter
from snipetrade.scoring.confluence import ConfluenceScorer
from snipetrade.output.json_formatter import JSONFormatter
from snipetrade.output.telegram import TelegramNotifier
from snipetrade.output.audit import AuditLogger
from snipetrade.utils.cache import TTLCache

if TYPE_CHECKING:
    from snipetrade.config import Config

from snipetrade import config as cfg_defaults
from snipetrade.planner import (
    decide_execution,
    position_size_leverage,
    propose_entries_adv,
)
from snipetrade.outputs import formatter as planner_formatter


class TradeScanner:
    """Main scanner orchestrating all components"""

    def __init__(self, config: Union[Dict, 'Config']):
        """Initialize trade scanner
        
        Args:
            config: Configuration dictionary or Config object
        """
        # Handle both dict and Config object
        if hasattr(config, 'to_dict'):
            self.config_obj = config
            self.config = config.to_dict()
        else:
            self.config_obj = None
            self.config = config
        
        # Initialize components
        adapter_exchange = config.get('exchange', DEFAULT_EXCHANGE)
        adapter_ttls = config.get('adapter_cache_ttl', {})
        self.exchange = CcxtAdapter(
            adapter_exchange,
            config.get('exchange_config', {}),
            ttl_overrides=adapter_ttls
        )
        
        self.pair_filter = PairFilter(
            exclude_stables=config.get('exclude_stablecoins', True),
            custom_exclude=set(config.get('custom_exclude', []))
        )
        
        configured_timeframes = normalize_timeframes(
            config.get('timeframes', [
                Timeframe.M15.value,
                Timeframe.H1.value,
                Timeframe.H4.value
            ])
        )
        if not configured_timeframes:
            configured_timeframes = [
                Timeframe.M15.value,
                Timeframe.H1.value,
                Timeframe.H4.value
            ]

        self.scorer = ConfluenceScorer(
            timeframes=configured_timeframes
        )
        
        # Optional components
        self.json_formatter = None
        if config.get('json_output_dir'):
            from pathlib import Path
            self.json_formatter = JSONFormatter(Path(config['json_output_dir']))
        
        self.telegram = None
        if (self.config.get('enable_notifications', True) and 
            self.config.get('telegram_bot_token') and 
            self.config.get('telegram_chat_id')):
            self.telegram = TelegramNotifier(
                self.config['telegram_bot_token'],
                self.config['telegram_chat_id']
            )
        
        self.audit_logger = None
        if config.get('enable_audit', True):
            from pathlib import Path
            audit_dir = Path(config.get('audit_dir', './audit_logs'))
            self.audit_logger = AuditLogger(audit_dir)
        
        # Scanning parameters
        self.min_score = config.get('min_score', 50.0)
        self.max_pairs = config.get('max_pairs', 50)
        self.max_workers = config.get('max_workers', 5)
        self.top_setups_limit = config.get('top_setups_limit', 10)
        timeframe_cache_ttl = config.get('timeframe_cache_ttl', 300)
        try:
            timeframe_cache_ttl = int(timeframe_cache_ttl)
        except (TypeError, ValueError):
            timeframe_cache_ttl = 300
        if timeframe_cache_ttl <= 0:
            timeframe_cache_ttl = 300
        self._timeframe_cache: TTLCache[str, List[MarketData]] = TTLCache(timeframe_cache_ttl)

    def _scan_pair(self, symbol: str) -> Optional[TradeSetup]:
        """Scan a single trading pair
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            TradeSetup if found, None otherwise
        """
        try:
            # Ensure pair is tradable on the target exchange (Phemex specific)
            if not is_pair_on_phemex(symbol, self.exchange):
                return None

            # Fetch multi-timeframe data
            timeframe_data = {}

            for timeframe in self.scorer.timeframes:
                try:
                    cache_key = f"{symbol}:{timeframe}"
                    cached_data = self._timeframe_cache.get(cache_key)
                    if cached_data is not None:
                        timeframe_data[timeframe] = cached_data
                        continue

                    ohlcv_candles = self.exchange.fetch_ohlcv(symbol, timeframe, limit=200)
                    market_data = self._convert_ohlcv_to_market_data(
                        symbol,
                        timeframe,
                        ohlcv_candles
                    )
                    if market_data:
                        timeframe_data[timeframe] = market_data
                        self._timeframe_cache.set(cache_key, market_data)
                except Exception as e:
                    if self.audit_logger:
                        self.audit_logger.log_error(
                            "data_fetch_error",
                            str(e),
                            {"symbol": symbol, "timeframe": timeframe}
                        )
                    continue
            
            if not timeframe_data:
                return None
            
            # Get current price
            current_price = self.exchange.get_current_price(symbol)
            
            # Score the setup
            setup = self.scorer.score_setup(
                symbol=symbol,
                exchange=self.exchange.exchange_id,
                timeframe_data=timeframe_data,
                current_price=current_price
            )
            
            if setup and setup.score >= self.min_score:
                if self.audit_logger:
                    self.audit_logger.log_setup_found(setup)
                return setup
            
            return None
            
        except Exception as e:
            if self.audit_logger:
                self.audit_logger.log_error(
                    "pair_scan_error",
                    str(e),
                    {"symbol": symbol}
                )
            return None

    def scan(self, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> ScanResult:
        """Execute a complete market scan
        
        Args:
            progress_callback: Optional callback function(current, total, symbol)
            
        Returns:
            ScanResult with all found setups
        """
        scan_id = str(uuid.uuid4())
        
        if self.audit_logger:
            self.audit_logger.log_scan_started(
                self.exchange.exchange_id,
                self.max_pairs,
                self.config
            )
        
        # Get top pairs
        print(f"Fetching top {self.max_pairs} pairs from {self.exchange.exchange_id}...")
        all_pairs = self.exchange.get_top_pairs(limit=self.max_pairs * 2)
        filtered_pairs = self.pair_filter.get_top_pairs(all_pairs, self.max_pairs)
        
        print(f"Scanning {len(filtered_pairs)} pairs...")
        
        # Scan pairs in parallel
        setups = []
        total_pairs = len(filtered_pairs)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_symbol = {
                executor.submit(self._scan_pair, symbol): symbol
                for symbol in filtered_pairs
            }
            
            # Process results as they complete
            for i, future in enumerate(as_completed(future_to_symbol), 1):
                symbol = future_to_symbol[future]
                
                if progress_callback:
                    progress_callback(i, total_pairs, symbol)
                
                try:
                    setup = future.result()
                    if setup:
                        setups.append(setup)
                except Exception as e:
                    if self.audit_logger:
                        self.audit_logger.log_error(
                            "scan_execution_error",
                            str(e),
                            {"symbol": symbol}
                        )
        
        # Sort setups by score
        setups.sort(key=lambda x: x.score, reverse=True)
        top_setups = setups[:self.top_setups_limit]

        scan_result = ScanResult(
            scan_id=scan_id,
            exchange=self.exchange.exchange_id,
            total_pairs_scanned=total_pairs,
            total_setups_found=len(setups),
            setups=top_setups,
            metadata={
                "config": self.config,
                "timeframes": self.scorer.timeframes
            }
        )
        
        if self.audit_logger:
            self.audit_logger.log_scan_completed(scan_result)
        
        return scan_result

    def _convert_ohlcv_to_market_data(
        self,
        symbol: str,
        timeframe: str,
        candles: List[OHLCVTuple]
    ) -> List[MarketData]:
        market_data = []
        exchange_id = self.exchange.exchange_id
        for candle in candles:
            ts_value = candle.timestamp
            if ts_value > 1_000_000_000_000:  # milliseconds
                ts_value = ts_value / 1000
            timestamp = datetime.fromtimestamp(ts_value)
            market_data.append(MarketData(
                symbol=symbol,
                exchange=exchange_id,
                timeframe=timeframe,
                timestamp=timestamp,
                ohlcv=candle,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume
            ))
        return market_data

    def output_results(self, scan_result: ScanResult) -> None:
        """Output scan results to configured channels
        
        Args:
            scan_result: ScanResult to output
        """
        # Save to JSON
        if self.json_formatter:
            try:
                filepath = self.json_formatter.save_scan_result(scan_result)
                print(f"Results saved to: {filepath}")
            except Exception as e:
                print(f"Error saving JSON: {e}")
                if self.audit_logger:
                    self.audit_logger.log_error("json_save_error", str(e))
        
        # Send Telegram alerts
        if self.telegram and self.config.get('enable_notifications', True):
            try:
                print("\nSending Telegram notifications...")
                
                # Send summary
                success = self.telegram.send_scan_summary_sync(scan_result)
                if success:
                    print("✓ Scan summary sent to Telegram")
                if self.audit_logger:
                    self.audit_logger.log_event("scan_summary_sent", {
                        "channel": "telegram",
                        "success": success
                    })
                
                # Send individual alerts for top setups
                max_alerts = min(5, len(scan_result.setups))
                for i, setup in enumerate(scan_result.setups[:max_alerts], 1):
                    alert_success = self.telegram.send_setup_alert_sync(setup)
                    if alert_success:
                        print(f"✓ Alert {i}/{max_alerts} sent: {setup.symbol}")
                    if self.audit_logger:
                        self.audit_logger.log_alert_sent(setup, "telegram", alert_success)
                    
                print(f"✓ Sent {max_alerts} trade alerts to Telegram")
                    
            except Exception as e:
                print(f"✗ Error sending Telegram alerts: {e}")
                if self.audit_logger:
                    self.audit_logger.log_error("telegram_error", str(e))

    def run(self) -> ScanResult:
        """Run complete scan and output results
        
        Returns:
            ScanResult
        """
        def progress_callback(current: int, total: int, symbol: str):
            print(f"Progress: {current}/{total} - Scanning {symbol}")
        
        # Execute scan
        scan_result = self.scan(progress_callback)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Scan Complete!")
        print(f"{'='*60}")
        print(f"Exchange: {scan_result.exchange}")
        print(f"Pairs Scanned: {scan_result.total_pairs_scanned}")
        print(f"Setups Found: {scan_result.total_setups_found}")
        print(f"\nTop Setups:")
        
        for i, setup in enumerate(scan_result.setups, 1):
            print(f"\n{i}. {setup.symbol} - {setup.direction}")
            print(f"   Score: {setup.score:.1f}/100 | Confidence: {setup.confidence:.1%}")
            entry_values = ', '.join(f"${price:.2f}" for price in setup.entry_plan)
            print(f"   Entry Plan: {entry_values}")
            if setup.reasons:
                print(f"   Reason: {setup.reasons[0]}")
        
        # Output to configured channels
        self.output_results(scan_result)
        
        return scan_result


def build_trade_plan(
    setup: Dict,
    price_ctx: Dict,
    orderflow_ctx: Dict,
    structure_ctx: Dict,
    vwap_ctx: Dict,
    atr: float,
    stop: float,
    tps: List[float],
    now_ts_ms: int,
    leverage: float = None,
    cfg=cfg_defaults,
) -> Dict:
    """Build a complete trade plan payload wired through the planner stack."""

    leverage = leverage or cfg.DEFAULT_LEVERAGE
    entries = propose_entries_adv(
        {"direction": setup["direction"], "atr": atr, "stop": stop},
        price_ctx,
        orderflow_ctx,
        structure_ctx,
        vwap_ctx,
        cfg,
    )

    size_info = position_size_leverage(
        entry=entries["near"]["price"],
        stop=stop,
        side=setup["direction"],
        leverage=leverage,
        price=price_ctx.get("price"),
        risk_usd=cfg.RISK_USD,
        lot_size=cfg.LOT_SIZE,
        min_notional=cfg.MIN_NOTIONAL,
        maint_margin_rate=cfg.MAINT_MARGIN_RATE,
        atr=atr,
        cfg=cfg,
    )

    execution = decide_execution(entries["near"], entries["far"], now_ts_ms, cfg)

    liq_gap = abs(stop - size_info["liq"])
    liq_buffer = f"gap {liq_gap:.3f}"

    payload = {
        "symbol": setup["symbol"],
        "timeframe": setup.get("timeframe", "15m"),
        "direction": setup["direction"],
        "score": setup.get("score", 0),
        "entry_near": entries["near"]["price"],
        "entry_far": entries["far"]["price"],
        "stop": stop,
        "tp1": tps[0] if tps else None,
        "leverage": leverage,
        "qty": size_info["qty"],
        "liq": size_info["liq"],
        "liq_buffer": liq_buffer,
        "rr": setup.get("rr"),
        "distance_pct": setup.get("distance_pct"),
        "spread_bps": orderflow_ctx.get("spread_bps"),
        "volume_usd_24h": setup.get("volume_usd_24h"),
        "reasons": setup.get("reasons", []),
        "execution": execution,
        "links": setup.get("links", []),
    }

    payload["alert_text"] = planner_formatter.format_telegram_alert(payload)

    return {
        "entries": entries,
        "size": size_info,
        "execution": execution,
        "payload": payload,
    }
