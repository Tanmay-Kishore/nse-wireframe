from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import random
from datetime import datetime, timedelta

router = APIRouter(prefix="/api", tags=["stocks"])

# Mock data helpers (wireframe)
SYMBOLS = ["RELIANCE","HDFCBANK","TCS","INFY","ICICIBANK","SBIN","BHARTIARTL","LT","ITC","KOTAKBANK","HINDUNILVR","AXISBANK"]
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
        # Try to use Upstox API first
        from services.upstox_service import get_upstox_service
        upstox = get_upstox_service()
        
        if upstox.is_configured():
            # Get real data from Upstox
            symbols_to_fetch = SYMBOLS[:limit]  # Limit API calls
            
            if q:  # If search query provided, try to find matching symbols
                search_results = upstox.search_instruments(q)
                if search_results:
                    # Extract symbols from search results
                    symbols_to_fetch = [result.get("tradingsymbol", result.get("instrument_key", "").split(":")[-1]) 
                                      for result in search_results[:limit]]
                else:
                    # Filter existing symbols by query
                    ql = q.lower()
                    symbols_to_fetch = [s for s in SYMBOLS if ql in s.lower() or ql in NAMES.get(s, "").lower()][:limit]
            
            # Fetch real market data
            quotes_data = upstox.get_market_quotes_batch(symbols_to_fetch)
            items = []
            
            for symbol in symbols_to_fetch:
                instrument_key = f"NSE_EQ:{symbol}"
                quote = quotes_data.get(instrument_key, {})
                
                if quote:
                    stock_data = upstox.format_stock_data(symbol, quote)
                else:
                    # Fallback to mock data for this symbol
                    stock_data = mock_stock(symbol)
                    stock_data["data_source"] = "mock"
                
                items.append(stock_data)
            
            # Apply filters
            if min_gap is not None:
                items = [s for s in items if abs(s["gap"]) >= float(min_gap)]
            if min_volume is not None:
                items = [s for s in items if s["volume"] >= int(min_volume)]
            
            return {"items": items, "data_source": "upstox"}
        
        else:
            # Fallback to mock data
            items = [mock_stock(s) for s in SYMBOLS]
            if q:
                ql = q.lower()
                items = [s for s in items if ql in s["symbol"].lower() or ql in s["name"].lower()]
            if min_gap is not None:
                items = [s for s in items if abs(s["gap"]) >= float(min_gap)]
            if min_volume is not None:
                items = [s for s in items if s["volume"] >= int(min_volume)]
            return {"items": items[:limit], "data_source": "mock"}
            
    except Exception as e:
        # If Upstox fails, fallback to mock data
        items = [mock_stock(s) for s in SYMBOLS]
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
        # Try to use Upstox API first
        from services.upstox_service import get_upstox_service
        upstox = get_upstox_service()
        
        symbol = symbol.upper()
        
        if upstox.is_configured():
            # Get real data from Upstox
            quote_data = upstox.get_market_quote(symbol)
            
            if quote_data:
                s = upstox.format_stock_data(symbol, quote_data)
                s["data_source"] = "upstox"
                
                # Try to get historical data
                historical_data = upstox.get_historical_data(symbol)
                if historical_data:
                    # Convert to our format (last 60 data points)
                    s["history"] = []
                    for i, candle in enumerate(historical_data[-60:]):
                        if len(candle) >= 5:  # [timestamp, open, high, low, close, volume]
                            s["history"].append({
                                "ts": candle[0],
                                "price": candle[4]  # Close price
                            })
                else:
                    # Fallback to simulated history
                    s["history"] = [{"ts": (datetime.utcnow() - timedelta(minutes=i)).isoformat(), 
                                   "price": round(s["price"]*(1+random.uniform(-0.01,0.01)),2)} 
                                  for i in range(60)]
            else:
                # Upstox failed for this symbol, use mock data
                s = mock_stock(symbol)
                s["data_source"] = "mock"
                s["history"] = [{"ts": (datetime.utcnow() - timedelta(minutes=i)).isoformat(), 
                               "price": round(s["price"]*(1+random.uniform(-0.01,0.01)),2)} 
                              for i in range(60)]
        else:
            # No Upstox config, use mock data
            s = mock_stock(symbol)
            s["data_source"] = "mock"
            s["history"] = [{"ts": (datetime.utcnow() - timedelta(minutes=i)).isoformat(), 
                           "price": round(s["price"]*(1+random.uniform(-0.01,0.01)),2)} 
                          for i in range(60)]
        
        # Add mock alerts (could be enhanced with real alert logic)
        s["alerts"] = [mock_alert(symbol) for _ in range(random.randint(0,3))]
        
        return s
        
    except Exception as e:
        # Fallback to mock data on any error
        s = mock_stock(symbol.upper())
        s["alerts"] = [mock_alert(symbol) for _ in range(random.randint(0,3))]
        s["history"] = [{"ts": (datetime.utcnow() - timedelta(minutes=i)).isoformat(), 
                        "price": round(s["price"]*(1+random.uniform(-0.01,0.01)),2)} 
                       for i in range(60)]
        s["data_source"] = "mock"
        s["error"] = str(e)
        return s
