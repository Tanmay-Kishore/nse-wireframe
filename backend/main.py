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
    from routers import stocks, alerts, journal, settings, websocket
    from routers import nifty, indexes
except ImportError:
    # If running from root directory
    from backend.routers import stocks, alerts, journal, settings, websocket
    from backend.routers import nifty, indexes

app = FastAPI(title="NSE Monitor Wireframe")

# Auto-start Telegram bot if configured
@app.on_event("startup")
async def startup_event():
    try:
        from services.telegram_bot import start_telegram_bot_if_configured
        await start_telegram_bot_if_configured()
    except Exception as e:
        print(f"Warning: Could not auto-start Telegram bot: {e}")

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