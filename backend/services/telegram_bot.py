"""
Telegram Bot Service
Handles bot functionality including helping users find their chat ID
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from routers.settings import load_telegram_config

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBotService:
    def __init__(self):
        self.application = None
        self.is_running = False
    
    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        welcome_message = f"""
🤖 **NSE Monitor Bot**

Hello {user.first_name}! 👋

Your Chat ID is: `{chat_id}`

You can use this Chat ID to configure the bot in your NSE Monitor settings.

**Available Commands:**
/start - Show this message and your chat ID
/chatid - Get your chat ID
/help - Show help information

To set up notifications:
1. Copy your Chat ID: `{chat_id}`
2. Go to NSE Monitor Settings
3. Click "Link" under Telegram
4. Enter your bot token and this Chat ID
5. Save configuration

Ready to receive stock alerts! 📈
        """
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def chatid_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /chatid command"""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        message = f"""
📋 **Chat ID Information**

User: {user.first_name}
Chat ID: `{chat_id}`
Chat Type: {update.effective_chat.type}

Copy this Chat ID and use it in your NSE Monitor settings to receive alerts.
        """
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def help_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        help_message = """
🤖 **NSE Monitor Bot Help**

**Commands:**
/start - Welcome message with your Chat ID
/chatid - Get your Chat ID for configuration  
/help - Show this help message

**Setup Instructions:**
1. Get your bot token from @BotFather
2. Use /chatid to get your Chat ID
3. Configure both in NSE Monitor settings
4. Start receiving stock alerts!

**Features:**
• Real-time stock price alerts
• RSI & technical indicator notifications  
• Gap up/down alerts
• Custom threshold monitoring

For support, check your NSE Monitor application.
        """
        
        await update.message.reply_text(help_message, parse_mode='Markdown')
    
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle any text message"""
        chat_id = update.effective_chat.id
        
        # If it's a new user or they're asking for chat ID
        message_text = update.message.text.lower()
        
        if any(word in message_text for word in ['chat id', 'chatid', 'id', 'setup', 'configure']):
            await self.chatid_handler(update, context)
        else:
            # General response with chat ID
            response = f"""
Hello! Your Chat ID is: `{chat_id}`

Use /help to see available commands or /chatid to get your Chat ID for NSE Monitor configuration.
            """
            await update.message.reply_text(response, parse_mode='Markdown')
    
    async def start_bot(self, bot_token: str) -> bool:
        """Start the Telegram bot"""
        try:
            if self.is_running:
                logger.info("Bot is already running")
                return True
            
            # Create application
            self.application = Application.builder().token(bot_token).build()
            
            # Add handlers
            self.application.add_handler(CommandHandler("start", self.start_handler))
            self.application.add_handler(CommandHandler("chatid", self.chatid_handler))
            self.application.add_handler(CommandHandler("help", self.help_handler))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
            
            # Start polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            self.is_running = True
            logger.info("Telegram bot started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            return False
    
    async def stop_bot(self):
        """Stop the Telegram bot"""
        try:
            if self.application and self.is_running:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                self.is_running = False
                logger.info("Telegram bot stopped")
            
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
    
    async def send_message(self, chat_id: str, message: str) -> bool:
        """Send a message to a specific chat"""
        try:
            if not self.application or not self.is_running:
                logger.error("Bot not running")
                return False
            
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )
            return True
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

# Global bot instance
telegram_bot = TelegramBotService()

async def start_telegram_bot_if_configured():
    """Start bot if Telegram is configured"""
    try:
        config = load_telegram_config()
        if config and config.get("bot_token"):
            bot_token = config["bot_token"]
            success = await telegram_bot.start_bot(bot_token)
            if success:
                logger.info("Telegram bot auto-started from saved configuration")
            else:
                logger.error("Failed to auto-start Telegram bot")
    except Exception as e:
        logger.error(f"Error auto-starting bot: {e}")

async def send_alert(message: str) -> bool:
    """Send alert to configured chat"""
    try:
        config = load_telegram_config()
        if not config or not config.get("chat_id"):
            logger.warning("No Telegram chat configured")
            return False
        
        chat_id = config["chat_id"]
        return await telegram_bot.send_message(chat_id, message)
        
    except Exception as e:
        logger.error(f"Error sending alert: {e}")
        return False
