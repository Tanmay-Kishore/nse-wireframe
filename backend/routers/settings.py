from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["settings"])

@router.get("/settings")
async def get_settings():
    """Get application settings"""
    return {"telegram_linked": False, "thresholds": {"gap": 2.0, "rsi": 70}}
