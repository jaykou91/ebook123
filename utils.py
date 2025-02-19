from typing import List, Tuple
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def clean_title(title: str) -> str:
    """Clean and normalize book title"""
    # Remove file extensions
    title = re.sub(r'\.(pdf|epub|mobi|txt)$', '', title, flags=re.IGNORECASE)
    # Remove special characters
    title = re.sub(r'[^\w\s\-]', ' ', title)
    # Normalize whitespace
    title = ' '.join(title.split())
    return title

def format_book_result(book: Tuple) -> str:
    """Format book search result for display"""
    title, message_id, chat_id, _ = book
    message_link = f"https://t.me/c/{str(chat_id)[4:]}/{message_id}"
    # Return title as a clickable link using Markdown
    return f"📚 [{title}]({message_link})"

def create_pagination_keyboard(current_page: int, total_pages: int, query: str, advertisements: List[Tuple]) -> InlineKeyboardMarkup:
    """Create pagination keyboard with advertisements"""
    keyboard = []

    # Add pagination buttons
    pagination_buttons = []
    if current_page > 1:
        pagination_buttons.append(
            InlineKeyboardButton("⬅️ 上一页", callback_data=f"page_{current_page-1}_{query}")
        )

    pagination_buttons.append(
        InlineKeyboardButton(f"📖 {current_page}/{total_pages}", callback_data="noop")
    )

    if current_page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton("下一页 ➡️", callback_data=f"page_{current_page+1}_{query}")
        )

    keyboard.append(pagination_buttons)

    # Add advertisement buttons if available
    for ad_text, ad_url in advertisements:
        keyboard.append([InlineKeyboardButton(text=ad_text, url=ad_url)])

    return InlineKeyboardMarkup(keyboard)

def format_search_results(books: List[Tuple], total_count: int, current_page: int, query: str, advertisements: List[Tuple]) -> Tuple[str, InlineKeyboardMarkup]:
    """Format multiple search results with pagination and advertisements"""
    if not books:
        return "❌ 未找到相关书籍", None

    per_page = 10
    total_pages = (total_count + per_page - 1) // per_page

    results = [f"📚 找到 {total_count} 本相关书籍:"]
    for i, book in enumerate(books, 1):
        results.append(f"\n{(current_page-1)*per_page + i}. {format_book_result(book)}")

    pagination_keyboard = create_pagination_keyboard(current_page, total_pages, query, advertisements)

    return '\n'.join(results), pagination_keyboard

def process_username_links(text: str) -> str:
    """Process @ mentions to create proper Telegram links
    Supports both @username and @:username formats
    """
    # First replace @:username format
    text = re.sub(r'@:(\w+)', r'@\1', text)

    # Then handle remaining @username format
    # But don't process if it's part of a URL
    text = re.sub(r'(?<!https?://)@(\w+)', r'@\1', text)

    return text