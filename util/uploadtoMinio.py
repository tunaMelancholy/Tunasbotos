import asyncio
import os
import config
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

async def upload_files_with_threadpool(
        file_paths: List[str],
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        s3_prefix: Optional[str] = None,
        max_workers: int = 10
) -> List[str]:

    import boto3
    from botocore.client import Config

    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'),
        verify=False
    )

    url_list = []
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=max_workers)

    async def process_file(local_file_path: str) -> Optional[str]:
        if not os.path.isfile(local_file_path):
            print(f"警告: 文件不存在，跳过: {local_file_path}")
            return None

        try:
            filename = os.path.basename(local_file_path)
            s3_key = f"{s3_prefix}/{filename}" if s3_prefix else filename

            await loop.run_in_executor(
                executor,
                lambda: s3_client.upload_file(local_file_path, bucket_name, s3_key)
            )

            print(f"{local_file_path} -> {s3_key}")
            direct_url = f"{endpoint_url.rstrip('/')}/{bucket_name}/{s3_key}"
            return direct_url

        except Exception as e:
            print(f"✗ {local_file_path}: {e}")
            return None

    tasks = [process_file(file_path) for file_path in file_paths]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if not isinstance(result, Exception) and result is not None:
            url_list.append(result)

    return url_list

async def execute(files_to_upload):
    CONFIG = config.MINIO_CONFIG
    urls = await upload_files_with_threadpool(
        file_paths=files_to_upload,
        **CONFIG,
        s3_prefix='uploads',
        max_workers=15
    )
    for i, url in enumerate(urls, 1):
        print(f"{i}. {url}")

    return urls

