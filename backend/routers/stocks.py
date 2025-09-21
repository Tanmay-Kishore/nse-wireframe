from fastapi import APIRouter, HTTPException
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

@router.get("/stocks")
async def list_stocks(q: Optional[str] = None, min_gap: Optional[float] = None, min_volume: Optional[int] = None, limit: int = 20):
    """Get list of stocks with optional filters"""
    try:
        with open(instruments_path, 'r') as f:
            instruments = json.load(f)
        symbol_to_key = {inst['tradingsymbol'].upper(): inst['instrument_key'] for inst in instruments if 'tradingsymbol' in inst and 'instrument_key' in inst}

        # Prepare list of symbols
        symbols = get_watchlist_symbols()
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
            symbols_to_fetch = symbols_to_fetch[:limit]

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

@router.get("/stocks/{symbol}")
async def get_stock(symbol: str):
    """Get detailed information for a specific stock"""
    try:
        symbol = symbol.upper()

        with open(instruments_path, 'r') as f:
            instruments = json.load(f)
        symbol_to_key = {inst['tradingsymbol'].upper(): inst['instrument_key'] for inst in instruments if 'tradingsymbol' in inst and 'instrument_key' in inst}

        instrument_key = symbol_to_key.get(symbol)
        if not instrument_key:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found in instruments")

        if not upstox.is_configured():
            raise HTTPException(status_code=503, detail="Market data service not configured")

        upstox_key = f"NSE_EQ:{symbol}"
        quotes_data = upstox.get_market_quotes_batch([instrument_key])
        quote = quotes_data.get(upstox_key, {})

        if not quote:
            raise HTTPException(status_code=404, detail=f"No market data available for {symbol}")

        stock_data = upstox.format_stock_data(symbol, quote)
        stock_data["data_source"] = "upstox"

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

        return stock_data

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
