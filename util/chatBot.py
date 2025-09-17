# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import time
import textdistance
from datetime import datetime
from openai import OpenAI
from telethon.errors import MessageNotModifiedError, FloodWaitError
from telethon.tl.types import Message

import config
import util.initdatabase as initialize_database
from util.imagePredict import get_tags
from util.outputformatter import get_logger

logger = get_logger(logging.DEBUG)
logging.getLogger('telethon').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
conn, cursor = initialize_database.df_initialize_database()
def load_user_config(user_id):

    cursor.execute('SELECT * FROM prompts WHERE userid = ?', (str(user_id),))
    record_cursorfetch = cursor.fetchall()
    if not record_cursorfetch:
        logger.info("No record found for user.")
        return config.default_promptes

    else:
        sys_prompts = cursor.execute('SELECT user_text FROM prompts WHERE userid = ?', (str(user_id),)).fetchall()[0][0]
        logger.info(f"Loaded system prompts: {sys_prompts}")
        return sys_prompts

def check_and_clean_database():
    db_size = os.path.getsize('msg.db') / (1024 * 1024)

    if db_size > config.MAX_SIZE_DB:
        cursor.execute('DELETE FROM messages')
        conn.commit()
    return db_size

def save_message(username, user_text, reply, size):
    timestamp = datetime.now().strftime("%Y-%m-%d |%H:%M:%S|")
    cursor.execute('''
        INSERT INTO messages (timestamp, username, user_text, reply, size)
        VALUES (?, ?, ?, ?, ?)
    ''', (timestamp, username, user_text, reply, size))
    conn.commit()
    return


def truncate_history(history,  MAX_CONTEXT_LENGTH=config.MAX_CONTEXT_LENGTH):

    total_length = sum(len(msg.get("content", "")) for msg in history)
    logger.info(f"Total length: {total_length}")
    if total_length <= MAX_CONTEXT_LENGTH:
        return history

    system_msg = [msg for msg in history if msg["role"] == "system"]
    other_msgs = [msg for msg in history if msg["role"] != "system"]

    while total_length > MAX_CONTEXT_LENGTH and other_msgs:
        removed = other_msgs.pop(0)
        total_length -= len(removed.get("content", ""))

    return system_msg + other_msgs

async def check_similarity_and_reply(history, event):
    assistant_replies = [item["content"] for item in history if item["role"] == "assistant"]

    if len(assistant_replies) < 2:
        return

    latest_reply = assistant_replies[-1]
    previous_reply = assistant_replies[-2]
    similarity = textdistance.cosine(latest_reply, previous_reply)
    logger.info(f"Similarity: {similarity}")
    if similarity > 0.85:
        await event.reply(f"当前文本与前一次回复的相似度是否过高？(similarity.cosine:{similarity})，\n 使用 /newchat 来清空对话缓存。")
        return


async def stream_and_edit(prompt: str, message_to_edit: Message, history) -> str:
    full_reply = ""
    last_sent_text = ""
    last_edit_time = time.monotonic()
    update_interval = config.UPDATE_INTERVAL

    thinking_animation = [' ...', '.. .', '. ..', '... ']
    animation_index = 0

    try:
        text_client = OpenAI(
            api_key=config.CHAT_CONFIG["DEEPSEEK_API_KEY"],
            base_url=config.CHAT_CONFIG["DEEPSEEK_BASE_URL"]
        )

        def sync_ai_call():
            return text_client.chat.completions.create(
                model=config.CHAT_CONFIG["DEEPSEEK_MODEL_TYPE"],
                messages=history,
                stream=True,
                timeout=55
            )

        stream = await asyncio.to_thread(sync_ai_call)

        for chunk in stream:
            new_content = chunk.choices[0].delta.content or ""
            if new_content:
                full_reply += new_content

            now = time.monotonic()

            if now - last_edit_time > update_interval:
                animation_index = (animation_index + 1) % len(thinking_animation)
                display_text = full_reply + thinking_animation[animation_index]

                if display_text != last_sent_text:
                    try:
                        await message_to_edit.edit(text=display_text)
                        last_sent_text = display_text
                        last_edit_time = now
                    except MessageNotModifiedError:
                        pass
                    except FloodWaitError as e:
                        logger.warning(f"FloodWaitError: waiting for {e.seconds} seconds.")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        logger.error(f"Error editing message: {e}")
                        pass

    except Exception as e:
        error_message = f"API ERROR: {e}"
        logger.error(error_message)
        try:
            await message_to_edit.edit(error_message)
        except Exception as edit_err:
            logger.error(f"Failed to even edit the error message: {edit_err}")
        return ""

    finally:
        if full_reply and full_reply != last_sent_text:
            try:
                await message_to_edit.edit(text=full_reply)
            except Exception as e:
                logger.error(f"Error during final edit cleanup: {e}")
    return full_reply
async def chat_func(event,user_text,image = ""):

    try:
        if image != "":
            predicted_tags = get_tags(image)
            logger.info(f"Get Tags: {predicted_tags}")
            prefix_text = f"以下是图片的tag信息：{predicted_tags}；你需要使用以上的视觉tag信息来回应用户，请利用合理的语言，来理解这些Tag，不要直接给出tag信息，应该经过你的翻译和处理返回给用户完整的信息，尽量描述详细，请使用中文回答；"
            user_text = user_text + prefix_text

        sender = await event.get_sender()
        user_id = sender.id
        user_name = sender.username or sender.first_name

        histories = config.conversation_histories
        sys_prompts = load_user_config(user_id)

        history = histories.get(user_id, [{"role": "system", "content": sys_prompts}])

        history.append({"role": "user", "content": user_text})
        message_to_edit = await event.reply("...")
        final_reply = await stream_and_edit(user_text, message_to_edit,history)
        if final_reply and not final_reply.startswith("Error:"):
            history.append({"role": "assistant", "content": final_reply})
            history = truncate_history(history)
            histories[user_id] = history

        await check_similarity_and_reply(history, event)
        check_and_clean_database()
        save_message(user_id,user_text, final_reply, len(final_reply))
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        logger.warning(f"ERROR: {e}")
