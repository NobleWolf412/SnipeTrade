"""Telegram notification module for trade alerts"""

import asyncio
from typing import List, Optional
from telegram import Bot
from telegram.error import TelegramError
from snipetrade.models import TradeSetup, ScanResult


class TelegramNotifier:
    """Send trade alerts via Telegram"""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """Initialize Telegram notifier
        
        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID to send messages to
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token) if bot_token else None

    def format_setup_message(self, setup: TradeSetup) -> str:
        """Format a trade setup as a Telegram message
        
        Args:
            setup: TradeSetup to format
            
        Returns:
            Formatted message string
        """
        # Message header
        direction_emoji = "🟢" if setup.direction.value == "LONG" else "🔴"
        message = f"{direction_emoji} *{setup.symbol}* - {setup.direction.value}\n\n"
        
        # Score and confidence
        message += f"📊 Score: *{setup.score:.1f}/100*\n"
        message += f"🎯 Confidence: *{setup.confidence:.1%}*\n"
        message += f"💰 Entry: *${setup.entry_price:.2f}*\n\n"
        
        # Timeframe confluence
        if setup.timeframe_confluence:
            message += "⏰ *Timeframe Confluence:*\n"
            for tf, direction in setup.timeframe_confluence.items():
                tf_emoji = "✅" if direction == setup.direction else "⚠️"
                message += f"  {tf_emoji} {tf}: {direction.value}\n"
            message += "\n"
        
        # Top indicators
        strong_signals = sorted(
            [s for s in setup.indicator_signals if s.strength > 0.5],
            key=lambda x: x.strength,
            reverse=True
        )[:3]
        
        if strong_signals:
            message += "📈 *Key Indicators:*\n"
            for signal in strong_signals:
                message += f"  • {signal.name} ({signal.timeframe}): {signal.signal.value}\n"
            message += "\n"
        
        # Reasons
        if setup.reasons:
            message += "💡 *Analysis:*\n"
            for reason in setup.reasons[:3]:  # Top 3 reasons
                message += f"  • {reason}\n"
        
        # Exchange
        message += f"\n🏦 Exchange: {setup.exchange}"
        
        return message

    def format_scan_summary(self, scan_result: ScanResult) -> str:
        """Format a scan summary as a Telegram message
        
        Args:
            scan_result: ScanResult to format
            
        Returns:
            Formatted message string
        """
        message = "📡 *Scan Complete*\n\n"
        message += f"🔍 Pairs Scanned: {scan_result.total_pairs_scanned}\n"
        message += f"✨ Setups Found: {scan_result.total_setups_found}\n"
        message += f"🏦 Exchange: {scan_result.exchange}\n"
        message += f"🕐 Time: {scan_result.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        
        if scan_result.top_setups:
            message += "*Top Opportunities:*\n"
            for i, setup in enumerate(scan_result.top_setups[:5], 1):
                direction_emoji = "🟢" if setup.direction.value == "LONG" else "🔴"
                message += f"{i}. {direction_emoji} {setup.symbol} - {setup.score:.1f}\n"
        
        return message

    async def send_setup_alert(self, setup: TradeSetup) -> bool:
        """Send a trade setup alert via Telegram
        
        Args:
            setup: TradeSetup to send
            
        Returns:
            True if successful, False otherwise
        """
        if not self.bot or not self.chat_id:
            return False
        
        try:
            message = self.format_setup_message(setup)
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            return True
        except TelegramError as e:
            print(f"Error sending Telegram alert: {e}")
            return False

    async def send_scan_summary(self, scan_result: ScanResult) -> bool:
        """Send a scan summary via Telegram
        
        Args:
            scan_result: ScanResult to send
            
        Returns:
            True if successful, False otherwise
        """
        if not self.bot or not self.chat_id:
            return False
        
        try:
            message = self.format_scan_summary(scan_result)
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
            return True
        except TelegramError as e:
            print(f"Error sending Telegram summary: {e}")
            return False

    async def send_multiple_alerts(self, setups: List[TradeSetup], 
                                     max_alerts: int = 5) -> int:
        """Send multiple trade setup alerts
        
        Args:
            setups: List of TradeSetups to send
            max_alerts: Maximum number of alerts to send
            
        Returns:
            Number of alerts sent successfully
        """
        sent_count = 0
        
        for setup in setups[:max_alerts]:
            if await self.send_setup_alert(setup):
                sent_count += 1
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
        
        return sent_count

    def send_setup_alert_sync(self, setup: TradeSetup) -> bool:
        """Synchronous wrapper for send_setup_alert
        
        Args:
            setup: TradeSetup to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            return asyncio.run(self.send_setup_alert(setup))
        except Exception as e:
            print(f"Error in sync send: {e}")
            return False

    def send_scan_summary_sync(self, scan_result: ScanResult) -> bool:
        """Synchronous wrapper for send_scan_summary
        
        Args:
            scan_result: ScanResult to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            return asyncio.run(self.send_scan_summary(scan_result))
        except Exception as e:
            print(f"Error in sync send: {e}")
            return False
