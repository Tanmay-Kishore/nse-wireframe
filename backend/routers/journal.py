from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging
import json
import os
from services.trade_journal import get_trade_journal, log_trade
from services.upstox_service import get_upstox_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["journal"])

trade_journal = get_trade_journal()
upstox = get_upstox_service()

def consolidate_positions(trades: List[Dict]) -> List[Dict]:
    """Consolidate BUY/SELL trades into net positions"""
    try:
        from collections import defaultdict

        # Group trades by symbol
        symbol_trades = defaultdict(list)
        for trade in trades:
            symbol = trade.get("symbol", "")
            if symbol:
                symbol_trades[symbol].append(trade)

        consolidated = []

        for symbol, symbol_trade_list in symbol_trades.items():
            # Sort trades by date (oldest first)
            sorted_trades = sorted(symbol_trade_list, key=lambda x: x.get("entry_time", ""))

            position = 0  # Current position
            weighted_entry = 0  # Weighted average entry price
            total_cost = 0

            for i, trade in enumerate(sorted_trades):
                action = trade.get("action", "")
                quantity = trade.get("quantity", 1)
                price = trade.get("entry_price", 0)

                if action == "BUY":
                    # Add to position
                    total_cost += price * quantity
                    position += quantity
                    weighted_entry = total_cost / position if position > 0 else price

                elif action == "SELL" and position > 0:
                    # Close part or all of the position
                    sold_quantity = min(quantity, position)

                    # Calculate P&L for the sold portion
                    pnl = (price - weighted_entry) * sold_quantity

                    # Create a completed trade record
                    consolidated.append({
                        **sorted_trades[0],  # Base from first BUY trade
                        "entry_price": weighted_entry,
                        "exit_price": price,
                        "quantity": sold_quantity,
                        "status": "CLOSED",
                        "pnl": round(pnl, 2),
                        "exit_time": trade.get("entry_time"),
                        "action": "BUY",  # Show as BUY position that was closed
                        "notes": f"Position closed by SELL @ ₹{price}"
                    })

                    # Update remaining position
                    position -= sold_quantity
                    if position > 0:
                        total_cost = weighted_entry * position
                    else:
                        total_cost = 0
                        weighted_entry = 0

            # Add any remaining open position
            if position > 0:
                consolidated.append({
                    **sorted_trades[0],  # Base from first BUY trade
                    "entry_price": weighted_entry,
                    "quantity": position,
                    "status": "OPEN",
                    "action": "BUY"
                })

        # Sort by date (newest first for display)
        return sorted(consolidated, key=lambda x: x.get("entry_time", ""), reverse=True)

    except Exception as e:
        logger.error(f"Error consolidating positions: {e}")
        # Return original trades if consolidation fails
        return trades

async def get_current_prices(symbols: List[str]) -> Dict[str, float]:
    """Get current market prices for a list of symbols"""
    try:
        if not symbols or not upstox.is_configured():
            return {}

        # Load instruments mapping
        instruments_path = os.path.join(os.path.dirname(__file__), '../data/instruments.json')
        with open(instruments_path, 'r') as f:
            instruments = json.load(f)

        # Create symbol to instrument key mapping
        symbol_to_key = {
            inst['tradingsymbol'].upper(): inst['instrument_key']
            for inst in instruments
            if 'tradingsymbol' in inst and 'instrument_key' in inst
        }

        # Get instrument keys for our symbols
        instrument_keys = [
            symbol_to_key.get(symbol.upper())
            for symbol in symbols
            if symbol_to_key.get(symbol.upper())
        ]

        if not instrument_keys:
            return {}

        # Fetch current market prices
        quotes_data = upstox.get_market_quotes_batch(instrument_keys)
        current_prices = {}

        for symbol in symbols:
            upstox_key = f"NSE_EQ:{symbol}"
            quote = quotes_data.get(upstox_key, {})
            if quote:
                current_prices[symbol] = quote.get('last_price', 0)

        return current_prices

    except Exception as e:
        logger.error(f"Error fetching current prices: {e}")
        return {}

class TradeRequest(BaseModel):
    symbol: str
    action: str  # BUY or SELL
    price: float
    quantity: int = 1
    confidence: int = 0
    source: str = "manual"

@router.get("/journal")
async def get_journal(limit: int = 50):
    """Get trading journal entries with current prices and position consolidation"""
    try:
        raw_trades = trade_journal.get_trades(limit)
        stats = trade_journal.get_portfolio_stats()

        # Get current prices for all symbols
        symbols = list(set(trade.get("symbol") for trade in raw_trades if trade.get("symbol")))
        current_prices = await get_current_prices(symbols)

        # Consolidate trades by position (group BUY/SELL for same symbol)
        consolidated_trades = consolidate_positions(raw_trades)

        # Format trades for frontend compatibility
        formatted_trades = []
        for trade in consolidated_trades:
            symbol = trade.get("symbol", "")
            current_price = current_prices.get(symbol, 0)
            entry_price = trade.get("entry_price", 0)
            quantity = trade.get("quantity", 1)
            action = trade.get("action", "")

            # Calculate current P&L if trade is open
            current_pnl = 0
            if trade.get("status") == "OPEN" and current_price > 0 and entry_price > 0:
                if action == "BUY":
                    current_pnl = round((current_price - entry_price) * quantity, 2)
                elif action == "SELL":
                    current_pnl = round((entry_price - current_price) * quantity, 2)

            formatted_trade = {
                "date": trade.get("entry_time", ""),  # Frontend expects 'date'
                "symbol": symbol,
                "direction": action,  # Frontend expects 'direction'
                "entry": entry_price,  # Frontend expects 'entry'
                "current_price": current_price,  # NEW: Current market price
                "sl": trade.get("sl", 0),
                "target": trade.get("target", 0),
                "exit": trade.get("exit_price"),  # Can be null
                "pnl": current_pnl if trade.get("status") == "OPEN" else trade.get("pnl", 0),  # Use current P&L for open trades, closed P&L for closed trades
                "current_pnl": current_pnl,  # NEW: Real-time P&L
                # Additional fields for API users
                "trade_id": trade.get("trade_id", ""),
                "quantity": quantity,
                "status": trade.get("status", "OPEN"),
                "confidence": trade.get("confidence", 0),
                "source": trade.get("source", ""),
                "notes": trade.get("notes", "")
            }
            formatted_trades.append(formatted_trade)

        return {
            "items": formatted_trades,
            "stats": stats,
            "count": len(formatted_trades)
        }

    except Exception as e:
        logger.error(f"Error getting journal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/journal/trade")
async def add_trade(trade_request: TradeRequest):
    """Add a new trade to the journal"""
    try:
        trade_data = trade_request.dict()
        success = await log_trade(trade_data)

        if success:
            return {
                "success": True,
                "message": f"Trade logged: {trade_request.action} {trade_request.symbol} at ₹{trade_request.price}"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to log trade")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/journal/open")
async def get_open_trades():
    """Get currently open trades with current prices"""
    try:
        open_trades = trade_journal.get_open_trades()

        # Get current prices for open positions
        symbols = list(set(trade.get("symbol") for trade in open_trades if trade.get("symbol")))
        current_prices = await get_current_prices(symbols)

        # Enhance open trades with current prices and P&L
        enhanced_trades = []
        for trade in open_trades:
            symbol = trade.get("symbol", "")
            current_price = current_prices.get(symbol, 0)
            entry_price = trade.get("entry_price", 0)
            quantity = trade.get("quantity", 1)
            action = trade.get("action", "")

            # Calculate current P&L
            current_pnl = 0
            if current_price > 0 and entry_price > 0:
                if action == "BUY":
                    current_pnl = round((current_price - entry_price) * quantity, 2)
                elif action == "SELL":
                    current_pnl = round((entry_price - current_price) * quantity, 2)

            enhanced_trade = trade.copy()
            enhanced_trade.update({
                "current_price": current_price,
                "current_pnl": current_pnl,
                "price_change": current_price - entry_price if entry_price > 0 else 0,
                "price_change_pct": ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            })
            enhanced_trades.append(enhanced_trade)

        return {
            "items": enhanced_trades,
            "count": len(enhanced_trades)
        }

    except Exception as e:
        logger.error(f"Error getting open trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/journal/close/{trade_id}")
async def close_trade(trade_id: str, exit_price: float, notes: str = ""):
    """Close an open trade"""
    try:
        success = trade_journal.close_trade(trade_id, exit_price, notes)

        if success:
            return {
                "success": True,
                "message": f"Trade {trade_id} closed at ₹{exit_price}"
            }
        else:
            raise HTTPException(status_code=404, detail="Trade not found or already closed")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/journal/close-symbol/{symbol}")
async def close_all_trades_for_symbol(symbol: str, exit_price: float, notes: str = ""):
    """Close all open trades for a specific symbol"""
    try:
        symbol = symbol.upper()
        closed_trades = []
        
        # Get all open trades for this symbol
        open_trades = trade_journal.get_open_trades()
        symbol_trades = [t for t in open_trades if t.get('symbol') == symbol]
        
        if not symbol_trades:
            raise HTTPException(status_code=404, detail=f"No open trades found for {symbol}")
        
        # Close each trade
        for trade in symbol_trades:
            trade_id = trade['trade_id']
            success = trade_journal.close_trade(trade_id, exit_price, notes)
            if success:
                closed_trades.append(trade_id)
            else:
                logger.warning(f"Failed to close trade {trade_id} for {symbol}")
        
        if closed_trades:
            return {
                "success": True,
                "message": f"Closed {len(closed_trades)} trades for {symbol} at ₹{exit_price}",
                "closed_trades": closed_trades
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to close any trades for {symbol}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing trades for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/journal/stats")
async def get_portfolio_stats():
    """Get portfolio performance statistics"""
    try:
        stats = trade_journal.get_portfolio_stats()
        return stats

    except Exception as e:
        logger.error(f"Error getting portfolio stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/journal/positions")
async def get_current_positions():
    """Get current stock positions"""
    try:
        positions = trade_journal.get_all_positions()
        return {
            "positions": positions,
            "total_positions": len(positions)
        }

    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/journal/position/{symbol}")
async def get_position_for_symbol(symbol: str):
    """Get current position for a specific symbol"""
    try:
        symbol = symbol.upper()
        position = trade_journal.get_current_position(symbol)

        return {
            "symbol": symbol,
            "position": position,
            "can_sell": position > 0
        }

    except Exception as e:
        logger.error(f"Error getting position for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
