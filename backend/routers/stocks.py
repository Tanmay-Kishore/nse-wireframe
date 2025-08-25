from fastapi import APIRouter, Query
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
    items = [mock_stock(s) for s in SYMBOLS]
    if q:
        ql = q.lower()
        items = [s for s in items if ql in s["symbol"].lower() or ql in s["name"].lower()]
    if min_gap is not None:
        items = [s for s in items if abs(s["gap"]) >= float(min_gap)]
    if min_volume is not None:
        items = [s for s in items if s["volume"] >= int(min_volume)]
    return {"items": items[:limit]}

@router.get("/stocks/{symbol}")
async def get_stock(symbol: str):
    """Get detailed information for a specific stock"""
    s = mock_stock(symbol.upper())
    s["alerts"] = [mock_alert(symbol) for _ in range(random.randint(0,3))]
    # history (wireframe)
    s["history"] = [{"ts": (datetime.utcnow() - timedelta(minutes=i)).isoformat(), "price": round(s["price"]*(1+random.uniform(-0.01,0.01)),2)} for i in range(60)]
    return s
