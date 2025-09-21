from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["journal"])

@router.get("/journal")
async def get_journal():
    """Get trading journal entries - TODO: Implement real trading journal"""
    # For now, return empty journal until real trading journal system is implemented
    return {
        "items": [],
        "message": "Trading journal not yet implemented. This will be replaced with real trading records.",
        "total_trades": 0,
        "total_pnl": 0
    }
