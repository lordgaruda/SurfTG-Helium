from os.path import splitext
import re
from bot.config import Telegram
from bot.helper.database import Database
from bot.telegram import StreamBot
from bot.helper.file_size import get_readable_file_size
from bot.helper.cache import get_cache, save_cache
from asyncio import gather

db = Database()


async def fetch_message(chat_id, message_id):
    try:
        message = await StreamBot.get_messages(chat_id, message_id)
        return message
    except Exception as e:
        return None


async def get_messages(chat_id, first_message_id, last_message_id, batch_size=50):
    messages = []
    current_message_id = first_message_id
    while current_message_id <= last_message_id:
        batch_message_ids = list(range(current_message_id, min(current_message_id + batch_size, last_message_id + 1)))
        tasks = [fetch_message(chat_id, message_id) for message_id in batch_message_ids]
        batch_messages = await gather(*tasks)
        for message in batch_messages:
            if message:
                if file := message.video or message.document:
                    title = file.file_name or message.caption or file.file_id
                    title, _ = splitext(title)
                    title = re.sub(r'[.,|_\',]', ' ', title)
                    messages.append({"msg_id": message.id, "title": title,
                                     "hash": file.file_unique_id[:6], "size": get_readable_file_size(file.file_size),
                                     "type": file.mime_type, "chat_id": str(chat_id)})
        current_message_id += batch_size
    return messages


async def get_files(chat_id, page=1):
    # Try database first
    db_results = await db.list_tgfiles(id=chat_id, page=page)
    if db_results:
        return db_results
    
    # Check cache
    if cache := get_cache(chat_id, int(page)):
        return cache
    
    # Fallback to StreamBot using get_messages (bot-compatible)
    # Note: This requires the channel to be indexed first using /index command
    # as bots cannot use get_chat_history (messages.GetHistory is user-only)
    posts = []
    batch_size = 50
    # Calculate message ID range based on page (newer messages have higher IDs)
    # This is a best-effort fallback - for reliable results, use /index command
    start_id = ((int(page) - 1) * batch_size) + 1
    end_id = int(page) * batch_size
    
    message_ids = list(range(start_id, end_id + 1))
    try:
        messages = await StreamBot.get_messages(int(chat_id), message_ids)
        if not isinstance(messages, list):
            messages = [messages]
        for post in messages:
            if post and not post.empty:
                file = post.video or post.document
                if not file:
                    continue
                title = file.file_name or post.caption or file.file_id
                title, _ = splitext(title)
                title = re.sub(r'[.,|_\',]', ' ', title)
                posts.append({"msg_id": post.id, "title": title,
                            "hash": file.file_unique_id[:6], "size": get_readable_file_size(file.file_size), "type": file.mime_type})
    except Exception as e:
        # If fetching by IDs fails, return empty - user should run /index command
        pass
    
    if posts:
        save_cache(chat_id, {"posts": posts}, page)
    return posts

async def posts_file(posts, chat_id):
    phtml = """
            <div class="col">
                
                    <div class="card text-white bg-primary mb-3">
                        <input type="checkbox" class="admin-only form-check-input position-absolute top-0 end-0 m-2"
                            onchange="checkSendButton()" id="selectCheckbox"
                            data-id="{id}|{hash}|{title}|{size}|{type}|{img}">
                        <img src="https://cdn.jsdelivr.net/gh/weebzone/weebzone/data/Surf-TG/src/loading.gif" class="lzy_img card-img-top rounded-top"
                            data-src="{img}" alt="{title}">
                        <a href="/watch/{chat_id}?id={id}&hash={hash}">
                        <div class="card-body p-1">
                            <h6 class="card-title">{title}</h6>
                            <span class="badge bg-warning">{type}</span>
                            <span class="badge bg-info">{size}</span>
                        </div>
                        </a>
                    </div>
                
            </div>
"""
    return ''.join(phtml.format(chat_id=str(chat_id).replace("-100", ""), id=post["msg_id"], img=f"/api/thumb/{chat_id}?id={post['msg_id']}", title=post["title"], hash=post["hash"], size=post['size'], type=post['type']) for post in posts)
