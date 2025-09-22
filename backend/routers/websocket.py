from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import asyncio, json, os
from services.upstox_service import get_upstox_service
from services.alert_service import get_alert_service


router = APIRouter(tags=["websocket"])
instruments_path = os.path.join(os.path.dirname(__file__), '../data/instruments.json')
upstox_service = get_upstox_service()
alert_service = get_alert_service()

@router.websocket("/ws/screener")
async def ws_screener(websocket: WebSocket):
    """WebSocket endpoint for real-time screener updates"""
    await websocket.accept()
    
    try:
        # Get the list of stocks directly from the stocks module
        from routers.stocks import list_stocks
        stocks_data = await list_stocks(limit=30)
        symbols = [stock["symbol"] for stock in stocks_data["items"]]
        
        # Get instrument keys for all symbols
        instrument_keys = []
        with open(instruments_path, "r") as f:
            instruments = json.load(f)
        symbol_to_key = {inst['tradingsymbol'].upper(): inst['instrument_key'] 
                        for inst in instruments if 'tradingsymbol' in inst and 'instrument_key' in inst}
        
        for symbol in symbols:
            key = symbol_to_key.get(symbol.upper())
            if key:
                instrument_keys.append(key)
        
        if not instrument_keys:
            await websocket.send_json({"error": "No instrument keys found"})
            return
            
        # Stream ticks for all instruments
        async for tick in upstox_service.subscribe_price_stream(instrument_keys):
            # Find symbol for this instrument key
            symbol = None
            tick_instrument_key = tick.get("instrument_key")
            for sym, key in symbol_to_key.items():
                if key == tick_instrument_key:
                    symbol = sym
                    break
                    
            if symbol:
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
                
                # Bollinger Band alerts disabled - only BUY/SELL signals in Telegram
                # if formatted_stock_data.get("bb_upper") and formatted_stock_data.get("bb_lower"):
                #     alert_message = await alert_service.check_bollinger_band_crosses(
                #         symbol,
                #         formatted_stock_data["price"],
                #         formatted_stock_data["bb_upper"],
                #         formatted_stock_data["bb_lower"]
                #     )
                #
                #     if alert_message:
                #         # Send Telegram alert
                #         alert_sent = await alert_service.send_telegram_alert(alert_message)
                #         if alert_sent:
                #             print(f"Bollinger Band alert sent for {symbol}")
                
                # Send formatted data to frontend
                response = {
                    "type": "stock_update",
                    "symbol": symbol,
                    "data": formatted_stock_data
                }
                await websocket.send_json(response)
                
    except WebSocketDisconnect:
        return
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()

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
                    formatted_stock_data = upstox_service.format_stock_data(current_symbol, quote_data)
                    
                    # Send formatted data to frontend
                    response = {
                        "symbol": current_symbol,
                        "price": formatted_stock_data.get("price"),
                        "tick": formatted_stock_data
                    }
                    await websocket.send_json(response)
    except WebSocketDisconnect:
        if price_stream_task:
            price_stream_task.cancel()
        return
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()
        return
