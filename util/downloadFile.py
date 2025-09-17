import asyncio
import os
import uuid
import httpx
from typing import List
from PIL import Image
from moviepy import VideoFileClip

class SimpleDownloader:

    def __init__(self, url_list: List[str], dest_folder : str, exh_trigger):
        self.url_list = url_list
        self.dest_folder = dest_folder
        self.client = httpx.AsyncClient(http2=True, timeout=60.0, follow_redirects=True)
        self.exh_trigger = exh_trigger

        os.makedirs(self.dest_folder, exist_ok=True)

    def _convert_webp_to_jpg(self, webp_path: str) -> str | None:
        base_name = os.path.splitext(webp_path)[0]
        jpg_path = f"{base_name}.jpg"

        try:
            with Image.open(webp_path) as img:
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, (0, 0), img.convert('RGBA'))
                    background.save(jpg_path, 'jpeg', quality=90)
                else:
                    img.convert('RGB').save(jpg_path, 'jpeg', quality=90)

            os.remove(webp_path)
            return jpg_path
        except Exception as e:
            if os.path.exists(webp_path):
                os.remove(webp_path)
            return None

    def _convert_gif_to_mp4(self, gif_path: str) -> str | None:
        base_name = os.path.splitext(gif_path)[0]
        mp4_path = f"{base_name}.mp4"
        try:
            clip = VideoFileClip(gif_path)

            clip.write_videofile(
                mp4_path,
                codec='libx264',
                audio=False,
                logger=None,
                ffmpeg_params=['-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2']
            )
            clip.close()

            os.remove(gif_path)
            return mp4_path
        except Exception as e:
            if os.path.exists(gif_path): os.remove(gif_path)
            if os.path.exists(mp4_path): os.remove(mp4_path)
            return None
    async def _download_file(self, url: str) -> str | None:
        original_filename = ""
        try:
            original_filename = url.split('/')[-1].split('?')[0]
            if not original_filename:
                original_filename = f"{uuid.uuid4()}.tmp"

            local_filepath = os.path.join(self.dest_folder, original_filename)

            response = await self.client.get(url)

            response.raise_for_status()

            with open(local_filepath, 'wb') as f:
                f.write(response.content)

            lower_path = local_filepath.lower()
            if lower_path.endswith('.webp') and not self.exh_trigger :
                return self._convert_webp_to_jpg(local_filepath)
            elif lower_path.endswith('.gif'):
                return self._convert_gif_to_mp4(local_filepath)
            else:
                return local_filepath

        except httpx.HTTPStatusError as e:
            return None
        except Exception as e:
            return None

    async def run(self) -> List[str]:

        download_tasks = [self._download_file(url) for url in self.url_list]

        results = await asyncio.gather(*download_tasks)
        await self.client.aclose()

        successful_downloads = [path for path in results if path is not None]

        return successful_downloads

async def main(files_to_download,download_path : str = "downloads/temp",exh_trigger : bool = False):

    downloader = SimpleDownloader(
        url_list=files_to_download,
        dest_folder=download_path,
        exh_trigger = exh_trigger
    )

    local_file_list = await downloader.run()

    return local_file_list