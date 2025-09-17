# -*- coding: utf-8 -*-
import argparse
import asyncio
import shlex
import re
import logging
import traceback

import httpx
import jmespath
from curl_cffi import AsyncSession
import util.cleanupFiles
from telethon.tl.types import MessageEntityBlockquote, DocumentAttributeVideo
from typing import Any
from datetime import datetime

import config
import util.downloadFile
import util.webpConverter
import util.tgmp4Parser
from telethon.errors.rpcerrorlist import MediaEmptyError, EntityBoundsInvalidError, WebpageMediaEmptyError
from bs4 import BeautifulSoup
from util.outputformatter import get_logger
from util.telegraphUpload import upload_urls_to_telegraph

whitelist_user = config.WHITELIST_USER
logger = get_logger(logging.DEBUG)
logging.getLogger('telethon').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)
def parse_input(text: str):
    """
    Args:
        text: str

    Returns:
        {
            "URL": str,
            "sp_detector": str,
            "author_name": str,
            "page_index": str
        }
    """
    try:
        parts = shlex.split(text, posix=False)
        url = parts[0]
        args_to_parse = parts[1:]

        parser = argparse.ArgumentParser(
            description='Parse URL and arguments',
            exit_on_error=False,
            prefix_chars='-+'
        )

        parser.add_argument('+sp', dest='sp_detector', action='store_true', help='Special detector flag.')

        author_name = None
        page_index = None

        remaining_args = []
        for arg in args_to_parse:

            if author_match := re.match(r'@(.*)', arg):
                author_name = author_match.group(1)
                continue

            if page_match := re.match(r'!(.*)', arg):
                page_index = page_match.group(1)
                continue

            remaining_args.append(arg)

        parsed_args = parser.parse_args(remaining_args)

        result = {
            "URL": url,
            "sp_detector": parsed_args.sp_detector,
            "author_name": author_name,
            "page_index": page_index
        }

        return result
    except argparse.ArgumentError:
        return "ERROR"
    except Exception as e:
        # logger.warning(f"{type(e)}\nError parsing input: {e}\n{traceback.format_exc()}")
        return "ERROR"


async def match_site(result: dict, client: Any, event : Any) -> dict | tuple | None:
    sender = await event.get_sender()
    # Twitter
    if "x.com" in result["URL"] or "twitter.com" in result["URL"]:
        fixed_url = result["URL"].split('?')[0]
        source_url = fixed_url

        import extractor.twitterex
        data = await extractor.twitterex.api_response(result)
        try:
            # print(data,result)
            await client.send_file(
                event.chat_id,
                file=data['media'],
                spoiler=result['sp_detector'],
                caption=f"#{data['author']}\n{data['tweet_text']}\n\n{source_url}",
                reply_to=event.message
            )
        except MediaEmptyError:
            await client.send_file(
                event.chat_id,
                file=data['media'][0],
                spoiler=result['sp_detector'],
                caption=f"#{data['author']}\n{data['tweet_text']}\n\n{source_url}",
                reply_to=event.message)
        except WebpageMediaEmptyError:
            file_list = await util.downloadFile.main(data['media'])
            processed_path , width, height, duration = util.tgmp4Parser.main(file_list)
            video_attributes = [
                DocumentAttributeVideo(
                    duration=duration,
                    w=width,
                    h=height,
                    supports_streaming=True
                )
            ]
            await client.send_file(
                event.chat_id,
                file=processed_path,
                caption=f"#{data['author']}\n{data['tweet_text']}\n\n{source_url}",
                reply_to=event.message,
                attributes=video_attributes
            )
            util.cleanupFiles.cleanup_files(list(processed_path))
        except Exception as e:
            logger.warning(f"Error loading data: {e}\n{traceback.format_exc()}")
            logger.error(type(e))
        return data, source_url

    # Gelbooru
    if "gelbooru.com" in result["URL"]:
        source_url = result["URL"]

        def extract_id(url):
            match = re.search(r"id=(\d+)", url)
            return match.group(1) if match else None

        fixed_id = extract_id(result["URL"])
        base_url = config.gelbooru_endpoint + fixed_id

        logger.info(f"Get Link : {base_url}")
        result["URL"] = base_url
        logger.info(f"Result : {result}")

        import extractor.gelbooruex

        data = await extractor.gelbooruex.api_response(result)

        # photo = MessageMediaPhoto(photo=data[0]['url'],spoiler=bool(result['sp_detector']))
        await client.send_file(
            event.chat_id,
            file=data[0]['url'],
            spoiler=bool(result['sp_detector']),
            caption=f"Source:{data[0]['source']}\n\n{source_url}",
            reply_to=event.message
        )
        return data, source_url

    # Yande.Re
    if "yande.re" in result["URL"]:
        source_url = result["URL"]

        def extract_id(url):
            match = re.search(r"show/(\d+)", url)
            return match.group(1) if match else None

        fixed_id = extract_id(result["URL"])
        base_url = config.yandere_endpoint + fixed_id
        logger.info(f"Get Link : {base_url}")
        result["URL"] = base_url
        logger.info(f"Result : {result}")
        import extractor.yanderex
        data = await extractor.yanderex.api_response(result)
        await client.send_file(
            event.chat_id,
            spoiler=bool(result['sp_detector']),
            file=data[0]['url'],
            caption=f"Source:{data[0]['source']}\n\n{source_url}",
            reply_to=event.message
        )
        return data, source_url

    # Pixiv
    if "pixiv.net" in result["URL"]:
        source_url = result["URL"]
        if not event.is_private:
            return None

        def extract_id(url):
            match = re.search(r"artworks/(\d+)", url)
            return match.group(1) if match else None

        fixed_id = extract_id(result["URL"])
        import extractor.pixivex
        local_list, info_dict = await extractor.pixivex.main(fixed_id)

        await client.send_file(
            event.chat_id,
            spoiler=bool(result['sp_detector']),
            file=local_list,
            caption=f"#{info_dict['author']}\nTitle: {info_dict['title']}\n{BeautifulSoup(info_dict['caption'], 'lxml').get_text()}\n{source_url}",
            reply_to=event.message
        )
        util.cleanupFiles.cleanup_files(local_list)

    # Misskey
    if "misskey.io" in result["URL"]:
        source_url = result["URL"]
        import extractor.misskeyex
        data, clean_file_list = await extractor.misskeyex.api_response(result)

        try:

            await client.send_file(
                event.chat_id,
                file=data['media'],
                spoiler=result['sp_detector'],
                caption=f"#{data['author']}\n{data['misskey_text']}\n\n{source_url}",
                reply_to=event.message
            )
            #
            util.cleanupFiles.cleanup_files(clean_file_list)

            return data, source_url
        except Exception as e:
            logger.warning(f"Error loading data: {e}\n{traceback.format_exc()}")

    # Baraag
    if "baraag.net" in result["URL"]:
        source_url = result["URL"]
        import extractor.baraagex
        data = await extractor.baraagex.api_response(result)

        fixed_text = BeautifulSoup(data['text'], 'lxml').get_text()
        try:
            video_urls = []
            image_urls = []

            if 'media' in data and data['media']:
                for url in data['media']:
                    if isinstance(url, str):
                        if url.lower().endswith(('.mp4', '.gif')):
                            video_urls.append(url)
                        else:
                            image_urls.append(url)

            tasks = []
            if video_urls:
                logger.info(f"{len(video_urls)} videos found,Processing..")
                video_task = util.downloadFile.main(video_urls)
                tasks.append(video_task)

            if image_urls:
                logger.info(f"{len(image_urls)} images found,Processing..")
                image_task = util.webpConverter.process_image_list(image_urls, trigger=True)
                tasks.append(image_task)

            local_path_list = []
            if tasks:
                results_from_tasks = await asyncio.gather(*tasks)
                for sublist in results_from_tasks:
                    if isinstance(sublist, list):
                        local_path_list.extend(sublist)

            if local_path_list:
                logger.info(f"Finished processing,{len(local_path_list)} videos or images processed")
                await client.send_file(
                    event.chat_id,
                    file=local_path_list,
                    spoiler=result.get('sp_detector', False),
                    caption=f"#{data.get('author')}\n{fixed_text}\n\n{source_url}",
                    reply_to=event.message
                )
                util.cleanupFiles.cleanup_files(local_path_list)
        except Exception as e:
            logger.warning(f"{type(e)}\nERROR: {e} \n{traceback.format_exc()}")

    # _func fanbox2kemono
    async def get_kemono_page(url_dict: dict):
        pattern = r"^https://kemono\.(?:cr|su)/([^/]+/user/\d+/post/\d+)"
        match = re.search(pattern, url_dict['URL'])

        def html_tag_remover(html_content, allowed_tags):
            if allowed_tags is None:
                allowed_tags = ['p', 'br']
            if not html_content:
                return ""

            soup = BeautifulSoup(html_content, 'lxml')

            for tag in soup.find_all(True):
                if tag.name not in allowed_tags:
                    tag.unwrap()

            return str(soup)

        if match:
            fixed_url = "https://kemono.cr/api/v1/" + match.group(1)
            import extractor.kemonoex

            result_dict = await extractor.kemonoex.execute(fixed_url)
            msg = await event.reply("...")
            urls_list = []
            content = []
            title = result_dict.get('title')

            if result_dict.get('banner'):
                urls_list.append(result_dict['banner'])
            if result_dict.get('url'):
                for url in result_dict['url']:
                    urls_list.append(url)
            if result_dict.get('content'):
                # content.append("<br><p>" + (BeautifulSoup(result_dict['content'], 'lxml').get_text()).replace('\n','<br>') + "</p>")
                content.append(html_tag_remover(result_dict['content'], allowed_tags=['p', 'br']))


            remote_url = await upload_urls_to_telegraph(str(title), urls_list, str(content[0]) if content else "")
            logger.info(f"Telegraph Page: {remote_url}")
            await msg.delete()
            await event.reply(f"{remote_url}\n\n已生成Telegraph预览页(https://kemono.cr/{match.group(1)})")

    # _func fanbox-post type
    async def fanbox_detector(fanbox_post_id: str, account_cookie: str, trigger: bool = False, creator_id: str = None):
        proxies = config.fanbox_proxies
        async def api_response(input_url, df_account_cookie=config.FANBOX_CONFIG['account1']):
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/135.0",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.fanbox.cc",
            }
            cookies = {"FANBOXSESSID": df_account_cookie}
            async with AsyncSession() as session:
                response_rq = await session.get(input_url, headers=headers, cookies=cookies, impersonate="firefox135",timeout=12)
                data_rq = response_rq.json()
                return data_rq

        if not creator_id and not trigger:
            postId_endpoint = "https://api.fanbox.cc/post.info?postId="
            target_url = postId_endpoint + fanbox_post_id

            post_data_dc = await api_response(target_url)
            feeReq = jmespath.search('body.feeRequired', post_data_dc)
            creatorId = jmespath.search('body.creatorId', post_data_dc)
            if str(feeReq)[0] == '0' and not trigger:
                return "PUB"
            else:
                return await fanbox_detector(fanbox_post_id, account_cookie, True, creatorId)

        if trigger:
            creatorId_endpoint = "https://api.fanbox.cc/creator.get?creatorId=" + creator_id

            for i in list(config.FANBOX_CONFIG.values()):
                creator_data_dc = await api_response(creatorId_endpoint, i)
                is_Supported = jmespath.search('*.isSupported', creator_data_dc)
                if is_Supported[0]:
                    return i
            return "NSP"
        return None

    # KemonoParty
    if "kemono.su" in result["URL"] or "kemono.cr" in result["URL"]:
        await get_kemono_page(result)

    # pixivFanbox
    if "fanbox.cc" in result["URL"]:
        import extractor.fanbox2kemonoEx
        source_url = str(result['URL'])

        def strip_number(fanbox_url: str):
            try:
                match = re.search(r"/posts/(\d+)", fanbox_url)
                return match.group(1)
            except Exception as e:
                pattern_e = r'(?:https?://)?(?:www\.)?(?:([^/]+)\.fanbox\.cc|fanbox\.cc/@([^/]+))'
                match = re.search(pattern_e, fanbox_url)
                logger.warning(f"{type(e)}\nERROR: {e} \n{traceback.format_exc()}")
                return match.group(1) or match.group(2),"HOMEPAGE"

        post_id = strip_number(source_url)
        if type(post_id) == tuple:
            user_name = post_id[0]
            kemono_url = await extractor.fanbox2kemonoEx.execute(account_cookies=config.FANBOX_CONFIG['account1'],homepage=user_name)
            if kemono_url == "error" or kemono_url is None or kemono_url == "None":
                msg = await event.reply("未找到对应的Kemono页面，5秒后删除此消息")
                await asyncio.sleep(5)
                await msg.delete()
                return None
            await event.reply(f"对应创作者可能的Kemono主页: {kemono_url}")
            return None
        kemono_url = await extractor.fanbox2kemonoEx.execute(post_id, config.FANBOX_CONFIG['account1'])
        if kemono_url == "error":
            import extractor.fanbox.fanboxex
            try:
                fanbox_data = await fanbox_detector(post_id, config.FANBOX_CONFIG['account1'])
                if fanbox_data == "PUB":
                    msg = await event.reply("公开Fanbox, 正在处理...")
                    remote_url, single_url, text_info, title_info = await extractor.fanbox.fanboxex.execute(
                        config.FANBOX_CONFIG['account1'], post_id, event, client)
                    edited_text = ""
                    tph_text = ""
                    if isinstance(text_info, list):
                        for i in text_info:
                            edited_text += f"{i} \n"
                            tph_text += f"{i} <br>"
                    else:
                        edited_text += text_info
                        tph_text += text_info.replace('\n', '<br>')

                    processed = []
                    pattern = re.compile(r'^https?://.*\.(?:jpe?g|png|gif|bmp|webp)(?:\?.*)?$', re.IGNORECASE)
                    for url in single_url:
                        url = url.strip()
                        if pattern.match(url):
                            processed.append(f"https://image.tunacholy.vip/?url={url}")
                        else:
                            processed.append(url)
                    tph_link = await upload_urls_to_telegraph(title_info, processed, tph_text if tph_text else "")
                    # await msg.edit(
                    #     f"Fanbox Post Title:\n{title_info}\nContent:\n{edited_text if len(edited_text) < 300 else edited_text[:300] + "\n文字内容过长，省略..."}")
                    prefix_text = f"Fanbox Post Title:\n{title_info}\nContent:\n"
                    edited_text = edited_text if len(edited_text) < 300 else edited_text[:300] + "\n文字内容过长，省略..."
                    try:
                        await msg.edit(prefix_text + edited_text, formatting_entities=[
                            MessageEntityBlockquote(offset=len(prefix_text), length=len(edited_text), collapsed=True)])
                    except EntityBoundsInvalidError as e:
                        await msg.edit(prefix_text + edited_text)
                    await event.reply(
                        f"文件已上传至: \n{remote_url} \n所有文件将在每周一(UTC)凌晨删除 请尽快保存")
                    await event.reply(f"临时Telegraph预览链接 \n{tph_link}")
                elif fanbox_data == "NSP":
                    msg = await event.reply("KemonoParty和本地均未检索到此赞助记录...3秒后删除此消息")
                    await asyncio.sleep(3)
                    await msg.delete()
                elif fanbox_data in list(config.FANBOX_CONFIG.values()) and str(sender.id) in whitelist_user:
                    def find_key_by_value(value):
                        for key, val in config.FANBOX_CONFIG.items():
                            if val == value:
                                return key
                        return None
                    msg = await event.reply(f"检索到pixivFanbox账户 `{find_key_by_value(fanbox_data)+":"+fanbox_data[-4:]}` 存在当月赞助记录,正在处理...")
                    remote_url, single_url, text_info, title_info = await extractor.fanbox.fanboxex.execute(fanbox_data,post_id,event,client)
                    edited_text = ""
                    tph_text = ""
                    if isinstance(text_info, list):
                        for i in text_info:
                            edited_text += f"{i} \n"
                            tph_text += f"{i} <br>"
                    else:
                        edited_text += text_info
                        tph_text += text_info.replace('\n', '<br>')

                    processed = []
                    pattern = re.compile(r'^https?://.*\.(?:jpe?g|png|gif|bmp|webp)(?:\?.*)?$', re.IGNORECASE)
                    for url in single_url:
                        url = url.strip()
                        if pattern.match(url):
                            processed.append(f"https://image.tunacholy.vip/?url={url}")
                        else:
                            processed.append(url)

                    tph_link = await upload_urls_to_telegraph(title_info, processed, tph_text if tph_text else "")

                    prefix_text = f"Fanbox Post Title:\n{title_info}\nContent:\n"
                    edited_text = edited_text if len(edited_text) < 300 else edited_text[:300] + "\n文字内容过长，省略..."
                    try:
                        await msg.edit(prefix_text + edited_text, formatting_entities=[
                            MessageEntityBlockquote(offset=len(prefix_text), length=len(edited_text), collapsed=True)])
                    except EntityBoundsInvalidError as e:
                        await msg.edit(prefix_text + edited_text)
                    await event.reply(
                        f"文件已上传至: \n{remote_url} \n所有文件将在每周一(UTC)凌晨删除 请尽快保存")
                    await event.reply(f"临时Telegraph预览链接 \n{tph_link}")

                    return None
                elif fanbox_data in list(config.FANBOX_CONFIG.values()) and str(sender.id) not in whitelist_user:
                    await event.reply(
                        f"检索到pixivFanbox账户{fanbox_data[-4:]}存在当月赞助记录,但是当前用户未在白名单中，等待处理... \n\n`{source_url}` \n\n @tunaloli ")
            except Exception as e:
                logger.warning(f"ERROR: {e} \n{traceback.format_exc()}")
                await event.reply("发生错误")

        else:
            temp_dict = {
                "URL": kemono_url
            }
            msg = await event.reply("检索到KemonoParty存在此Fanbox存档，等待处理...")
            await get_kemono_page(temp_dict)
            await msg.delete()

    # E-Hentai
    if "e-hentai.org" in result["URL"] or "exhentai.org" in result["URL"]:
        user_id = sender.id
        import extractor.exhentaiex
        if str(event.chat_id) not in config.WHITELIST_GROUP and event.is_private and str(
                user_id) not in config.WHITELIST_USER:
            await event.reply("此功能仅限白名单群组使用")
            return None
        try:
            msg = await event.reply("正在处理...")
            link_list, metadata = await extractor.exhentaiex.execute(result)
            chunk_size = 200
            link_chunks = [link_list[i:i + chunk_size] for i in range(0, len(link_list), chunk_size)]

            remote_link = ""
            for i in link_chunks:
                remote_link += await upload_urls_to_telegraph(metadata.get("title", "N/A"), i, "") + "\n"

            await msg.delete()
            await event.reply(remote_link)
        except Exception as e:
            logger.info(f"ERROR: {e} \n{traceback.format_exc()}")
            await msg.delete()
            await event.reply(f"ERROR:{metadata['error']}")
        return None

    # Discord
    if "discord.com" in result["URL"]:
        if str(sender.id) not in config.WHITELIST_USER:
            return None
        source_url = result['URL']
        try:
            import extractor.discordex

            msg = await event.reply("正在获取...")
            content , discord_urls = await extractor.discordex.api_response(result)
            await msg.edit(f"共找到{len(discord_urls)}个链接,正在下载...")

            local_list = await util.downloadFile.main(discord_urls)

            if local_list:
                await client.send_file(
                    event.chat_id,
                    file=local_list,
                    spoiler=result.get('sp_detector', False),
                    caption=f"{content}\n{source_url}",
                    reply_to=event.message
                )
                util.cleanupFiles.cleanup_files(local_list)
                telegraph_link = await util.telegraphUpload.upload_urls_to_telegraph(str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")), discord_urls,attachments_content=content)
                await event.reply(f"下载原图(文件) \n{telegraph_link}")
            await msg.edit(f"Content:\n`{content}`")
            # print(content)
        except Exception as e:
            logger.warning(f"ERROR: {e} \n{traceback.format_exc()}")
            await event.reply(f"ERROR: {e}")

        return None

    #Nhentai
    if "nhentai.net" in result["URL"]:
        source_url = result['URL']
        import extractor.nhentaiex as nhentaiex
        try:
            msg = await event.reply("正在处理...")
            meta_info , links = await nhentaiex.execute(result)
            remote_link = await upload_urls_to_telegraph(meta_info.get("title", "N/A"), links, f"页数：{meta_info.get("num_pages", "N/A")} <br> 原始地址: {source_url}")
            # for i in range(len(links)):
            #     remote_link += await upload_urls_to_telegraph(meta_info.get("title", "N/A"), links[i], "")
            await msg.delete()
            await event.reply(remote_link)
        except Exception as e:
            logger.warning(f"ERROR: {type(e)} \n{traceback.format_exc()}")
            await msg.delete()
            return None

    # _func hitomi-gallery metadata
    async def get_hitomi_metainfo(gid:str):

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://heliotrope.saebasol.org/api/hitomi/galleryinfo/{gid}")
                data = response.json()
            return jmespath.search("title", data)
        except Exception:
            return None

    if "hitomi.la" in result["URL"]:
        source_url = result['URL']
        pattern = r'https://hitomi\.la/\w+/.+?-(\d+)\.html'
        match = re.search(pattern, result['URL'])
        if match:
            gid = match.group(1)
        else : return None
        import extractor.hitomiex as hitomiex
        import util.uploadtoMinio as uploadtoMinio
        try:
            msg = await event.reply("正在处理...")
            file_list = await hitomiex.execute(gid)
            title = await get_hitomi_metainfo(gid)
            print(title)
            if title is None or file_list is None :
                await msg.delete()
                await msg.edit("ERROR: 获取元数据失败")
                return None

            sorted_list = sorted(file_list)
            print("Sour",sorted_list)
            remote_link = await uploadtoMinio.execute(sorted_list)
            tgh_link = await util.telegraphUpload.upload_urls_to_telegraph(title, remote_link, f"原始地址:{source_url}<br>")

            await msg.delete()
            await event.reply(tgh_link)

            await asyncio.sleep(5)
            print(file_list)
            util.cleanupFiles.cleanup_files(file_list)
            print("cleanup")
        except Exception as e:
            logger.warning(f"ERROR: {type(e)} \n{traceback.format_exc()}")
        return None

    if "plurk.com" in result["URL"]:
        source_url = result['URL']
        import extractor.plurkex as plurkex
        try:
            _urls,_meta = await plurkex.execute(result['URL'])
            await client.send_file(
                event.chat_id,
                file=_urls,
                spoiler=result['sp_detector'],
                caption=f"#{_meta['author']}\n{_meta['content']}\n\n{source_url}",
                reply_to=event.message
            )
        except Exception as e:
            await client.send_file(
                event.chat_id,
                file=_urls[0],
                spoiler=result['sp_detector'],
                caption=f"#{_meta['author']}\n{_meta['content']}\n\n{source_url}",
                reply_to=event.message)
            return None


    return None



def detector(input_text) -> str:
    decode_data = "OK"
    if parse_input(input_text) == "ERROR":
        decode_data = "ERROR"
    return decode_data

async def execute(input_text, client, event) -> tuple[dict[str, str | None | Any] | str, dict | tuple | None] | None:
    decode_data = parse_input(input_text)
    if decode_data:
        final_data = await match_site(decode_data, client, event)
        return decode_data, final_data
    return None
#
# if __name__ == "__main__":
#     asyncio.run(execute(input_text = "https://kemono.cr/fanbox/user/24838/post/10232977"))
