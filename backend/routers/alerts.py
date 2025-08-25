from fastapi import APIRouter
import random
from datetime import datetime

router = APIRouter(prefix="/api", tags=["alerts"])

SYMBOLS = ["RELIANCE","HDFCBANK","TCS","INFY","ICICIBANK","SBIN","BHARTIARTL","LT","ITC","KOTAKBANK","HINDUNILVR","AXISBANK"]

def mock_alert(symbol: str):
    severity = random.choice(["buy","sell","warn"])
    msg = {
        "buy": "Crossed VWAP upward",
        "sell": "RSI overbought; pullback",
        "warn": "Gap spike detected"
    }[severity]
    return {"symbol": symbol, "severity": severity, "message": msg, "ts": datetime.utcnow().isoformat()}

@router.get("/alerts")
async def get_alerts(limit: int = 15):
    """Get recent trading alerts"""
    items = [mock_alert(random.choice(SYMBOLS)) for _ in range(limit)]
    return {"items": items}
