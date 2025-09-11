from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import asyncio, json, os
from services.upstox_service import get_upstox_service


router = APIRouter(tags=["websocket"])
instruments_path = os.path.join(os.path.dirname(__file__), '../data/instruments.json')
upstox_service = get_upstox_service()

@router.websocket("/ws/price")
async def ws_price(websocket: WebSocket, symbol: Optional[str] = Query(None)):
    """WebSocket endpoint for real-time price updates"""
    await websocket.accept()
    current_symbol = symbol
    current_instrument_key = None
    price_stream_task = None
    async def get_instrument_key(symbol):
        try:
            with open(instruments_path, "r") as f:
                instruments = json.load(f)
            for inst in instruments:
                if inst.get("tradingsymbol", "").upper() == symbol.upper():
                    return inst["instrument_key"]
        except Exception as e:
            print("Error getting instrument key:", e)
            # pass
        return None
    async def price_streamer(symbol, instrument_key):
        try:
            print("Subscribing to Upstox price stream for:", instrument_key)
            async for tick in upstox_service.subscribe_price_stream([instrument_key]):      
                await websocket.send_json({"symbol": symbol, "price": tick.get("ltp", None), "tick": tick})
        except WebSocketDisconnect:
            return
        except Exception as e:
            await websocket.send_json({"error": str(e)})
            await websocket.close()
            return
    try:
        if not current_symbol:
            await websocket.send_json({"error": "No symbol provided. Send a symbol as a query param or in a message."})
        else:
            current_instrument_key = await get_instrument_key(current_symbol)
            if not current_instrument_key:
                await websocket.send_json({"error": f"Instrument key not found for {current_symbol}"})
            else:
                # Start streaming price ticks immediately
                async for tick in upstox_service.subscribe_price_stream([current_instrument_key]):
                    print("Tick received:", tick)  # Debug log  
                    await websocket.send_json(tick)
    except WebSocketDisconnect:
        if price_stream_task:
            price_stream_task.cancel()
        return
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()
        return
