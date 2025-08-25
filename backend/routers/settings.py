from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
from datetime import datetime, timedelta
import asyncio

router = APIRouter(prefix="/api", tags=["settings"])

# Configuration file paths
UPSTOX_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "upstox_config.json")
TELEGRAM_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "telegram_config.json")

class UpstoxConfig(BaseModel):
    access_token: str
    api_key: str = ""
    api_secret: str = ""

class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str
    username: str = ""

class Settings(BaseModel):
    telegram_linked: bool = False
    thresholds: dict = {"gap": 2.0, "rsi": 70}
    upstox_connected: bool = False
    upstox_token_expiry: str = ""

def ensure_config_dir():
    """Ensure config directory exists"""
    config_dir = os.path.dirname(UPSTOX_CONFIG_FILE)
    os.makedirs(config_dir, exist_ok=True)

def load_upstox_config():
    """Load Upstox configuration from file"""
    try:
        if os.path.exists(UPSTOX_CONFIG_FILE):
            with open(UPSTOX_CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading Upstox config: {e}")
    return None

def save_upstox_config(config_data):
    """Save Upstox configuration to file"""
    try:
        ensure_config_dir()
        with open(UPSTOX_CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving Upstox config: {e}")
        return False

def load_telegram_config():
    """Load Telegram configuration from file"""
    try:
        if os.path.exists(TELEGRAM_CONFIG_FILE):
            with open(TELEGRAM_CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading Telegram config: {e}")
    return None

def save_telegram_config(config_data):
    """Save Telegram configuration to file"""
    try:
        ensure_config_dir()
        with open(TELEGRAM_CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving Telegram config: {e}")
        return False

@router.get("/settings")
async def get_settings():
    """Get all application settings"""
    upstox_config = load_upstox_config()
    telegram_config = load_telegram_config()
    
    upstox_connected = False
    upstox_token_expiry = ""
    telegram_connected = False
    
    if upstox_config:
        upstox_connected = bool(upstox_config.get("access_token"))
        upstox_token_expiry = upstox_config.get("expires_at", "")
    
    if telegram_config:
        telegram_connected = bool(telegram_config.get("bot_token") and telegram_config.get("chat_id"))
    
    return {
        "telegram_linked": telegram_connected, 
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
        if os.path.exists(UPSTOX_CONFIG_FILE):
            os.remove(UPSTOX_CONFIG_FILE)
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

# Telegram endpoints
@router.post("/settings/telegram")
async def save_telegram_settings(config: TelegramConfig):
    """Save Telegram configuration"""
    try:
        config_data = {
            "bot_token": config.bot_token,
            "chat_id": config.chat_id,
            "created_at": datetime.now().isoformat(),
        }
        
        if save_telegram_config(config_data):
            return {"success": True, "message": "Telegram configuration saved successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Configuration error: {str(e)}")

@router.delete("/settings/telegram")
async def disconnect_telegram():
    """Disconnect Telegram bot"""
    try:
        if os.path.exists(TELEGRAM_CONFIG_FILE):
            os.remove(TELEGRAM_CONFIG_FILE)
        return {"success": True, "message": "Telegram configuration removed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing configuration: {str(e)}")

@router.get("/settings/telegram/status")
async def get_telegram_status():
    """Check Telegram connection status"""
    config = load_telegram_config()
    if not config:
        return {"connected": False, "message": "No configuration found"}
    
    return {
        "connected": bool(config.get("bot_token") and config.get("chat_id")),
        "created_at": config.get("created_at"),
        "message": "Bot configured"
    }

@router.post("/settings/telegram/start")
async def start_telegram_bot():
    """Start the Telegram bot"""
    try:
        # Import here to avoid circular imports
        from services.telegram_bot import telegram_bot, start_telegram_bot_if_configured
        
        config = load_telegram_config()
        if not config or not config.get("bot_token"):
            raise HTTPException(status_code=400, detail="Telegram not configured")
        
        bot_token = config["bot_token"]
        success = await telegram_bot.start_bot(bot_token)
        
        if success:
            return {"success": True, "message": "Telegram bot started successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to start bot")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting bot: {str(e)}")

@router.post("/settings/telegram/stop")
async def stop_telegram_bot():
    """Stop the Telegram bot"""
    try:
        from services.telegram_bot import telegram_bot
        
        await telegram_bot.stop_bot()
        return {"success": True, "message": "Telegram bot stopped"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping bot: {str(e)}")

@router.post("/settings/telegram/test")
async def test_telegram_message():
    """Send a test message to configured chat"""
    try:
        from services.telegram_bot import send_alert
        
        test_message = """
🧪 **Test Alert from NSE Monitor**

This is a test message to verify your Telegram integration is working correctly.

✅ Configuration successful!
📱 You will receive stock alerts here
🕐 Timestamp: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        success = await send_alert(test_message)
        
        if success:
            return {"success": True, "message": "Test message sent successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send test message")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending test message: {str(e)}")
