from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
from datetime import datetime, timedelta

router = APIRouter(prefix="/api", tags=["settings"])

# Configuration file path
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "upstox_config.json")

class UpstoxConfig(BaseModel):
    access_token: str
    api_key: str = ""
    api_secret: str = ""

class Settings(BaseModel):
    telegram_linked: bool = False
    thresholds: dict = {"gap": 2.0, "rsi": 70}
    upstox_connected: bool = False
    upstox_token_expiry: str = ""

def ensure_config_dir():
    """Ensure config directory exists"""
    config_dir = os.path.dirname(CONFIG_FILE)
    os.makedirs(config_dir, exist_ok=True)

def load_upstox_config():
    """Load Upstox configuration from file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading Upstox config: {e}")
    return None

def save_upstox_config(config_data):
    """Save Upstox configuration to file"""
    try:
        ensure_config_dir()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving Upstox config: {e}")
        return False

@router.get("/settings")
async def get_settings():
    """Get application settings"""
    upstox_config = load_upstox_config()
    upstox_connected = False
    upstox_token_expiry = ""
    
    if upstox_config:
        upstox_connected = bool(upstox_config.get("access_token"))
        upstox_token_expiry = upstox_config.get("expires_at", "")
    
    return {
        "telegram_linked": False, 
        "thresholds": {"gap": 2.0, "rsi": 70},
        "upstox_connected": upstox_connected,
        "upstox_token_expiry": upstox_token_expiry
    }

@router.post("/settings/upstox")
async def configure_upstox(config: UpstoxConfig):
    """Configure Upstox API settings"""
    try:
        # Calculate expiry date (Upstox tokens expire next day at market close)
        tomorrow = datetime.now() + timedelta(days=1)
        expiry_time = tomorrow.replace(hour=15, minute=30, second=0, microsecond=0)  # 3:30 PM next day
        
        config_data = {
            "access_token": config.access_token,
            "api_key": config.api_key,
            "api_secret": config.api_secret,
            "created_at": datetime.now().isoformat(),
            "expires_at": expiry_time.isoformat()
        }
        
        if save_upstox_config(config_data):
            return {
                "success": True, 
                "message": "Upstox configuration saved successfully",
                "expires_at": expiry_time.isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Configuration error: {str(e)}")

@router.delete("/settings/upstox")
async def disconnect_upstox():
    """Disconnect Upstox API"""
    try:
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        return {"success": True, "message": "Upstox configuration removed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing configuration: {str(e)}")

@router.get("/settings/upstox/status")
async def get_upstox_status():
    """Check Upstox connection status"""
    config = load_upstox_config()
    if not config:
        return {"connected": False, "message": "No configuration found"}
    
    # Check if token is expired
    try:
        expires_at = datetime.fromisoformat(config.get("expires_at", ""))
        if datetime.now() > expires_at:
            return {"connected": False, "message": "Token expired", "expired": True}
    except:
        pass
    
    return {
        "connected": bool(config.get("access_token")),
        "expires_at": config.get("expires_at"),
        "message": "Token active"
    }
