# -*- coding: utf-8 -*-
import asyncio

import jmespath
import re
from curl_cffi import AsyncSession
import config

async def api_response(result_input: dict):
    """
    :param result_input: a dict type param which include ["URL"]
    :type result_input: dict
    :return: Example : {"media_url": str, "author": str, "text": str}
    :rtype: dict
    """

    pattern = r"https://discord\.com/channels/\d+/(\d+)/(\d+)"
    match = re.match(pattern, result_input['URL'])
    if match:
        channel_id = match.group(1)
        chat_id = match.group(2)
    else:
        return None
    discord_endpoint = f"https://discord.com/api/v9/channels/{channel_id}/messages?limit=50"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/135.0",
        "Content-Type": "application/json",
        "Referer": f"https://discord.com/",
        "Origin": f"https://discord.com/",
        "Authorization": config.discord_token
    }

    async with AsyncSession() as session:
        response = await session.get(discord_endpoint, headers=headers,proxies={"https":"http://127.0.0.1:10808"})
        data = response.json()
    expression = f"[?id=='{chat_id}'].{{content: content, urls: attachments[].url}}"
    result = jmespath.search(expression, data)

    return result[0]['content'], result[0]['urls']

async def download_file():
    result = {
        "URL": "https://discord.com/channels/1174418001496395856/1316671930992037918/1413473925689507960",
        "SP_detector": True,
        "Author_name": "Text",
        "Page_index": "1"
    }
    result,urls = await api_response(result)
    import util.downloadFile
    filelist = await util.downloadFile.main(urls)
    print( filelist)

if __name__ == "__main__":
    import os
    asyncio.run(download_file())
    os.system("explorer downloads")