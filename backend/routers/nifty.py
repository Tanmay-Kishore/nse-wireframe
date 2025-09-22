from fastapi import APIRouter
from nsetools import Nse

router = APIRouter()


import time
import os
import json
from datetime import datetime, time as dt_time, timedelta
from fastapi.responses import JSONResponse

# Load instruments for company name lookup
instruments_path = os.path.join(os.path.dirname(__file__), '../data/instruments.json')
instruments_data = None

def get_company_name(symbol):
    global instruments_data
    if instruments_data is None:
        try:
            with open(instruments_path, 'r') as f:
                instruments_data = json.load(f)
        except Exception:
            return None

    # Look up company name by symbol
    for inst in instruments_data:
        if inst.get('tradingsymbol', '').upper() == symbol.upper():
            return inst.get('name', '')
    return None

def add_company_names(movers_list):
    """Add company names to movers data"""
    for mover in movers_list:
        company_name = get_company_name(mover.get('symbol', ''))
        if company_name:
            mover['company_name'] = company_name
    return movers_list


@router.get("/api/nifty-movers")
def get_nifty_movers():
    config_path = os.path.join(os.path.dirname(__file__), '../config/top_movers_config.json')
    today = datetime.now().date()
    expiry_time = datetime.combine(today, dt_time(23, 59, 0))
    # Try to load config
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        config_date = datetime.strptime(config.get('date', ''), '%Y-%m-%d').date() if config.get('date') else None
        config_expiry = datetime.strptime(config.get('expiry', ''), '%Y-%m-%d %H:%M:%S') if config.get('expiry') else None
        # If config is for today and not expired, serve cached data
        if config_date == today and config_expiry and datetime.now() < config_expiry:
            gainers = add_company_names(config.get('gainers', []))
            losers = add_company_names(config.get('losers', []))
            return {
                "gainers": gainers,
                "losers": losers
            }
    except Exception:
        pass

    # Otherwise, fetch fresh data
    nse = Nse()
    retries = 3
    for attempt in range(retries):
        try:
            gainers = nse.get_top_gainers()
            losers = nse.get_top_losers()
            # Add company names
            gainers = add_company_names(gainers[:10])
            losers = add_company_names(losers[:10])
            # Save to config
            config = {
                "date": today.strftime('%Y-%m-%d'),
                "expiry": expiry_time.strftime('%Y-%m-%d %H:%M:%S'),
                "gainers": gainers,
                "losers": losers
            }
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            return {
                "gainers": gainers,
                "losers": losers
            }
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                return JSONResponse(status_code=503, content={"error": "Could not fetch NIFTY movers", "detail": str(e)})
