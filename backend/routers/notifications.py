"""
Notifications Router
API endpoints for managing signal change notifications
"""

from fastapi import APIRouter, HTTPException, Query
import logging
from services.signal_monitor import get_signal_monitor, start_signal_monitoring, stop_signal_monitoring
from services.telegram_bot import send_alert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])

signal_monitor = get_signal_monitor()

@router.get("/status")
async def get_notification_status():
    """Get current notification monitoring status"""
    try:
        status = signal_monitor.get_monitoring_status()
        return {
            "status": status,
            "message": "Monitoring active" if status['monitoring'] else "Monitoring inactive"
        }
    except Exception as e:
        logger.error(f"Error getting notification status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start")
async def start_notifications(interval_minutes: int = Query(5, ge=1, le=60, description="Check interval in minutes")):
    """Start signal change monitoring and notifications"""
    try:
        if signal_monitor.monitoring:
            return {
                "success": True,
                "message": "Monitoring already active",
                "interval_minutes": interval_minutes
            }

        await start_signal_monitoring(interval_minutes)

        return {
            "success": True,
            "message": f"Signal monitoring started with {interval_minutes}min intervals",
            "interval_minutes": interval_minutes
        }

    except Exception as e:
        logger.error(f"Error starting notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_notifications():
    """Stop signal change monitoring"""
    try:
        if not signal_monitor.monitoring:
            return {
                "success": True,
                "message": "Monitoring was not active"
            }

        await stop_signal_monitoring()

        return {
            "success": True,
            "message": "Signal monitoring stopped"
        }

    except Exception as e:
        logger.error(f"Error stopping notifications: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test")
async def test_notification():
    """Send a test notification to verify Telegram setup"""
    try:
        test_message = """
🤖 **Test Notification**

This is a test message from NSE Monitor to verify your Telegram notification setup.

✅ If you received this message, notifications are working correctly!

⏰ """ + f"{logger.name}"

        success = await send_alert(test_message)

        if success:
            return {
                "success": True,
                "message": "Test notification sent successfully"
            }
        else:
            return {
                "success": False,
                "message": "Failed to send test notification. Check Telegram configuration."
            }

    except Exception as e:
        logger.error(f"Error sending test notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/check-now")
async def check_signals_now():
    """Manually trigger a signal check and send notifications if changes detected"""
    try:
        changes_count = await signal_monitor.check_and_notify()

        return {
            "success": True,
            "changes_detected": changes_count,
            "message": f"Signal check completed. {changes_count} changes detected." if changes_count > 0 else "No signal changes detected."
        }

    except Exception as e:
        logger.error(f"Error in manual signal check: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_notification_history():
    """Get recent signal change history"""
    try:
        # Get cached signals for history
        status = signal_monitor.get_monitoring_status()

        return {
            "monitoring_active": status['monitoring'],
            "cached_signals": status['cached_signals_count'],
            "last_check": status['last_check'],
            "upstox_configured": status['upstox_configured']
        }

    except Exception as e:
        logger.error(f"Error getting notification history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/settings")
async def get_notification_settings():
    """Get notification settings and configuration"""
    try:
        from routers.settings import load_telegram_config

        config = load_telegram_config()
        telegram_configured = bool(config and config.get("bot_token") and config.get("chat_id"))

        status = signal_monitor.get_monitoring_status()

        return {
            "telegram_configured": telegram_configured,
            "upstox_configured": status['upstox_configured'],
            "monitoring_active": status['monitoring'],
            "requirements_met": telegram_configured and status['upstox_configured'],
            "setup_instructions": {
                "telegram": "Configure bot token and chat ID in Settings",
                "upstox": "Configure Upstox API credentials in Settings",
                "monitoring": "Use /start endpoint to begin monitoring"
            }
        }

    except Exception as e:
        logger.error(f"Error getting notification settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))