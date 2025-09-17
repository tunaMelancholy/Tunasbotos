# for Windows
import os
import ofDownload
import curl_cffi
import jmespath
import config
import getpostinfo
proxies = {
    "http": "http://127.0.0.1:10808",
    "https": "http://127.0.0.1:10808",
}

def api_response(userId:str):
    base_url = f'https://api.fanbox.cc/post.paginateCreator?creatorId={userId}&sort=newest'

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/135.0",
        "Cookie": f"FANBOXSESSID={config.FANBOX_CONFIG['account2']}",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.fanbox.cc",
    }

    response = curl_cffi.get(base_url,proxies=proxies,headers=headers,impersonate='firefox135')
    json_data = response.json()

    return json_data


if __name__ == "__main__":
    import asyncio
    userId = 'freehoney'
    data = api_response(userId)
    page_list = jmespath.search('body[*]', data)

    post_ids, titles = getpostinfo.execute(page_list,'2025-06-29')

    os.makedirs(f"downloads/{userId}", exist_ok=True)

    for i in range(len(post_ids)):
        asyncio.run(ofDownload.execute(config.FANBOX_CONFIG['account1'],post_ids[i],f"downloads/{userId}/{titles[i]}"))