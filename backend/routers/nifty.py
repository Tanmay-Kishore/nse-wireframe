from fastapi import APIRouter
from nsetools import Nse

router = APIRouter()

@router.get("/api/nifty-gainers")
def get_nifty_gainers():
    nse = Nse()
    gainers = nse.get_top_gainers()
    # Filter for NIFTY stocks only (if needed)
    # gainers = [g for g in gainers if g['symbol'] in NIFTY_SYMBOLS]
    return gainers
