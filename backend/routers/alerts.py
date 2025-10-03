
import os, json
from fastapi import APIRouter, Request
from datetime import datetime

ALERTS_PATH = os.path.join(os.path.dirname(__file__), '../data/alerts.json')

router = APIRouter(prefix="/api", tags=["alerts"])

def load_alerts():
    try:
        with open(ALERTS_PATH, 'r') as f:
            alerts = json.load(f)
        return alerts if isinstance(alerts, list) else []
    except Exception:
        return []

def save_alert(alert):
    alerts = load_alerts()
    alerts.append(alert)
    # Keep only latest 100 alerts
    alerts = alerts[-100:]
    try:
        with open(ALERTS_PATH, 'w') as f:
            json.dump(alerts, f, indent=2)
    except Exception:
        pass

@router.get("/alerts")
async def get_alerts(limit: int = 100):
    """Get recent trading alerts"""
    alerts = load_alerts()
    # Return latest alerts, most recent first
    items = list(reversed(alerts[-limit:]))
    return {
        "items": items,
        "limit": limit
    }

@router.post("/alerts")
async def post_alert(request: Request):
    """Add a new alert (called when Telegram alert is sent)"""
    data = await request.json()
    alert = {
        "ts": data.get("ts", datetime.now().isoformat()),
        "message": data.get("message", ""),
        "symbol": data.get("symbol", "SYSTEM"),
        "severity": data.get("severity", "info")
    }
    save_alert(alert)
    return {"success": True, "alert": alert}
