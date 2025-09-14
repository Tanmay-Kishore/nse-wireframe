"""
Alert Service for Bollinger Band Monitoring
Monitors price crosses and sends Telegram notifications
"""

import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
import os

logger = logging.getLogger(__name__)

class AlertService:
    def __init__(self):
        self.active_alerts = {}  # symbol -> {price, bb_upper, bb_lower, last_alert_time}
        self.alert_cooldown = 300  # 5 minutes cooldown between alerts for same symbol
        
    async def check_bollinger_band_crosses(self, symbol: str, current_price: float, 
                                         bb_upper: float, bb_lower: float) -> Optional[str]:
        """
        Check if price has crossed Bollinger Bands and return alert message if needed
        """
        try:
            current_time = datetime.now()
            alert_key = f"{symbol}_bollinger"
            
            # Get previous state
            prev_state = self.active_alerts.get(alert_key)
            
            # Determine current position relative to bands
            if current_price > bb_upper:
                position = "above_upper"
                alert_type = "resistance_break"
                message = f"🔴 **BOLLINGER BAND BREAKOUT**\n\n" \
                         f"**{symbol}** has broken above resistance!\n" \
                         f"💰 Current Price: ₹{current_price:.2f}\n" \
                         f"📈 Upper Band: ₹{bb_upper:.2f}\n" \
                         f"📊 Lower Band: ₹{bb_lower:.2f}\n" \
                         f"🚀 Price is **{((current_price - bb_upper) / bb_upper * 100):.1f}%** above upper band\n\n" \
                         f"⚠️ This could indicate strong upward momentum or overbought conditions.\n" \
                         f"🕐 {current_time.strftime('%H:%M:%S')}"
            elif current_price < bb_lower:
                position = "below_lower"
                alert_type = "support_break"
                message = f"🟢 **BOLLINGER BAND BREAKDOWN**\n\n" \
                         f"**{symbol}** has fallen below support!\n" \
                         f"💰 Current Price: ₹{current_price:.2f}\n" \
                         f"📉 Lower Band: ₹{bb_lower:.2f}\n" \
                         f"📊 Upper Band: ₹{bb_upper:.2f}\n" \
                         f"📉 Price is **{((bb_lower - current_price) / bb_lower * 100):.1f}%** below lower band\n\n" \
                         f"⚠️ This could indicate strong downward momentum or oversold conditions.\n" \
                         f"🕐 {current_time.strftime('%H:%M:%S')}"
            else:
                position = "within_bands"
                alert_type = None
                message = None
            
            # Check if we should send alert
            if alert_type and message:
                # Check cooldown
                if prev_state:
                    last_alert_time = prev_state.get("last_alert_time")
                    if last_alert_time:
                        time_since_alert = (current_time - last_alert_time).total_seconds()
                        if time_since_alert < self.alert_cooldown:
                            return None
                    
                    # Check if position changed (avoid repeated alerts for same condition)
                    if prev_state.get("position") == position:
                        return None
                
                # Update alert state
                self.active_alerts[alert_key] = {
                    "price": current_price,
                    "bb_upper": bb_upper,
                    "bb_lower": bb_lower,
                    "position": position,
                    "alert_type": alert_type,
                    "last_alert_time": current_time
                }
                
                return message
            
            # Update state without alert
            self.active_alerts[alert_key] = {
                "price": current_price,
                "bb_upper": bb_upper,
                "bb_lower": bb_lower,
                "position": position,
                "alert_type": None,
                "last_alert_time": prev_state.get("last_alert_time") if prev_state else None
            }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking Bollinger Band crosses for {symbol}: {e}")
            return None
    
    async def send_telegram_alert(self, message: str) -> bool:
        """Send alert via Telegram bot"""
        try:
            from services.telegram_bot import send_alert
            success = await send_alert(message)
            return success
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
            return False

# Global alert service instance
alert_service = AlertService()

def get_alert_service() -> AlertService:
    """Get the global alert service instance"""
    return alert_service