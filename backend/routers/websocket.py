from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import asyncio
import random

router = APIRouter(tags=["websocket"])

@router.websocket("/ws/price")
async def ws_price(websocket: WebSocket, symbol: Optional[str] = Query(None)):
    """WebSocket endpoint for real-time price updates"""
    await websocket.accept()
    price = random.uniform(100, 3000)
    try:
        while True:
            # jitter price
            price = price * (1 + random.uniform(-0.001, 0.001))
            await websocket.send_json({"symbol": symbol or "N/A", "price": price})
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
