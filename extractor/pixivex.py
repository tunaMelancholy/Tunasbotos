# -*- coding: utf-8 -*-
import asyncio
import os
from typing import List
from pixivpy_async import AppPixivAPI
from PIL import Image
import config

def format_webp_to_jpg(image_paths: List[str]) -> List[str]:
    final_paths = []
    paths_to_delete = []

    for original_path in image_paths:
        try:
            with Image.open(original_path) as img:
                if img.format == 'WEBP':
                    new_path = os.path.splitext(original_path)[0] + '.jpg'
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    img.save(new_path, 'jpeg', quality=95)

                    final_paths.append(new_path)
                    paths_to_delete.append(original_path)
                else:
                    final_paths.append(original_path)
        except Exception as e:
            print(e)
            final_paths.append(original_path)

    for path in paths_to_delete:
        try:
            os.remove(path)
        except Exception as e:
            print(e)

    return final_paths


async def download_illust_large(
        api: AppPixivAPI,
        illust_id: int,
        save_path: str = './downloads/pixiv'
):
    os.makedirs(save_path, exist_ok=True)

    json_result = await api.illust_detail(illust_id)
    if json_result.error:
        print(f"failed to get {illust_id} ERROR: {json_result.error}")
        return []

    illust = json_result.illust
    #Debug
    page_count = illust.page_count
    tags = []
    for i in range(len(illust.tags)):
        tags.append(illust.tags[i]['name'])
    info_dict = {
        "illust_id": illust.id,
        "title": illust.title,
        "caption": illust.caption,
        "author": illust.user.name,
        "tags": tags,
        "page_count": page_count
    }
    print(info_dict)

    image_urls = []
    if page_count == 1:
        image_urls.append(illust.image_urls.large)
    else:
        for page in illust.meta_pages:
            image_urls.append(page.image_urls.large)

    tasks = []
    base_filenames = []
    for i, url in enumerate(image_urls):
        file_extension = os.path.splitext(url)[1]
        suggested_filename = f"{illust_id}_p{i}{file_extension}"
        base_filenames.append(f"{illust_id}_p{i}")

        task = asyncio.create_task(api.download(url, path=save_path, name=suggested_filename))
        tasks.append(task)

    download_statuses = await asyncio.gather(*tasks)

    if not all(download_statuses):
        print("Some images process failed")
    else:
        print("All download")

    real_paths = []
    try:
        files_in_dir = os.listdir(save_path)
        for base_name in base_filenames:
            found = False
            for actual_filename in files_in_dir:
                if actual_filename.startswith(base_name):
                    real_path = os.path.join(save_path, actual_filename)
                    real_paths.append(real_path)
                    found = True
                    break
            if not found:
                print(f" NotFound {base_name}。")
    except Exception as e:
        print(f"ERROR : {e}")

    return real_paths, info_dict


async def main(ill_id):
    REFRESH_TOKEN = config.pixiv_refresh_token
    ILLUST_ID_TO_DOWNLOAD = int(ill_id)
    api = AppPixivAPI()
    try:
        await api.login(refresh_token=REFRESH_TOKEN)

        save_directory = os.path.abspath('./downloads/pixiv')
        downloaded_files ,info_dict = await download_illust_large(api, ILLUST_ID_TO_DOWNLOAD, save_path=save_directory)
        if not downloaded_files:
            return

        for path in downloaded_files:
            print(f"  - {path}")

        final_files = format_webp_to_jpg(downloaded_files)
        # for path in final_files:
        #     print(f"  - {path}")
        return final_files, info_dict
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == '__main__':
    asyncio.run(main(127415120))