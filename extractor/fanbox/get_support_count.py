# -*- coding: utf-8 -*-

import traceback
import jmespath
import httpx
from curl_cffi.requests import AsyncSession as CurlAsyncSession
from datetime import datetime
import config
async def async_api_response(session: CurlAsyncSession, account_cookie: str):

    fanbox_url = f'https://api.fanbox.cc/plan.listSupporting'
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
        print(f"Failed to get API response for account {account_cookie}:\n{traceback.format_exc()}")
        return None

async def get_cound_and_fee(json_data):
    try:
        count_expression = "length(body)"
        item_count = jmespath.search(count_expression, json_data)

        sum_expression = "sum(body[].fee)"
        fee_total = jmespath.search(sum_expression, json_data)

        return item_count, fee_total
    except Exception as e:
        print(f"Error: {e}")
        return None, None

async def get_all_account():
    count_list = []
    fee_list = []
    try:
        for i in list(config.FANBOX_CONFIG.values()):
            account_cookie = i
            async with CurlAsyncSession() as curl_session, httpx.AsyncClient(http2=True, follow_redirects=True) as http_client:
                json_data = await async_api_response(curl_session, account_cookie)
                if not json_data:
                    print("API错误，请检查配置")
                    return None, [], None, None
                fanbox_count , fanbox_fee = await  get_cound_and_fee(json_data)
                count_list.append(fanbox_count)
                fee_list.append(fanbox_fee)

    except Exception as e:
        print(f"Error: {e}")

    total_count = sum(count_list)
    total_fee = sum(fee_list)
    text = f"当前月份 <strong>{datetime.now().strftime('%Y-%m')}</strong> 总计赞助创作者数量: <strong>{total_count}</strong> , 总计金额: <strong>{total_fee:,}</strong> JPY\n"
    detail_text = "详细信息:\n"
    ct = 0
    for key in config.FANBOX_CONFIG:
        detail_text = detail_text + f"账户 {key} : 赞助创作者 <strong>{count_list[ct]}</strong> 个 | 消费金额 </strong>{fee_list[ct]:,}</strong> JPY\n"
        ct += 1
    return text ,detail_text

if __name__ == "__main__":
    import asyncio
    text ,detail_text = asyncio.run(get_all_account())
    print(text,detail_text)

