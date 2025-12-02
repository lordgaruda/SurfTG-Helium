import re
from bot.config import Telegram
from bot.helper.database import Database
from bot.telegram import StreamBot
from os.path import splitext
from bot.helper.file_size import get_readable_file_size

db = Database()
async def search(chat_id, query, page):
    # Always use database search, or fallback to StreamBot
    db_results = await db.search_tgfiles(id=chat_id, query=query, page=page)
    if db_results:
        return db_results
    
    # Fallback to StreamBot search if database is empty
    posts = []
    async for post in StreamBot.search_messages(chat_id=int(chat_id), limit=50, query=str(query), offset=(int(page) - 1) * 50):
        file = post.video or post.document
        if not file:
            continue
        title = file.file_name or post.caption or file.file_id
        title, _ = splitext(title)
        title = re.sub(r'[.,|_\',]', ' ', title)
        posts.append({"msg_id": post.id, "title": title,
                     "hash": file.file_unique_id[:6], "size": get_readable_file_size(file.file_size), "type": file.mime_type})
    return posts
