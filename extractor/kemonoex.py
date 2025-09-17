# -*- coding: utf-8 -*-
import asyncio
import jmespath
from curl_cffi import AsyncSession

async def api_response(result_input: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/135.0",
        "Content-Type": "application/json;text/css; charset=utf-8",
        "Accept": "text/css",
        "Referer": "https://fanbox.cc/",
        "Origin": "https://fanbox.cc"
    }
    async with AsyncSession() as session:
        response = await session.get(result_input, headers=headers)
        data = response.json()
    expression = """
                            {
                                "banner": post.file.path,
                                "url": post.attachments[*].path,
                                "content": post.content,
                                "title": post.title
                            }
                            """
    result = jmespath.search(expression, data)
    return result

async def execute(url : str) -> dict:
    """
    :param url: the kemono post link
    :type url: dict
    :return: Example : {"banner": str, "url": list, "content": str,"title": str}
    :rtype: dict
    """

    data = await api_response(url)

    if data.get('banner'):
        data['banner'] = "https://kemono.cr" + data['banner']

    if data.get('url'):
        data['url'] = ["https://kemono.cr" + path for path in data['url']]

    return data

if __name__ == "__main__":
    URL = "https://kemono.cr/api/v1/fanbox/user/24838/post/10195827"
    data = asyncio.run(execute(URL))
    print( data)

