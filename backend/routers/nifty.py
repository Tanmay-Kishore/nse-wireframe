from fastapi import APIRouter
from nsetools import Nse

router = APIRouter()


import time
from fastapi.responses import JSONResponse


@router.get("/api/nifty-movers")
def get_nifty_movers():
    import os
    import json
    from datetime import datetime, time as dt_time, timedelta
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
            return {
                "gainers": config.get('gainers', []),
                "losers": config.get('losers', [])
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
            # Save to config
            config = {
                "date": today.strftime('%Y-%m-%d'),
                "expiry": expiry_time.strftime('%Y-%m-%d %H:%M:%S'),
                "gainers": gainers[:6],
                "losers": losers[:6]
            }
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            return {
                "gainers": gainers[:6],
                "losers": losers[:6]
            }
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                return JSONResponse(status_code=503, content={"error": "Could not fetch NIFTY movers", "detail": str(e)})
