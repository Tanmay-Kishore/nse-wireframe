from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import json
import os
from datetime import datetime, timedelta
import asyncio
import requests
from urllib.parse import urlencode

router = APIRouter(prefix="/api", tags=["settings"])

# Configuration file paths
UPSTOX_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "upstox_config.json")
TELEGRAM_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "telegram_config.json")
THRESHOLDS_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "thresholds_config.json")

class UpstoxOAuthCredentials(BaseModel):
    api_key: str
    api_secret: str

class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str
    username: str = ""

class ThresholdConfig(BaseModel):
    gap: float
    rsi: int

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
        # Check if token exists and is not expired
        access_token = upstox_config.get("access_token")
        expires_at_str = upstox_config.get("expires_at", "")
        
        if access_token and expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                upstox_connected = datetime.now() < expires_at
            except:
                upstox_connected = False
        else:
            upstox_connected = False
            
        upstox_token_expiry = expires_at_str
    
    if telegram_config:
        telegram_connected = bool(telegram_config.get("bot_token") and telegram_config.get("chat_id"))
    
    return {
        "telegram_linked": telegram_connected, 
        "thresholds": {"gap": 2.0, "rsi": 70},
        "upstox_connected": upstox_connected,
        "upstox_token_expiry": upstox_token_expiry,
        "upstox_api_key": upstox_config.get("api_key", "") if upstox_config else "",
        "upstox_api_secret": upstox_config.get("api_secret", "") if upstox_config else ""
    }

@router.post("/settings/upstox/test")
async def test_upstox_connection():
    """Test Upstox API connection"""
    try:
        from services.upstox_service import get_upstox_service
        upstox = get_upstox_service()
        
        if not upstox.is_configured():
            raise HTTPException(status_code=400, detail="Upstox not configured")
        
        result = upstox.test_connection()
        
        if result.get("success"):
            return {
                "success": True,
                "message": "Upstox connection test successful",
                "user_name": result.get("user_name"),
                "broker": result.get("broker")
            }
        else:
            return {
                "success": False,
                "message": result.get("message", "Connection test failed")
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection test error: {str(e)}")

@router.get("/settings/upstox/quote/{symbol}")
async def get_upstox_quote(symbol: str):
    """Get real-time quote from Upstox for testing"""
    try:
        from services.upstox_service import get_upstox_service
        upstox = get_upstox_service()
        
        if not upstox.is_configured():
            raise HTTPException(status_code=400, detail="Upstox not configured")
        
        quote_data = upstox.get_market_quote(symbol.upper())
        
        if quote_data:
            formatted_data = upstox.format_stock_data(symbol.upper(), quote_data)
            return {
                "success": True,
                "data": formatted_data,
                "raw_data": quote_data
            }
        else:
            return {
                "success": False,
                "message": f"No data found for symbol {symbol}"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quote fetch error: {str(e)}")

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

# Upstox OAuth endpoints
@router.post("/settings/upstox/oauth/temp")
async def store_temp_upstox_credentials(config: UpstoxOAuthCredentials):
    """Temporarily store Upstox API credentials for OAuth flow"""
    try:
        # Store temporarily (will be replaced with actual token after OAuth)
        temp_config = {
            "api_key": config.api_key,
            "api_secret": config.api_secret,
            "temp_storage": True  # Mark as temporary
        }
        save_upstox_config(temp_config)
        
        return {"message": "Credentials stored temporarily for OAuth flow"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing temporary credentials: {str(e)}")

@router.post("/settings/upstox/oauth/initiate")
async def initiate_upstox_oauth():
    """Initiate Upstox OAuth flow"""
    try:
        # Load temporary credentials
        config = load_upstox_config()
        if not config or not config.get("temp_storage"):
            raise HTTPException(status_code=400, detail="API credentials not found. Please provide API Key and Secret first.")
        
        api_key = config.get("api_key")
        api_secret = config.get("api_secret")
        
        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API Key and API Secret are required")
        
        # Upstox OAuth authorization URL
        base_url = "https://api.upstox.com/v2/login/authorization/dialog"
        redirect_uri = "http://127.0.0.1:8000/api/settings/upstox/oauth/callback"
        
        params = {
            "client_id": api_key,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "orders holdings positions",
            "state": "upstox_oauth"  # For CSRF protection
        }
        
        auth_url = f"{base_url}?{urlencode(params)}"
        
        # Update temp config with OAuth state
        config["redirect_uri"] = redirect_uri
        config["state"] = params["state"]
        save_upstox_config(config)
        
        return {
            "success": True,
            "authorization_url": auth_url,
            "message": "Redirect user to this URL to complete OAuth"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth initiation error: {str(e)}")

@router.get("/settings/upstox/oauth/callback")
async def upstox_oauth_callback(code: str, state: str):
    """Handle Upstox OAuth callback and exchange code for access token"""
    try:
        # Load temporary config
        config = load_upstox_config()
        if not config or config.get("state") != state:
            raise HTTPException(status_code=400, detail="Invalid OAuth state")
        
        api_key = config.get("api_key")
        api_secret = config.get("api_secret")
        redirect_uri = config.get("redirect_uri")
        
        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API credentials not found")
        
        # Exchange authorization code for access token
        token_url = "https://api.upstox.com/v2/login/authorization/token"
        
        token_data = {
            "code": code,
            "client_id": api_key,
            "client_secret": api_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        
        response = requests.post(token_url, data=token_data, timeout=30)
        response.raise_for_status()
        
        token_response = response.json()
        
        # Extract and save access token
        access_token = token_response.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received from Upstox")
        
        # Calculate expiry (Upstox tokens typically expire in 1 day)
        expires_in = token_response.get("expires_in", 86400)  # Default 24 hours
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        # Save complete configuration
        config_data = {
            "access_token": access_token,
            "api_key": api_key,
            "api_secret": api_secret,
            "created_at": datetime.now().isoformat(),
            "expires_at": expires_at.isoformat(),
            "token_type": token_response.get("token_type", "Bearer")
        }
        
        if save_upstox_config(config_data):
            # Refresh the Upstox service
            try:
                from services.upstox_service import refresh_upstox_config
                refresh_upstox_config()
            except Exception as e:
                print(f"Warning: Could not refresh Upstox service: {e}")
            
            # Return HTML page that redirects to homepage
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Upstox Connected Successfully!</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: #0f172a;
                        color: #e5e7eb;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                        text-align: center;
                    }
                    .success-icon {
                        font-size: 4rem;
                        color: #10b981;
                        margin-bottom: 1rem;
                    }
                    .message {
                        font-size: 1.2rem;
                        margin-bottom: 2rem;
                    }
                    .redirect-text {
                        color: #9ca3af;
                        font-size: 0.9rem;
                    }
                </style>
                <script>
                    setTimeout(function() {
                        window.location.href = '/';
                    }, 2000);
                </script>
            </head>
            <body>
                <div class="success-icon">✅</div>
                <div class="message">Upstox connected successfully!</div>
                <div class="redirect-text">Redirecting to homepage...</div>
            </body>
            </html>
            """
            
            return HTMLResponse(content=html_content, status_code=200)
        else:
            raise HTTPException(status_code=500, detail="Failed to save access token")
            
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth callback error: {str(e)}")

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


@router.post("/settings/thresholds")
async def save_thresholds(config: ThresholdConfig):
    """Save threshold configuration."""
    try:
        config_data = {
            "gap": config.gap,
            "rsi": config.rsi
        }
        
        with open(THRESHOLDS_CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        return {"message": "Threshold configuration saved successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving threshold configuration: {str(e)}")


@router.get("/settings/thresholds")
async def get_thresholds():
    """Get threshold configuration."""
    try:
        if os.path.exists(THRESHOLDS_CONFIG_FILE):
            with open(THRESHOLDS_CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
            return config_data
        else:
            # Return default values
            return {"gap": 5.0, "rsi": 30}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading threshold configuration: {str(e)}")
