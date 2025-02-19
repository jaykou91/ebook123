import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import TOKEN, COMMANDS, DATABASE_FILE, HELP_MESSAGE
from database import Database
from handlers import MessageHandler as BotMessageHandler

# Configure logging with more detailed format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

async def error_handler(update, context):
    """Log Errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=True)
    if update and update.message:
        await update.message.reply_text("抱歉，处理您的请求时出现了错误。请稍后重试。")

async def post_init(application: Application) -> None:
    """Post initialization hook to set bot commands"""
    try:
        await application.bot.set_my_commands(
            [(cmd, desc) for cmd, desc in COMMANDS.items()]
        )
        logger.info("Bot commands set successfully")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}", exc_info=True)

def main():
    try:
        # Initialize database
        db = Database(DATABASE_FILE)
        logger.info("Database initialized successfully")

        # Initialize message handler
        handler = BotMessageHandler(db)
        logger.info("Message handler initialized")

        # Initialize bot application
        application = Application.builder().token(TOKEN).post_init(post_init).build()
        logger.info("Application built successfully")

        # Add error handler
        application.add_error_handler(error_handler)

        # Add command handlers
        application.add_handler(CommandHandler("start", handler.start_command))
        application.add_handler(CommandHandler("help", handler.help_command))
        application.add_handler(CommandHandler("search", handler.search_command))
        application.add_handler(CommandHandler("addad", handler.add_advertisement_command))
        application.add_handler(CommandHandler("editad", handler.edit_advertisement_command))
        application.add_handler(CommandHandler("removead", handler.remove_advertisement_command))
        application.add_handler(CommandHandler("listad", handler.list_advertisements_command))
        application.add_handler(CommandHandler("sethelp", handler.set_help_message_command))

        # Add callback query handler for pagination
        application.add_handler(CallbackQueryHandler(handler.handle_pagination))

        # Add message handlers for documents and text
        application.add_handler(MessageHandler(
            filters.Document.ALL & ~filters.COMMAND,
            handler.handle_document,
            block=True
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handler.handle_text,
            block=True
        ))

        logger.info("Starting bot application...")
        application.run_polling(
            allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post", "callback_query"],
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    main()