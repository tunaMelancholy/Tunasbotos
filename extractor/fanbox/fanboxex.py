# -*- coding: utf-8 -*-
import asyncio
import os
import random
import string
import traceback
import logging

import jmespath
import aiofiles
import httpx
from curl_cffi.requests import AsyncSession as CurlAsyncSession

import config
from util.outputformatter import get_logger

logger = get_logger(logging.DEBUG)
logging.getLogger('curl_cffi').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

DOWNLOAD_ROOT_PATH = '.'
BASE_URL = "."
MAX_FILE_SIZE_GB = config.fanbox_max_file_limit_gb
MAX_FILE_COUNT = config.fanbox_max_file_count
proxies = config.fanbox_proxies

def generate_random_folder(length=5):
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))

async def async_api_response(session: CurlAsyncSession, account_cookie: str, post_id: str):

    fanbox_url = f'https://api.fanbox.cc/post.info?postId={post_id}'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/135.0",
        "Cookie": f"FANBOXSESSID={account_cookie}",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.fanbox.cc",
    }
    try:
        response = await session.get(fanbox_url, headers=headers, impersonate="firefox135", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception:
        logger.error(f"Failed to get API response for post {post_id}:\n{traceback.format_exc()}")
        return None

async def _download_chunk(client: httpx.AsyncClient, url: str, headers: dict, output_path: str, start_byte: int, end_byte: int):

    chunk_headers = headers.copy()
    chunk_headers['Range'] = f'bytes={start_byte}-{end_byte}'
    max_retries = config.fanbox_max_retries
    for attempt in range(max_retries):
        try:
            async with client.stream("GET", url, headers=chunk_headers, timeout=300) as response:
                response.raise_for_status()
                content = await response.aread()
                async with aiofiles.open(output_path, "r+b") as f:
                    await f.seek(start_byte)
                    await f.write(content)
                return True
        except Exception as e:
            logger.warning(f"Chunk ERROR {start_byte}-{end_byte} when downloading... ({attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 * (attempt + 1))
            else:
                logger.error(f"Chunk {start_byte}-{end_byte} download failed after {max_retries} attempts!")
                return False
    return False

async def _single_connection_download(client: httpx.AsyncClient, url: str, output_path: str, headers: dict):

    max_retries = config.fanbox_max_retries
    for attempt in range(max_retries):
        try:
            async with client.stream("GET", url, headers=headers, timeout=300) as response:
                response.raise_for_status()
                async with aiofiles.open(output_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=128 * 1024):
                        await f.write(chunk)
            return True # Success
        except Exception as e:
            logger.warning(f"Single-connection download error ({attempt + 1}/{max_retries}): {os.path.basename(output_path)}. Error: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 * (attempt + 1))
            else:
                logger.error(f"Single-connection download failed for {os.path.basename(output_path)}.")
                return False
    return False

async def async_download_file(client: httpx.AsyncClient, url: str, output_path: str, account_cookie: str):

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/135.0",
        "Cookie": f"FANBOXSESSID={account_cookie}",
        "Referer": "https://fanbox.cc/",
    }
    num_connections = config.fanbox_download_thread

    try:
        response = await client.head(url, headers=headers, timeout=30, follow_redirects=True)
        response.raise_for_status()
        total_size = int(response.headers.get('Content-Length', 0))

        if total_size < config.fanbox_single_file_limit_mb * 1024 * 1024:
            logger.info(f"File size is small. Using single connection for: {os.path.basename(output_path)}")
            return await _single_connection_download(client, url, output_path, headers)

        logger.info(f"File size: {total_size / 1024 / 1024:.2f} MB. Starting download with {num_connections} connections.")

        async with aiofiles.open(output_path, 'wb') as f:
            await f.truncate(total_size)

        chunk_size = total_size // num_connections
        tasks = []
        for i in range(num_connections):
            start = i * chunk_size
            end = start + chunk_size - 1 if i != num_connections - 1 else total_size - 1
            task = _download_chunk(client, url, headers, output_path, start, end)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        if all(results):
            logger.info(f"Multi-connection download successful: {os.path.basename(output_path)}")
            return True
        else:
            logger.warning(f"Some chunks failed to download for: {os.path.basename(output_path)}")
            return False

    except Exception as e:
        logger.error(f"Failed to start download for {os.path.basename(output_path)}. Error: {e}")
        return False

async def download_worker(semaphore: asyncio.Semaphore, client: httpx.AsyncClient, url: str, output_path: str, account_cookie: str):

    async with semaphore:
        return await async_download_file(client, url, output_path, account_cookie)

async def send_files_to_telegram(folder_path: str, event, client):
    logger.info("Prepare to sending files")

    max_size_bytes = MAX_FILE_SIZE_GB * 1024 * 1024 * 1024

    try:
        files_to_send = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if
                         os.path.isfile(os.path.join(folder_path, f))]

        if len(files_to_send) > MAX_FILE_COUNT:
            await event.reply(f"文件总数 `{len(files_to_send)}` 请从网站下载。")
            logger.info("File upload cancelled")
            return

        for file_path in files_to_send:
            if os.path.getsize(file_path) > max_size_bytes:
                await event.reply(f"文件 `{os.path.basename(file_path)}` 大小超过 {MAX_FILE_SIZE_GB}GB，无法发送，请从网站下载")
                return
        logger.info(f"Check pass {len(files_to_send)} ...")
        for file_path in files_to_send:
            logger.info(f"Uploading: {os.path.basename(file_path)}")
            await client.send_file(event.chat_id, file_path, force_document=True)

        logger.info("file downloaded")

    except Exception as e:
        logger.warning(f"ERROR: {e} \n{traceback.format_exc()}")
        await event.reply(f"ERROR: {e}")

async def execute(account_cookie: str, post_id: str, event, client):

    random_folder = generate_random_folder()
    folder_path = os.path.join(DOWNLOAD_ROOT_PATH, random_folder)
    os.makedirs(folder_path, exist_ok=True)

    async with CurlAsyncSession() as curl_session, httpx.AsyncClient(http2=True, follow_redirects=True) as http_client:
        json_data = await async_api_response(curl_session, account_cookie, post_id)
        if not json_data:
            await event.reply("获取FanboxPost过程中发生错误，请检查配置")
            return None, [], None, None

        files_to_download = []
        cover_url = jmespath.search("body.coverImageUrl", json_data)
        if cover_url:
            filename = f"cover.{cover_url.split('.')[-1].split('?')[0]}"
            files_to_download.append((cover_url, filename))

        text_info = jmespath.search('body.body.blocks[*].text', json_data) or jmespath.search('body.body.text', json_data) or []
        title_info = jmespath.search('body.title', json_data)

        images_info = jmespath.search("body.body.images", json_data) or []
        if not images_info:
            images_info = jmespath.search("body.body.imageMap.*", json_data) or []
        for i, image_item in enumerate(images_info):
            if image_item.get('originalUrl') and image_item.get('extension'):
                filename = f"image_{i + 1}.{image_item['extension']}"
                files_to_download.append((image_item['originalUrl'], filename))

        file_map_items = jmespath.search("body.body.fileMap.*", json_data) or jmespath.search("body.body.files", json_data) or []
        for file_item in file_map_items:
            if file_item.get('url') and file_item.get('name') and file_item.get('extension'):
                filename = f"{file_item['name']}.{file_item['extension']}"
                files_to_download.append((file_item['url'], filename))

        files_info_legacy = jmespath.search("body.files", json_data) or []
        for file_item in files_info_legacy:
            if file_item.get('url') and file_item.get('name'):
                files_to_download.append((file_item['url'], file_item['name']))

        if not files_to_download:
            await event.reply("部分文件可能下载未完成")
            return random_folder, [], text_info, title_info

        msg = await event.reply(f"找到 {len(files_to_download)} 个文件，开始下载...")

        CONCURRENT_DOWNLOADS = 4
        semaphore = asyncio.Semaphore(CONCURRENT_DOWNLOADS)
        logger.info(f"Limiting concurrent downloads to: {CONCURRENT_DOWNLOADS}")

        tasks = []
        for url, name in files_to_download:
            safe_name = name.replace('/', '_').replace('\\', '_')
            output_path = os.path.join(folder_path, safe_name)
            task = download_worker(semaphore, http_client, url, output_path, account_cookie)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        successful_downloads = [res for res in results if res]
        logger.info(f"Download process finished. {len(successful_downloads)}/{len(tasks)} files downloaded successfully.")

        if not successful_downloads:
            await msg.edit("文件下载失败，请查看日志")
            return None, [], None, None

        await msg.edit(f"下载完成，正在上传 {len(successful_downloads)} 个文件")
        await send_files_to_telegram(folder_path, event, client)

        final_file_urls = [
            BASE_URL + random_folder + "/" + name.replace('/', '_').replace('\\', '_')
            for (_, name), success in zip(files_to_download, results) if success
        ]
        remote_url = "https://file.proxy.tunacholy.vip/files/" + random_folder
        await msg.delete()
        return remote_url, final_file_urls, text_info, title_info
