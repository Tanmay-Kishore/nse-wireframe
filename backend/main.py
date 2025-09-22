import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add the backend directory to Python path to handle imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import routers
try:
    from routers import stocks, alerts, journal, settings, websocket, notifications
    from routers import nifty, indexes
except ImportError:
    # If running from root directory
    from backend.routers import stocks, alerts, journal, settings, websocket, notifications
    from backend.routers import nifty, indexes

app = FastAPI(title="NSE Monitor Wireframe")

# Auto-start services if configured
@app.on_event("startup")
async def startup_event():
    try:
        from services.telegram_bot import start_telegram_bot_if_configured
        await start_telegram_bot_if_configured()
    except Exception as e:
        print(f"Warning: Could not auto-start Telegram bot: {e}")

    try:
        from services.stop_loss_monitor import start_stop_loss_monitoring
        from services.upstox_service import get_upstox_service

        upstox = get_upstox_service()
        if upstox.is_configured():
            await start_stop_loss_monitoring(interval_minutes=2)
            print("✅ Stop-loss monitoring auto-started")
        else:
            print("⚠️ Stop-loss monitoring not started: Upstox not configured")
    except Exception as e:
        print(f"Warning: Could not auto-start stop-loss monitoring: {e}")

    # Real-time monitoring using periodic checks instead
    try:
        from services.signal_monitor import start_signal_monitoring
        await start_signal_monitoring(interval_minutes=2)
        print("✅ Signal monitoring auto-started (2-minute intervals)")
    except Exception as e:
        print(f"Warning: Could not auto-start signal monitoring: {e}")

# CORS (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/data", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "data")), name="data")
# Include routers
app.include_router(stocks.router)
app.include_router(alerts.router)
app.include_router(journal.router)
app.include_router(settings.router)
app.include_router(websocket.router)
app.include_router(notifications.router)
app.include_router(nifty.router)
app.include_router(indexes.router)

@app.get("/")
async def root():
    """Serve the overview page"""
    public_index = os.path.join(os.path.dirname(__file__), "..", "public", "index.html")
    return FileResponse(public_index)

# Serve static files (HTML/CSS/JS)
public_dir = os.path.join(os.path.dirname(__file__), "..", "public")
app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")