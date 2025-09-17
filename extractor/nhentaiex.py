# -*- coding: utf-8 -*-
import re

from httpx import AsyncClient
import jmespath

import config
from extractor.getHeaders import get_headers


async def api_response(result_input: dict):

    match = re.search(r'https?://nhentai\.net/g/(\d+)', result_input['URL'])

    result_input["URL"] = config.nhnetai_endpoint + match.group(1)
    headers = get_headers("https://nhentai.net")
    async with AsyncClient() as session:
        response = await session.get(result_input["URL"], headers=headers)
        data = response.json()
    expression = "{media_id : media_id,title: title.japanese, num_pages : num_pages,format : images.pages[0].t }"
    result = jmespath.search(expression, data)
    return result

async def get_links(result_dict:dict) -> list:

    _pages = result_dict["num_pages"]
    _format = ".jpg" if result_dict["format"]=="j" else ".webp"
    _media_id = result_dict["media_id"]
    def generate_radom_cdn():
        import random
        cdn_list = [
            "https://i1.nhentai.net/galleries/",
            "https://i2.nhentai.net/galleries/",
            "https://i4.nhentai.net/galleries/",
            "https://i9.nhentai.net/galleries/"
        ]
        return random.choice(cdn_list)
    link_list = []
    for i in range(1,int(_pages)+1):
        link_list.append(generate_radom_cdn()+_media_id+"/"+str(i)+_format)

    return link_list

async def execute(reslut:dict) -> tuple[dict, list]:
    _meta = await api_response(reslut)
    urls = await get_links(_meta)
    return _meta, urls

if __name__ == "__main__":
    import asyncio
    result = {
        "URL": "https://nhentai.net/g/596932/",
        "SP_detector": True,
        "Author_name": "Text",
        "Page_index": "1"
    }
    asyncio.run(execute(result))