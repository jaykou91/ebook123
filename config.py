import os

# Telegram Bot configuration
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")  # Get token from environment variable

# Database configuration
DATABASE_FILE = "ebooks.db"

# Admin configuration
ADMIN_IDS = [int(id.strip()) for id in os.environ.get("ADMIN_IDS", "").split(",") if id.strip()]

# Default help message
HELP_MESSAGE = """👋 欢迎使用电子书管理机器人！

📚 使用说明:

1. 上传电子书:
   • 直接在群组中发送电子书文件
   • 机器人会自动记录书籍信息

2. 搜索书籍:
   • 使用 /search 命令搜索
   • 例如: /search Python编程
   • 或直接发送书名

3. 其他命令:
   /start - 开始使用机器人
   /help - 显示此帮助信息

如需帮助请联系管理员 @admin_username
加入我们的频道获取更多资源: https://t.me/ebooks_channel
"""

# Bot command descriptions
COMMANDS = {
    'start': '开始使用机器人',
    'help': '显示帮助信息',
    'search': '搜索书籍，用法: /search 书名',
    'addad': '添加广告，用法: /addad 广告文本 URL（仅管理员可用）',
    'editad': '编辑广告，用法: /editad 广告ID 新广告文本 新URL（仅管理员可用）',
    'removead': '删除广告，用法: /removead 广告ID（仅管理员可用）',
    'listad': '列出所有广告（仅管理员可用）',
    'sethelp': '设置帮助信息（仅管理员可用）',
}

# Admin help message
ADMIN_HELP_MESSAGE = """
*🔧 管理员命令:*

1. *添加广告:*
   `/addad 广告文本 广告链接`
   例如: `/addad 加入我们的频道 https://t.me/example`

2. *编辑广告:*
   `/editad 广告ID 新广告文本 新广告链接`
   例如: `/editad 1 更新后的广告文本 https://t.me/new_example`

3. *删除广告:*
   `/removead 广告ID`
   例如: `/removead 1`

4. *查看广告列表:*
   `/listad`
   - 显示所有活动广告的ID、文本和链接

5. *设置帮助信息:*
   `/sethelp 新的帮助信息`
   - 设置新的帮助信息内容
   - 支持 Markdown 格式:
     • *加粗*: 使用 *文字*
     • 用户名: 使用 @username
     • 链接: 使用 [文字](链接)
     • 换行: 使用 \\n
"""