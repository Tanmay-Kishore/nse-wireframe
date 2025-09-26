from fastapi import APIRouter, HTTPException, WebSocket
from typing import Optional
import os, json, logging
from services.upstox_service import get_upstox_service

upstox = get_upstox_service()
instruments_path = os.path.join(os.path.dirname(__file__), '../data/instruments.json')
router = APIRouter(prefix="/api", tags=["stocks"])

logger = logging.getLogger(__name__)

# Watchlist helpers
watchlist_path = os.path.join(os.path.dirname(__file__), '../data/watchlist.json')

def get_watchlist_symbols():
    try:
        with open(watchlist_path, 'r') as f:
            data = json.load(f)
        return data.get("symbols", [])
    except Exception:
        return []

def get_all_monitored_symbols():
    """Get all symbols from both journal and watchlist"""
    try:
        # Get watchlist symbols
        watchlist_symbols = get_watchlist_symbols()
        
        # Get journal symbols from trades
        from services.trade_journal import get_trade_journal
        trade_journal = get_trade_journal()
        raw_trades = trade_journal.get_trades(limit=1000)  # Get all trades
        
        # Extract unique symbols from trades
        journal_symbols = list(set(trade.get("symbol", "") for trade in raw_trades if trade.get("symbol")))
        
        # Combine and deduplicate
        all_symbols = list(set(watchlist_symbols + journal_symbols))
        return all_symbols
        
    except Exception as e:
        logger.error(f"Error getting all monitored symbols: {e}")
        return []

@router.get("/stocks")
async def list_stocks(q: Optional[str] = None, min_gap: Optional[float] = None, min_volume: Optional[int] = None, limit: int = 20):
    """Get list of stocks with optional filters"""
    try:
        with open(instruments_path, 'r') as f:
            instruments = json.load(f)
        symbol_to_key = {inst['tradingsymbol'].upper(): inst['instrument_key'] for inst in instruments if 'tradingsymbol' in inst and 'instrument_key' in inst}

        # Prepare list of symbols in alphabetical order
        symbols = sorted(get_watchlist_symbols())
        symbols_to_fetch = symbols[:limit]

        # Apply search filter if provided
        if q:
            ql = q.lower()
            # Look up names from instruments data instead of hardcoded NAMES
            symbols_to_fetch = []
            for s in symbols:
                symbol_match = ql in s.lower()
                name_match = False
                # Find name in instruments
                for inst in instruments:
                    if inst.get('tradingsymbol', '').upper() == s.upper():
                        name = inst.get('name', '')
                        if ql in name.lower():
                            name_match = True
                        break
                if symbol_match or name_match:
                    symbols_to_fetch.append(s)
            symbols_to_fetch = sorted(symbols_to_fetch)[:limit]

        # Get instrument keys for symbols
        instrument_keys = [symbol_to_key.get(s.upper()) for s in symbols_to_fetch if symbol_to_key.get(s.upper())]

        if not upstox.is_configured():
            raise HTTPException(status_code=503, detail="Market data service not configured")

        if not instrument_keys:
            return {"items": [], "message": "No valid instruments found for watchlist symbols"}

        # Fetch real market data
        quotes_data = upstox.get_market_quotes_batch(instrument_keys)
        items = []

        for symbol in symbols_to_fetch:
            upstox_key = f"NSE_EQ:{symbol}"
            quote = quotes_data.get(upstox_key, {})
            if quote:
                stock_data = upstox.format_stock_data(symbol, quote)
                stock_data["data_source"] = "upstox"
                if "instrument_token" in quote:
                    stock_data["instrument_token"] = quote["instrument_token"]
                items.append(stock_data)

        # Apply filters
        if min_gap is not None:
            items = [s for s in items if abs(s["gap"]) >= float(min_gap)]
        if min_volume is not None:
            items = [s for s in items if s["volume"] >= int(min_volume)]

        return {"items": items, "data_source": "upstox"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching stocks: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching market data: {str(e)}")

@router.websocket("/stocks/{symbol}")
async def ws_get_stock(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for real-time stock data and updates"""
    await websocket.accept()

    try:
        symbol = symbol.upper()

        with open(instruments_path, 'r') as f:
            instruments = json.load(f)
        symbol_to_key = {inst['tradingsymbol'].upper(): inst['instrument_key'] for inst in instruments if 'tradingsymbol' in inst and 'instrument_key' in inst}

        instrument_key = symbol_to_key.get(symbol)
        if not instrument_key:
            await websocket.send_json({"error": f"Symbol {symbol} not found in instruments"})
            await websocket.close()
            return

        if not upstox.is_configured():
            await websocket.send_json({"error": "Market data service not configured"})
            await websocket.close()
            return

        # Send initial stock data
        upstox_key = f"NSE_EQ:{symbol}"
        quotes_data = upstox.get_market_quotes_batch([instrument_key])
        quote = quotes_data.get(upstox_key, {})

        if not quote:
            await websocket.send_json({"error": f"No market data available for {symbol}"})
            await websocket.close()
            return

        stock_data = upstox.format_stock_data(symbol, quote)
        stock_data["data_source"] = "upstox"
        stock_data["type"] = "initial"

        if "instrument_token" in quote:
            stock_data["instrument_token"] = quote["instrument_token"]

        # Get historical data for price history
        historical_data = upstox.get_historical_data(symbol)
        if historical_data:
            stock_data["history"] = []
            for candle in historical_data[-60:]:
                if len(candle) >= 5:
                    stock_data["history"].append({
                        "ts": candle[0],
                        "price": candle[4]
                    })
        else:
            stock_data["history"] = []
            logger.warning(f"No historical data available for {symbol}")

        # For now, return empty alerts array - this should be replaced with real alert system
        stock_data["alerts"] = []

        # Send initial data wrapped in stock property as expected by frontend
        initial_data = {
            "stock": stock_data,
            "type": "initial"
        }
        
        # Validate JSON serializability of initial data
        try:
            json.dumps(initial_data)
        except (TypeError, ValueError) as json_error:
            logger.error(f"Invalid JSON initial data for {symbol}: {json_error}")
            await websocket.send_json({"error": "Invalid data format"})
            await websocket.close()
            return
            
        logger.info(f"Sending initial data for {symbol}")
        await websocket.send_json(initial_data)

        # Now subscribe to real-time updates for this symbol
        try:
            async for tick in upstox.subscribe_price_stream([instrument_key]):
                # Find if this tick is for our symbol
                tick_instrument_key = tick.get("instrument_key")
                if tick_instrument_key == instrument_key:
                    try:
                        # Convert raw tick to quote format for processing
                        quote_data = {
                            "last_price": tick.get("ltp", 0),
                            "prev_close_price": tick.get("cp", tick.get("ltp", 0)),
                            "open_price": tick.get("open", tick.get("ltp", 0)),
                            "volume": tick.get("vol", 0),
                            "average_price": tick.get("atp", tick.get("ltp", 0)),
                            "ohlc": {
                                "open": tick.get("open", 0),
                                "high": tick.get("high", 0),
                                "low": tick.get("low", 0),
                                "close": tick.get("close", tick.get("ltp", 0))
                            }
                        }

                        # Format using the existing formatter
                        formatted_stock_data = upstox.format_stock_data(symbol, quote_data)
                        formatted_stock_data["type"] = "update"
                        formatted_stock_data["symbol"] = symbol

                        # Extract only the fields that the frontend expects for updates
                        update_fields = {
                            "price": formatted_stock_data.get("price"),
                            "gap": formatted_stock_data.get("gap"),
                            "volume": formatted_stock_data.get("volume"),
                            "vwap": formatted_stock_data.get("vwap"),
                            "rsi": formatted_stock_data.get("rsi"),
                            "ma20": formatted_stock_data.get("ma20"),
                            "ma50": formatted_stock_data.get("ma50"),
                            "ma200": formatted_stock_data.get("ma200"),
                            "bb_upper": formatted_stock_data.get("bb_upper"),
                            "bb_lower": formatted_stock_data.get("bb_lower")
                        }

                        # Ensure all values are JSON serializable
                        for key, value in update_fields.items():
                            if value is None or (isinstance(value, float) and (value != value or value == float('inf') or value == float('-inf'))):
                                update_fields[key] = 0  # Replace invalid values with 0

                        # Send real-time update wrapped in updates property as expected by frontend
                        update_message = {
                            "type": "update",
                            "updates": update_fields
                        }

                        # Validate JSON serializability
                        try:
                            json.dumps(update_message)
                        except (TypeError, ValueError) as json_error:
                            logger.error(f"Invalid JSON data for {symbol}: {json_error}, data: {update_message}")
                            continue

                        logger.debug(f"Sending update for {symbol}: {update_message}")

                        # Send real-time update with only the changed fields
                        try:
                            await websocket.send_json(update_message)
                        except Exception as send_error:
                            logger.error(f"Error sending data for symbol {symbol}: {send_error} (type: {type(send_error).__name__})")
                            if "close message has been sent" in str(send_error):
                                logger.info(f"WebSocket disconnected, stopping tick processing for {symbol}")
                                break
                            else:
                                logger.error(f"Unexpected error sending data for symbol {symbol}: {send_error}")
                                continue

                    except Exception as e:
                        logger.error(f"Error processing tick data for symbol {symbol}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error in stock price stream for {symbol}: {e}")
            await websocket.send_json({"error": "Price streaming service unavailable"})
            return

    except Exception as e:
        logger.error(f"Error in stock WebSocket for {symbol}: {e}")
        try:
            await websocket.send_json({"error": f"Internal server error: {str(e)}"})
        except:
            pass
        await websocket.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching stock data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching data for {symbol}: {str(e)}")
    
@router.get("/watchlist/check/{symbol}")
async def check_watchlist_status(symbol: str):
    """Check if a symbol is in the watchlist"""
    symbol = symbol.upper()
    try:
        symbols = get_watchlist_symbols()
        return {"symbol": symbol, "in_watchlist": symbol in symbols}
    except Exception as e:
        return {"symbol": symbol, "in_watchlist": False, "error": str(e)}

@router.post("/watchlist/add")
async def add_to_watchlist(symbol: str):
    """Add a stock symbol to the watchlist"""
    symbol = symbol.upper()
    try:
        with open(watchlist_path, 'r') as f:
            data = json.load(f)
        symbols = set(data.get("symbols", []))
        symbols.add(symbol)
        data["symbols"] = list(symbols)
        with open(watchlist_path, 'w') as f:
            json.dump(data, f, indent=2)
        return {"success": True, "symbols": data["symbols"]}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/watchlist/remove")
async def remove_from_watchlist(symbol: str):
    """Remove a stock symbol from the watchlist"""
    symbol = symbol.upper()
    try:
        with open(watchlist_path, 'r') as f:
            data = json.load(f)
        symbols = set(data.get("symbols", []))
        symbols.discard(symbol)
        data["symbols"] = list(symbols)
        with open(watchlist_path, 'w') as f:
            json.dump(data, f, indent=2)
        return {"success": True, "symbols": data["symbols"]}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/stocks/{symbol}/chart")
async def get_stock_chart_data(symbol: str):
    """Get historical chart data for a stock"""
    try:
        symbol = symbol.upper()

        if not upstox.is_configured():
            raise HTTPException(status_code=503, detail="Market data service not configured")

        historical_data = upstox.get_historical_data(symbol)

        if not historical_data or len(historical_data) == 0:
            raise HTTPException(status_code=404, detail=f"No historical data available for {symbol}")

        chart_data = []
        for candle in historical_data[-30:]:  # Last 30 days
            if len(candle) >= 5:
                chart_data.append({
                    "time": candle[0][:10],  # Date only (YYYY-MM-DD)
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": int(candle[5]) if len(candle) > 5 else 0
                })

        if not chart_data:
            raise HTTPException(status_code=404, detail=f"No valid chart data found for {symbol}")

        return {"symbol": symbol, "data": chart_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chart data for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching chart data for {symbol}: {str(e)}")
