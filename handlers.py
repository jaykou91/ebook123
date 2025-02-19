import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from database import Database
from utils import clean_title, format_search_results
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, database: Database):
        self.db = database
        self.context = None

    async def delete_message_later(self, chat_id: int, message_id: int, delay: int = 10):
        """Delete a message after specified delay in seconds"""
        try:
            if not self.context:
                logger.error("Context not available for delete_message_later")
                return
            logger.info(f"Scheduled deletion of message {message_id} in {delay} seconds")
            await asyncio.sleep(delay)
            try:
                await self.context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"Successfully deleted message {message_id} in chat {chat_id}")
            except Exception as delete_error:
                logger.error(f"Failed to delete message {message_id}: {delete_error}")
        except Exception as e:
            logger.error(f"Error in delete_message_later: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        logger.info("Handling /start command")
        help_message = self.db.get_help_message()
        await update.message.reply_text(help_message, parse_mode='HTML')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        logger.info("Handling /help command")
        help_message = self.db.get_help_message()
        await update.message.reply_text(help_message, parse_mode='HTML')

    async def set_help_message_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sethelp command (admin only)"""
        try:
            logger.info("Handling /sethelp command")
            if not self.is_admin(update.effective_user.id):
                await update.message.reply_text("❌ 此命令仅管理员可用")
                return

            # Use the raw message text after the command to preserve formatting
            command_length = len("/sethelp ")
            new_message = update.message.text[command_length:]
            if not new_message:
                await update.message.reply_text(
                    "❌ 请在命令后输入新的帮助信息\n\n"
                    "您可以直接使用 Telegram 的文本编辑功能：\n"
                    "• 直接输入文字并使用 Telegram 的格式工具\n"
                    "• 直接换行即可\n"
                    "• 支持所有 Telegram 的富文本格式\n\n"
                    "例如：\n/sethelp 欢迎使用机器人"
                )
                return

            # Keep the original formatting from Telegram
            if self.db.update_help_message(new_message):
                await update.message.reply_text("✅ 帮助信息已更新，以下是预览效果：")
                await update.message.reply_text(new_message, parse_mode='HTML')
            else:
                logger.error("Database update failed for help message")
                await update.message.reply_text("❌ 更新帮助信息失败，请重试")

        except Exception as e:
            logger.error(f"Error in set_help_message_command: {str(e)}", exc_info=True)
            await update.message.reply_text(
                "❌ 设置帮助信息时出错，请重试"
            )

    async def add_advertisement_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /addad command (admin only)"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 此命令仅管理员可用")
            return

        if not context.args or len(context.args) < 2:
            await update.message.reply_text("❌ 请提供广告文本和链接\n例如: /addad 加入我们的频道 https://t.me/example")
            return

        text = ' '.join(context.args[:-1])
        url = context.args[-1]

        if self.db.add_advertisement(text, url):
            await update.message.reply_text(f"✅ 广告已添加:\n文本: {text}\n链接: {url}")
        else:
            await update.message.reply_text("❌ 添加广告失败，请重试")

    async def remove_advertisement_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /removead command (admin only)"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 此命令仅管理员可用")
            return

        if not context.args:
            await update.message.reply_text("❌ 请提供要删除的广告ID\n例如: /removead 1")
            return

        try:
            ad_id = int(context.args[0])
            if self.db.remove_advertisement(ad_id):
                await update.message.reply_text(f"✅ 广告 #{ad_id} 已删除")
            else:
                await update.message.reply_text(f"❌ 未找到ID为 {ad_id} 的广告")
        except ValueError:
            await update.message.reply_text("❌ 请提供有效的广告ID")

    async def list_advertisements_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /listad command (admin only)"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 此命令仅管理员可用")
            return

        ads = self.db.list_advertisements()
        if not ads:
            await update.message.reply_text("📢 目前没有活动的广告")
            return

        response = ["📢 当前活动的广告列表:"]
        for ad_id, text, url in ads:
            response.append(f"\n🔸 ID: {ad_id}")
            response.append(f"   文本: {text}")
            response.append(f"   链接: {url}")

        await update.message.reply_text('\n'.join(response))

    async def edit_advertisement_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /editad command (admin only)"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ 此命令仅管理员可用")
            return

        if not context.args or len(context.args) < 3:
            await update.message.reply_text(
                "❌ 请提供广告ID、新的广告文本和链接\n"
                "例如: /editad 1 更新后的广告文本 https://t.me/new_example"
            )
            return

        try:
            ad_id = int(context.args[0])
            url = context.args[-1]
            text = ' '.join(context.args[1:-1])

            # 检查广告是否存在
            existing_ad = self.db.get_advertisement(ad_id)
            if not existing_ad:
                await update.message.reply_text(f"❌ 未找到ID为 {ad_id} 的广告")
                return

            if self.db.edit_advertisement(ad_id, text, url):
                await update.message.reply_text(
                    f"✅ 广告已更新:\n"
                    f"ID: {ad_id}\n"
                    f"新文本: {text}\n"
                    f"新链接: {url}"
                )
            else:
                await update.message.reply_text("❌ 更新广告失败，请重试")
        except ValueError:
            await update.message.reply_text("❌ 请提供有效的广告ID")
        except Exception as e:
            logger.error(f"Error editing advertisement: {e}")
            await update.message.reply_text("❌ 编辑广告时出错，请重试")

    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search command"""
        query = ' '.join(context.args) if context.args else ''
        if not query:
            reply = await update.message.reply_text("请输入要搜索的书名，例如: /search Python编程")
            asyncio.create_task(self.delete_message_later(reply.chat_id, reply.message_id))
            return

        logger.info(f"Searching for books with query: {query}")
        results, total_count = self.db.search_books(query, page=1)

        # Get active advertisements
        advertisements = self.db.get_active_advertisements()
        response, reply_markup = format_search_results(results, total_count, 1, query, advertisements)
        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)

    async def handle_pagination(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle pagination button clicks"""
        query = update.callback_query
        await query.answer()

        try:
            # Extract page number and search query from callback data
            _, page, search_query = query.data.split('_', 2)
            page = int(page)

            # Get books for the requested page
            results, total_count = self.db.search_books(search_query, page=page)
            advertisements = self.db.get_active_advertisements()
            response, reply_markup = format_search_results(results, total_count, page, search_query, advertisements)

            # Update the message with new results
            await query.edit_message_text(
                text=response,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error handling pagination: {e}")
            await query.edit_message_text("❌ 翻页出错，请重新搜索")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document messages (file uploads)"""
        try:
            # Store context at the beginning
            self.context = context
            logger.info("Document handler started, context stored")

            if not update.message or not update.message.document:
                logger.warning("Received document handler call without proper document")
                return

            document = update.message.document
            file_name = document.file_name
            if not file_name:
                logger.warning("Document without filename received")
                reply = await update.message.reply_text("❌ 无法获取文件名")
                asyncio.create_task(self.delete_message_later(reply.chat_id, reply.message_id))
                return

            # Check if it's an ebook
            supported_extensions = ['.pdf', '.epub', '.mobi', '.txt']
            is_ebook = any(file_name.lower().endswith(ext) for ext in supported_extensions)
            if not is_ebook:
                logger.info(f"Ignoring non-ebook file: {file_name}")
                reply = await update.message.reply_text(
                    "❌ 不支持的文件格式。请上传 PDF、EPUB、MOBI 或 TXT 格式的电子书。"
                )
                asyncio.create_task(self.delete_message_later(reply.chat_id, reply.message_id))
                return

            title = clean_title(file_name)
            message_id = update.message.message_id
            chat_id = update.message.chat_id
            file_id = document.file_id

            logger.info(f"Processing book upload: {title}")

            try:
                # Check if book already exists
                existing_book = self.db.check_book_exists(title)
                if existing_book:
                    logger.info(f"Found existing book with title: {title}")
                    existing_title, existing_msg_id, existing_chat_id, _ = existing_book
                    # Check if the existing message still exists
                    if self.db.check_message_exists(existing_chat_id, existing_msg_id):
                        # Message still exists, show duplicate warning
                        logger.info(f"Book already exists and message is still valid: {title}")
                        message_link = f"https://t.me/c/{str(existing_chat_id)[4:]}/{existing_msg_id}"
                        response = f"📚 该书籍已收录，请勿重复上传\n标题: [{existing_title}]({message_link})"
                        reply = await update.message.reply_text(
                            response,
                            parse_mode='Markdown',
                            disable_web_page_preview=True
                        )
                        logger.info(f"Sent duplicate warning for: {title}")
                        asyncio.create_task(self.delete_message_later(reply.chat_id, reply.message_id))
                        return
                    else:
                        # If message was deleted, remove it from database and proceed with new upload
                        logger.info(f"Removing deleted message for book: {title}")
                        self.db.remove_deleted_messages(existing_chat_id, existing_msg_id)

                # Store book information
                logger.info(f"Attempting to add book to database: {title}")
                success = self.db.add_book(title, message_id, chat_id, file_id)

                # Prepare response message
                if success:
                    logger.info(f"Successfully added book: {title}")
                    message_link = f"https://t.me/c/{str(chat_id)[4:]}/{message_id}"
                    response = f"✅ 已收录电子书: [{title}]({message_link})"
                else:
                    logger.error(f"Failed to add book: {title}")
                    response = "❌ 保存书籍信息失败，请稍后重试"

                # Always send a response and schedule its deletion
                logger.info(f"Sending response message for book: {title}")
                reply = await update.message.reply_text(
                    response,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                logger.info(f"Response sent, message ID: {reply.message_id}")
                asyncio.create_task(self.delete_message_later(reply.chat_id, reply.message_id))

            except Exception as db_error:
                logger.error(f"Database operation error for {title}: {str(db_error)}", exc_info=True)
                reply = await update.message.reply_text("❌ 处理书籍信息时出错，请稍后重试")
                asyncio.create_task(self.delete_message_later(reply.chat_id, reply.message_id))

        except Exception as e:
            logger.error(f"Error in document handler: {str(e)}", exc_info=True)
            try:
                reply = await update.message.reply_text("❌ 处理文件时出错，请稍后重试")
                asyncio.create_task(self.delete_message_later(reply.chat_id, reply.message_id))
            except Exception as reply_error:
                logger.error(f"Failed to send error message: {reply_error}", exc_info=True)

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin"""
        return user_id in ADMIN_IDS

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (book searches)"""
        try:
            # Store context at the beginning
            self.context = context

            if not update.message:
                logger.warning("Received text handler call without message")
                return

            query = update.message.text.strip()
            if not query or query.startswith('/'):
                return

            logger.info(f"Processing text search: {query}")
            results, total_count = self.db.search_books(query, page=1)
            advertisements = self.db.get_active_advertisements()
            response, reply_markup = format_search_results(results, total_count, 1, query, advertisements)
            await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error handling text search: {e}")
            await update.message.reply_text("❌ 搜索时出错，请稍后重试")