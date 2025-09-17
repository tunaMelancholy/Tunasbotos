# -*- coding: utf-8 -*-
import asyncio
import json
import jmespath
from httpx import AsyncClient

async def get_twitter_data(result_input: dict):
    try:
        async with AsyncClient(http2=True) as session:
            response = await session.get(result_input["URL"])
            data = response.json()
        # print( data)
        return data
    except json.JSONDecodeError:
        return None

async def api_response(result_input: dict):

    fixed_url = result_input["URL"].split('?')[0]
    source_url = fixed_url
    # print('Source:',source_url)

    def replace_x_com(input_url, api_url='api.vxtwitter.com'):
        if 'api.vxtwitter.com' in input_url:
            input_url = input_url.replace('api.vxtwitter.com', 'x.com')
        elif 'api.fxtwitter.com' in input_url:
            input_url = input_url.replace('api.fxtwitter.com', 'x.com')

        if 'x.com' in input_url.lower():
            return input_url.replace('x.com', api_url).replace('X.com', api_url)
        elif 'twitter.com' in input_url.lower():
            return input_url.replace('twitter.com', api_url).replace('Twitter.com', api_url)
        return input_url

    fixed_url = replace_x_com(source_url, 'api.vxtwitter.com')
    result_input["URL"] = fixed_url
    # print('Pre:',fixed_url)

    data = await get_twitter_data(result_input)

    if data is None:
        # print("Change to fx")
        fixed_url = replace_x_com(source_url, 'api.fxtwitter.com')
        result_input["URL"] = fixed_url
        # print('Aft',fixed_url)
        data = await get_twitter_data(result_input)

    if 'api.vxtwitter.com' in fixed_url:
        expression = jmespath.compile('{media: mediaURLs, tweet_text: text, author: user_name}')
        extracted_data = expression.search(data)

        media_urls_list = extracted_data.get('media', [])
        text_str = extracted_data.get('tweet_text', '')
        user_name_str = extracted_data.get('author', '')
        return {
            "media": media_urls_list,
            "tweet_text": text_str,
            "author": user_name_str
        }
    if 'api.fxtwitter.com' in fixed_url:
        media_urls_list = []
        if data.get('tweet', {}).get('media', {}).get('all'):
            for media_item in data['tweet']['media']['all']:
                media_urls_list.append(media_item['url'])
        text_str = data.get('tweet', {}).get('text', '')

        user_name_str = data.get('tweet', {}).get('author', {}).get('name', '')

        return {
            "media": media_urls_list,
            "tweet_text": text_str,
            "author": user_name_str
        }


    return None

if __name__ == "__main__":
    result = {
        "URL": "https://x.com/cjdcjd616/status/1966316533409312913",
        "SP_detector": True,
        "Author_name": "Text",
        "Page_index": "1"
    }
    data = asyncio.run(api_response(result))
    # print( data)