import time
import base64
from telethon import events, Button
import aiosqlite
from telethon.tl.types import MessageEntityBlockquote

DB_FILE = "msg.db"

async def initialize_database():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userid TEXT,
                user_text TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prompts_post (
                index_id TEXT PRIMARY KEY,
                user_id TEXT,
                user_name TEXT,
                title TEXT,
                prompts_content TEXT
            )
        """)
        await db.commit()


async def load_user_config(user_id: str) -> str | None:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT user_text FROM prompts WHERE userid = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def upload_prompts_to_database(user_id: str, user_name: str, prompts_content: str, title: str) -> str:
    index_id = generate_index_id(user_id)
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO prompts_post (index_id, user_id, user_name, title, prompts_content) VALUES (?, ?, ?, ?, ?)",
            (index_id, user_id, user_name, title, prompts_content)
        )
        await db.commit()
    return index_id


async def delete_prompt_from_post(index_id: str, user_id: str) -> bool:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT user_id FROM prompts_post WHERE index_id = ?", (index_id,))
        row = await cursor.fetchone()
        if not row or row[0] != user_id:
            return False
        await db.execute("DELETE FROM prompts_post WHERE index_id = ?", (index_id,))
        await db.commit()
        return db.total_changes > 0


async def get_prompt_title_by_id(index_id: str) -> tuple | None:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT title, user_id FROM prompts_post WHERE index_id = ?", (index_id,))
        return await cursor.fetchone()


async def get_user_posts(user_id: str) -> list:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT title, index_id FROM prompts_post WHERE user_id = ? ORDER BY rowid DESC",
                                  (user_id,))
        return await cursor.fetchall()


async def get_all_posts() -> list:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT title, index_id, user_name FROM prompts_post ORDER BY rowid DESC")
        return await cursor.fetchall()


async def apply_prompt_to_user(target_user_id: str, index_id: str):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT prompts_content FROM prompts_post WHERE index_id = ?", (index_id,))
        prompt_row = await cursor.fetchone()
        if not prompt_row:
            return

        content_to_apply = prompt_row[0]

        cursor = await db.execute("SELECT 1 FROM prompts WHERE userid = ?", (target_user_id,))
        user_exists = await cursor.fetchone()

        if user_exists:
            await db.execute(
                "UPDATE prompts SET user_text = ? WHERE userid = ?",
                (content_to_apply, target_user_id)
            )
        else:
            await db.execute(
                "INSERT INTO prompts (userid, user_text) VALUES (?, ?)",
                (target_user_id, content_to_apply)
            )

        await db.commit()

def get_user_display_name(sender) -> str:
    return sender.username or sender.first_name or sender.last_name or "UnknownUser"


def generate_index_id(user_id: str) -> str:
    timestamp_ms = int(time.time() * 1000)
    timestamp_bytes = timestamp_ms.to_bytes(8, 'big')
    timestamp_b64 = base64.urlsafe_b64encode(timestamp_bytes).decode('utf-8').rstrip('=')
    return user_id[:5] + timestamp_b64

def register_prompt_handlers(client, whitelist_user: list):

    @client.on(events.NewMessage(pattern=r"/prompts_upload(?:$|\s+)(.*)"))
    async def prompts_upload_command(event: events.NewMessage.Event):
        title = event.pattern_match.group(1).strip()
        if not title:
            await event.reply("请提供一个标题,用法: `/prompts_upload [提示词标题]`")
            return

        user_id = str(event.sender_id)
        prompts_content = await load_user_config(user_id)

        if not prompts_content:
            await event.reply("尚未设置过任何提示词，无法上传")
            return

        message_text = (
            f"**内容预览:**\n`{prompts_content[:200]}...`\n\n"
            f"是否将当前提示词以标题 **'{title}'** 上传?"
        )

        buttons = [
            Button.inline("是", data=f"upload_confirm:{user_id}:{title}"),
            Button.inline("否", data=f"upload_cancel:{user_id}")
        ]
        await event.reply(message_text, buttons=buttons, parse_mode='md')

    @client.on(events.NewMessage(pattern=r"/prompts_delete(?:$|\s+)(.*)"))
    async def prompts_delete_command(event: events.NewMessage.Event):
        index_id = event.pattern_match.group(1).strip()
        if not index_id:
            await event.reply("请提供要删除的提示词ID,用法: `/prompts_delete [PromptsID]`")
            return

        user_id = str(event.sender_id)
        prompt_info = await get_prompt_title_by_id(index_id)

        if not prompt_info:
            await event.reply(f"不存在ID为 `{index_id}` 的提示词", parse_mode='md')
            return

        title, owner_id = prompt_info

        if user_id != owner_id:
            await event.reply("没有权限删除不属于你的提示词")
            return

        message_text = f"是否确认删除标题为 **'{title}'** 的提示词?\nID: `{index_id}`"
        buttons = [
            Button.inline("是", data=f"delete_confirm:{user_id}:{index_id}"),
            Button.inline("否", data=f"delete_cancel:{user_id}")
        ]
        await event.reply(message_text, buttons=buttons, parse_mode='md')

    @client.on(events.NewMessage(pattern=r"/prompts_check"))
    async def prompts_check_command(event: events.NewMessage.Event):
        user_id = str(event.sender_id)
        all_user_posts = await get_user_posts(user_id)

        if not all_user_posts:
            await event.reply("尚未上传过任何提示词")
            return

        await send_paginated_list(event, all_user_posts, "check_page", user_id, page=0)

    @client.on(events.NewMessage(pattern=r"/prompts_explore"))
    async def prompts_explore_command(event: events.NewMessage.Event):
        all_posts = await get_all_posts()
        if not all_posts:
            await event.reply("公共提示词库中没有任何内容")
            return

        await send_paginated_list(event, all_posts, "explore_page", str(event.sender_id), page=0)

    @client.on(events.NewMessage(pattern=r"/prompts_view(?:$|\s+)(.*)"))
    async def prompts_view_command(event: events.NewMessage.Event):
        index_id = event.pattern_match.group(1).strip()
        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute("SELECT prompts_content FROM prompts_post WHERE index_id = ?", (index_id,))
            row = await cursor.fetchone()
            prompts_content =  row[0] if row else None
        if not prompts_content:
            await event.reply("未找到该提示词")
            return
        start_message = prompts_content + f"提示词 `{index_id}` 内容"
        await event.reply(start_message, formatting_entities=[
            MessageEntityBlockquote(offset=0, length=len(prompts_content), collapsed=True)])


    async def send_paginated_list(event, items: list, action_prefix: str, user_id: str, page: int = 0):
        items_per_page = 5
        start = page * items_per_page
        end = start + items_per_page

        page_items = items[start:end]
        if not page_items:
            await event.answer("已经是最后一页了")
            return

        text = ""
        action_buttons = []

        if action_prefix == "check_page":
            text = f"**您已上传的提示词 (第 {page + 1} 页):**\n\n"
            for title, index_id in page_items:
                text += f"- **{title}**\n  ID: `{index_id}`\n"

        elif action_prefix == "explore_page":
            text = f"**公共提示词浏览 (第 {page + 1} 页):**\n使用 `/prompts_view [PromptsID]` 以查看对应的提示词内容 \n\n"
            for i, (title, index_id, user_name) in enumerate(page_items):
                text += f"**{i + 1}. {title}**\n   by {user_name} | ID: `{index_id}`\n"
                action_buttons.append(
                    Button.inline(f"使用 {i + 1}", data=f"apply_prompt:{user_id}:{index_id}")
                )

        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("上一页", data=f"{action_prefix}:{user_id}:{page - 1}"))
        if end < len(items):
            nav_buttons.append(Button.inline("下一页", data=f"{action_prefix}:{user_id}:{page + 1}"))

        buttons = [nav_buttons]
        if action_buttons:
            buttons.append(action_buttons)
        if action_prefix == "explore_page":
            buttons.append([Button.inline("取消", data=f"cancel_explore:{user_id}")])

        final_buttons = [row for row in buttons if row]

        markup = final_buttons if final_buttons else None

        if isinstance(event, events.NewMessage.Event):
            await event.reply(text, buttons=markup, parse_mode='md')
        elif isinstance(event, events.CallbackQuery.Event):
            await event.edit(text, buttons=markup, parse_mode='md')

    @client.on(events.CallbackQuery)
    async def callback_handler(event: events.CallbackQuery.Event):
        query_data = event.data.decode('utf-8')
        parts = query_data.split(':')
        action = parts[0]
        original_user_id = parts[1]

        user_id = str(event.sender_id)
        if user_id != original_user_id and user_id not in whitelist_user:
            await event.answer("这不是属于你的按钮", alert=True)
            return

        if action == "upload_confirm":
            title = ":".join(parts[2:])
            prompts_content = await load_user_config(original_user_id)
            user_name = get_user_display_name(event.sender)
            index_id = await upload_prompts_to_database(original_user_id, user_name, prompts_content, title)
            await event.edit(f"当前提示词内容已上传。\n**提示词ID:** `{index_id}`", parse_mode='md')
        elif action == "upload_cancel":
            await event.edit("操作已取消")
        elif action == "delete_confirm":
            index_id = parts[2]
            success = await delete_prompt_from_post(index_id, original_user_id)
            if success:
                await event.edit(f"已删除PromptsID为 `{index_id}` 的提示词", parse_mode='md')
            else:
                await event.edit("删除失败，可能已被删除或没有权限")
        elif action == "delete_cancel":
            await event.edit("操作已取消")
        elif action == "check_page":
            page = int(parts[2])
            all_user_posts = await get_user_posts(original_user_id)
            await send_paginated_list(event, all_user_posts, "check_page", original_user_id, page=page)
        elif action == "explore_page":
            page = int(parts[2])
            all_posts = await get_all_posts()
            await send_paginated_list(event, all_posts, "explore_page", original_user_id, page=page)
        elif action == "apply_prompt":
            index_id = parts[2]
            await apply_prompt_to_user(original_user_id, index_id)
            await event.answer(f"已成功应用提示词 {index_id}！")
        elif action == "cancel_explore":
            await event.delete()
