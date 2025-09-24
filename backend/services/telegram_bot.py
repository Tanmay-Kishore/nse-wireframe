"""
Telegram Bot Service
Handles bot functionality including helping users find their chat ID
"""

import asyncio
import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from routers.settings import load_telegram_config

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states for manual trade entry
SYMBOL, PRICE, ACTION, QUANTITY, CONFIRMATION = range(5)

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
/trade - Manually enter a trade

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
/trade - Manually enter a trade (symbol, price, quantity)

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
• Manual trade entry via /trade

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
    
    async def trade_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /trade command - start manual trade entry"""
        await update.message.reply_text(
            "📊 **Manual Trade Entry**\n\n"
            "Let's enter a trade manually. I'll guide you through the process.\n\n"
            "First, enter the **stock symbol** (e.g., RELIANCE, TCS, INFY):",
            parse_mode='Markdown'
        )
        return SYMBOL
    
    async def symbol_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle symbol input"""
        symbol = update.message.text.upper().strip()
        
        # Basic validation
        if not symbol or len(symbol) < 2 or len(symbol) > 10:
            await update.message.reply_text(
                "❌ Invalid symbol. Please enter a valid stock symbol (2-10 characters):"
            )
            return SYMBOL
        
        # Store symbol in context
        context.user_data['symbol'] = symbol
        
        await update.message.reply_text(
            f"✅ Symbol: **{symbol}**\n\n"
            f"Now enter the **current price** per share (e.g., 2500.50):",
            parse_mode='Markdown'
        )
        return PRICE
    
    async def price_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle price input"""
        try:
            price = float(update.message.text.strip())
            if price <= 0 or price > 100000:
                raise ValueError("Invalid price range")
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid price. Please enter a valid price (e.g., 2500.50):"
            )
            return PRICE
        
        # Store price in context
        context.user_data['price'] = price
        
        # Create action selection buttons
        keyboard = [
            [InlineKeyboardButton("🟢 BUY", callback_data="action_buy")],
            [InlineKeyboardButton("🔴 SELL", callback_data="action_sell")],
            [InlineKeyboardButton("❌ Cancel", callback_data="action_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Price: **₹{price:.2f}**\n\n"
            f"Now select the **action** (BUY or SELL):",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return ACTION
    
    async def action_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle action selection via buttons"""
        query = update.callback_query
        await query.answer()
        
        action = query.data.split('_')[1]
        
        if action == 'cancel':
            await query.edit_message_text("❌ Trade entry cancelled.")
            return ConversationHandler.END
        
        # Store action in context
        context.user_data['action'] = action
        
        # Check position for SELL orders
        if action == 'sell':
            from services.trade_journal import get_trade_journal
            journal = get_trade_journal()
            current_position = journal.get_current_position(context.user_data['symbol'])
            
            if current_position <= 0:
                await query.edit_message_text(
                    f"❌ **Cannot SELL {context.user_data['symbol']}**\n\n"
                    f"🚫 **No Position Held**\n"
                    f"Current position: {current_position} shares\n\n"
                    f"You cannot sell a stock you don't own.\n"
                    f"First BUY the stock to build a position.",
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
        
        await query.edit_message_text(
            f"✅ Action: **{action.upper()}**\n\n"
            f"Now enter the **quantity** (number of shares):",
            parse_mode='Markdown'
        )
        return QUANTITY
    
    async def quantity_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle quantity input"""
        try:
            quantity = int(update.message.text.strip())
            if quantity <= 0 or quantity > 10000:
                raise ValueError("Invalid quantity range")
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid quantity. Please enter a valid number of shares (1-10000):"
            )
            return QUANTITY
        
        # Store quantity in context
        context.user_data['quantity'] = quantity
        
        # Calculate total value
        total_value = context.user_data['price'] * quantity
        
        # Create confirmation buttons
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Trade", callback_data="confirm_yes")],
            [InlineKeyboardButton("❌ Cancel", callback_data="confirm_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📋 **Trade Summary**\n\n"
            f"📈 Symbol: **{context.user_data['symbol']}**\n"
            f"💰 Price: **₹{context.user_data['price']:.2f}**\n"
            f"{'🟢' if context.user_data['action'] == 'buy' else '🔴'} Action: **{context.user_data['action'].upper()}**\n"
            f"📊 Quantity: **{quantity} shares**\n"
            f"💵 Total Value: **₹{total_value:,.2f}**\n\n"
            f"**Confirm this trade?**",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return CONFIRMATION
    
    async def confirmation_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle trade confirmation"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'confirm_no':
            await query.edit_message_text("❌ Trade cancelled.")
            return ConversationHandler.END
        
        # Execute the trade
        try:
            from services.trade_journal import log_trade
            
            trade_data = {
                'symbol': context.user_data['symbol'],
                'action': context.user_data['action'].upper(),
                'price': context.user_data['price'],
                'quantity': context.user_data['quantity'],
                'confidence': 3,  # Default confidence for manual trades
                'source': 'telegram_manual'
            }
            
            success = await log_trade(trade_data)
            
            if success:
                # Get updated position
                from services.trade_journal import get_trade_journal
                journal = get_trade_journal()
                new_position = journal.get_current_position(context.user_data['symbol'])
                
                emoji = "🟢" if context.user_data['action'] == 'buy' else "🔴"
                total_value = context.user_data['price'] * context.user_data['quantity']
                
                await query.edit_message_text(
                    f"✅ **Trade Executed Successfully**\n\n"
                    f"{emoji} **{context.user_data['action'].upper()} {context.user_data['quantity']} shares of {context.user_data['symbol']}**\n"
                    f"💰 Price: ₹{context.user_data['price']:.2f} per share\n"
                    f"💵 Total: ₹{total_value:,.2f}\n"
                    f"📊 New Position: {new_position} shares\n"
                    f"⏰ {await self._get_current_time()}\n\n"
                    f"Trade recorded in your journal.",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text("❌ Failed to execute trade. Please try again.")
                
        except Exception as e:
            logger.error(f"Error executing manual trade: {e}")
            await query.edit_message_text(f"❌ Error executing trade: {str(e)}")
        
        return ConversationHandler.END
    
    async def cancel_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the conversation"""
        await update.message.reply_text("❌ Trade entry cancelled.")
        return ConversationHandler.END
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

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle button clicks from inline keyboards"""
        query = update.callback_query

        # Acknowledge the button click with timeout handling
        try:
            await asyncio.wait_for(query.answer(), timeout=5.0)
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Button acknowledgment timeout (continuing anyway): {e}")

        try:
            # Parse callback data: format "action_symbol_price_confidence" or "qty_action_symbol_price_quantity"
            callback_data = query.data
            parts = callback_data.split('_')

            if len(parts) < 4:
                await query.edit_message_text("❌ Invalid button data")
                return

            # Handle quantity selection format first
            if parts[0] == 'qty' and len(parts) == 5:
                # Format: "qty_action_symbol_price_quantity"
                action = parts[1]
                symbol = parts[2]
                price = float(parts[3])
                quantity = int(parts[4])
                confidence = 3  # Default confidence for quantity selection

                # Log the trade with specified quantity
                success = await self._log_trade_with_quantity(action, symbol, price, confidence, quantity)

                if success:
                    emoji = "🟢" if action == 'buy' else "🔴"

                    # Get updated position after trade
                    from services.trade_journal import get_trade_journal
                    journal = get_trade_journal()
                    new_position = journal.get_current_position(symbol)

                    response = f"""
✅ **Trade Logged Successfully**

{emoji} **{action.upper()} {quantity} shares of {symbol}**
💰 Price: ₹{price} per share
💵 Total: ₹{price * quantity:,.2f}
📊 New Position: {new_position} shares
⏰ {await self._get_current_time()}

Trade recorded in your journal.
                    """
                else:
                    response = f"❌ Failed to log {action.upper()} trade for {symbol}"

                await query.edit_message_text(response, parse_mode='Markdown')
                return

            # Handle regular signal button format
            action = parts[0]  # 'buy', 'sell', or 'skip'
            symbol = parts[1]
            price = float(parts[2])
            confidence = int(parts[3])

            if action in ['buy', 'sell']:
                # Check position for SELL orders before asking quantity
                if action == 'sell':
                    from services.trade_journal import get_trade_journal
                    journal = get_trade_journal()
                    current_position = journal.get_current_position(symbol)

                    if current_position <= 0:
                        response = f"""
❌ **Cannot SELL {symbol}**

🚫 **No Position Held**
Current position: {current_position} shares

You cannot sell a stock you don't own.
First BUY the stock to build a position.

💡 *Tip: Only BUY signals are available for stocks you don't hold.*
                        """
                        await query.edit_message_text(response, parse_mode='Markdown')
                        return

                # Ask for quantity instead of logging immediately
                await self._ask_for_quantity(query, action, symbol, price, confidence)
                return

            elif action == 'skip':
                response = f"⚪ **Skipped {symbol}**\n\nNo trade recorded."
                await query.edit_message_text(response, parse_mode='Markdown')

            else:
                response = "❌ Unknown action"
                await query.edit_message_text(response, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling button click: {e}")
            await query.edit_message_text(f"❌ Error processing button click: {str(e)}")

    async def _log_trade(self, action: str, symbol: str, price: float, confidence: int) -> bool:
        """Log trade to journal via internal API call"""
        try:
            # Import here to avoid circular imports
            from services.trade_journal import log_trade

            trade_data = {
                'symbol': symbol,
                'action': action.upper(),
                'price': price,
                'confidence': confidence,
                'source': 'telegram_button'
            }

            return await log_trade(trade_data)

        except Exception as e:
            logger.error(f"Error logging trade: {e}")
            return False

    async def _get_current_time(self) -> str:
        """Get formatted current time"""
        from datetime import datetime
        return datetime.now().strftime('%H:%M:%S')

    async def _ask_for_quantity(self, query, action: str, symbol: str, price: float, confidence: int):
        """Ask user for trade quantity with quick selection buttons"""
        from services.trade_journal import get_trade_journal

        journal = get_trade_journal()
        current_position = journal.get_current_position(symbol)

        emoji = "🟢" if action == 'buy' else "🔴"

        # Create quantity selection message
        message = f"""
{emoji} **{action.upper()} {symbol}**

💰 Price: ₹{price} per share
📊 Current Position: {current_position} shares
📊 Signal Confidence: {confidence}/5

**How many shares do you want to {action.lower()}?**

Choose quantity:
        """

        # Create quantity buttons
        quantity_buttons = []

        if action == 'sell':
            # For SELL, limit to current position
            max_sell = min(current_position, 10)  # Max 10 or current position
            quantities = [1, 5, 10, max_sell] if max_sell > 10 else [1, max_sell//2, max_sell] if max_sell > 2 else [1]
            quantities = list(set([q for q in quantities if 0 < q <= current_position]))  # Remove duplicates and invalid
        else:
            # For BUY, offer common quantities
            quantities = [1, 5, 10, 25]

        # Create button rows (2 buttons per row)
        for i in range(0, len(quantities), 2):
            row = []
            for j in range(2):
                if i + j < len(quantities):
                    qty = quantities[i + j]
                    total_value = price * qty
                    row.append(InlineKeyboardButton(
                        f"{qty} shares (₹{total_value:,.0f})",
                        callback_data=f"qty_{action}_{symbol}_{price}_{qty}"
                    ))
            quantity_buttons.append(row)

        # Add cancel button
        quantity_buttons.append([
            InlineKeyboardButton("❌ Cancel", callback_data=f"skip_{symbol}_{price}_{confidence}")
        ])

        reply_markup = InlineKeyboardMarkup(quantity_buttons)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    async def _log_trade_with_quantity(self, action: str, symbol: str, price: float, confidence: int, quantity: int) -> bool:
        """Log trade with specified quantity"""
        try:
            from services.trade_journal import log_trade

            trade_data = {
                'symbol': symbol,
                'action': action.upper(),
                'price': price,
                'quantity': quantity,
                'confidence': confidence,
                'source': 'telegram_button'
            }

            return await log_trade(trade_data)

        except Exception as e:
            logger.error(f"Error logging trade with quantity: {e}")
            return False
    
    async def start_bot(self, bot_token: str) -> bool:
        """Start the Telegram bot"""
        try:
            if self.is_running:
                logger.info("Bot is already running")
                return True
            
            # Create application
            self.application = Application.builder().token(bot_token).build()
            
            # Create conversation handler for manual trade entry
            trade_conversation = ConversationHandler(
                entry_points=[CommandHandler("trade", self.trade_handler)],
                states={
                    SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.symbol_handler)],
                    PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.price_handler)],
                    ACTION: [CallbackQueryHandler(self.action_handler)],
                    QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.quantity_handler)],
                    CONFIRMATION: [CallbackQueryHandler(self.confirmation_handler)],
                },
                fallbacks=[CommandHandler("cancel", self.cancel_handler)],
                per_message=False
            )
            
            # Add handlers
            self.application.add_handler(CommandHandler("start", self.start_handler))
            self.application.add_handler(CommandHandler("chatid", self.chatid_handler))
            self.application.add_handler(CommandHandler("help", self.help_handler))
            self.application.add_handler(trade_conversation)
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
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
    
    async def send_message(self, chat_id: str, message: str, reply_markup=None) -> bool:
        """Send a message to a specific chat with optional buttons"""
        try:
            if not self.application or not self.is_running:
                logger.error("Bot not running")
                return False

            await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return True

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def create_trade_buttons(self, symbol: str, signal_direction: str, price: float, confidence: int) -> InlineKeyboardMarkup:
        """Create inline keyboard buttons for buy/sell actions"""
        buttons = []

        # Create buttons based on signal direction
        if signal_direction == 'BUY':
            buttons.append([
                InlineKeyboardButton(f"🟢 BUY {symbol}", callback_data=f"buy_{symbol}_{price}_{confidence}"),
                InlineKeyboardButton("⚪ Skip", callback_data=f"skip_{symbol}_{price}_{confidence}")
            ])
        elif signal_direction == 'SELL':
            buttons.append([
                InlineKeyboardButton(f"🔴 SELL {symbol}", callback_data=f"sell_{symbol}_{price}_{confidence}"),
                InlineKeyboardButton("⚪ Skip", callback_data=f"skip_{symbol}_{price}_{confidence}")
            ])
        else:  # HOLD
            buttons.append([
                InlineKeyboardButton("ℹ️ Hold Signal", callback_data=f"skip_{symbol}_{price}_{confidence}")
            ])

        return InlineKeyboardMarkup(buttons)

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

async def send_alert(message: str, reply_markup=None) -> bool:
    """Send alert to configured chat with optional buttons"""
    try:
        config = load_telegram_config()
        if not config or not config.get("chat_id"):
            logger.warning("No Telegram chat configured")
            return False

        chat_id = config["chat_id"]
        return await telegram_bot.send_message(chat_id, message, reply_markup)

    except Exception as e:
        logger.error(f"Error sending alert: {e}")
        return False

async def send_alert_with_buttons(message: str, buttons) -> bool:
    """Send alert with interactive buttons"""
    return await send_alert(message, reply_markup=buttons)
