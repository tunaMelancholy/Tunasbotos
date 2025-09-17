
# for Windows
import re

import curl_cffi
import jmespath
import config
proxies = {
    "http": "http://127.0.0.1:10808",
    "https": "http://127.0.0.1:10808",
}

def api_response(inputUrl,target_date):

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/135.0",
        "Cookie": f"FANBOXSESSID={config.FANBOX_CONFIG['account2']}",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.fanbox.cc",
    }

    respose = curl_cffi.get(inputUrl,proxies=proxies,headers=headers,impersonate='firefox135')

    json_data = respose.json()
    # post_id = jmespath.search('body[*].id', json_data)
    # publishedDatetime = jmespath.search(f'body[{len(post_id)-1}].publishedDatetime', json_data)
    # print(json_data)
    def clean_title_for_windows(title):
        cleaned = re.sub(r'[\\/*?:"<>|]', '', title).strip()
        cleaned = cleaned.rstrip('.')
        return cleaned
    def filter_posts_by_date(data, cutoff_date):
        query = "body[].[id, title, publishedDatetime]"
        all_posts = jmespath.search(query, data)

        post_ids_list = []
        formatted_titles_list = []

        if not all_posts:
            return post_ids_list, formatted_titles_list

        for post_id, title, pub_datetime in all_posts:
            post_date = pub_datetime[:10]

            if cutoff_date <= post_date:
                post_ids_list.append(post_id)

                if title:
                    cleaned_title = clean_title_for_windows(title)
                    formatted_title = f"{post_date}-{cleaned_title}"
                else:
                    formatted_title = f"{post_date}-None"
                formatted_titles_list.append(formatted_title)

        return post_ids_list, formatted_titles_list
    post_ids, formatted_titles = filter_posts_by_date(json_data, target_date)
    return post_ids,formatted_titles

def execute(link_list:list,target_date):
    post_id = []
    title_list = []
    for i in range(len(link_list)):
        ids,titles=api_response(link_list[i],target_date)
        post_id.extend(ids)
        title_list.extend(titles)
    print(post_id,title_list)
    print(f"找到 {len(post_id)} 个帖子")
    return post_id,title_list
