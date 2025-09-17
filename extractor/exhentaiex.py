# -*- coding: utf-8 -*-
import asyncio
import random
import re
import shutil
import string
import traceback
from datetime import datetime

import httpx
import logging
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, Tuple

import config

COOKIE = config.exhentai_config.get('cookie', '')
MAX_CONCURRENT_REQUESTS = config.exhentai_config.get('threads', 10)
RETRY_COUNT = config.exhentai_config.get('retru_count', 3)
RETRY_WAIT_SECONDS = config.exhentai_config.get('delay_time', 5)
API_URL = config.e_hentai_endpoint
EX_API_URL = config.exhentai_endpoint

def get_logger(level):
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)


logger = get_logger(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

HEADERS = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://e-hentai.org",
}

SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def _parse_url(gallery_url: str) -> Optional[Tuple[int, str, str]]:
    is_ex = "exhentai.org" in gallery_url
    api_url = EX_API_URL if is_ex else API_URL

    match = re.search(r"/g/(\d+)/([\da-f]{10})", gallery_url)
    if not match:
        logger.error("Failed to parse gallery URL. Check the URL format.")
        return None

    gid = int(match.group(1))
    token = match.group(2)
    return gid, token, api_url


def _parse_page_index(page_index_str: Optional[str]) -> None | dict[str, str] | tuple[int, int]:
    if not page_index_str:
        return None

    match = re.match(r"(\d+)-(\d+)", page_index_str)
    if not match:
        logger.warning(f"Invalid page_index format: '{page_index_str}'. Should be 'start-end'.")
        return {'error':f"Invalid page_index format: '{page_index_str}'. Should be '!start-end \n索引范围出错 !格式 start-end"}

    start_page, end_page = int(match.group(1)), int(match.group(2))

    if start_page <= 0:
        logger.warning("Start page must be greater than 0.")
        return {'error':"Start page must be greater than 0.\n起始页不能小于1"}

    if start_page > end_page:
        logger.warning(f"Invalid page range: start page {start_page} is greater than end page {end_page}")
        return {'error':f"Invalid page range: start page {start_page} is greater than end page {end_page} \n起始页应该比结束页数值小"}

    if (end_page - start_page + 1) > 150:
        logger.warning(f"Page range span exceeds the maximum of 150. Please use a smaller range.")
        return {'error':f"Page range span exceeds the maximum of 150. Please use a smaller range. \n索引范围不能超过150页"}

    return start_page, end_page


async def _fetch_single_image_api(
        client: httpx.AsyncClient,
        api_url: str,
        payload: Dict[str, Any]
) -> Optional[str]:
    page_num = payload.get("page", "N/A")

    for attempt in range(RETRY_COUNT):
        try:
            async with SEMAPHORE:
                sp_response = await client.post(api_url, json=payload, timeout=40.0)
                sp_response.raise_for_status()
                sp_data = sp_response.json()

                if "error" in sp_data:
                    logger.warning(f"Page {page_num} API ERROR: {sp_data['error']}")
                    return "pageError"

                img_tag_html = sp_data.get("i3", "")
                img_soup = BeautifulSoup(img_tag_html, "lxml")
                img_tag = img_soup.find("img")

                if img_tag and img_tag.has_attr("src"):
                    return img_tag["src"]
                else:
                    logger.warning(f"Could not find image source for page {page_num}.")
                    return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait_time = RETRY_WAIT_SECONDS * (2 ** attempt)
                logger.warning(f"Rate limited on page {page_num}. Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.warning(f"Page {page_num} API HTTP Error: {e.response.status_code}")
                await asyncio.sleep(RETRY_WAIT_SECONDS)
        except Exception as e:
            logger.error(f"An unexpected error occurred for page {page_num}: {e}")
            logger.debug(f"{type(e)}\nAPI ERROR:\n{traceback.format_exc()}")
            await asyncio.sleep(RETRY_WAIT_SECONDS)

    logger.error(f"Page {page_num} failed to fetch after {RETRY_COUNT} attempts.")
    return None


async def fetch_gallery_info_api(gallery_url: str, page_index: Optional[str] = None) -> Optional[Dict[str, Any]]:

    parsed_url = _parse_url(gallery_url)
    if not parsed_url:
        return {"error": "metaNotfound"}
    gid, token, api_url = parsed_url

    page_range = _parse_page_index(page_index)
    if type(page_range) == dict:
        raise ValueError(page_range['error'])
    start_page, end_page = page_range if page_range else (None, None)

    base_domain = "https://exhentai.org" if "exhentai" in gallery_url else "https://e-hentai.org"
    web_headers = {
        **HEADERS,
        "Accept": "text/html,application/xhtml+xml",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    async with httpx.AsyncClient(headers=HEADERS, timeout=60.0) as client:
        logger.info("Job Started! Fetching metadata...")
        gdata_payload = {"method": "gdata", "gidlist": [[gid, token]], "namespace": 1}
        try:
            gdata_response = await client.post(api_url, json=gdata_payload)
            gdata_response.raise_for_status()
            gdata = gdata_response.json()
            metadata_raw = gdata["gmetadata"][0]
        except Exception as e:
            logger.error("Failed to fetch metadata. Check cookies or network settings.")
            logger.debug(f"{type(e)}\nMetadata Error:\n{traceback.format_exc()}")
            return {"error": "metaError"}

        metadata = {
            "gallery_url": gallery_url,
            "gid": metadata_raw.get("gid"),
            "title": metadata_raw.get("title"),
            "image_count": int(metadata_raw.get("filecount", 0)),
        }

        if metadata["image_count"] == 0:
            logger.info("Gallery has 0 images.")
            return metadata

        if not page_index and metadata["image_count"] > 150:
            logger.warning(f"Gallery has {metadata['image_count']} images, which is more than 150.")
            logger.warning("Please specify a page_index (e.g., '1-150') to scrape in batches.")
            metadata["error"] = "galleryTooLarge 画廊太长，请指定页码范围\n例如：https://exhentai.org/..../ !1-150"
            return metadata

        if page_range and end_page > metadata["image_count"]:
            logger.warning(
                f"Requested end page ({end_page}) is greater than total image count ({metadata['image_count']}). Adjusting to max.")
            end_page = metadata['image_count']

        logger.info("Fetching all imgkey and showkey...")
        first_page_html_response = await client.get(gallery_url, headers=web_headers)
        first_page_html = first_page_html_response.text

        imgkeys_map = {}

        def parse_keys_from_html(html_text):
            matches = re.finditer(r"/s/([\da-f]+)/" + str(gid) + r"-(\d+)", html_text)
            for match in matches:
                imgkey, page_num_str = match.groups()
                imgkeys_map[int(page_num_str)] = imgkey

        parse_keys_from_html(first_page_html)

        page_tags = BeautifulSoup(first_page_html, 'lxml').select('.ptb td a')
        if len(page_tags) > 1:
            try:
                last_page_num = int(page_tags[-2].text)
                page_urls_to_fetch = [f"{gallery_url}?p={i}" for i in range(1, last_page_num)]
                tasks = [client.get(url, headers=web_headers) for url in page_urls_to_fetch]
                responses = await asyncio.gather(*tasks)
                for res in responses:
                    parse_keys_from_html(res.text)
            except (IndexError, ValueError):
                logger.warning("Could not parse all page numbers for imgkeys.")

        if len(imgkeys_map) != metadata["image_count"]:
            logger.warning(
                f"Key mismatch: Found {len(imgkeys_map)} imgkeys, but metadata reports {metadata['image_count']} images.")

        first_imgkey = imgkeys_map.get(1)
        if not first_imgkey:
            logger.error("Could not find the imgkey for the first page.")
            return {"error": "imgkeyError"}

        viewer_page_url = f"{base_domain}/s/{first_imgkey}/{gid}-1"
        viewer_html = (await client.get(viewer_page_url, headers=web_headers)).text
        showkey_match = re.search(r"showkey\s*=\s*['\"]([\w-]+)['\"]", viewer_html)
        if not showkey_match:
            logger.error("Failed to extract showkey.")
            return {"error": "showkeyError"}
        showkey = showkey_match.group(1)

        logger.info(f"Successfully fetched showkey. Found {len(imgkeys_map)} total imgkeys.")

        target_imgkeys = {}
        if page_range:
            logger.info(f"Scraping specified range: Pages {start_page} to {end_page}.")
            for page_num, imgkey in imgkeys_map.items():
                if start_page <= page_num <= end_page:
                    target_imgkeys[page_num] = imgkey
        else:
            logger.info(f"Scraping all {metadata['image_count']} pages.")
            target_imgkeys = imgkeys_map

        if not target_imgkeys:
            logger.warning("No images found in the specified page range.")
            metadata["image_links"] = []
            return metadata

        logger.info(
            f"Requesting {len(target_imgkeys)} image links with {MAX_CONCURRENT_REQUESTS} concurrent connections.")

        api_tasks = []
        for page_num, imgkey in sorted(target_imgkeys.items()):
            payload = {"method": "showpage", "gid": gid, "page": page_num, "imgkey": imgkey, "showkey": showkey}
            api_tasks.append(_fetch_single_image_api(client, api_url, payload))

        image_links_results = await asyncio.gather(*api_tasks)
        metadata["image_links"] = [link for link in image_links_results if link and link not in ["pageError"]]

        logger.info(f"All jobs finished. Successfully fetched {len(metadata['image_links'])} links.")
        return metadata


async def execute(request_data: Dict[str, str], error_code="None"):
    gallery_url = request_data.get("URL")
    page_index = request_data.get("page_index")

    if not gallery_url:
        print("Error: 'URL' key not found in the input dictionary.\nURL缺失")
        return None,{"error": "URL missing"}
    try:
        gallery_data = await fetch_gallery_info_api(gallery_url, page_index)
    except ValueError as e:
        return None,{"error": e}
    if gallery_data and "error" not in gallery_data:

        link_list = []
        ori_link = []
        for i, img_link in enumerate(gallery_data.get('image_links', [])):
            print(f"  Image {i + 1}: {img_link}")
            link_list.append("https://image.tunacholy.vip/?url="+img_link)
            ori_link.append(img_link)

        try:
            import util.downloadFile
            import util.webpConverter
            import util.uploadImageToR2
            def generate_random_folder(length=7):

                date_part = datetime.now().strftime('%y%m%d%H')
                random_part = ''.join(random.choice(string.ascii_letters) for _ in range(length))
                return f"{date_part}{random_part}"

            target_dir_name = generate_random_folder()
            target_path = "downloads/"+target_dir_name

            file_list = await util.webpConverter.convert_folder_to_webp(target_path)

            final_list = []
            if file_list:
                final_list = file_list
            else:
                file_download_list = await util.downloadFile.main(ori_link, download_path=target_path, exh_trigger=True)
                final_list = file_download_list

            logger.info(f"File List{file_list}")

            if final_list and gallery_data['image_count'] < 80:
                remote_url = await util.uploadImageToR2.main(final_list,f'{target_path}/')
                logger.info(f"Remote URL: {remote_url}")
                shutil.rmtree(target_path)
                return remote_url, gallery_data
            else:
                logger.info("No files to upload.")
                logger.info(f"File List: {link_list}")
                return link_list, gallery_data

        except Exception as e:
            logger.warning(f"Error processing image link: {e},\n {type(e)}")

        return link_list, gallery_data
    else:
        link_list = None
        error_code = gallery_data.get('error', 'UnknownError') if gallery_data else 'FetchError'
        print(f"\nFailed to process {gallery_url}. Reason: {error_code}\n")
        return link_list,{"error": error_code}

if __name__ == "__main__":

    request_data = {
        "URL":"https://exhentai.org/g/3501920/6a6bdd9e1b/",
        "page_index": "1-100"
    }

    asyncio.run(execute(request_data))
