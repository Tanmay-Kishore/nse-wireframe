from fastapi import APIRouter
from nsetools import Nse

router = APIRouter()


import time
from fastapi.responses import JSONResponse


@router.get("/api/nifty-movers")
def get_nifty_movers():
    nse = Nse()
    retries = 3
    for attempt in range(retries):
        try:
            gainers = nse.get_top_gainers()
            losers = nse.get_top_losers()
            return {
                "gainers": gainers[:6],
                "losers": losers[:6]
            }
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                return JSONResponse(status_code=503, content={"error": "Could not fetch NIFTY movers", "detail": str(e)})
