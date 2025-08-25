from fastapi import APIRouter
import random
from datetime import datetime

router = APIRouter(prefix="/api", tags=["journal"])

SYMBOLS = ["RELIANCE","HDFCBANK","TCS","INFY","ICICIBANK","SBIN","BHARTIARTL","LT","ITC","KOTAKBANK","HINDUNILVR","AXISBANK"]

@router.get("/journal")
async def get_journal():
    """Get trading journal entries"""
    items = []
    for _ in range(8):
        sym = random.choice(SYMBOLS)
        entry = round(random.uniform(100,2000),2)
        direction = random.choice(["LONG","SHORT"])
        pnl = round(random.uniform(-5000, 5000),2)
        items.append({
            "date": datetime.utcnow().isoformat(),
            "symbol": sym,
            "direction": direction,
            "entry": entry,
            "sl": round(entry*0.98,2),
            "target": round(entry*1.03,2),
            "exit": round(entry*(1+random.uniform(-0.02,0.02)),2),
            "pnl": pnl
        })
    return {"items": items}
