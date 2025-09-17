# -*- coding: utf-8 -*-
import asyncio
import jmespath
from curl_cffi.requests import AsyncSession
import config

proxies = config.fanbox_proxies
# proxies = {
#             "http": "http://127.0.0.1:10808",
#             "https": "http://127.0.0.1:10808"
#         }
async def fanbox_api_reponse(session: AsyncSession, post_id: str = None, account_cookies: str = None,user_id: str = None):
    base_url = f'https://api.fanbox.cc/post.info?postId={post_id}'
    if user_id is not None and post_id is None:
        base_url = f'https://api.fanbox.cc/creator.get?creatorId={user_id}'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/135.0",
        "Cookie": f"FANBOXSESSID={account_cookies}",
        "Content-Type": "application/json",
        "Referer": "https://fanbox.cc/",
        "Origin": "https://fanbox.cc"
    }

    response = await session.get(headers=headers, url=base_url, impersonate="firefox135",timeout=6.0)
    data = response.json()
    return data, response.status_code

async def kemono_api_reponse(session: AsyncSession, user_id: str, post_id: str = None):
    base_url = f"https://kemono.cr/api/v1/fanbox/user/{user_id}/post/{post_id}"
    if post_id is None and user_id is not None:
        base_url = f"https://kemono.cr/api/v1/fanbox/user/{user_id}/profile"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/135.0",
        "Content-Type": "application/json;text/css; charset=utf-8",
        "Accept": "text/css",
        "Referer": "https://fanbox.cc/",
        "Origin": "https://fanbox.cc"
    }

    response = await session.get(url=base_url,headers=headers)
    data = response.json()
    # print(data)
    return data, response.status_code


async def get_homepage(account_cookies,homepage):
    async with AsyncSession() as session:
        raw_data, fanbox_status_code = await fanbox_api_reponse(session,account_cookies=account_cookies,user_id=homepage)

        if fanbox_status_code != 200 or "body" not in raw_data:
            print(f"Error fetching from Fanbox. Status: {fanbox_status_code}, Response: {raw_data}")
            return

        user_id = jmespath.search("body.user.userId", raw_data)
        kemono_response, kemono_status_code = await kemono_api_reponse(session, user_id)

        if kemono_status_code != 200 or jmespath.search("error", kemono_response):
            return
        else:
            kemono_url = f"https://kemono.cr/fanbox/user/{user_id}"
            return kemono_url

async def execute(post_id: str = None, account_cookies: str =None,homepage : str = None):
    if homepage is not None:
        kemono_url = await get_homepage(account_cookies,homepage)
        return  kemono_url
    async with AsyncSession() as session:
        raw_data, fanbox_status_code = await fanbox_api_reponse(session, post_id, account_cookies)

        if fanbox_status_code != 200 or "body" not in raw_data:
            print(f"Error fetching from Fanbox. Status: {fanbox_status_code}, Response: {raw_data}")
            return "error"

        post_id_from_api = jmespath.search("body.id", raw_data)
        user_id = jmespath.search("body.user.userId", raw_data)

        if not post_id_from_api or not user_id:
            print(f"Error: Could not find post_id or user_id in Fanbox response. Data: {raw_data}")
            return "error"

        kemono_response, kemono_status_code = await kemono_api_reponse(session, user_id, post_id_from_api)

        if kemono_status_code != 200:
            print(f"Error fetching from Kemono. Status: {kemono_status_code}")
            return "error"

        if jmespath.search("error", kemono_response):
            print(f"Kemono API returned an error: {kemono_response['error']}")
            return "error"
        else:
            kemono_url = f"https://kemono.cr/fanbox/user/{user_id}/post/{post_id_from_api}"
            return kemono_url



if __name__ == "__main__":

   url = asyncio.run(execute(account_cookies= config.FANBOX_CONFIG['account1'],homepage='urabesan'))
   print(url)

