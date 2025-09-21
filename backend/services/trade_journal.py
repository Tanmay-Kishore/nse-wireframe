"""
Trade Journal Service
Manages trade recording and portfolio tracking
"""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class TradeJournalService:
    def __init__(self):
        self.trades_path = os.path.join(os.path.dirname(__file__), '../data/trades.json')
        self._ensure_trades_file()

    def _ensure_trades_file(self):
        """Ensure trades.json file exists"""
        try:
            if not os.path.exists(self.trades_path):
                with open(self.trades_path, 'w') as f:
                    json.dump([], f)
        except Exception as e:
            logger.error(f"Error creating trades file: {e}")

    def _load_trades(self) -> List[Dict]:
        """Load all trades from file"""
        try:
            with open(self.trades_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading trades: {e}")
            return []

    def _save_trades(self, trades: List[Dict]):
        """Save trades to file"""
        try:
            with open(self.trades_path, 'w') as f:
                json.dump(trades, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving trades: {e}")

    async def log_trade(self, trade_data: Dict) -> bool:
        """Log a new trade with position validation"""
        try:
            # Load existing trades
            trades = self._load_trades()

            # Get signal details for stop-loss and target calculation
            symbol = trade_data['symbol']
            action = trade_data['action']
            price = trade_data['price']
            confidence = trade_data.get('confidence', 0)

            # Check position before allowing SELL
            if action == 'SELL':
                current_position = self.get_current_position(symbol)
                if current_position <= 0:
                    logger.warning(f"Cannot SELL {symbol}: No position held (current: {current_position})")
                    return False

            # Calculate stop-loss and target based on action
            if action == 'BUY':
                sl = round(price * 0.97, 2)  # 3% stop loss
                target = round(price * (1 + 0.03 + 0.01 * confidence), 2)  # 3-8% target
            elif action == 'SELL':
                sl = round(price * 1.03, 2)  # 3% stop loss
                target = round(price * (1 - 0.03 - 0.01 * confidence), 2)  # 3-8% target
            else:
                sl = price
                target = price

            # Create trade record
            trade_record = {
                'trade_id': str(uuid.uuid4())[:8],
                'symbol': symbol,
                'action': action,
                'entry_price': price,
                'quantity': 1,  # Default quantity
                'sl': sl,
                'target': target,
                'confidence': confidence,
                'source': trade_data.get('source', 'manual'),
                'status': 'OPEN',
                'entry_time': datetime.now().isoformat(),
                'exit_time': None,
                'exit_price': None,
                'pnl': 0.0,
                'notes': f"Signal confidence: {confidence}/5"
            }

            # Add trade to list
            trades.append(trade_record)

            # Keep only last 1000 trades
            if len(trades) > 1000:
                trades = trades[-1000:]

            # Save updated trades
            self._save_trades(trades)

            logger.info(f"Trade logged: {action} {symbol} at ₹{price}")
            return True

        except Exception as e:
            logger.error(f"Error logging trade: {e}")
            return False

    def get_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent trades"""
        try:
            trades = self._load_trades()
            return sorted(trades, key=lambda x: x.get('entry_time', ''), reverse=True)[:limit]
        except Exception as e:
            logger.error(f"Error getting trades: {e}")
            return []

    def get_open_trades(self) -> List[Dict]:
        """Get currently open trades"""
        try:
            trades = self._load_trades()
            return [t for t in trades if t.get('status') == 'OPEN']
        except Exception as e:
            logger.error(f"Error getting open trades: {e}")
            return []

    def close_trade(self, trade_id: str, exit_price: float, notes: str = "") -> bool:
        """Close an open trade"""
        try:
            trades = self._load_trades()

            for trade in trades:
                if trade.get('trade_id') == trade_id and trade.get('status') == 'OPEN':
                    # Calculate P&L
                    entry_price = trade['entry_price']
                    quantity = trade['quantity']
                    action = trade['action']

                    if action == 'BUY':
                        pnl = (exit_price - entry_price) * quantity
                    elif action == 'SELL':
                        pnl = (entry_price - exit_price) * quantity
                    else:
                        pnl = 0

                    # Update trade
                    trade.update({
                        'status': 'CLOSED',
                        'exit_time': datetime.now().isoformat(),
                        'exit_price': exit_price,
                        'pnl': round(pnl, 2),
                        'notes': notes
                    })

                    self._save_trades(trades)
                    logger.info(f"Trade closed: {trade_id} with P&L ₹{pnl}")
                    return True

            logger.warning(f"Trade {trade_id} not found or not open")
            return False

        except Exception as e:
            logger.error(f"Error closing trade: {e}")
            return False

    def get_current_position(self, symbol: str) -> int:
        """Get current position quantity for a symbol"""
        try:
            trades = self._load_trades()
            position = 0

            for trade in trades:
                if trade.get('symbol') == symbol and trade.get('status') == 'OPEN':
                    quantity = trade.get('quantity', 0)
                    action = trade.get('action', '')

                    if action == 'BUY':
                        position += quantity
                    elif action == 'SELL':
                        position -= quantity

            return position

        except Exception as e:
            logger.error(f"Error calculating position for {symbol}: {e}")
            return 0

    def get_all_positions(self) -> Dict[str, int]:
        """Get current positions for all symbols"""
        try:
            trades = self._load_trades()
            positions = {}

            for trade in trades:
                if trade.get('status') == 'OPEN':
                    symbol = trade.get('symbol')
                    quantity = trade.get('quantity', 0)
                    action = trade.get('action', '')

                    if symbol not in positions:
                        positions[symbol] = 0

                    if action == 'BUY':
                        positions[symbol] += quantity
                    elif action == 'SELL':
                        positions[symbol] -= quantity

            # Remove zero positions
            return {symbol: qty for symbol, qty in positions.items() if qty != 0}

        except Exception as e:
            logger.error(f"Error calculating all positions: {e}")
            return {}

    def get_portfolio_stats(self) -> Dict:
        """Get portfolio statistics"""
        try:
            trades = self._load_trades()
            closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
            open_trades = [t for t in trades if t.get('status') == 'OPEN']

            total_pnl = sum(t.get('pnl', 0) for t in closed_trades)
            winning_trades = [t for t in closed_trades if t.get('pnl', 0) > 0]
            losing_trades = [t for t in closed_trades if t.get('pnl', 0) < 0]

            win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0

            # Get current positions
            current_positions = self.get_all_positions()

            return {
                'total_trades': len(trades),
                'open_trades': len(open_trades),
                'closed_trades': len(closed_trades),
                'total_pnl': round(total_pnl, 2),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': round(win_rate * 100, 2),
                'avg_win': round(sum(t['pnl'] for t in winning_trades) / len(winning_trades), 2) if winning_trades else 0,
                'avg_loss': round(sum(t['pnl'] for t in losing_trades) / len(losing_trades), 2) if losing_trades else 0,
                'current_positions': current_positions
            }

        except Exception as e:
            logger.error(f"Error calculating portfolio stats: {e}")
            return {}

# Global journal instance
trade_journal = TradeJournalService()

async def log_trade(trade_data: Dict) -> bool:
    """Log a trade using the global journal instance"""
    return await trade_journal.log_trade(trade_data)

def get_trade_journal() -> TradeJournalService:
    """Get the global trade journal instance"""
    return trade_journal