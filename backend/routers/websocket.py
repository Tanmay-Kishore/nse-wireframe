from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import asyncio, json
from services.upstox_service import get_upstox_service

router = APIRouter(tags=["websocket"])

@router.websocket("/ws/price")
async def ws_price(websocket: WebSocket, symbol: Optional[str] = Query(None)):
    """WebSocket endpoint for real-time price updates"""
    await websocket.accept()
    upstox = get_upstox_service()
    current_symbol = symbol
    current_instrument_key = None
    price_stream_task = None
    async def get_instrument_key(symbol):
        try:
            with open("backend/data/instruments.json", "r") as f:
                instruments = json.load(f)
            for inst in instruments:
                if inst.get("tradingsymbol", "").upper() == symbol.upper():
                    return inst["instrument_key"]
        except Exception:
            pass
        return None
    async def price_streamer(symbol, instrument_key):
        try:
            async for tick in upstox.subscribe_price_stream([instrument_key]):
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
                price_stream_task = asyncio.create_task(price_streamer(current_symbol, current_instrument_key))
        while True:
            data = await websocket.receive_json()
            new_symbol = data.get("symbol")
            if new_symbol and new_symbol != current_symbol:
                # Cancel previous price stream
                if price_stream_task:
                    price_stream_task.cancel()
                    try:
                        await price_stream_task
                    except asyncio.CancelledError:
                        pass
                current_symbol = new_symbol
                current_instrument_key = await get_instrument_key(current_symbol)
                if not current_instrument_key:
                    await websocket.send_json({"error": f"Instrument key not found for {current_symbol}"})
                else:
                    price_stream_task = asyncio.create_task(price_streamer(current_symbol, current_instrument_key))
    except WebSocketDisconnect:
        if price_stream_task:
            price_stream_task.cancel()
        return
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()
        return
