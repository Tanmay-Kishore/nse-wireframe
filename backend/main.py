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
except ImportError:
    # If running from root directory
    from backend.routers import stocks, alerts, journal, settings, websocket

app = FastAPI(title="NSE Monitor Wireframe")

# CORS (adjust as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(stocks.router)
app.include_router(alerts.router)
app.include_router(journal.router)
app.include_router(settings.router)
app.include_router(websocket.router)

@app.get("/")
async def root():
    """Serve the overview page"""
    public_index = os.path.join(os.path.dirname(__file__), "..", "public", "index.html")
    return FileResponse(public_index)

# Serve static files (HTML/CSS/JS)
public_dir = os.path.join(os.path.dirname(__file__), "..", "public")
app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")