# -*- coding: utf-8 -*-
import re
from telegraph.aio import Telegraph

def _classify_and_render_urls(input_urls: list) -> str:
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.svg', '.gif'}
    images = []
    other_files = []

    for url in input_urls:
        ext_match = re.search(r'\.([a-zA-Z0-9]+)(?:$|\?|#)', url.lower())
        if ext_match:
            extension = '.' + ext_match.group(1)
            if extension in image_extensions:
                images.append(url)
            else:
                other_files.append((url, extension[1:]))
        else:
            other_files.append((url, 'file'))

    images_html = "".join(f'<img src="{url}">' for url in images)
    other_files_html = ""
    if other_files:
        other_files_html = "<p><strong>Other Files:</strong></p>" + "".join(
            f'<a href="{url}">{ext} download</a><br>' for url, ext in other_files
        )

    return images_html + other_files_html


async def upload_urls_to_telegraph(title: str, urls: list,attachments_content : str) -> str:
    """

    :param title: the title of telegraph page
    :type title: str
    :param urls: a list type var which include target urls
    :type urls: list
    :param attachments_content:
    :type attachments_content: str
    :return: remote_link: Telegraph Page Link
    :rtype remote_link: str
    """
    telegraph = Telegraph()
    await telegraph.create_account(short_name='TunasBot')

    if len(title) > 256:
        title = title[:253] + "..."

    content = _classify_and_render_urls(urls)

    response = await telegraph.create_page(
        title=title,
        html_content=attachments_content+content
    )
    return f"https://telegra.ph/{response['path']}"
