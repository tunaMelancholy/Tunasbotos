# -*- coding: utf-8 -*-
import jmespath
from curl_cffi import AsyncSession
from extractor.getHeaders import get_headers

async def api_response(result_input: dict):
    """
    :param result_input: a dict type param which include ["URL"]
    :type result_input: dict
    :return: Example : {"url": str, "source": str, "id": str}
    :rtype: dict
    """
    headers = get_headers("gelbooru.com")
    async with AsyncSession() as session:
        response = await session.get(result_input["URL"], headers=headers)
        data = response.json()
    expression = """
                            post[*].{
                                "url": (@.sample_url || @.file_url),
                                "source": source,
                                "id": id
                            }
                            """
    result = jmespath.search(expression, data)
    print(result)
    return result
