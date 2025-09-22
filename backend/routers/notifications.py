"""
Notifications Router
API endpoints for managing signal change notifications
"""

from fastapi import APIRouter, HTTPException, Query
import logging
from services.signal_monitor import get_signal_monitor, start_signal_monitoring, stop_signal_monitoring
from services.stop_loss_monitor import get_stop_loss_monitor, start_stop_loss_monitoring, stop_stop_loss_monitoring
# Real-time monitor temporarily unavailable
from services.telegram_bot import send_alert

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])

signal_monitor = get_signal_monitor()
stop_loss_monitor = get_stop_loss_monitor()

# Real-time monitor not available after revert
realtime_monitor = None
realtime_available = False

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

@router.post("/stop-loss/start")
async def start_stop_loss_monitoring_endpoint(interval_minutes: int = Query(2, ge=1, le=30, description="Check interval in minutes")):
    """Start stop-loss monitoring for open positions"""
    try:
        if stop_loss_monitor.monitoring:
            return {
                "success": True,
                "message": "Stop-loss monitoring already active",
                "interval_minutes": interval_minutes
            }

        await start_stop_loss_monitoring(interval_minutes)

        return {
            "success": True,
            "message": f"Stop-loss monitoring started with {interval_minutes}min intervals",
            "interval_minutes": interval_minutes
        }

    except Exception as e:
        logger.error(f"Error starting stop-loss monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop-loss/stop")
async def stop_stop_loss_monitoring_endpoint():
    """Stop stop-loss monitoring"""
    try:
        if not stop_loss_monitor.monitoring:
            return {
                "success": True,
                "message": "Stop-loss monitoring was not active"
            }

        await stop_stop_loss_monitoring()

        return {
            "success": True,
            "message": "Stop-loss monitoring stopped"
        }

    except Exception as e:
        logger.error(f"Error stopping stop-loss monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop-loss/check-now")
async def check_stop_losses_now():
    """Manually check all positions for stop-loss hits"""
    try:
        hits_count = await stop_loss_monitor.check_and_alert()

        return {
            "success": True,
            "stop_loss_hits": hits_count,
            "message": f"Stop-loss check completed. {hits_count} alerts sent." if hits_count > 0 else "No stop-losses hit."
        }

    except Exception as e:
        logger.error(f"Error in manual stop-loss check: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stop-loss/status")
async def get_stop_loss_status():
    """Get stop-loss monitoring status"""
    try:
        status = stop_loss_monitor.get_monitoring_status()
        return {
            "stop_loss_monitoring": status,
            "message": "Stop-loss monitoring active" if status['monitoring'] else "Stop-loss monitoring inactive"
        }

    except Exception as e:
        logger.error(f"Error getting stop-loss status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/realtime/start")
async def start_realtime_monitoring():
    """Start real-time watchlist signal monitoring"""
    try:
        if not realtime_available:
            return {
                "success": False,
                "message": "Real-time monitoring not available - service not found"
            }

        if realtime_monitor.monitoring:
            return {
                "success": True,
                "message": "Real-time monitoring already active"
            }

        # Real-time monitoring not available
        pass

        return {
            "success": True,
            "message": "Real-time watchlist monitoring started successfully",
            "type": "websocket_stream"
        }

    except Exception as e:
        logger.error(f"Error starting real-time monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/realtime/stop")
async def stop_realtime_monitoring():
    """Stop real-time watchlist monitoring"""
    try:
        if not realtime_available:
            return {
                "success": False,
                "message": "Real-time monitoring not available"
            }

        if not realtime_monitor.monitoring:
            return {
                "success": True,
                "message": "Real-time monitoring was not active"
            }

        # Real-time monitoring not available
        pass

        return {
            "success": True,
            "message": "Real-time monitoring stopped"
        }

    except Exception as e:
        logger.error(f"Error stopping real-time monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/realtime/status")
async def get_realtime_monitoring_status():
    """Get real-time monitoring status"""
    try:
        if not realtime_available:
            return {
                "realtime_available": False,
                "message": "Real-time monitoring service not available"
            }

        status = realtime_monitor.get_monitoring_status()
        return {
            "realtime_status": status,
            "message": "Real-time monitoring active" if status['realtime_monitoring'] else "Real-time monitoring inactive"
        }

    except Exception as e:
        logger.error(f"Error getting real-time status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-signal")
async def send_test_signal_notification(signal_type: str = "BUY", symbol: str = "TCS", price: float = 3200.0, confidence: int = 4):
    """Send a test signal notification with interactive buttons"""
    try:
        from services.telegram_bot import telegram_bot
        from routers.settings import load_telegram_config
        from datetime import datetime

        config = load_telegram_config()
        if not config or not config.get("chat_id"):
            return {
                "success": False,
                "message": "Telegram not configured - no chat ID"
            }

        chat_id = config["chat_id"]

        # Create sample signal data
        sample_signal = {
            'symbol': symbol.upper(),
            'new_signal': {
                'direction': signal_type.upper(),
                'confidence': confidence,
                'price': price,
                'sentiment': 'BULLISH' if signal_type.upper() == 'BUY' else 'BEARISH',
                'entry': price,
                'sl': price * 0.97 if signal_type.upper() == 'BUY' else price * 1.03,
                'target': price * 1.06 if signal_type.upper() == 'BUY' else price * 0.94,
                'reasons': [
                    f"Strong {signal_type.lower()}ish trend: Price > MA50 > MA200" if signal_type.upper() == 'BUY' else f"Strong {signal_type.lower()}ish trend: Price < MA50 < MA200",
                    f"RSI momentum: RSI 65.0 > 40" if signal_type.upper() == 'BUY' else f"RSI momentum: RSI 35.0 < 60",
                    f"Above MA20: Price above short-term MA" if signal_type.upper() == 'BUY' else f"Below MA20: Price below short-term MA"
                ]
            },
            'change_type': f"Test Signal: HOLD → {signal_type.upper()}"
        }

        # Format the message
        message = f"""🚨 **TEST SIGNAL NOTIFICATION**

{'🟢' if signal_type.upper() == 'BUY' else '🔴'} **{symbol.upper()}** - {sample_signal['new_signal']['sentiment']}
📊 **Signal**: {signal_type.upper()} {'⭐' * confidence}{'☆' * (5 - confidence)} ({confidence}/5)
💰 **Current Price**: ₹{price:,.2f}

🎯 **Trading Levels**:
   📈 Entry: ₹{sample_signal['new_signal']['entry']:,.2f}
   🛑 Stop Loss: ₹{sample_signal['new_signal']['sl']:,.2f}
   🎯 Target: ₹{sample_signal['new_signal']['target']:,.2f}

🔍 **Analysis**:
• {sample_signal['new_signal']['reasons'][0]}
• {sample_signal['new_signal']['reasons'][1]}
• {sample_signal['new_signal']['reasons'][2]}

📈 **Change**: {sample_signal['change_type']}

⏰ **Test Notification** - {datetime.now().strftime('%H:%M:%S')}

Choose your action:"""

        # Create interactive buttons
        buttons = telegram_bot.create_trade_buttons(
            symbol.upper(),
            signal_type.upper(),
            price,
            confidence
        )

        # Send the test notification
        success = await telegram_bot.send_message(chat_id, message, reply_markup=buttons)

        if success:
            return {
                "success": True,
                "message": f"Test {signal_type.upper()} signal sent for {symbol.upper()}",
                "signal_details": {
                    "symbol": symbol.upper(),
                    "signal": signal_type.upper(),
                    "price": price,
                    "confidence": confidence,
                    "entry": sample_signal['new_signal']['entry'],
                    "sl": sample_signal['new_signal']['sl'],
                    "target": sample_signal['new_signal']['target']
                }
            }
        else:
            return {
                "success": False,
                "message": "Failed to send test notification"
            }

    except Exception as e:
        logger.error(f"Error sending test signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))