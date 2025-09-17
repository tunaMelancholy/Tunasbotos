# -*- coding: utf-8 -*-
import jmespath

from curl_cffi import AsyncSession
from extractor.getHeaders import get_headers

async def api_response(result_input: dict):
    headers = get_headers("yande.re")
    async with AsyncSession() as session:
        response = await session.get(result_input["URL"], headers=headers)
        data = response.json()
    expression = """
                            [*].{
                                "url": (@.sample_url || @.file_url),
                                "source": source,
                                "id": id
                            }
                            """
    result = jmespath.search(expression, data)

    return result
#
# if __name__ == "__main__":
    # import asyncio
    # result = {
    #     "URL":"https://yande.re/post.json?tags=id:1236828"
    # }
    # result = asyncio.run(api_response(result))
    # print(result)