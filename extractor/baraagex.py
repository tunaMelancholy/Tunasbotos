# -*- coding: utf-8 -*-
# import asyncio
import jmespath
import re
from curl_cffi import AsyncSession

import config
from extractor.getHeaders import get_headers

async def api_response(result_input: dict):
    """
    :param result_input: a dict type param which include ["URL"]
    :type result_input: dict
    :return: Example : {"media_url": str, "author": str, "text": str}
    :rtype: dict
    """
    match = re.search(r'/(\d+)(?:/|/?\?|$)', result_input["URL"])

    result_input["URL"] = config.baraag_endpoint + match.group(1)
    headers = get_headers("https://baraag.net")
    async with AsyncSession() as session:
        response = await session.get(result_input["URL"], headers=headers)
        data = response.json()
    expression = "{media : media_attachments[*].url,author: account.display_name, text : content }"
    result = jmespath.search(expression, data)
    print(result)
    return result

if __name__ == "__main__":
    import asyncio
    result = {
        "URL": "https://baraag.net/@kurohi_drw/114904644838964306",
        "SP_detector": True,
        "Author_name": "Text",
        "Page_index": "1"
    }
    asyncio.run(api_response(result))