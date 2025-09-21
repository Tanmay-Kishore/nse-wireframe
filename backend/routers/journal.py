from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
from services.trade_journal import get_trade_journal, log_trade

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["journal"])

trade_journal = get_trade_journal()

class TradeRequest(BaseModel):
    symbol: str
    action: str  # BUY or SELL
    price: float
    quantity: int = 1
    confidence: int = 0
    source: str = "manual"

@router.get("/journal")
async def get_journal(limit: int = 50):
    """Get trading journal entries"""
    try:
        raw_trades = trade_journal.get_trades(limit)
        stats = trade_journal.get_portfolio_stats()

        # Format trades for frontend compatibility
        formatted_trades = []
        for trade in raw_trades:
            formatted_trade = {
                "date": trade.get("entry_time", ""),  # Frontend expects 'date'
                "symbol": trade.get("symbol", ""),
                "direction": trade.get("action", ""),  # Frontend expects 'direction'
                "entry": trade.get("entry_price", 0),  # Frontend expects 'entry'
                "sl": trade.get("sl", 0),
                "target": trade.get("target", 0),
                "exit": trade.get("exit_price"),  # Can be null
                "pnl": trade.get("pnl", 0),
                # Additional fields for API users
                "trade_id": trade.get("trade_id", ""),
                "quantity": trade.get("quantity", 1),
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
    """Get currently open trades"""
    try:
        open_trades = trade_journal.get_open_trades()
        return {
            "items": open_trades,
            "count": len(open_trades)
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
