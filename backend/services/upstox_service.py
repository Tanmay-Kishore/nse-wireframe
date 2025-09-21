"""
Upstox API Service
Handles real-time market data fetching from Upstox API
"""

import logging, os
import requests
import asyncio
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
        self.last_tick_cache = {}
        self._load_config()

    async def subscribe_price_stream(self, instrument_keys):
        """
        Connects to Upstox WebSocket and yields live ticks for the given instrument_keys, decoding protobuf messages.
        Aligned to Upstox official example: uses authorized websocket URL, SSL context, and correct subscribe message format.
        
        Features:
        - Market hours checking to avoid unnecessary reconnections
        - Exponential backoff for reconnection attempts
        - Cache last ticks for use when market is closed
        """
        # Check if market is open
        if not is_market_open():
            logger.info("Market is closed. Using cached data or returning mock data.")
            
            # Return cached ticks or generate mock data for each instrument key
            for key in instrument_keys:
                # Look for cached tick
                cached_tick = self.last_tick_cache.get(key)
                if cached_tick:
                    cached_tick["cached"] = True
                    yield cached_tick
                else:
                    # Create mock tick data
                    mock_tick = {
                        "ltp": 0,
                        "open": 0,
                        "high": 0,
                        "low": 0,
                        "close": 0,
                        "vol": 0,
                        "instrument_key": key,
                        "cached": True,
                        "mock": True,
                        "market_status": "CLOSED",
                        "next_market_event": get_market_status()["next_event"]
                    }
                    yield mock_tick
            
            # Don't proceed with websocket connection when market is closed
            return
            
        # Exponential backoff parameters
        max_retries = 5
        base_delay = 2  # seconds
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Step 1: Get authorized websocket URL
                auth_url = f"{self.base_url}/feed/market-data-feed/authorize"
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json"
                }
                resp = requests.get(auth_url, headers=headers, timeout=10)
                resp.raise_for_status()
                auth_data = resp.json()
                ws_url = auth_data["data"]["authorized_redirect_uri"]
                
                # Step 2: Create SSL context
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                # Reset retry count on successful connection
                retry_count = 0
                logger.info(f"Connecting to Upstox websocket with {len(instrument_keys)} instruments")
                
                # Step 3: Connect to websocket
                async with websockets.connect(ws_url, ssl=ssl_context, ping_interval=30, ping_timeout=10) as ws:
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
                    logger.info(f"Subscription sent for {len(instrument_keys)} instruments")
                    
                    # Step 5: Receive and decode messages
                    while True:
                        # Check if market is still open
                        if not is_market_open():
                            logger.info("Market closed during websocket session. Stopping stream.")
                            break
                            
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
                                    # Cache this tick
                                    self.last_tick_cache[key] = tick
                                    # Add market status
                                    tick["market_status"] = "OPEN"
                                    yield tick
                        except Exception as e:
                            logger.error(f"Error decoding Upstox tick: {e}")
                            continue
            
            except websockets.exceptions.ConnectionClosedError as e:
                # Connection closed, check if it's due to market being closed
                if not is_market_open():
                    logger.info("Market is now closed. Not attempting reconnection.")
                    break
                retry_count += 1
                wait_time = min(60, base_delay * (2 ** retry_count))  # Exponential backoff, max 60s
                logger.warning(f"WebSocket connection closed: {e}. Retry {retry_count}/{max_retries} in {wait_time}s")
                await asyncio.sleep(wait_time)
            
            except Exception as e:
                retry_count += 1
                wait_time = min(60, base_delay * (2 ** retry_count))
                logger.error(f"WebSocket error: {e}. Retry {retry_count}/{max_retries} in {wait_time}s")
                await asyncio.sleep(wait_time)
        
        # If we've reached max retries or market closed, yield cached data
        if retry_count >= max_retries:
            logger.error(f"Max retries ({max_retries}) reached. Using cached data.")
            
        # Return any cached data we have for the requested instruments
        for key in instrument_keys:
            cached_tick = self.last_tick_cache.get(key)
            if cached_tick:
                cached_tick["cached"] = True
                cached_tick["market_status"] = "CLOSED" if not is_market_open() else "ERROR"
                yield cached_tick
    
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

            result = {
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
            }
            
            # Get historical data for technical analysis
            historical_data = self.get_historical_data(symbol)
            if historical_data and len(historical_data) > 0:
                # Extract closing prices from historical data
                close_prices = []
                for candle in historical_data:
                    if isinstance(candle, list) and len(candle) >= 4:
                        # Format: [timestamp, open, high, low, close, volume]
                        close_prices.append(float(candle[4]))
                
                # Add current price to the end
                close_prices.append(last_price)
                
                # Calculate technical indicators
                rsi = self.calculate_rsi(close_prices)
                moving_averages = self.calculate_moving_averages(close_prices)
                bollinger_bands = self.calculate_bollinger_bands(close_prices)
                
                # Update result with calculated values
                result.update({
                    "rsi": rsi,
                    "ma20": moving_averages["ma20"],
                    "ma50": moving_averages["ma50"], 
                    "ma200": moving_averages["ma200"],
                    "bb_upper": bollinger_bands["upper"],
                    "bb_middle": bollinger_bands["middle"],
                    "bb_lower": bollinger_bands["lower"]
                })
            else:
                # Fallback values if no historical data
                result.update({
                    "rsi": 50.0,
                    "ma20": last_price * 0.98,
                    "ma50": last_price * 0.95,
                    "ma200": last_price * 0.90,
                    "bb_upper": last_price * 1.02,
                    "bb_middle": last_price,
                    "bb_lower": last_price * 0.98
                })
            
            # Calculate trading signal using strategy logic
            signal_data = self.calculate_trading_signal(
                symbol, last_price, result.get("rsi", 50),
                result.get("ma20", last_price), result.get("ma50", last_price),
                result.get("ma200", last_price), result.get("bb_upper", 0),
                result.get("bb_middle", 0), result.get("bb_lower", 0)
            )

            # Add sentiment and signal
            result.update({
                "sentiment": signal_data["sentiment"],
                "signal": signal_data["signal"]
            })
            
            return result
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
            "rsi": 50.0,
            "ma20": 0.0,
            "ma50": 0.0,
            "ma200": 0.0,
            "bb_upper": 0.0,
            "bb_middle": 0.0,
            "bb_lower": 0.0,
            "sentiment": "UNKNOWN",
            "signal": {
                "direction": "-",
                "entry": 0,
                "sl": 0,
                "target": 0
            },
            "error": "API data unavailable"
        }

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index)"""
        if len(prices) < period + 1:
            return 50.0  # Default if insufficient data
        
        try:
            # Calculate price changes
            changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            
            # Separate gains and losses
            gains = [max(change, 0) for change in changes]
            losses = [-min(change, 0) for change in changes]
            
            # Calculate average gains and losses
            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period
            
            # Calculate subsequent gains and losses using smoothing
            for i in range(period, len(gains)):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            # Calculate RSI
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            return round(rsi, 1)
        except:
            return 50.0

    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict[str, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return {"upper": 0.0, "middle": 0.0, "lower": 0.0}
        
        try:
            # Get the last 'period' prices
            recent_prices = prices[-period:]
            
            # Calculate SMA (Simple Moving Average)
            sma = sum(recent_prices) / len(recent_prices)
            
            # Calculate standard deviation
            variance = sum([(price - sma) ** 2 for price in recent_prices]) / len(recent_prices)
            std = variance ** 0.5
            
            # Calculate bands
            upper_band = sma + (std_dev * std)
            lower_band = sma - (std_dev * std)
            
            return {
                "upper": round(upper_band, 2),
                "middle": round(sma, 2),
                "lower": round(lower_band, 2)
            }
        except:
            return {"upper": 0.0, "middle": 0.0, "lower": 0.0}

    def calculate_moving_averages(self, prices: List[float]) -> Dict[str, float]:
        """Calculate moving averages"""
        try:
            ma20 = sum(prices[-20:]) / min(20, len(prices)) if len(prices) >= 1 else 0.0
            ma50 = sum(prices[-50:]) / min(50, len(prices)) if len(prices) >= 1 else 0.0
            ma200 = sum(prices[-200:]) / min(200, len(prices)) if len(prices) >= 1 else 0.0

            return {
                "ma20": round(ma20, 2),
                "ma50": round(ma50, 2),
                "ma200": round(ma200, 2)
            }
        except:
            return {"ma20": 0.0, "ma50": 0.0, "ma200": 0.0}

    def calculate_trading_signal(self, symbol: str, current_price: float, rsi: float,
                               ma20: float, ma50: float, ma200: float, bb_upper: float = 0,
                               bb_middle: float = 0, bb_lower: float = 0) -> Dict:
        """
        Enhanced trading signal with Bollinger Bands integration:

        Core AND Logic:
        BUY: (Price > MA50 > MA200) AND (RSI > 40) AND (Price > MA20)
        SELL: (Price < MA50 < MA200) AND (RSI < 60) AND (Price < MA20)

        Bollinger Band Enhancements:
        - Oversold bounce: Price touches BB Lower + RSI < 30
        - Overbought rejection: Price touches BB Upper + RSI > 70
        - Squeeze breakout: Price breaks out of tight bands
        - Mean reversion: Price returns to BB Middle
        """
        try:
            buy_conditions = []
            sell_conditions = []
            reasons = []

            # Core AND Logic Conditions
            # Relaxed conditions for real market scenarios
            # BUY Signal Logic - More flexible for sideways markets
            buy_condition_1 = (current_price > ma50 > ma200) or (ma50 >= ma200 * 0.999 and current_price > ma50)  # Bullish or sideways upward
            buy_condition_2 = rsi > 40  # RSI momentum
            buy_condition_3 = current_price > ma20 * 0.998  # Price above MA20 (with small buffer)

            # SELL Signal Logic - More flexible for sideways markets
            sell_condition_1 = (current_price < ma50 < ma200) or (ma50 <= ma200 * 1.001 and current_price < ma50)  # Bearish or sideways downward
            sell_condition_2 = rsi < 60  # RSI momentum
            sell_condition_3 = current_price < ma20 * 1.002  # Price below MA20 (with small buffer)

            # Bollinger Bands Analysis (if available)
            bb_buy_signals = 0
            bb_sell_signals = 0
            bb_reasons = []

            if bb_upper > 0 and bb_lower > 0 and bb_middle > 0:
                # Calculate Bollinger Band width for squeeze detection
                bb_width = (bb_upper - bb_lower) / bb_middle * 100

                # 1. Oversold Bounce Signal (Strong BUY)
                if current_price <= bb_lower * 1.02 and rsi < 35:  # Price at/near lower band + oversold RSI
                    bb_buy_signals += 2
                    bb_reasons.append(f"BB Oversold bounce: Price {current_price:.2f} near lower band ({bb_lower:.2f}) + RSI {rsi:.1f}")

                # 2. Overbought Rejection Signal (Strong SELL)
                elif current_price >= bb_upper * 0.98 and rsi > 65:  # Price at/near upper band + overbought RSI
                    bb_sell_signals += 2
                    bb_reasons.append(f"BB Overbought rejection: Price {current_price:.2f} near upper band ({bb_upper:.2f}) + RSI {rsi:.1f}")

                # 3. Additional oversold/overbought without strict band proximity
                elif rsi <= 25:  # Very oversold
                    bb_buy_signals += 1.5
                    bb_reasons.append(f"BB Very oversold: RSI {rsi:.1f} <= 25")

                elif rsi >= 75:  # Very overbought
                    bb_sell_signals += 1.5
                    bb_reasons.append(f"BB Very overbought: RSI {rsi:.1f} >= 75")

                # 3. Squeeze Breakout (Moderate signals)
                elif bb_width < 10:  # Tight bands indicate low volatility
                    if current_price > bb_upper and buy_condition_1:  # Breakout above upper band in uptrend
                        bb_buy_signals += 1
                        bb_reasons.append(f"BB Squeeze breakout: Price {current_price:.2f} > Upper {bb_upper:.2f}")
                    elif current_price < bb_lower and sell_condition_1:  # Breakdown below lower band in downtrend
                        bb_sell_signals += 1
                        bb_reasons.append(f"BB Squeeze breakdown: Price {current_price:.2f} < Lower {bb_lower:.2f}")

                # 4. Mean Reversion Signals
                elif current_price < bb_middle and buy_condition_2 and buy_condition_3:  # Price below middle, but other conditions bullish
                    bb_buy_signals += 0.5
                    bb_reasons.append(f"BB Mean reversion: Price {current_price:.2f} below middle {bb_middle:.2f}")
                elif current_price > bb_middle and sell_condition_2 and sell_condition_3:  # Price above middle, but other conditions bearish
                    bb_sell_signals += 0.5
                    bb_reasons.append(f"BB Mean reversion: Price {current_price:.2f} above middle {bb_middle:.2f}")

                # 5. Band Position Analysis
                if bb_lower < current_price < bb_middle:
                    bb_reasons.append(f"BB Position: Lower third (potential support)")
                elif bb_middle < current_price < bb_upper:
                    bb_reasons.append(f"BB Position: Upper third (potential resistance)")

            # Check core conditions with flexible explanations
            if buy_condition_1:
                if current_price > ma50 > ma200:
                    buy_conditions.append("Strong bullish trend: Price > MA50 > MA200")
                else:
                    buy_conditions.append("Sideways bullish: Price > MA50, MAs aligned")
            if buy_condition_2:
                buy_conditions.append(f"RSI momentum: RSI {rsi:.1f} > 40")
            if buy_condition_3:
                buy_conditions.append("Above MA20: Price above short-term MA")

            if sell_condition_1:
                if current_price < ma50 < ma200:
                    sell_conditions.append("Strong bearish trend: Price < MA50 < MA200")
                else:
                    sell_conditions.append("Sideways bearish: Price < MA50, MAs aligned")
            if sell_condition_2:
                sell_conditions.append(f"RSI momentum: RSI {rsi:.1f} < 60")
            if sell_condition_3:
                sell_conditions.append("Below MA20: Price below short-term MA")

            # Enhanced Signal Determination with Bollinger Bands
            direction = "HOLD"
            confidence = 0
            sentiment = "NEUTRAL"

            # Primary Signal: Core AND Logic
            core_buy_signal = buy_condition_1 and buy_condition_2 and buy_condition_3
            core_sell_signal = sell_condition_1 and sell_condition_2 and sell_condition_3

            # Secondary Signal: Strong Bollinger Band signals can override
            strong_bb_buy = bb_buy_signals >= 2  # Oversold bounce
            strong_bb_sell = bb_sell_signals >= 2  # Overbought rejection

            # Priority 1: Strong BB Signals (can override core logic)
            if strong_bb_buy and sum([buy_condition_1, buy_condition_2, buy_condition_3]) >= 1:
                # Strong BB oversold bounce with at least 1 core condition
                direction = "BUY"
                confidence = 2 + int(bb_buy_signals)  # 4-5 confidence
                sentiment = "BULLISH" if bb_buy_signals >= 2 else "NEUTRAL"
                reasons = ["🎯 BB Override: Strong oversold bounce"] + bb_reasons + buy_conditions

            elif strong_bb_sell and sum([sell_condition_1, sell_condition_2, sell_condition_3]) >= 1:
                # Strong BB overbought rejection with at least 1 core condition
                direction = "SELL"
                confidence = 2 + int(bb_sell_signals)  # 4-5 confidence
                sentiment = "BEARISH" if bb_sell_signals >= 2 else "NEUTRAL"
                reasons = ["🎯 BB Override: Strong overbought rejection"] + bb_reasons + sell_conditions

            # Priority 2: Perfect Core Conditions
            elif core_buy_signal:
                # Perfect core BUY conditions met
                direction = "BUY"
                confidence = 3 + min(int(bb_buy_signals), 2)  # 3-5 confidence
                sentiment = "BULLISH"
                reasons = buy_conditions + bb_reasons[:2]

            elif core_sell_signal:
                # Perfect core SELL conditions met
                direction = "SELL"
                confidence = 3 + min(int(bb_sell_signals), 2)  # 3-5 confidence
                sentiment = "BEARISH"
                reasons = sell_conditions + bb_reasons[:2]

            # Priority 3: Moderate BB signals with partial core conditions
            elif bb_buy_signals >= 1 and sum([buy_condition_1, buy_condition_2, buy_condition_3]) >= 2:
                # Moderate BB buy signal with 2/3 core conditions
                direction = "BUY"
                confidence = 2 + int(bb_buy_signals)  # 3-4 confidence
                sentiment = "NEUTRAL"
                reasons = ["🔄 BB Enhanced: " + bb_reasons[0]] + buy_conditions if bb_reasons else buy_conditions

            elif bb_sell_signals >= 1 and sum([sell_condition_1, sell_condition_2, sell_condition_3]) >= 2:
                # Moderate BB sell signal with 2/3 core conditions
                direction = "SELL"
                confidence = 2 + int(bb_sell_signals)  # 3-4 confidence
                sentiment = "NEUTRAL"
                reasons = ["🔄 BB Enhanced: " + bb_reasons[0]] + sell_conditions if bb_reasons else sell_conditions

            # Priority 4: High-confidence partial signals (2/3 conditions with good RSI)
            elif sum([buy_condition_1, buy_condition_2, buy_condition_3]) == 2 and rsi > 50:
                direction = "BUY"
                confidence = 2
                sentiment = "NEUTRAL"
                reasons = ["⚠️ Partial BUY: 2/3 conditions + bullish RSI"] + buy_conditions

            elif sum([sell_condition_1, sell_condition_2, sell_condition_3]) == 2 and rsi < 50:
                direction = "SELL"
                confidence = 2
                sentiment = "NEUTRAL"
                reasons = ["⚠️ Partial SELL: 2/3 conditions + bearish RSI"] + sell_conditions

            else:
                # HOLD: Core conditions not met and no strong BB signals
                confidence = 0
                partial_buy = sum([buy_condition_1, buy_condition_2, buy_condition_3])
                partial_sell = sum([sell_condition_1, sell_condition_2, sell_condition_3])

                reasons = [f"Mixed signals: {partial_buy}/3 BUY, {partial_sell}/3 SELL conditions"]
                if bb_reasons:
                    reasons.extend(bb_reasons[:1])  # Add one BB context

            # Enhanced Price Calculation with Bollinger Bands
            entry_price = current_price

            if direction == "BUY":
                # BUY Stop Loss: Use BB Lower as dynamic support when available
                if bb_lower > 0:
                    bb_sl = bb_lower * 0.98  # 2% below lower band for buffer
                    ma_sl = ma20 * 0.97  # 3% below MA20
                    sl = round(max(bb_sl, ma_sl, current_price * 0.96), 2)  # Take the highest (closest) stop
                else:
                    sl = round(min(ma20 * 0.97, current_price * 0.97), 2)

                # BUY Target: Use BB Upper as dynamic resistance when available
                if bb_upper > 0 and strong_bb_buy:
                    # For strong BB signals, target the upper band
                    target = round(min(bb_upper * 0.98, current_price * (1 + 0.02 * confidence)), 2)
                else:
                    # Standard percentage target
                    target = round(current_price * (1 + 0.03 + 0.01 * confidence), 2)  # 3-8% target

            elif direction == "SELL":
                # SELL Stop Loss: Use BB Upper as dynamic resistance when available
                if bb_upper > 0:
                    bb_sl = bb_upper * 1.02  # 2% above upper band for buffer
                    ma_sl = ma20 * 1.03  # 3% above MA20
                    sl = round(min(bb_sl, ma_sl, current_price * 1.04), 2)  # Take the lowest (closest) stop
                else:
                    sl = round(max(ma20 * 1.03, current_price * 1.03), 2)

                # SELL Target: Use BB Lower as dynamic support when available
                if bb_lower > 0 and strong_bb_sell:
                    # For strong BB signals, target the lower band
                    target = round(max(bb_lower * 1.02, current_price * (1 - 0.02 * confidence)), 2)
                else:
                    # Standard percentage target
                    target = round(current_price * (1 - 0.03 - 0.01 * confidence), 2)  # 3-8% target

            else:
                # HOLD signals: Conservative risk management
                if bb_middle > 0:
                    # Use BB middle as reference for neutral signals
                    sl = round(current_price * 0.97, 2)
                    target = round(bb_middle, 2) if abs(current_price - bb_middle) > current_price * 0.02 else round(current_price * 1.02, 2)
                else:
                    sl = round(current_price * 0.97, 2)
                    target = round(current_price * 1.03, 2)

            return {
                "sentiment": sentiment,
                "signal": {
                    "direction": direction,
                    "entry": round(entry_price, 2),
                    "sl": sl,
                    "target": target,
                    "confidence": confidence,
                    "reasons": reasons
                },
                "conditions": {
                    "buy_met": [buy_condition_1, buy_condition_2, buy_condition_3],
                    "sell_met": [sell_condition_1, sell_condition_2, sell_condition_3]
                },
                "bollinger": {
                    "buy_signals": bb_buy_signals,
                    "sell_signals": bb_sell_signals,
                    "width_pct": round((bb_upper - bb_lower) / bb_middle * 100, 1) if bb_middle > 0 else 0,
                    "position": "lower" if bb_lower > 0 and current_price < bb_middle else
                               "upper" if bb_upper > 0 and current_price > bb_middle else "middle"
                }
            }

        except Exception as e:
            logger.error(f"Error calculating trading signal for {symbol}: {e}")
            # Fallback to safe HOLD signal
            return {
                "sentiment": "NEUTRAL",
                "signal": {
                    "direction": "HOLD",
                    "entry": round(current_price, 2),
                    "sl": round(current_price * 0.97, 2),
                    "target": round(current_price * 1.03, 2),
                    "confidence": 0,
                    "reasons": ["Error in signal calculation"]
                },
                "scores": {
                    "buy_score": 0.0,
                    "sell_score": 0.0
                }
            }

# Global service instance
upstox_service = UpstoxService()

def get_upstox_service() -> UpstoxService:
    """Get the global Upstox service instance"""
    return upstox_service

def refresh_upstox_config():
    """Refresh Upstox configuration from file"""
    upstox_service._load_config()
    
    
# Market hours related methods
def is_market_open():
    """
    Check if the market is currently open based on typical NSE market hours.
    
    Returns:
        bool: True if market is open, False otherwise
    """
    # India Standard Time (IST)
    now = datetime.now()
    
    # NSE typically operates Monday to Friday
    if now.weekday() > 4:  # 5 = Saturday, 6 = Sunday
        return False
    
    # Market hours: 9:15 AM to 3:30 PM IST
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    return market_start <= now <= market_end

def get_market_status():
    """
    Get the current market status.
    
    Returns:
        dict: Market status information
    """
    is_open = is_market_open()
    
    # Get the next opening/closing time
    now = datetime.now()
    today = now.date()
    next_day = today + timedelta(days=1)
    
    # Handle weekends
    if now.weekday() == 4 and now.hour >= 15:  # Friday after closing
        next_day = today + timedelta(days=3)  # Next Monday
    elif now.weekday() == 5:  # Saturday
        next_day = today + timedelta(days=2)  # Next Monday
    elif now.weekday() == 6:  # Sunday
        next_day = today + timedelta(days=1)  # Next Monday
        
    # Set the next event time
    if is_open:
        next_event = datetime.combine(today, datetime.time(15, 30))
        next_event_type = "closing"
    else:
        # If current time is after market close
        if now.hour > 15 or (now.hour == 15 and now.minute >= 30):
            # Set for next day's opening
            next_event = datetime.combine(next_day, datetime.time(9, 15))
            next_event_type = "opening"
        else:
            # Set for today's opening
            next_event = datetime.combine(today, datetime.time(9, 15))
            next_event_type = "opening"
            
    return {
        "is_open": is_open,
        "next_event": next_event.isoformat(),
        "next_event_type": next_event_type
    }
