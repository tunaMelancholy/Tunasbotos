# -*- coding: utf-8 -*-
# @Time       : 2025/7/13 16:05
# @File       : main.py
# @Author     : @tunacholy
# @Description: TunasBot - A bot with couple of boring funcs.
import logging
import os
import random
import sqlite3
import traceback

import httpx
import jmespath
from telethon import TelegramClient, events
from telethon.tl.types import ReactionEmoji , MessageEntityBlockquote
from telethon.utils import pack_bot_file_id
from telethon.tl.functions.messages import SendReactionRequest

#Custom package
import config
import util.chatBot
from extractor import mainExtractor
from extractor.getHeaders import get_headers
from util import prompts_manager
from util.imagePredict import get_tags
from util.outputformatter import get_logger
from util.initdatabase import df_initialize_database

logging.getLogger('telethon').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('aiosqlite').setLevel(logging.WARNING)
logging.getLogger('sqlite3').setLevel(logging.WARNING)

logger = get_logger(logging.DEBUG)
app_id = config.BOT_APP_ID
app_hash = config.BOT_APP_HASH
whitelist_user = config.WHITELIST_USER
whitelist_group = config.WHITELIST_GROUP

bot_token = config.BOT_TOKEN
client_name = config.BOT_CLIENT_NAME
client = TelegramClient(client_name, app_id, app_hash)

@client.on(events.NewMessage(pattern="/start"))
async def start_command(event : events.NewMessage.Event):

    start_message = config.COMMAND_INFO_TEXT+config.START_INFO_TEXT
    await event.reply(start_message, formatting_entities=[MessageEntityBlockquote(offset=0, length=len(config.COMMAND_INFO_TEXT), collapsed=True)])
    return

# Handler
@client.on(events.NewMessage())
async def main_handler(event: events.NewMessage.Event):

    # Basic config
    sender = await event.get_sender()
    chat_id = event.chat_id
    user_text = event.message.text
    is_whitelisted = str(chat_id) in whitelist_group or event.is_private
    if not is_whitelisted:
        logger.info(f"Not in whitelistGroup: {sender.first_name} (ID: {sender.id})")
        return

    # Random Sticker or Reaction
    random_num = random.randint(0, 99)
    if random_num <= config.ACTION_TRIGGER_RATE:
        action_to_take = random.choice(['reaction', 'sticker'])
        if action_to_take == 'reaction':
            emoji = random.choice(config.REACTION_LIST)
            await client(SendReactionRequest(
                peer=event.chat_id,
                msg_id=event.message.id,
                reaction=[ReactionEmoji(emoticon=emoji)],
            ))
        elif action_to_take == 'sticker':
            from util.randomSticker import random_sticker
            sticker_id = random_sticker()
            await event.reply(file=sticker_id)

        # Sticker Fetch
    if event.message and event.message.sticker:
        sticker = event.message.sticker
        stk_id = pack_bot_file_id(sticker)

        from util.stickerFetch import insert_sticker
        insert_sticker(stk_id)

    # Main Extractor
    parse_code = mainExtractor.detector(event.message.text)
    if parse_code == "OK":
        try:
            await mainExtractor.execute(user_text,client, event)
        except Exception as e:
            logger.warning(f"Error sending image: {e}\n{traceback.format_exc()}")

    # Image Chat
    if event.message.photo and event.message.text :
        if event.message.text.startswith('/chat'):
            logger.info(f"Received message from {sender.first_name} (ID: {sender.id}) \nUSERTEXT: {user_text}")
            try:
                download_path = await event.download_media(file="./downloads/temp")
                if event.message.text.startswith('/get_tags'):
                    image_tag = get_tags(download_path)
                    await event.reply(f"`{image_tag}`")
                else:
                    await util.chatBot.chat_func(event, user_text, download_path)
                os.remove(download_path)
            except Exception as e:
                logger.warning(f"Error:{e}")

    return None

@client.on(events.NewMessage(pattern=r'/chat(?:$|\s+)(.*)'))
async def chat_handler(event: events.NewMessage.Event) -> None:
    usertext = event.pattern_match.group(1)
    sender = await event.get_sender()
    chat_id = event.chat_id
    if event.message.photo:
        return None
    if not usertext:
        logger.info("No text provided")
        return None
    if str(sender.id) in whitelist_user or event.is_private or (str(chat_id) in whitelist_group):
        await util.chatBot.chat_func(event, usertext)
    return None

@client.on(events.NewMessage(pattern=r'/trans(?:$|\s+)(.*)'))
async def trans_command(event: events.NewMessage.Event) -> None:
    content = event.pattern_match.group(1).strip()
    if not content:
        await event.reply("请在指令后输入要查询的缩写 例如: `/trans yyds`", parse_mode='md')
        return

    base_url = "https://lab.magiconch.com/api/nbnhhsh/guess"
    payload = {"text": content}
    headers = get_headers("https://lab.magiconch.com/")

    try:
        async with httpx.AsyncClient() as session:
            response = await session.post(
                base_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

        result = jmespath.search("[*].trans", data)

        if result and result[0]:
            translations = result[0]
            translation_lines = [f"{''.join(sublist)}" for sublist in translations]
            translation_text = "\n".join(translation_lines)

            prefix_text = f"缩写 {content} 可能的全称为"
            await event.reply(prefix_text+translation_text,formatting_entities=[MessageEntityBlockquote(offset=len(prefix_text), length=len(translation_text), collapsed=True)])

        else:
            await event.reply(f"缩写 {content} 没有找到对应的全称。")
    except Exception as e:
        logger.warning(f"Error: {e}\n{traceback.format_exc()}")
        await event.reply(f"查询 {content} 时发生错误,{e}")



@client.on(events.NewMessage(pattern=r'^/prompts_query$'))
async def prompts_query_command(event : events.NewMessage.Event):
    sender = await event.get_sender()
    user_id = sender.id

    try:
        def pmt_query(user_id):
            conn, cursor = df_initialize_database()
            text = cursor.execute('SELECT user_text FROM prompts WHERE userid = ?', (user_id,)).fetchone()
            conn.commit()
            conn.close()
            return str(text)
        text = pmt_query(str(user_id))
        await event.reply(text, formatting_entities=[MessageEntityBlockquote(offset=0, length=len(text), collapsed=True)])
    except Exception as e:
        logger.warning(f"{type(e)}\nError: {e}")
    return


@client.on(events.NewMessage(pattern=r'/prompts(?:$|\s+)([\s\S]*)'))
async def prompts_command(event : events.NewMessage.Event):
    changed_content = event.pattern_match.group(1)
    content = changed_content.strip()

    if not content:
        return None
    sender = await event.get_sender()
    user_id = sender.id
    conn, cursor = df_initialize_database()
    logger.info(f"Received message from {sender.first_name} (ID: {sender.id}) \nUSERTEXT: {content}")
    cursor.execute('SELECT * FROM prompts WHERE userid = ?', (str(user_id),))
    existing_records = cursor.fetchall()

    if not existing_records:
        cursor.execute('INSERT INTO prompts (userid, user_text) VALUES (?, ?)',
                       (str(user_id), changed_content))
        await event.reply("提示词内容已更改，使用 /newchat (开启新对话)清空缓存")
        await event.delete()
    else:
        cursor.execute('UPDATE prompts SET user_text = ? WHERE userid = ?',
                       ( changed_content, str(user_id)))
        await event.reply("提示词内容已更改，使用 /newchat (开启新对话)清空缓存")
        await event.delete()

    conn.commit()
    conn.close()

    return None


@client.on(events.NewMessage(pattern=r'^/kemomimi$'))
async def kemomimi_command(event : events.NewMessage.Event):
    sender = await event.get_sender()
    user_id = sender.id

    def init_database():
        conn = sqlite3.connect('kemomimi.db')
        cursor = conn.cursor()
        return conn, cursor

    conn, cursor = init_database()
    try:
        random_number = random.randint(0, cursor.execute("SELECT COUNT(*) FROM posts;").fetchone()[0])
        load_data = cursor.execute(f"SELECT * FROM posts LIMIT 1 OFFSET {random_number};").fetchall()[0]
        # print(load_data)
        prefix_id = f"https://gelbooru.com/index.php?page=post&s=view&id={load_data[0]}"
        source_url = load_data[1]
        prefix_url = load_data[2]
        await client.send_file(
            event.chat_id,
            file=prefix_url,
            caption=f"Source: {source_url}\n\nGelbooru: {prefix_id}",
            reply_to=event.message
        )
        return None
    except Exception as e:
        logger.warning(f"Error loading data: {e}")
    return None

@client.on(events.NewMessage(pattern=r'/kemomimi_update(?:$|\s+)(.*)'))
async def kemomimi_update_command(event : events.NewMessage.Event):
    page_index = event.pattern_match.group(1).strip()
    sender = await event.get_sender()
    if str(sender.id) not in whitelist_user:
        print("Not in whitelist")
        return None
    else:
        from util.kemomimiUpdate import update_database
        content = page_index
        if content:
            msg = await event.reply("正在更新数据库")
            await update_database(int(content))
            await msg.edit(f"更新完成，共更新了 {int(content) * 100} 个Posts")
        else:
            msg = await event.reply("正在更新数据库")
            await update_database()
            await msg.edit("更新完成，共更新了 500 个Posts")
    return None

@client.on(events.NewMessage(pattern="/newchat"))
async def newchat_command(event : events.NewMessage.Event):
    sender = await event.get_sender()
    user_id = sender.id
    chat_id = event.chat_id
    if str(sender.id) in whitelist_user or event.is_private or (str(chat_id) in whitelist_group):
        config.conversation_histories.pop(user_id, None)
        await event.reply("对话已清空")
        return None
    return None

@client.on(events.NewMessage(pattern="/server_info"))
async def server_info_command(event : events.NewMessage.Event):
    sender = await event.get_sender()
    if str(sender.id) not in config.WHITELIST_USER:
        print("Not in whitelist")
        return

    import util.get_serverinfo

    msg = await event.reply("正在查询信息....")

    import util.get_serverinfo
    base_info ,inst_info0 ,inst_info1 ,chat_info = await util.get_serverinfo.get_info()

    sum_info = base_info + chat_info + inst_info0 + inst_info1
    await msg.delete()
    await event.reply(
        f"{base_info}{chat_info}<blockquote expandable>{inst_info0}{inst_info1}</blockquote>",
        parse_mode = "html"
    )
    return None

@client.on(events.NewMessage(pattern="/get_all_support"))
async def get_all_support_command(event : events.NewMessage.Event):
    sender = await event.get_sender()
    if str(sender.id) not in config.WHITELIST_USER:
        print("Not in whitelist")
        return

    msg = await event.reply("正在查询信息....")
    try:
        import extractor.fanbox.get_support_count as get_all_support
        text, detail_text = await get_all_support.get_all_account()
    except Exception as e:
        await msg.edit(f"Error:{type(e)}:{e}")
        return None
    await msg.edit(
        f"{text}<blockquote expandable>{detail_text}</blockquote>",
        parse_mode = "html"
    )
    return None


@client.on(events.NewMessage(pattern="/more"))
async def more_command(event : events.NewMessage.Event):
    sender = await event.get_sender()
    if str(sender.id) !='6086014392':
        print("Not in whitelist")
        return
    chat = event.chat
    more_text = "更多指令如下："
    command_text = """
        /get_all_support - 获取当月所有账户赞助的fanbox创作者数量
        /server_info - 查看实例信息
        /delete_cache - 删除下载缓存
    """
    more_message = config.COMMAND_INFO_TEXT+config.START_INFO_TEXT
    await event.reply(more_message, formatting_entities=[MessageEntityBlockquote(offset=0, length=len(config.COMMAND_INFO_TEXT), collapsed=True)])
    return

async def main():
    await client.start(bot_token=bot_token)
    logger.info("Connecting...")

    me = await client.get_me()
    logger.warning(f"Logging: {me.first_name} (ID: {me.id}, Username: @{me.username})")
    logger.info("Connected")

    logger.info("Init Chat Database...")
    await prompts_manager.initialize_database()
    prompts_manager.register_prompt_handlers(client, whitelist_user)
    logger.info("Success!")

    await client.run_until_disconnected()


if __name__ == '__main__':
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        raise SystemExit("Keyboard Interrupt")
    finally:
        if client.is_connected():
            client.loop.run_until_complete(client.disconnect())
            logger.warning("Disconnected")
