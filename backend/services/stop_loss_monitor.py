"""
Stop Loss Monitor Service
Monitors open positions and alerts when stop-loss levels are hit
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List
from services.trade_journal import get_trade_journal
from services.telegram_bot import send_alert_with_buttons, telegram_bot
from services.upstox_service import get_upstox_service

logger = logging.getLogger(__name__)

class StopLossMonitorService:
    def __init__(self):
        self.journal = get_trade_journal()
        self.upstox = get_upstox_service()
        self.monitoring = False
        self.monitor_task = None

    async def check_stop_losses(self) -> List[Dict]:
        """Check all open positions for stop-loss hits"""
        try:
            # Get consolidated positions instead of individual trades
            all_positions = self.journal.get_all_positions()
            
            # Only monitor symbols with non-zero net positions
            symbols_with_positions = [symbol for symbol, qty in all_positions.items() if qty != 0]
            
            if not symbols_with_positions:
                return []

            # Get current market prices for symbols with open positions
            current_prices = await self._get_current_prices(symbols_with_positions)

            stop_loss_hits = []

            # Check each symbol's net position
            for symbol in symbols_with_positions:
                net_quantity = all_positions[symbol]
                current_price = current_prices.get(symbol, 0)

                if current_price == 0:
                    continue  # Skip if no current price available

                # Get all open trades for this symbol to check stop losses
                open_trades = self.journal.get_open_trades()
                symbol_trades = [t for t in open_trades if t['symbol'] == symbol]
                
                # Find the most recent trade for this symbol (for SL reference)
                if symbol_trades:
                    # Sort by entry time, most recent first
                    recent_trade = max(symbol_trades, key=lambda x: x.get('entry_time', ''))
                    
                    action = recent_trade['action']
                    entry_price = recent_trade['entry_price']
                    sl_price = recent_trade['sl']
                    
                    # Check if stop-loss is hit based on position direction
                    sl_hit = False
                    
                    if net_quantity > 0:  # Net long position
                        # For long positions, SL is hit when current price <= stop-loss
                        sl_hit = current_price <= sl_price
                        if sl_hit:
                            loss_amount = (entry_price - current_price) * abs(net_quantity)
                            loss_pct = ((entry_price - current_price) / entry_price) * 100
                    elif net_quantity < 0:  # Net short position
                        # For short positions, SL is hit when current price >= stop-loss
                        sl_hit = current_price >= sl_price
                        if sl_hit:
                            loss_amount = (current_price - entry_price) * abs(net_quantity)
                            loss_pct = ((current_price - entry_price) / entry_price) * 100
                    
                    if sl_hit:
                        stop_loss_hits.append({
                            'symbol': symbol,
                            'net_quantity': net_quantity,
                            'current_price': current_price,
                            'sl_price': sl_price,
                            'entry_price': entry_price,
                            'loss_amount': round(loss_amount, 2),
                            'loss_pct': round(loss_pct, 2),
                            'urgency': 'HIGH' if abs(loss_pct) > 5 else 'MEDIUM',
                            'trades': symbol_trades  # Include all related trades for reference
                        })

            return stop_loss_hits

        except Exception as e:
            logger.error(f"Error checking stop losses: {e}")
            return []

    async def _get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current market prices for symbols"""
        try:
            if not self.upstox.is_configured():
                return {}

            # Load instruments mapping
            import os, json
            instruments_path = os.path.join(os.path.dirname(__file__), '../data/instruments.json')
            with open(instruments_path, 'r') as f:
                instruments = json.load(f)

            symbol_to_key = {
                inst['tradingsymbol'].upper(): inst['instrument_key']
                for inst in instruments
                if 'tradingsymbol' in inst and 'instrument_key' in inst
            }

            # Get instrument keys
            instrument_keys = [
                symbol_to_key.get(s.upper())
                for s in symbols
                if symbol_to_key.get(s.upper())
            ]

            if not instrument_keys:
                return {}

            # Fetch market quotes
            quotes_data = self.upstox.get_market_quotes_batch(instrument_keys)
            current_prices = {}

            for symbol in symbols:
                upstox_key = f"NSE_EQ:{symbol}"
                quote = quotes_data.get(upstox_key, {})
                if quote:
                    current_prices[symbol] = quote.get('last_price', 0)

            return current_prices

        except Exception as e:
            logger.error(f"Error getting current prices: {e}")
            return {}

    async def send_stop_loss_alerts(self, stop_loss_hits: List[Dict]) -> bool:
        """Send stop-loss alerts via Telegram"""
        if not stop_loss_hits:
            return True

        try:
            for sl_hit in stop_loss_hits:
                symbol = sl_hit['symbol']
                net_quantity = sl_hit['net_quantity']
                current_price = sl_hit['current_price']
                sl_price = sl_hit['sl_price']
                entry_price = sl_hit['entry_price']
                loss_amount = sl_hit['loss_amount']
                loss_pct = sl_hit['loss_pct']
                urgency = sl_hit['urgency']
                trades = sl_hit.get('trades', [])

                # Determine position type from net quantity
                position_type = "LONG" if net_quantity > 0 else "SHORT"
                action_emoji = "�" if net_quantity > 0 else "🔴"

                # Create urgency emoji
                urgency_emoji = "�" if urgency == 'HIGH' else "⚠️"

                # Format stop-loss alert message
                message = f"""
{urgency_emoji} **STOP-LOSS HIT!**

{action_emoji} **{symbol}** ({position_type} Position)
💰 Avg Entry: ₹{entry_price:.2f} per share
🛑 Stop-Loss: ₹{sl_price:.2f}
📉 Current: ₹{current_price:.2f}

📊 **Loss Details:**
💸 Loss: ₹{abs(loss_amount):,.2f} ({abs(loss_pct):.1f}%)
📦 Net Quantity: {abs(net_quantity)} shares

🔥 **URGENT ACTION REQUIRED**
Consider closing position immediately to limit losses!

⏰ {datetime.now().strftime('%H:%M:%S')}
                """

                # Create sell button for the position
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                # Determine action based on position type
                action_text = "SELL" if net_quantity > 0 else "BUY BACK"
                action_emoji_btn = "🔴" if net_quantity > 0 else "🟢"

                sell_buttons = [
                    [InlineKeyboardButton(
                        f"{action_emoji_btn} {action_text} ALL {symbol} ({abs(net_quantity)} shares)",
                        callback_data=f"qty_sell_{symbol}_{current_price}_{abs(net_quantity)}"
                    )],
                    [InlineKeyboardButton(
                        "⏰ Remind in 5 min",
                        callback_data=f"remind_{symbol}_{current_price}_5"
                    )],
                    [InlineKeyboardButton(
                        "ℹ️ Keep Monitoring",
                        callback_data=f"skip_{symbol}_{current_price}_0"
                    )]
                ]

                reply_markup = InlineKeyboardMarkup(sell_buttons)

                # Send alert with buttons
                success = await send_alert_with_buttons(message.strip(), reply_markup)

                if success:
                    logger.info(f"Stop-loss alert sent for {symbol}")
                else:
                    logger.warning(f"Failed to send stop-loss alert for {symbol}")

            return True

        except Exception as e:
            logger.error(f"Error sending stop-loss alerts: {e}")
            return False

    async def check_and_alert(self) -> int:
        """Check for stop-loss hits and send alerts"""
        try:
            stop_loss_hits = await self.check_stop_losses()

            if stop_loss_hits:
                logger.info(f"Found {len(stop_loss_hits)} stop-loss hits")
                await self.send_stop_loss_alerts(stop_loss_hits)
                return len(stop_loss_hits)

            return 0

        except Exception as e:
            logger.error(f"Error in stop-loss check: {e}")
            return 0

    async def start_monitoring(self, interval_minutes: int = 2):
        """Start continuous stop-loss monitoring"""
        if self.monitoring:
            logger.info("Stop-loss monitoring already running")
            return

        self.monitoring = True
        logger.info(f"Starting stop-loss monitoring with {interval_minutes}min intervals")

        async def monitor_loop():
            while self.monitoring:
                try:
                    hits_count = await self.check_and_alert()
                    if hits_count > 0:
                        logger.info(f"Processed {hits_count} stop-loss alerts")

                    # Wait for next check
                    await asyncio.sleep(interval_minutes * 60)

                except Exception as e:
                    logger.error(f"Error in stop-loss monitoring loop: {e}")
                    await asyncio.sleep(30)  # Wait 30s on error

        self.monitor_task = asyncio.create_task(monitor_loop())

    async def stop_monitoring(self):
        """Stop stop-loss monitoring"""
        if not self.monitoring:
            return

        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Stop-loss monitoring stopped")

    def get_monitoring_status(self) -> Dict:
        """Get stop-loss monitoring status"""
        open_trades = self.journal.get_open_trades()
        positions_at_risk = 0

        # Count positions that are close to stop-loss (within 5%)
        for trade in open_trades:
            if trade.get('sl', 0) > 0:
                positions_at_risk += 1

        return {
            'monitoring': self.monitoring,
            'open_positions': len(open_trades),
            'positions_at_risk': positions_at_risk,
            'check_interval': '2 minutes'
        }

# Global stop-loss monitor instance
stop_loss_monitor = StopLossMonitorService()

async def start_stop_loss_monitoring(interval_minutes: int = 2):
    """Start the global stop-loss monitor"""
    await stop_loss_monitor.start_monitoring(interval_minutes)

async def stop_stop_loss_monitoring():
    """Stop the global stop-loss monitor"""
    await stop_loss_monitor.stop_monitoring()

def get_stop_loss_monitor() -> StopLossMonitorService:
    """Get the global stop-loss monitor instance"""
    return stop_loss_monitor