from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import random
from datetime import datetime, timedelta
import os, json, logging
from services.upstox_service import get_upstox_service

upstox = get_upstox_service()
instruments_path = os.path.join(os.path.dirname(__file__), '../data/instruments.json')
router = APIRouter(prefix="/api", tags=["stocks"])

# Mock data helpers (wireframe)
watchlist_path = os.path.join(os.path.dirname(__file__), '../data/watchlist.json')

def get_watchlist_symbols():
    try:
        with open(watchlist_path, 'r') as f:
            data = json.load(f)
        # Expecting {"symbols": ["RELIANCE", ...]}
        return data.get("symbols", [])
    except Exception:
        return []
NAMES = {
    "RELIANCE": "Reliance Industries",
    "HDFCBANK": "HDFC Bank",
    "TCS": "Tata Consultancy Services",
    "INFY": "Infosys",
    "ICICIBANK": "ICICI Bank",
    "SBIN": "State Bank of India",
    "BHARTIARTL": "Bharti Airtel",
    "LT": "Larsen & Toubro",
    "ITC": "ITC",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "HINDUNILVR": "Hindustan Unilever",
    "AXISBANK": "Axis Bank",
}

def mock_stock(symbol: str):
    base = random.uniform(100, 3000)
    gap = random.uniform(-5, 5)
    s = {
        "symbol": symbol,
        "name": NAMES.get(symbol, symbol),
        "price": round(base * (1 + gap/100), 2),
        "gap": round(gap, 2),
        "volume": random.randint(1_00_000, 2_00_00_000),
        "vwap": round(base * (1 + random.uniform(-0.5,0.5)/100), 2),
        "rsi": round(random.uniform(20, 80), 1),
        "ma20": round(base * (1 + random.uniform(-1,1)/100), 2),
        "ma50": round(base * (1 + random.uniform(-2,2)/100), 2),
        "ma200": round(base * (1 + random.uniform(-5,5)/100), 2),
        "sentiment": random.choice(["bullish","bearish","neutral"]),
        "signal": {
            "direction": random.choice(["BUY","SELL","HOLD"]),
            "entry": round(base, 2),
            "sl": round(base * 0.98, 2),
            "target": round(base * 1.03, 2)
        }
    }
    return s

def mock_alert(symbol: str):
    severity = random.choice(["buy","sell","warn"])
    msg = {
        "buy": "Crossed VWAP upward",
        "sell": "RSI overbought; pullback",
        "warn": "Gap spike detected"
    }[severity]
    return {"symbol": symbol, "severity": severity, "message": msg, "ts": datetime.utcnow().isoformat()}

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
        if q:
            ql = q.lower()
            symbols_to_fetch = [s for s in symbols if ql in s.lower() or ql in NAMES.get(s, "").lower()][:limit]
        # Get instrument keys for symbols
        instrument_keys = [symbol_to_key.get(s.upper()) for s in symbols_to_fetch if symbol_to_key.get(s.upper())]
        # Fetch real market data
        items = []
        quotes_data = {}
        if upstox.is_configured() and instrument_keys:
            quotes_data = upstox.get_market_quotes_batch(instrument_keys)
        for symbol in symbols_to_fetch:
            # Upstox response uses NSE_EQ:SYMBOL as key
            upstox_key = f"NSE_EQ:{symbol}"
            quote = quotes_data.get(upstox_key, {})
            if quote:
                stock_data = upstox.format_stock_data(symbol, quote)
                stock_data["data_source"] = "upstox"
                # Optionally add instrument_token from quote
                if "instrument_token" in quote:
                    stock_data["instrument_token"] = quote["instrument_token"]
            else:
                stock_data = mock_stock(symbol)
                stock_data["data_source"] = "mock"
            items.append(stock_data)
        # Apply filters
        if min_gap is not None:
            items = [s for s in items if abs(s["gap"]) >= float(min_gap)]
        if min_volume is not None:
            items = [s for s in items if s["volume"] >= int(min_volume)]
        return {"items": items, "data_source": "upstox"}
            
    except Exception as e:
        # If Upstox fails, fallback to mock data
        symbols = get_watchlist_symbols()
        items = [mock_stock(s) for s in symbols]
        if q:
            ql = q.lower()
            items = [s for s in items if ql in s["symbol"].lower() or ql in s["name"].lower()]
        if min_gap is not None:
            items = [s for s in items if abs(s["gap"]) >= float(min_gap)]
        if min_volume is not None:
            items = [s for s in items if s["volume"] >= int(min_volume)]
        return {"items": items[:limit], "data_source": "mock", "error": str(e)}

@router.get("/stocks/{symbol}")
async def get_stock(symbol: str):
    """Get detailed information for a specific stock"""
    try:
        symbol = symbol.upper()
        with open(instruments_path, 'r') as f:
            instruments = json.load(f)
        symbol_to_key = {inst['tradingsymbol'].upper(): inst['instrument_key'] for inst in instruments if 'tradingsymbol' in inst and 'instrument_key' in inst}
        instrument_key = symbol_to_key.get(symbol)
        upstox_key = f"NSE_EQ:{symbol}"
        s = None
        if upstox.is_configured() and instrument_key:
            quotes_data = upstox.get_market_quotes_batch([instrument_key])
            quote = quotes_data.get(upstox_key, {})
            if quote:
                s = upstox.format_stock_data(symbol, quote)
                s["data_source"] = "upstox"
                if "instrument_token" in quote:
                    s["instrument_token"] = quote["instrument_token"]
                # Try to get historical data (optional, can be improved)
                historical_data = upstox.get_historical_data(symbol)
                if historical_data:
                    s["history"] = []
                    for i, candle in enumerate(historical_data[-60:]):
                        if len(candle) >= 5:
                            s["history"].append({
                                "ts": candle[0],
                                "price": candle[4]
                            })
                else:
                    s["history"] = [{"ts": (datetime.utcnow() - timedelta(minutes=i)).isoformat(),
                                   "price": round(s["price"]*(1+random.uniform(-0.01,0.01)),2)}
                                  for i in range(60)]
        if not s:
            s = mock_stock(symbol)
            s["data_source"] = "mock"
            s["history"] = [{"ts": (datetime.utcnow() - timedelta(minutes=i)).isoformat(),
                           "price": round(s["price"]*(1+random.uniform(-0.01,0.01)),2)}
                          for i in range(60)]
        s["alerts"] = [mock_alert(symbol) for _ in range(random.randint(0,3))]
        return s
    except Exception as e:
        s = mock_stock(symbol.upper())
        s["alerts"] = [mock_alert(symbol) for _ in range(random.randint(0,3))]
        s["history"] = [{"ts": (datetime.utcnow() - timedelta(minutes=i)).isoformat(),
                        "price": round(s["price"]*(1+random.uniform(-0.01,0.01)),2)}
                       for i in range(60)]
        s["data_source"] = "mock"
        s["error"] = str(e)
        return s
    
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
    symbol = symbol.upper()
    
    # Try to get real historical data from Upstox
    try:
        historical_data = upstox.get_historical_data(symbol)
        if historical_data and len(historical_data) > 0:
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
            
            if chart_data:
                return {"symbol": symbol, "data": chart_data}
    except Exception as e:
        print(f"Error getting historical data: {e}")
    
    # Fallback to mock data
    base_price = random.uniform(100, 3000)
    chart_data = []
    
    for i in range(30):  # 30 days of mock data
        date = (datetime.now() - timedelta(days=29-i)).strftime('%Y-%m-%d')
        # Generate realistic OHLC data
        open_price = base_price * (1 + random.uniform(-0.02, 0.02))
        close_price = open_price * (1 + random.uniform(-0.05, 0.05))
        high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.03))
        low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.03))
        
        chart_data.append({
            "time": date,
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "close": round(close_price, 2),
            "volume": random.randint(100000, 5000000)
        })
        
        base_price = close_price  # Next day starts from previous close
    
    return {"symbol": symbol, "data": chart_data}
