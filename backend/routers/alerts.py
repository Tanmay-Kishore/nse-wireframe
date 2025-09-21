from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["alerts"])

@router.get("/alerts")
async def get_alerts(limit: int = 15):
    """Get recent trading alerts - TODO: Implement real alert system"""
    # For now, return empty alerts until real alert system is implemented
    return {
        "items": [],
        "message": "Alert system not yet implemented. This will be replaced with real trading alerts.",
        "limit": limit
    }
