from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import asyncio, json, os
import jwt
from datetime import datetime, timedelta
from services.upstox_service import get_upstox_service
from services.alert_service import get_alert_service
import logging


router = APIRouter(tags=["websocket"])
instruments_path = os.path.join(os.path.dirname(__file__), '../data/instruments.json')
upstox_service = get_upstox_service()
alert_service = get_alert_service()

# Set up logging
logger = logging.getLogger(__name__)

# Context manager for WebSocket lifecycle logging
from contextlib import asynccontextmanager

@asynccontextmanager
async def websocket_lifecycle(websocket: WebSocket, endpoint: str, user_id: str = None, symbol: str = None):
    """Context manager for WebSocket lifecycle logging"""
    client_info = f"user {user_id}" if user_id else "anonymous user"
    if symbol:
        client_info += f" (symbol: {symbol})"
    
    logger.info(f"WebSocket connection opened: {endpoint} for {client_info}")
    try:
        yield
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {endpoint} for {client_info}")
    except Exception as e:
        logger.error(f"WebSocket error in {endpoint} for {client_info}: {str(e)}", exc_info=True)
        try:
            await websocket.send_json({"error": "Internal server error"})
            await websocket.close()
        except:
            pass  # WebSocket might already be closed
    finally:
        logger.info(f"WebSocket connection closed: {endpoint} for {client_info}")

# Security scheme for JWT authentication
security = HTTPBearer()

# JWT configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate JWT token and return user ID"""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id"
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

@router.websocket("/ws/screener")
async def ws_screener(websocket: WebSocket, token: Optional[str] = Query(None)):
    """WebSocket endpoint for real-time screener updates"""
    await websocket.accept()
    
    # Validate JWT token
    if not token:
        await websocket.send_json({"error": "Authentication required"})
        await websocket.close()
        return
    
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            await websocket.send_json({"error": "Invalid token: missing user_id"})
            await websocket.close()
            return
    except jwt.ExpiredSignatureError:
        await websocket.send_json({"error": "Token expired"})
        await websocket.close()
        return
    except jwt.InvalidTokenError:
        await websocket.send_json({"error": "Invalid token"})
        await websocket.close()
        return
    
    async with websocket_lifecycle(websocket, "/ws/screener", user_id):
        # Get all monitored symbols from journal and watchlist
        from routers.stocks import get_all_monitored_symbols
        symbols = get_all_monitored_symbols()
        
        # Get instrument keys for all symbols
        instrument_keys = []
        try:
            with open(instruments_path, "r") as f:
                instruments = json.load(f)
        except FileNotFoundError:
            logger.error(f"Instruments file not found: {instruments_path}")
            await websocket.send_json({"error": "Instrument configuration not found"})
            return
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in instruments file: {e}")
            await websocket.send_json({"error": "Invalid instrument configuration"})
            return
        except Exception as e:
            logger.error(f"Error reading instruments file: {e}")
            await websocket.send_json({"error": "Failed to load instrument data"})
            return
            
        symbol_to_key = {inst['tradingsymbol'].upper(): inst['instrument_key'] 
                        for inst in instruments if 'tradingsymbol' in inst and 'instrument_key' in inst}
        
        for symbol in symbols:
            key = symbol_to_key.get(symbol.upper())
            if key:
                instrument_keys.append(key)
        
        if not instrument_keys:
            logger.warning(f"No instrument keys found for symbols: {symbols}")
            await websocket.send_json({"error": "No valid instruments found for screener"})
            return
            
        # Stream ticks for all instruments
        try:
            async for tick in upstox_service.subscribe_price_stream(instrument_keys):
                # Find symbol for this instrument key
                symbol = None
                tick_instrument_key = tick.get("instrument_key")
                for sym, key in symbol_to_key.items():
                    if key == tick_instrument_key:
                        symbol = sym
                        break
                        
                if symbol:
                    try:
                        # Convert raw tick to quote format for processing
                        quote_data = {
                            "last_price": tick.get("ltp", 0),
                            "prev_close_price": tick.get("cp", tick.get("ltp", 0)),
                            "open_price": tick.get("open", tick.get("ltp", 0)),
                            "volume": tick.get("vol", 0),
                            "average_price": tick.get("atp", tick.get("ltp", 0)),
                            "ohlc": {
                                "open": tick.get("open", 0),
                                "high": tick.get("high", 0),
                                "low": tick.get("low", 0),
                                "close": tick.get("close", tick.get("ltp", 0))
                            }
                        }
                        
                        # Format using the existing formatter
                        formatted_stock_data = upstox_service.format_stock_data(symbol, quote_data)
                        
                        # Send formatted data to frontend
                        response = {
                            "type": "stock_update",
                            "symbol": symbol,
                            "data": formatted_stock_data
                        }
                        await websocket.send_json(response)
                        
                    except Exception as e:
                        logger.error(f"Error processing tick data for symbol {symbol}: {e}")
                        continue  # Continue with other symbols
                        
        except Exception as e:
            logger.error(f"Error in price stream subscription: {e}")
            await websocket.send_json({"error": "Price streaming service unavailable"})
            return

@router.websocket("/ws/price")
async def ws_price(websocket: WebSocket, symbol: Optional[str] = Query(None), token: Optional[str] = Query(None)):
    """WebSocket endpoint for real-time price updates - now subscribes to all monitored symbols"""
    await websocket.accept()
    
    # Validate JWT token
    if not token:
        await websocket.send_json({"error": "Authentication required"})
        await websocket.close()
        return
    
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            await websocket.send_json({"error": "Invalid token: missing user_id"})
            await websocket.close()
            return
    except jwt.ExpiredSignatureError:
        await websocket.send_json({"error": "Token expired"})
        await websocket.close()
        return
    except jwt.InvalidTokenError:
        await websocket.send_json({"error": "Invalid token"})
        await websocket.close()
        return
    
    async with websocket_lifecycle(websocket, "/ws/price", user_id):
        # Get all monitored symbols from journal and watchlist
        from routers.stocks import get_all_monitored_symbols
        symbols = get_all_monitored_symbols()
        
        # Get instrument keys for all symbols
        instrument_keys = []
        try:
            with open(instruments_path, "r") as f:
                instruments = json.load(f)
        except FileNotFoundError:
            logger.error(f"Instruments file not found: {instruments_path}")
            await websocket.send_json({"error": "Instrument configuration not found"})
            return
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in instruments file: {e}")
            await websocket.send_json({"error": "Invalid instrument configuration"})
            return
        except Exception as e:
            logger.error(f"Error reading instruments file: {e}")
            await websocket.send_json({"error": "Failed to load instrument data"})
            return
            
        symbol_to_key = {inst['tradingsymbol'].upper(): inst['instrument_key'] 
                        for inst in instruments if 'tradingsymbol' in inst and 'instrument_key' in inst}
        
        for sym in symbols:
            key = symbol_to_key.get(sym.upper())
            if key:
                instrument_keys.append(key)
        
        if not instrument_keys:
            logger.warning(f"No instrument keys found for symbols: {symbols}")
            await websocket.send_json({"error": "No valid instruments found for price updates"})
            return
            
        # Stream ticks for all instruments
        try:
            async for tick in upstox_service.subscribe_price_stream(instrument_keys):
                # Find symbol for this instrument key
                tick_symbol = None
                tick_instrument_key = tick.get("instrument_key")
                for sym, key in symbol_to_key.items():
                    if key == tick_instrument_key:
                        tick_symbol = sym
                        break
                        
                if tick_symbol:
                    try:
                        # Convert raw tick to quote format for processing
                        quote_data = {
                            "last_price": tick.get("ltp", 0),
                            "prev_close_price": tick.get("cp", tick.get("ltp", 0)),
                            "open_price": tick.get("open", tick.get("ltp", 0)),
                            "volume": tick.get("vol", 0),
                            "average_price": tick.get("atp", tick.get("ltp", 0)),
                            "ohlc": {
                                "open": tick.get("open", 0),
                                "high": tick.get("high", 0),
                                "low": tick.get("low", 0),
                                "close": tick.get("close", tick.get("ltp", 0))
                            }
                        }
                        
                        # Format using the existing formatter
                        formatted_stock_data = upstox_service.format_stock_data(tick_symbol, quote_data)
                        
                        # Send formatted data to frontend
                        response = {
                            "symbol": tick_symbol,
                            "price": formatted_stock_data.get("price"),
                            "tick": formatted_stock_data
                        }
                        await websocket.send_json(response)
                        
                    except Exception as e:
                        logger.error(f"Error processing tick data for symbol {tick_symbol}: {e}")
                        continue  # Continue streaming despite processing errors
                        
        except Exception as e:
            logger.error(f"Error in price stream subscription: {e}")
            await websocket.send_json({"error": "Price streaming service unavailable"})
            return