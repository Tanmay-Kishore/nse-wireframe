"""
Upstox API Service
Handles real-time market data fetching from Upstox API
"""

import logging, os
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import websockets
from proto import market_data_feed_pb2
import base64
from routers.settings import load_upstox_config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
instruments_path = os.path.join(os.path.dirname(__file__), '../data/instruments.json')

class UpstoxService:
    def __init__(self):
        self.base_url = "https://api.upstox.com/v3"
        self.access_token = None
        self.api_key = None
        self.api_secret = None
        self._load_config()

    async def subscribe_price_stream(self, instrument_keys):
        """
        Connects to Upstox WebSocket and yields live ticks for the given instrument_keys, decoding protobuf messages.
        Aligned to Upstox official example: uses authorized websocket URL, SSL context, and correct subscribe message format.
        """
        # Step 1: Get authorized websocket URL
        try:
            auth_url = f"{self.base_url}/feed/market-data-feed/authorize"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json"
            }
            resp = requests.get(auth_url, headers=headers, timeout=10)
            resp.raise_for_status()
            auth_data = resp.json()
            ws_url = auth_data["data"]["authorized_redirect_uri"]
        except Exception as e:
            logger.error(f"Failed to get authorized websocket URL: {e}")
            return

        # Step 2: Create SSL context
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        # Step 3: Connect to websocket
        async with websockets.connect(ws_url, ssl=ssl_context) as ws:
            # Step 4: Send subscribe message (use 'instrumentKeys' camelCase)
            subscribe_msg = {
                "guid": "client-1",
                "method": "sub",
                "data": {
                    "mode": "full",
                    "instrumentKeys": instrument_keys
                }
            }
            await ws.send(json.dumps(subscribe_msg).encode('utf-8'))
            # Step 5: Receive and decode messages
            while True:
                msg = await ws.recv()
                try:
                    # Try to decode as protobuf directly (Upstox v3)
                    feed_response = market_data_feed_pb2.FeedResponse()
                    if isinstance(msg, bytes):
                        feed_response.ParseFromString(msg)
                    else:
                        # If message is JSON with base64 'data' field (older Upstox)
                        msg_obj = json.loads(msg)
                        if "data" in msg_obj:
                            pb_bytes = base64.b64decode(msg_obj["data"])
                            feed_response.ParseFromString(pb_bytes)
                        else:
                            continue
                    # Extract ticks for each instrument
                    for key, feed in feed_response.feeds.items():
                        tick = {}
                        fields = [desc.name for desc, _ in feed.ListFields()]
                        if "fullFeed" in fields:
                            full_feed = feed.fullFeed
                            # Log the structure for debugging
                            # Parse marketFF under fullFeed
                            if full_feed.HasField("marketFF"):
                                market_ff = full_feed.marketFF
                                # Parse ltpc (last traded price info)
                                if market_ff.HasField("ltpc"):
                                    tick["ltp"] = market_ff.ltpc.ltp
                                    tick["ltt"] = market_ff.ltpc.ltt
                                    tick["ltq"] = market_ff.ltpc.ltq
                                    tick["cp"] = market_ff.ltpc.cp
                                # Parse bid/ask quotes (market depth)
                                if market_ff.HasField("marketLevel"):
                                    bid_ask_quotes = []
                                    for baq in market_ff.marketLevel.bidAskQuote:
                                        bid_ask_quotes.append({
                                            "bidQ": baq.bidQ,
                                            "bidP": baq.bidP,
                                            "askQ": baq.askQ,
                                            "askP": baq.askP
                                        })
                                    tick["bid_ask_quotes"] = bid_ask_quotes
                                # Parse OHLC data
                                if market_ff.HasField("marketOHLC"):
                                    ohlc_list = market_ff.marketOHLC.ohlc
                                    ohlc_data = []
                                    for ohlc in ohlc_list:
                                        ohlc_data.append({
                                            "interval": ohlc.interval,
                                            "open": ohlc.open,
                                            "high": ohlc.high,
                                            "low": ohlc.low,
                                            "close": ohlc.close,
                                            "vol": ohlc.vol,
                                            "ts": ohlc.ts
                                        })
                                    tick["ohlc"] = ohlc_data
                                    # For convenience, also set 1d OHLC as top-level fields if present
                                    for ohlc in ohlc_data:
                                        if ohlc["interval"] == "1d":
                                            tick["open"] = ohlc["open"]
                                            tick["high"] = ohlc["high"]
                                            tick["low"] = ohlc["low"]
                                            tick["close"] = ohlc["close"]
                                            tick["vol"] = ohlc["vol"]
                                            break
                                # Parse ATP, VTT, TBQ, TSQ (scalar fields, no HasField)
                                tick["atp"] = market_ff.atp
                                tick["vtt"] = market_ff.vtt
                                tick["tbq"] = market_ff.tbq
                                tick["tsq"] = market_ff.tsq
                                tick["instrument_key"] = key
                        # Add more parsing as needed for other feed types
                        if tick:
                            yield tick
                except Exception as e:
                    logger.error(f"Error decoding Upstox tick: {e}")
                    continue
    
    def _load_config(self):
        """Load Upstox configuration"""
        try:
            config = load_upstox_config()
            if config:
                self.access_token = config.get("access_token")
                self.api_key = config.get("api_key")
                self.api_secret = config.get("api_secret")
                logger.info("Upstox configuration loaded successfully")
        except Exception as e:
            logger.error(f"Error loading Upstox config: {e}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API headers with authorization"""
        if not self.access_token:
            raise Exception("No access token configured")
        
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make API request to Upstox"""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in API request: {e}")
            return None
    
    def is_configured(self) -> bool:
        """Check if Upstox is properly configured"""
        return bool(self.access_token)
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the Upstox API connection"""
        try:
            if not self.is_configured():
                return {"success": False, "message": "No access token configured"}
            # Always use v2 for user/profile
            url = "https://api.upstox.com/v2/user/profile"
            headers = self._get_headers()
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            resp_json = response.json()
            if resp_json and resp_json.get("status") == "success":
                user_data = resp_json.get("data", {})
                return {
                    "success": True,
                    "message": "Connection successful",
                    "user_name": user_data.get("user_name", "Unknown"),
                    "broker": user_data.get("broker", "Unknown")
                }
            else:
                return {"success": False, "message": "API connection failed"}
        except Exception as e:
            return {"success": False, "message": f"Connection test failed: {str(e)}"}
    
    def get_market_quote(self, symbol: str, exchange: str = "NSE_EQ") -> Optional[Dict]:
        """Get real-time market quote for a symbol"""
        try:
            instrument_key = f"{exchange}:{symbol}"
            endpoint = f"/market-quote/quotes"
            params = {"instrument_key": instrument_key}
            
            response = self._make_request(endpoint, params)
            
            if response and response.get("status") == "success":
                return response.get("data", {}).get(instrument_key, {})
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None
    
    def get_market_quotes_batch(self, instrument_keys: List[str]) -> Dict[str, Dict]:
        """Get market quotes for multiple instrument keys (no prefix added), always use v2 endpoint."""
        try:
            url = "https://api.upstox.com/v2/market-quote/quotes"
            headers = self._get_headers()
            params = {"instrument_key": ",".join(instrument_keys)}
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            resp_json = response.json()
            if resp_json and resp_json.get("status") == "success":
                return resp_json.get("data", {})
            return {}
        except Exception as e:
            logger.error(f"Error fetching batch quotes: {e}")
            return {}
    
    def get_historical_data(self, symbol: str, exchange: str = "NSE_EQ") -> Optional[List[Dict]]:
        """Get daily historical candle data using Upstox v3 endpoint"""
        try:
            # Find instrument_key in format NSE_EQ|ISIN (URL-encoded)
            # If symbol is ISIN, use as is; else, lookup ISIN from instruments.json
            instrument_key = None
            try:
                with open(instruments_path, "r") as f:
                    instruments = json.load(f)
                for inst in instruments:
                    if inst.get("tradingsymbol", "").upper() == symbol.upper():
                        instrument_key = inst['instrument_key']
                        break
            except Exception as e:
                logger.error(f"Instrument lookup failed: {e}")
            if not instrument_key:
                instrument_key = f"{exchange}|{symbol}"  # fallback, may be ISIN
            encoded_key = instrument_key.replace("|", "%7C")
            to_date = datetime.now().strftime("%Y-%m-%d")
            from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            endpoint = f"/historical-candle/{encoded_key}/days/1/{to_date}/{from_date}"
            response = self._make_request(endpoint)
            if response and response.get("status") == "success":
                return response.get("data", {}).get("candles", [])
            return None
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None
    
    def search_instruments(self, query: str) -> List[Dict]:
        """Search for instruments/symbols"""
        try:
            endpoint = f"/search/instruments"
            params = {"query": query}
            
            response = self._make_request(endpoint, params)
            
            if response and response.get("status") == "success":
                return response.get("data", [])
            
            return []
            
        except Exception as e:
            logger.error(f"Error searching instruments: {e}")
            return []
    
    def format_stock_data(self, symbol: str, quote_data: Dict) -> Dict:
        """Format Upstox quote data to our application format"""
        try:
            last_price = quote_data.get("last_price", 0)
            prev_close = quote_data.get("prev_close_price", last_price)
            # Calculate percentage change
            change = last_price - prev_close
            change_percent = (change / prev_close * 100) if prev_close > 0 else 0
            # Calculate gap (assuming pre-market or opening gap)
            open_price = quote_data.get("open_price", last_price)
            gap = ((open_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
            # Get OHLC data
            ohlc = quote_data.get("ohlc", {})
            # Lookup name from instruments.json
            name = symbol
            try:
                with open(instruments_path, "r") as f:
                    instruments = json.load(f)
                for inst in instruments:
                    if inst.get("tradingsymbol", "").upper() == symbol.upper():
                        name = inst.get("name", symbol)
                        break
            except Exception:
                pass
            return {
                "symbol": symbol,
                "name": name,
                "price": round(last_price, 2),
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "gap": round(gap, 2),
                "volume": quote_data.get("volume", 0),
                "open": ohlc.get("open", 0),
                "high": ohlc.get("high", 0),
                "low": ohlc.get("low", 0),
                "close": last_price,
                "prev_close": prev_close,
                "vwap": quote_data.get("average_price", last_price),
                "upper_circuit": quote_data.get("upper_circuit_limit", 0),
                "lower_circuit": quote_data.get("lower_circuit_limit", 0),
                "timestamp": datetime.now().isoformat(),
                # Mock technical indicators (would need separate calculation)
                "rsi": 50.0,  # Placeholder
                "ma20": last_price * 0.98,  # Placeholder
                "ma50": last_price * 0.95,  # Placeholder
                "ma200": last_price * 0.90,  # Placeholder
                "sentiment": "NEUTRAL",  # Placeholder
                "signal": {
                    "direction": "HOLD",
                    "entry": last_price,
                    "sl": round(last_price * 0.95, 2),
                    "target": round(last_price * 1.05, 2)
                }
            }
        except Exception as e:
            logger.error(f"Error formatting stock data: {e}")
            return self._get_fallback_data(symbol)
    
    def _get_fallback_data(self, symbol: str) -> Dict:
        """Fallback data when API fails"""
        return {
            "symbol": symbol,
            "name": symbol,
            "price": 0.0,
            "change": 0.0,
            "change_percent": 0.0,
            "gap": 0.0,
            "volume": 0,
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "prev_close": 0.0,
            "vwap": 0.0,
            "upper_circuit": 0.0,
            "lower_circuit": 0.0,
            "timestamp": datetime.now().isoformat(),
            "rsi": 0.0,
            "ma20": 0.0,
            "ma50": 0.0,
            "ma200": 0.0,
            "sentiment": "UNKNOWN",
            "signal": {
                "direction": "-",
                "entry": 0,
                "sl": 0,
                "target": 0
            },
            "error": "API data unavailable"
        }

# Global service instance
upstox_service = UpstoxService()

def get_upstox_service() -> UpstoxService:
    """Get the global Upstox service instance"""
    return upstox_service

def refresh_upstox_config():
    """Refresh Upstox configuration from file"""
    upstox_service._load_config()
