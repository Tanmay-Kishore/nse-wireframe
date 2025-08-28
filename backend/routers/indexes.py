from fastapi import APIRouter
from services.upstox_service import get_upstox_service
import requests

router = APIRouter()

INDEX_LIST = [
    {"name": "Nifty 50", "instrument_key": "NSE_INDEX|Nifty 50", "symbol": "NIFTY"},
    {"name": "Nifty Next 50", "instrument_key": "NSE_INDEX|Nifty Next 50", "symbol": "NIFTYNXT50"},
    {"name": "Nifty 500", "instrument_key": "NSE_INDEX|Nifty 500", "symbol": "NIFTY 500"},
    {"name": "Nifty Bank", "instrument_key": "NSE_INDEX|Nifty Bank", "symbol": "BANKNIFTY"},
    {"name": "Nifty IT", "instrument_key": "NSE_INDEX|Nifty IT", "symbol": "NIFTY IT"},
    {"name": "Nifty Pharma", "instrument_key": "NSE_INDEX|Nifty Pharma", "symbol": "NIFTY PHARMA"},
    {"name": "Nifty Energy", "instrument_key": "NSE_INDEX|Nifty Energy", "symbol": "NIFTY ENERGY"},
    {"name": "Nifty FMCG", "instrument_key": "NSE_INDEX|Nifty FMCG", "symbol": "NIFTY FMCG"},
    {"name": "Nifty Auto", "instrument_key": "NSE_INDEX|Nifty Auto", "symbol": "NIFTY AUTO"},
    {"name": "Nifty Metal", "instrument_key": "NSE_INDEX|Nifty Metal", "symbol": "NIFTY METAL"},
    {"name": "Nifty Infra", "instrument_key": "NSE_INDEX|Nifty Infra", "symbol": "NIFTY INFRA"},
    {"name": "Nifty Midcap 100", "instrument_key": "NSE_INDEX|NIFTY MIDCAP 100", "symbol": "NIFTY MIDCAP 100"}
]

@router.get("/api/index-quotes")
def get_index_quotes():
    upstox = get_upstox_service()
    instrument_keys = [idx["instrument_key"] for idx in INDEX_LIST]
    quotes = {}
    try:
        endpoint = f"{upstox.base_url}/market-quote/ohlc"
        params = {"instrument_key": ",".join(instrument_keys), "interval": "1d"}
        headers = upstox._get_headers()
        headers["Accept"] = "application/json"
        response = requests.get(endpoint, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json().get("data", {})
        for key, val in data.items():
            quotes[key] = {
                "last_price": val.get("last_price"),
                "instrument_token": val.get("instrument_token"),
                "prev_ohlc": val.get("prev_ohlc", {}),
                "live_ohlc": val.get("live_ohlc", {})
            }
        return quotes
    except Exception as e:
        return {"error": str(e)}
