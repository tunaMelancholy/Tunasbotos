# -*- coding: utf-8 -*-
import asyncio
import logging

import boto3
import os
import config
from typing import List, Optional
R2_ACCOUNT_ID = config.r2_config["account_id"]
R2_BUCKET_NAME = config.r2_config["bucket_name"]
R2_ACCESS_KEY_ID = config.r2_config["access_key"]
R2_SECRET_ACCESS_KEY = config.r2_config["secret_key"]
R2_CUSTOM_DOMAIN = config.r2_config["domain"]

R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
CONCURRENCY_LIMIT = 8
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

def get_logger(level):
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)


logger = get_logger(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def create_s3_folder(s3_client, bucket_name: str, folder_name: str) -> bool:

    if not folder_name:
        return True

    folder_key = f"{folder_name.strip('/')}/"
    try:
        await asyncio.to_thread(
            s3_client.put_object,
            Bucket=bucket_name,
            Key=folder_key,
            Body=b''
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to create folder:{e}")
        return False


async def upload_single_file(
        s3_client,
        local_file_path: str,
        bucket_name: str,
        custom_domain: str,
        destination_folder: str
) -> Optional[str]:

    async with semaphore:
        try:
            if not os.path.exists(local_file_path):
                logger.info(f"file not exist{local_file_path}")
                return None

            file_name = os.path.basename(local_file_path)
            object_name = f"{destination_folder.strip('/')}/{file_name}"

            logger.warning(f"Start Upload Job :{local_file_path} -> S3 Remote {bucket_name}/{object_name}")

            await asyncio.to_thread(
                s3_client.upload_file,
                Filename=local_file_path,
                Bucket=bucket_name,
                Key=object_name
            )

            file_url = f"{custom_domain}/{object_name}"
            return file_url

        except Exception as e:
            logger.warning(f"Upload failed {local_file_path}, {e}")
            return None

async def main(local_file_list: List[str], folder_name: str) -> List[Optional[str]]:

    if not local_file_list:
        return []

    s3_client = boto3.client(
        service_name='s3',
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )

    folder_created = await create_s3_folder(s3_client, R2_BUCKET_NAME, folder_name)
    if not folder_created:
        logger.warning("Upload Job cancelled due to folder creation failure.")
        return [None] * len(local_file_list)

    tasks = [
        upload_single_file(s3_client, file_path, R2_BUCKET_NAME, R2_CUSTOM_DOMAIN, folder_name)
        for file_path in local_file_list
    ]
    results = await asyncio.gather(*tasks)

    return results