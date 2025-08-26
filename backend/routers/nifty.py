from fastapi import APIRouter
from nsetools import Nse

router = APIRouter()


import time
from fastapi.responses import JSONResponse

@router.get("/api/nifty-gainers")
def get_nifty_gainers():
    nse = Nse()
    retries = 3
    for attempt in range(retries):
        try:
            gainers = nse.get_top_gainers()
            return gainers
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                return JSONResponse(status_code=503, content={"error": "Could not fetch NIFTY gainers", "detail": str(e)})
