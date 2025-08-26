"""
Upstox API Service
Handles real-time market data fetching from Upstox API
"""

import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
from routers.settings import load_upstox_config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UpstoxService:
    def __init__(self):
        self.base_url = "https://api.upstox.com/v2"
        self.access_token = None
        self.api_key = None
        self.api_secret = None
        self._load_config()
    
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
            
            # Test with user profile endpoint
            response = self._make_request("/user/profile")
            
            if response and response.get("status") == "success":
                user_data = response.get("data", {})
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
    
    def get_market_quotes_batch(self, symbols: List[str], exchange: str = "NSE_EQ") -> Dict[str, Dict]:
        """Get market quotes for multiple symbols"""
        try:
            instrument_keys = [f"{exchange}:{symbol}" for symbol in symbols]
            endpoint = f"/market-quote/quotes"
            params = {"instrument_key": ",".join(instrument_keys)}
            
            response = self._make_request(endpoint, params)
            
            if response and response.get("status") == "success":
                return response.get("data", {})
            
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching batch quotes: {e}")
            return {}
    
    def get_historical_data(self, symbol: str, interval: str = "1day", exchange: str = "NSE_EQ") -> Optional[List[Dict]]:
        """Get historical candle data"""
        try:
            instrument_key = f"{exchange}:{symbol}"
            
            # Get data for last 30 days
            to_date = datetime.now().strftime("%Y-%m-%d")
            from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            
            endpoint = f"/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}"
            
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
            
            return {
                "symbol": symbol,
                "name": symbol,  # Upstox doesn't provide company name in quotes
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
