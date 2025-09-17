import asyncio
import httpx
import re
import json
import os
from typing import Tuple, Dict, List
from PIL import Image
from io import BytesIO

BASE_DOMAIN = "gold-usergeneratedcontent.net"
ROOT_REFERER = "https://hitomi.la/"


def parse_gg(js_text: str) -> Tuple[Dict[int, int], str, int]:
    m = {}
    keys = []
    for match in re.finditer(r"case\s+(\d+):(?:\s*o\s*=\s*(\d+))?", js_text):
        key_s, value_s = match.groups()
        keys.append(int(key_s))
        if value_s:
            v = int(value_s)
            for k in keys:
                m[k] = v
            keys.clear()

    for match in re.finditer(r"if\s+\(g\s*===?\s*(\d+)\)[\s{]*o\s*=\s*(\d+)", js_text):
        gval = int(match.group(1))
        oval = int(match.group(2))
        m[gval] = oval

    d_match = re.search(r"(?:var\s+|default:)\s*o\s*=\s*(\d+)", js_text)
    default = int(d_match.group(1)) if d_match else 0

    b_match = re.search(r"b:\s*['\"]([^'\"]+)['\"]", js_text)
    b = b_match.group(1).strip("/") if b_match else ""

    return m, b, default


def make_img_url(ihash: str, ext: str, m_map: Dict[int, int], b: str, default: int) -> str:
    inum_hex = ihash[-1] + ihash[-3:-1]
    inum = int(inum_hex, 16)
    sub_index = m_map.get(inum, default) + 1
    sub = f"{ext[0]}{sub_index}"
    return f"https://{sub}.{BASE_DOMAIN}/{b}/{inum}/{ihash}.{ext}"


async def write_webp(path: str, content: bytes):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with Image.open(BytesIO(content)) as img:
        img.save(path, format="WEBP", quality=90)


async def download_with_retries(client, url, path, headers, retries=3, backoff=1.0):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(url, headers=headers, follow_redirects=True, timeout=30.0)
            if resp.status_code == 200:
                await write_webp(path, resp.content)
                print(f"[OK] {os.path.basename(path)}")
                return path
            else:
                last_exc = f"status {resp.status_code}"
        except Exception as e:
            last_exc = e
            print(f"[ERR] attempt {attempt} download {url} -> {e}")
        await asyncio.sleep(backoff * attempt)
    print(f"[FAIL] {url} -> {last_exc}")
    return None


async def download_gallery(gid: str, out_dir="hitomi_downloads", concurrency=12, retries=3) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": ROOT_REFERER.rstrip("/"),
        "Referer": f"{ROOT_REFERER}reader/{gid}.html"
    }

    local_file_list: List[str] = []

    async with httpx.AsyncClient(http2=True, headers=headers, timeout=30.0) as client:
        gallery_url = f"https://ltn.{BASE_DOMAIN}/galleries/{gid}.js"
        r = await client.get(gallery_url)
        r.raise_for_status()
        m = re.search(r"(?s)\{.*\}", r.text)
        gallery_json = json.loads(m.group(0))
        files = gallery_json.get("files", [])

        r2 = await client.get(f"https://ltn.{BASE_DOMAIN}/gg.js")
        r2.raise_for_status()
        m_map, b, default = parse_gg(r2.text)

        sem = asyncio.Semaphore(concurrency)
        tasks = []
        for idx, f in enumerate(files, start=1):
            ext = "avif" if f.get("hasavif") else f.get("extension") or "jpg"
            ihash = f.get("hash")
            if not ihash:
                continue
            url = make_img_url(ihash, ext, m_map, b, default)
            filename = os.path.join(out_dir, f"{gid}_{idx:03d}.webp")
            img_headers = {
                "User-Agent": headers["User-Agent"],
                "Referer": headers["Referer"],
                "Origin": headers["Origin"],
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            }

            async def task(u=url, fn=filename, h=img_headers):
                async with sem:
                    result = await download_with_retries(client, u, fn, h, retries=retries)
                    if result:
                        local_file_list.append(result)

            tasks.append(task())

        print(f"[*] Starting {len(tasks)} downloads...")
        await asyncio.gather(*tasks)
        print("[*] Done.")

    return local_file_list

async def execute(gid:str):
    files_list = await download_gallery(gid, out_dir="./downloads", concurrency=5, retries=5)
    return files_list
