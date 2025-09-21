"""
Signal Monitor Service
Simple signal change tracking using internal API calls
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List
from services.telegram_bot import send_alert

logger = logging.getLogger(__name__)

class SignalMonitorService:
    def __init__(self):
        self.watchlist_path = os.path.join(os.path.dirname(__file__), '../data/watchlist.json')
        self.monitoring = False
        self.monitor_task = None

    def _load_watchlist_with_signals(self) -> Dict:
        """Load watchlist with cached signals"""
        try:
            with open(self.watchlist_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading watchlist: {e}")
            return {"symbols": []}

    def _save_watchlist_with_signals(self, data: Dict):
        """Save watchlist with updated signals"""
        try:
            with open(self.watchlist_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving watchlist: {e}")

    async def get_current_signals(self) -> Dict[str, Dict]:
        """Get current signals by calling internal /api/stocks endpoint"""
        try:
            # Use internal import to call the stocks endpoint directly
            from routers.stocks import list_stocks

            # Call the stocks endpoint internally
            response = await list_stocks()
            stocks = response.get('items', [])

            current_signals = {}
            for stock in stocks:
                symbol = stock.get('symbol')
                signal_data = stock.get('signal', {})

                current_signals[symbol] = {
                    'direction': signal_data.get('direction', 'HOLD'),
                    'confidence': signal_data.get('confidence', 0),
                    'price': stock.get('price', 0),
                    'sentiment': stock.get('sentiment', 'NEUTRAL'),
                    'timestamp': datetime.now().isoformat()
                }

            return current_signals

        except Exception as e:
            logger.error(f"Error getting current signals: {e}")
            return {}

    def detect_signal_changes(self, current_signals: Dict[str, Dict]) -> List[Dict]:
        """Detect changes by comparing with signals stored in watchlist.json"""
        changes = []

        # Load watchlist with previous signals
        watchlist_data = self._load_watchlist_with_signals()
        cached_signals = watchlist_data.get('last_signals', {})

        for symbol, current_signal in current_signals.items():
            last_signal = cached_signals.get(symbol, {})

            # Check for direction change
            last_direction = last_signal.get('direction', 'UNKNOWN')
            current_direction = current_signal.get('direction', 'HOLD')

            # Check for significant confidence change (±1 or more)
            last_confidence = last_signal.get('confidence', 0)
            current_confidence = current_signal.get('confidence', 0)

            direction_changed = last_direction != current_direction and last_direction != 'UNKNOWN'
            confidence_changed = abs(current_confidence - last_confidence) >= 1 and last_direction != 'UNKNOWN'

            # Only notify on significant changes
            if direction_changed or confidence_changed:
                change_type = []
                if direction_changed:
                    change_type.append(f"Signal: {last_direction} → {current_direction}")
                if confidence_changed:
                    change_type.append(f"Confidence: {last_confidence} → {current_confidence}")

                changes.append({
                    'symbol': symbol,
                    'change_type': ' | '.join(change_type),
                    'old_signal': last_signal,
                    'new_signal': current_signal,
                    'direction_changed': direction_changed,
                    'confidence_changed': confidence_changed
                })

        return changes

    def format_notification_message(self, changes: List[Dict]) -> str:
        """Format signal changes into a Telegram message"""
        if not changes:
            return ""

        message_parts = ["🚨 **Signal Changes Detected**\n"]

        for change in changes[:5]:  # Limit to 5 changes per message
            symbol = change['symbol']
            new_signal = change['new_signal']
            direction = new_signal['direction']
            confidence = new_signal['confidence']
            price = new_signal['price']

            # Choose emoji based on signal
            if direction == 'BUY':
                emoji = "🟢"
            elif direction == 'SELL':
                emoji = "🔴"
            else:
                emoji = "⚪"

            message_parts.append(
                f"{emoji} **{symbol}**\n"
                f"   Signal: {direction} (Confidence: {confidence})\n"
                f"   Price: ₹{price}\n"
                f"   Change: {change['change_type']}\n"
            )

        if len(changes) > 5:
            message_parts.append(f"\n... and {len(changes) - 5} more changes")

        message_parts.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")

        return "\n".join(message_parts)

    async def send_signal_notifications(self, changes: List[Dict]) -> bool:
        """Send signal change notifications via Telegram"""
        if not changes:
            return True

        try:
            message = self.format_notification_message(changes)
            if message:
                success = await send_alert(message)
                if success:
                    logger.info(f"Sent notification for {len(changes)} signal changes")
                else:
                    logger.warning("Failed to send Telegram notification")
                return success
            return True
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
            return False

    async def check_and_notify(self) -> int:
        """Check for signal changes and send notifications"""
        try:
            # Get current signals from internal API call
            current_signals = await self.get_current_signals()
            if not current_signals:
                return 0

            # Detect changes
            changes = self.detect_signal_changes(current_signals)

            if changes:
                logger.info(f"Detected {len(changes)} signal changes")
                await self.send_signal_notifications(changes)

            # Save signals to watchlist.json for simple lookup
            watchlist_data = self._load_watchlist_with_signals()
            watchlist_data['last_signals'] = current_signals
            watchlist_data['last_updated'] = datetime.now().isoformat()
            self._save_watchlist_with_signals(watchlist_data)

            return len(changes)

        except Exception as e:
            logger.error(f"Error in check_and_notify: {e}")
            return 0

    async def start_monitoring(self, interval_minutes: int = 5):
        """Start continuous signal monitoring"""
        if self.monitoring:
            logger.info("Signal monitoring already running")
            return

        self.monitoring = True
        logger.info(f"Starting signal monitoring with {interval_minutes}min intervals")

        async def monitor_loop():
            while self.monitoring:
                try:
                    changes_count = await self.check_and_notify()
                    if changes_count > 0:
                        logger.info(f"Processed {changes_count} signal changes")

                    # Wait for next check
                    await asyncio.sleep(interval_minutes * 60)

                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(30)  # Wait 30s on error

        self.monitor_task = asyncio.create_task(monitor_loop())

    async def stop_monitoring(self):
        """Stop signal monitoring"""
        if not self.monitoring:
            return

        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Signal monitoring stopped")

    def get_monitoring_status(self) -> Dict:
        """Get current monitoring status"""
        try:
            watchlist_data = self._load_watchlist_with_signals()
            cached_signals = watchlist_data.get('last_signals', {})

            return {
                'monitoring': self.monitoring,
                'cached_signals_count': len(cached_signals),
                'last_check': watchlist_data.get('last_updated'),
                'symbols_in_watchlist': len(watchlist_data.get('symbols', [])),
                'telegram_configured': self._check_telegram_config()
            }
        except Exception as e:
            logger.error(f"Error getting monitoring status: {e}")
            return {
                'monitoring': self.monitoring,
                'cached_signals_count': 0,
                'last_check': None,
                'symbols_in_watchlist': 0,
                'telegram_configured': False,
                'error': str(e)
            }

    def _check_telegram_config(self) -> bool:
        """Check if Telegram is properly configured"""
        try:
            from routers.settings import load_telegram_config
            config = load_telegram_config()
            return bool(config and config.get("bot_token") and config.get("chat_id"))
        except:
            return False

# Global monitor instance
signal_monitor = SignalMonitorService()

async def start_signal_monitoring(interval_minutes: int = 5):
    """Start the global signal monitor"""
    await signal_monitor.start_monitoring(interval_minutes)

async def stop_signal_monitoring():
    """Stop the global signal monitor"""
    await signal_monitor.stop_monitoring()

def get_signal_monitor() -> SignalMonitorService:
    """Get the global signal monitor instance"""
    return signal_monitor