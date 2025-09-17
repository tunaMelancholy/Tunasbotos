# -*- coding: utf-8 -*-
import asyncio
import io
import os
from pathlib import Path
from typing import Optional, List

import httpx
from PIL import Image


async def process_image_list(url_list: list,trigger = False) -> list:
    download_dir = Path("downloads/temp")
    download_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as client:
        tasks = [_process_single_url(url, i, download_dir, client, trigger) for i, url in enumerate(url_list)]

        processed_list = await asyncio.gather(*tasks)
    return processed_list

async def _process_single_url(url: str, index: int, download_dir: Path, client: httpx.AsyncClient(),trigger) -> str:
    if not url.lower().endswith(".webp") and not trigger:
        return url

    try:

        response = await client.get(url, timeout=30.0)
        response.raise_for_status()

        original_filename_str = Path(url).name
        new_filename_path = Path(original_filename_str).with_suffix(".jpg")
        local_jpg_path = download_dir / new_filename_path

        with Image.open(io.BytesIO(response.content)) as img:

            if img.mode != 'RGB':
                img = img.convert('RGB')

            img.save(local_jpg_path, 'jpeg', quality=90)

        new_path_str = str(local_jpg_path).replace('\\', '/')
        return new_path_str

    except Exception as e:
        return url

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


def process_and_convert_image(source_path: Path) -> Optional[str]:
    target_path = source_path.with_suffix('.webp')

    try:
        with Image.open(source_path) as img:
            img.save(target_path, 'webp', quality=85)

        source_path.unlink()

        return str(target_path)

    except FileNotFoundError:
        return None
    except Exception as e:
        if target_path.exists():
            target_path.unlink()
        return None


async def convert_folder_to_webp(folder_path: str) -> List[str]:
    path = Path(folder_path)
    if not path.is_dir():
        return []

    image_files = [
        file for file in path.rglob('*')
        if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not image_files:
        return []

    tasks = [
        asyncio.to_thread(process_and_convert_image, file)
        for file in image_files
    ]

    results = await asyncio.gather(*tasks)

    successful_paths = [path for path in results if path is not None]
    return successful_paths
async def convert_to_webp(path:str):

    target_directory = path

    converted_files = await convert_folder_to_webp(target_directory)

    if converted_files:
        for file_path in converted_files:
            print(f"- {file_path}")
    else:
        print("All Failed")


if __name__ == "__main__":
    asyncio.run(convert_to_webp(""))