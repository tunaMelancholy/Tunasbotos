# -*- coding: utf-8 -*-
import asyncio
import re
import jmespath
from curl_cffi import AsyncSession
from extractor.getHeaders import get_headers
from config import misskey_api_endpoint

async def api_response(result_input: dict):
    """
    :param result_input: a dict type param which include ["URL"]
    :type result_input: dict
    :return: Example : {"media_url": list or str, "misskey_text": str, "author": str}
    :rtype: dict
    """

    def extract_note_id(url):
        match = re.search(r'/notes/([^/?]+)', url)
        if match:
            return match.group(1)
        return None

    payload = {
        "noteId":f"{extract_note_id(result_input["URL"])}"
    }

    headers = get_headers("misskey.io")
    async with AsyncSession() as session:
        response = await session.post(url=misskey_api_endpoint, json=payload, headers=headers)
        data = response.json()

    expression = jmespath.compile('{media: files[*].url, misskey_text: text, author: user.name || user.username}')
    extracted_data = expression.search(data)

    media_urls_list = extracted_data.get('media', [])
    media_urls_list = [
        url.replace('?sensitive=true', '') if '?sensitive=true' in url else url
        for url in media_urls_list
    ]

    import util.downloadFile

    media_urls_list = await util.downloadFile.main(media_urls_list)

    text_str = extracted_data.get('misskey_text', '')
    user_name_str = extracted_data.get('author', '')
    return {
        "media": media_urls_list,
        "misskey_text": text_str,
        "author": user_name_str
    },media_urls_list

if __name__ == "__main__":
    #for test
    result = {
        "URL": "https://misskey.io/notes/abso1pwwxkwv05os",
        "SP_detector": True,
        "Author_name": "Text",
        "Page_index": "1"
    }
    result = asyncio.run(api_response(result))
    print(result)
