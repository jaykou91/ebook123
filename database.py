import sqlite3
from typing import List, Tuple, Optional
import logging
from config import HELP_MESSAGE  #Import only HELP_MESSAGE

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        """Initialize database and create tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                # Create ebooks table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS ebooks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        message_id INTEGER NOT NULL,
                        chat_id INTEGER NOT NULL,
                        file_id TEXT,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                # Create index for faster search
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_title ON ebooks(title)
                ''')

                # Create advertisements table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS advertisements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        text TEXT NOT NULL,
                        url TEXT NOT NULL,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Create system_messages table for configurable messages
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        type TEXT NOT NULL UNIQUE,
                        content TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Insert or update default help message
                cursor.execute('''
                    INSERT OR REPLACE INTO system_messages (type, content)
                    VALUES ('help', ?)
                ''', (HELP_MESSAGE,))

                conn.commit()
                logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise

    def get_help_message(self) -> str:
        """Get the current help message"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT content FROM system_messages
                    WHERE type = 'help'
                ''')
                result = cursor.fetchone()
                content = result[0] if result else HELP_MESSAGE
                logger.info(f"Retrieved help message (raw): {repr(content)}")
                return content
        except sqlite3.Error as e:
            logger.error(f"Error getting help message: {e}")
            return HELP_MESSAGE

    def update_help_message(self, new_message: str) -> bool:
        """Update the help message"""
        try:
            # Process @ mentions in the message
            from utils import process_username_links
            processed_message = process_username_links(new_message)

            logger.info(f"Updating help message. New content (raw): {repr(processed_message)}")
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO system_messages (type, content)
                    VALUES ('help', ?)
                ''', (processed_message,))
                conn.commit()
                logger.info("Help message updated successfully")
                return True
        except sqlite3.Error as e:
            logger.error(f"Error updating help message: {e}")
            return False

    def check_book_exists(self, title: str) -> Optional[Tuple]:
        """Check if a book with the same title exists"""
        try:
            logger.info(f"Checking if book exists: {title}")
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT title, message_id, chat_id, file_id
                    FROM ebooks
                    WHERE title = ?
                    LIMIT 1
                ''', (title,))
                result = cursor.fetchone()
                logger.info(f"Book exists: {result is not None}")
                return result
        except sqlite3.Error as e:
            logger.error(f"Error checking book existence: {e}")
            return None

    def add_book(self, title: str, message_id: int, chat_id: int, file_id: str) -> bool:
        """Add a new book to the database"""
        try:
            # Check if book already exists
            existing_book = self.check_book_exists(title)
            if existing_book:
                logger.info(f"Book already exists: {title}")
                return False

            logger.info(f"Adding new book: {title}")
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO ebooks (title, message_id, chat_id, file_id)
                    VALUES (?, ?, ?, ?)
                ''', (title, message_id, chat_id, file_id))
                conn.commit()
                logger.info(f"Successfully added book: {title}")
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to add book {title}: {e}")
            return False

    def search_books(self, query: str, page: int = 1, per_page: int = 10) -> Tuple[List[Tuple], int]:
        """
        Search for books in the database with pagination
        Returns: (books_list, total_count)
        """
        try:
            logger.info(f"Searching for books with query: {query}, page: {page}")
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                search_query = f"%{query}%"

                # Get paginated results (only latest version of each book)
                offset = (page - 1) * per_page
                cursor.execute('''
                    WITH RankedBooks AS (
                        SELECT e.*,
                               ROW_NUMBER() OVER (PARTITION BY e.title ORDER BY e.added_date DESC) as rn
                        FROM ebooks e
                        WHERE e.title LIKE ?
                    )
                    SELECT title, message_id, chat_id, file_id,
                           (SELECT COUNT(*) 
                            FROM RankedBooks rb2 
                            WHERE rb2.rn = 1) as total_count
                    FROM RankedBooks rb1
                    WHERE rn = 1
                    ORDER BY added_date DESC
                    LIMIT ? OFFSET ?
                ''', (search_query, per_page, offset))

                results = cursor.fetchall()
                if not results:
                    return [], 0

                total_count = results[0][4]  # Get total_count from the first row
                # Remove total_count from results
                filtered_results = [(row[0], row[1], row[2], row[3]) for row in results]

                # Filter out deleted messages
                valid_results = []
                actual_count = total_count

                for result in filtered_results:
                    title, msg_id, chat_id, file_id = result
                    if self.check_message_exists(chat_id, msg_id):
                        valid_results.append(result)
                    else:
                        self.remove_deleted_messages(chat_id, msg_id)
                        actual_count -= 1

                logger.info(f"Found {len(valid_results)} valid results for page {page} (total: {actual_count})")
                return valid_results, actual_count

        except sqlite3.Error as e:
            logger.error(f"Error searching for books: {e}")
            return [], 0

    def get_book(self, title: str) -> Optional[Tuple]:
        """Get a specific book by exact title"""
        try:
            logger.info(f"Getting book by title: {title}")
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT title, message_id, chat_id, file_id
                    FROM ebooks
                    WHERE title = ?
                    LIMIT 1
                ''', (title,))
                result = cursor.fetchone()
                logger.info(f"Book found: {result is not None}")
                return result
        except sqlite3.Error as e:
            logger.error(f"Error getting book: {e}")
            return None

    def add_advertisement(self, text: str, url: str) -> bool:
        """Add a new advertisement"""
        try:
            logger.info(f"Adding new advertisement: {text}")
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO advertisements (text, url)
                    VALUES (?, ?)
                ''', (text, url))
                conn.commit()
                logger.info("Advertisement added successfully")
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to add advertisement: {e}")
            return False

    def get_active_advertisements(self) -> List[Tuple]:
        """Get active advertisements (maximum 5)"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT text, url
                    FROM advertisements
                    WHERE is_active = 1
                    ORDER BY RANDOM()
                    LIMIT 5
                ''')
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error getting advertisements: {e}")
            return []

    def remove_advertisement(self, ad_id: int) -> bool:
        """Remove an advertisement by setting it as inactive"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE advertisements
                    SET is_active = 0
                    WHERE id = ?
                ''', (ad_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error removing advertisement: {e}")
            return False

    def edit_advertisement(self, ad_id: int, text: str, url: str) -> bool:
        """Edit an existing advertisement"""
        try:
            logger.info(f"Editing advertisement #{ad_id}")
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE advertisements
                    SET text = ?, url = ?
                    WHERE id = ? AND is_active = 1
                ''', (text, url, ad_id))
                conn.commit()
                success = cursor.rowcount > 0
                logger.info(f"Advertisement #{ad_id} edited successfully: {success}")
                return success
        except sqlite3.Error as e:
            logger.error(f"Failed to edit advertisement #{ad_id}: {e}")
            return False

    def get_advertisement(self, ad_id: int) -> Optional[Tuple]:
        """Get a specific advertisement by ID"""
        try:
            logger.info(f"Getting advertisement #{ad_id}")
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, text, url
                    FROM advertisements
                    WHERE id = ? AND is_active = 1
                ''', (ad_id,))
                result = cursor.fetchone()
                logger.info(f"Advertisement found: {result is not None}")
                return result
        except sqlite3.Error as e:
            logger.error(f"Error getting advertisement #{ad_id}: {e}")
            return None

    def list_advertisements(self) -> List[Tuple]:
        """Get all active advertisements with their IDs"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, text, url
                    FROM advertisements
                    WHERE is_active = 1
                    ORDER BY id
                ''')
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error listing advertisements: {e}")
            return []

    def check_message_exists(self, chat_id: int, message_id: int) -> bool:
        """Check if a message still exists in the chat"""
        try:
            logger.info(f"Checking if message exists: chat_id={chat_id}, message_id={message_id}")
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*)
                    FROM ebooks
                    WHERE chat_id = ? AND message_id = ?
                ''', (chat_id, message_id))
                count = cursor.fetchone()[0]
                return count > 0
        except sqlite3.Error as e:
            logger.error(f"Error checking message existence: {e}")
            return False

    def remove_deleted_messages(self, chat_id: int, message_id: int):
        """Remove book entry when the message is deleted"""
        try:
            logger.info(f"Removing deleted message: chat_id={chat_id}, message_id={message_id}")
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM ebooks
                    WHERE chat_id = ? AND message_id = ?
                ''', (chat_id, message_id))
                conn.commit()
                logger.info(f"Deleted {cursor.rowcount} records")
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error removing deleted message: {e}")
            return False