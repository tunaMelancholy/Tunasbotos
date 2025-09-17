# -*- coding: utf-8 -*-

import re
import json
import httpx
import html as html_mod
from typing import Tuple, List, Dict, Optional

async def extract_post_id(url: str) -> str:
    m = re.search(r"plurk\.com/p/(\w+)", url)
    if not m:
        raise ValueError(f"无法从URL中解析 PostID: {url}")
    return m.group(1)

async def fetch_post_html(client: httpx.AsyncClient, post_id: str) -> str:
    url = f"https://www.plurk.com/p/{post_id}"
    r = await client.get(url)
    r.raise_for_status()
    return r.text

def _fix_js_dates(text: str) -> str:
    return re.sub(r"new Date\(([^)]+)\)", r"\1", text)

def try_parse_json_block(html: str, varname: str) -> Optional[dict]:

    pat = rf"{re.escape(varname)}\s*=\s*(\{{.*?\}})\s*;"
    m = re.search(pat, html, re.S)
    if not m:
        return None
    try:
        text = _fix_js_dates(m.group(1))
        return json.loads(text)
    except Exception:
        return None

def extract_author_from_html(html: str) -> Optional[str]:

    m = re.search(r'<a[^>]+class=["\']name["\'][^>]*>([^<]+)</a>', html, re.S | re.I)
    if m:
        return html_mod.unescape(m.group(1).strip())

    patterns = [
        r'<a[^>]+class=["\']user_name["\'][^>]*>([^<]+)</a>',
        r'<a[^>]+class=["\']nickname["\'][^>]*>([^<]+)</a>',
        r'<meta\s+name=["\']author["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
    ]
    for p in patterns:
        m = re.search(p, html, re.S | re.I)
        if m:
            name = m.group(1).strip()
            if ' - ' in name and 'plurk' in name.lower():
                name = name.split(' - ')[0].strip()
            return html_mod.unescape(name)

    return None

def extract_image_urls_from_meta(plurk_data: dict, html: str) -> List[str]:

    found: List[str] = []

    for key in ("content", "content_raw"):
        v = plurk_data.get(key)
        if isinstance(v, str):
            found += re.findall(r"https?://images\.plurk\.com/[^\s\"'>]+", v)

    if not found:
        found += re.findall(r"https?://images\.plurk\.com/[^\s\"'>]+", html)

    prefixes = ("mx_", "small_", "medium_", "thumb_", "s_", "t_")

    def normalize(url: str) -> str:
        base, sep, filename = url.rpartition('/')
        for p in prefixes:
            if filename.startswith(p):
                return base + '/' + filename[len(p):]
        return url

    seen = set()
    result: List[str] = []
    for url in found:
        canon = normalize(url)
        if canon not in seen:
            seen.add(canon)
            result.append(canon)

    return result

async def extract_plurk_images_and_meta(url: str) -> Tuple[List[str], Dict[str, Optional[str]]]:

    async with httpx.AsyncClient(http2=True, headers={
        "User-Agent": "Mozilla/5.0 (compatible)",
        "Referer": "https://www.plurk.com"
    }) as client:
        post_id = await extract_post_id(url)
        html = await fetch_post_html(client, post_id)

    plurk_json = try_parse_json_block(html, "plurk") or {}
    global_json = try_parse_json_block(html, "GLOBAL")
    if global_json:
        page_user = global_json.get("page_user") or global_json.get("user")
        if page_user:
            plurk_json.setdefault("user", page_user)

    content = plurk_json.get("content_raw") or plurk_json.get("content") or None

    author = None
    user_block = plurk_json.get("user") or {}
    if isinstance(user_block, dict):
        for k in ("display_name", "nickname", "full_name", "nick", "name"):
            if k in user_block and user_block[k]:
                author = str(user_block[k])
                break

    if not author:
        author = extract_author_from_html(html)

    image_urls = extract_image_urls_from_meta(plurk_json, html)

    meta = {"content": content, "author": author}
    return image_urls, meta


async def execute(url):
    images, meta = await extract_plurk_images_and_meta(url)
    return images, meta

# if __name__ == "__main__":
#     #for test
#     result = asyncio.run(execute("https://www.plurk.com/p/3hkq35mrqc"))