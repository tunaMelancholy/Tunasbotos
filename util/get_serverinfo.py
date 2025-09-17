import asyncio
import hashlib
import sqlite3
import time
import httpx
import jmespath
import json
from datetime import datetime

import config
BASE_URL_1 = config.panel_sail_url
BASE_URL_2 = config.panel_nas_url
def get_token_headers(ck_token):
    system_key = ck_token
    panel_timestamp = str(int(time.time()))
    ckt_token = hashlib.md5(f"1panel{system_key}{panel_timestamp}".encode()).hexdigest()
    print(ckt_token)
    headers = {
        "1Panel-Token": ckt_token,
        "1Panel-Timestamp": panel_timestamp
    }
    return headers
async def get_sail_info():

    HEADERS = get_token_headers(config.panel_sail_token)

    async with httpx.AsyncClient() as client:
        payload_basic = {"scope": "basic", "ioOption": "all", "netOption": "all"}
        payload_ionet = {"scope": "ioNet", "ioOption": "all", "netOption": "all"}
        try:
            responses = await asyncio.gather(
                client.get(f"{BASE_URL_1}/base/all/all", headers=HEADERS),
                client.post(f"{BASE_URL_1}/current", headers=HEADERS, json=payload_basic),
                client.post(f"{BASE_URL_1}/current", headers=HEADERS, json=payload_ionet)
            )
            for r in responses:
                r.raise_for_status()

            base_data = responses[0].json()
            basic_data = responses[1].json()
            ionet_data = responses[2].json()

            return base_data, basic_data, ionet_data

        except httpx.HTTPStatusError as e:
            print(f"Failed.Code: {e.response.status_code}, response: {e.response.text}")
        except httpx.RequestError as e:
            print(f"Error Occurred: {e}")
        return None, None, None

async def get_nas_info():

    HEADERS = get_token_headers(config.panel_nas_token)

    async with httpx.AsyncClient() as client:

        try:
            responses = await asyncio.gather(
                client.get(f"{BASE_URL_2}/base/all/all", headers=HEADERS),
                client.get(f"{BASE_URL_2}/current/all/all", headers=HEADERS),
            )
            for r in responses:
                r.raise_for_status()

            base_data = responses[0].json()
            basic_data = responses[1].json()

            return base_data, basic_data

        except httpx.HTTPStatusError as e:
            print(f"Failed.Code: {e.response.status_code}, response: {e.response.text}")
        except httpx.RequestError as e:
            print(f"Error Occurred: {e}")
        return None, None

async def nas():
    base_data, basic_data = await get_nas_info()
    if not all((base_data, basic_data)):
        print("Error")
        return None

    jme_data = {
        "platform": jmespath.search('data.platform', base_data),
        "platformFamily": jmespath.search('data.platformFamily', base_data),
        "platformVersion": jmespath.search('data.platformVersion', base_data),
        "kernelVersion": jmespath.search('data.kernelVersion', base_data),
        "uptime": jmespath.search('data.uptime', basic_data),
        "cpu_load1": jmespath.search('data.load1', basic_data),
        "cpu_load5": jmespath.search('data.load5', basic_data),
        "cpu_load15": jmespath.search('data.load15', basic_data),
        "cpu_cores": jmespath.search('data.cpuTotal', basic_data),
        "cpu_usage": jmespath.search('data.cpuUsedPercent', basic_data),
        "memory_total": jmespath.search('data.memoryTotal', basic_data),
        "memory_Available": jmespath.search('data.memoryAvailable', basic_data),
        "memory_UsedPercent": jmespath.search('data.memoryUsedPercent', basic_data),
        "disk_usedpercent": jmespath.search('data.diskData[1].usedPercent', basic_data),
        "disk_usedtotal": jmespath.search('data.diskData[1].total', basic_data),
        "disk_used": jmespath.search('data.diskData[1].used', basic_data),
        "net_send": jmespath.search('data.netBytesSent', basic_data),
        "net_receive": jmespath.search('data.netBytesRecv', basic_data)
    }

    def print_formatted_summary(data):
        def format_bytes(byte_count):
            if not isinstance(byte_count, (int, float)) or byte_count is None:
                return "N/A"
            return f"{byte_count / (1024 ** 3):.2f} GB"

        def format_bytes_one_decimal(byte_count):
            if not isinstance(byte_count, (int, float)) or byte_count is None:
                return "N/A"
            return f"{byte_count / (1024 ** 3):.1f} GB"

        def format_uptime(seconds):
            if not isinstance(seconds, (int, float)) or seconds is None:
                return "N/A"
            days, rem = divmod(seconds, 86400)
            hours, rem = divmod(rem, 3600)
            minutes, _ = divmod(rem, 60)
            return f"{int(days)} 天 {int(hours)} 小时 {int(minutes)} 分钟"

        platform = data.get("platform", "N/A")
        platform_version = data.get("platformVersion", "N/A")
        platform_family = data.get("platformFamily", "N/A")
        kernel_version = data.get("kernelVersion", "N/A")

        uptime_str = format_uptime(data.get("uptime"))

        load1 = data.get("cpu_load1", 0)
        load5 = data.get("cpu_load5", 0)
        load15 = data.get("cpu_load15", 0)
        cpu_usage = data.get("cpu_usage", 0)
        cpu_cores = data.get("cpu_cores", "N/A")

        mem_percent = data.get("memory_UsedPercent", 0)
        mem_total_b = data.get("memory_total", 0)
        mem_avail_b = data.get("memory_Available", 0)
        mem_used_b = mem_total_b - mem_avail_b
        mem_total_gb = format_bytes(mem_total_b)
        mem_used_gb = format_bytes(mem_used_b)

        disk_percent = data.get("disk_usedpercent", [0])
        disk_used_b = data.get("disk_used", [0])
        disk_total_b = data.get("disk_usedtotal", [0])
        disk_used_gb = format_bytes(disk_used_b)
        disk_total_gb = format_bytes(disk_total_b)

        net_send_gb = format_bytes_one_decimal(data.get("net_send"))
        net_recv_gb = format_bytes_one_decimal(data.get("net_receive"))

        summary = f"""
== Exporter Info ==
系统平台: {platform} {platform_version}
内核版本: {platform_family} / {kernel_version}
在线时长: {uptime_str}
系统负载: {load1:.2f} / {load5:.2f} / {load15:.2f}
CPU 状态: {cpu_usage:.2f}% /  {cpu_cores} Cores
内存占用: {mem_percent:.2f}% - {mem_used_gb} / {mem_total_gb}
磁盘占用: {disk_percent:.2f}% - {disk_used_gb} / {disk_total_gb}
网络流量: TX: {net_send_gb} / RX: {net_recv_gb}
        """
        return summary

    data = print_formatted_summary(jme_data)
    return data

async def sail():


    base_data, basic_data, ionet_data = await get_sail_info()

    if not all((base_data, basic_data, ionet_data)):
        print("Error")
        return None

    jme_data = {
        "platform": jmespath.search('data.platform', base_data),
        "platformFamily": jmespath.search('data.platformFamily', base_data),
        "platformVersion": jmespath.search('data.platformVersion', base_data),
        "kernelVersion": jmespath.search('data.kernelVersion', base_data),
        "uptime": jmespath.search('data.uptime', basic_data),
        "cpu_load1": jmespath.search('data.load1', basic_data),
        "cpu_load5": jmespath.search('data.load5', basic_data),
        "cpu_load15": jmespath.search('data.load15', basic_data),
        "cpu_cores": jmespath.search('data.cpuTotal', basic_data),
        "cpu_usage": jmespath.search('data.cpuUsed', basic_data),
        "memory_total": jmespath.search('data.memoryTotal', basic_data),
        "memory_Available": jmespath.search('data.memoryAvailable', basic_data),
        "memory_UsedPercent": jmespath.search('data.memoryUsedPercent', basic_data),
        "disk_usedpercent": jmespath.search('data.diskData[].usedPercent', basic_data),
        "disk_usedtotal": jmespath.search('data.diskData[].total', basic_data),
        "disk_used": jmespath.search('data.diskData[].used', basic_data),
        "net_send": jmespath.search('data.netBytesSent', ionet_data),
        "net_receive": jmespath.search('data.netBytesRecv', ionet_data)
    }

    def print_formatted_summary(data):
        def format_bytes(byte_count):
            if not isinstance(byte_count, (int, float)) or byte_count is None:
                return "N/A"
            return f"{byte_count / (1024 ** 3):.2f} GB"

        def format_bytes_one_decimal(byte_count):
            if not isinstance(byte_count, (int, float)) or byte_count is None:
                return "N/A"
            return f"{byte_count / (1024 ** 3):.1f} GB"

        def format_uptime(seconds):
            if not isinstance(seconds, (int, float)) or seconds is None:
                return "N/A"
            days, rem = divmod(seconds, 86400)
            hours, rem = divmod(rem, 3600)
            minutes, _ = divmod(rem, 60)
            return f"{int(days)} 天 {int(hours)} 小时 {int(minutes)} 分钟"

        platform = data.get("platform", "N/A").capitalize()
        platform_version = data.get("platformVersion", "N/A")
        platform_family = data.get("platformFamily", "N/A")
        kernel_version = data.get("kernelVersion", "N/A")

        uptime_str = format_uptime(data.get("uptime"))

        load1 = data.get("cpu_load1", 0)
        load5 = data.get("cpu_load5", 0)
        load15 = data.get("cpu_load15", 0)
        cpu_usage = data.get("cpu_usage", 0) * 100
        cpu_cores = data.get("cpu_cores", "N/A")

        mem_percent = data.get("memory_UsedPercent", 0)
        mem_total_b = data.get("memory_total", 0)
        mem_avail_b = data.get("memory_Available", 0)
        mem_used_b = mem_total_b - mem_avail_b
        mem_total_gb = format_bytes(mem_total_b)
        mem_used_gb = format_bytes(mem_used_b)

        disk_percent = data.get("disk_usedpercent", [0])[0]
        disk_used_b = data.get("disk_used", [0])[0]
        disk_total_b = data.get("disk_usedtotal", [0])[0]
        disk_used_gb = format_bytes(disk_used_b)
        disk_total_gb = format_bytes(disk_total_b)

        net_send_gb = format_bytes_one_decimal(data.get("net_send"))
        net_recv_gb = format_bytes_one_decimal(data.get("net_receive"))

        summary = f"""
== [Main] Extractor Info ==
系统平台: {platform} {platform_version}
内核版本: {platform_family} / {kernel_version}
在线时长: {uptime_str}
系统负载: {load1:.2f} / {load5:.2f} / {load15:.2f}
CPU 状态: {cpu_usage:.2f}% /  {cpu_cores} Cores
内存占用: {mem_percent:.2f}% - {mem_used_gb} / {mem_total_gb}
磁盘占用: {disk_percent:.2f}% - {disk_used_gb} / {disk_total_gb}
网络流量: TX: {net_send_gb} / RX: {net_recv_gb}
    """
        return summary
    data = print_formatted_summary(jme_data)
    return data

def init_db():
    conn = sqlite3.connect('msg.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sticker_info (
            stk_id TEXT PRIMARY KEY,
            count INTEGER DEFAULT 1
        )
    ''')
    conn.commit()

    return conn, cursor

async def get_info():
    def get_deepseek_blance():
        url = "https://api.deepseek.com/user/balance"
        payload = {}
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {config.CHAT_CONFIG['DEEPSEEK_API_KEY']}'
        }
        try:
            response = httpx.request("GET", url, headers=headers, data=payload)
            data = response.json()
        except Exception as e:
            print(f"Error: {e}")
            return None
        expression = "balance_infos[].{currency: currency, total_balance: total_balance}"
        result = jmespath.search(expression, data)
        return result
    deepseek_result = get_deepseek_blance()
    def read_githead():
        try:
            Git_Path = '.git/refs/remotes/origin/main'
            with open(Git_Path, 'r') as file:
                return file.read()[:7]
        except:
            return 'unknown'

    def database_query():
        onn, cursor = init_db()
        sticker_count = cursor.execute("select count(stk_id) from sticker_info;").fetchone()[0]
        sticker_hot = cursor.execute("select sum(si.count) from sticker_info si where count > 5;").fetchone()[0]
        tokens = cursor.execute("select sum(m.size)*1.6 from messages m;").fetchone()[0]
        return sticker_count,sticker_hot,int(float(tokens))

    sticker_count, sticker_hot, tokens = database_query()
    base_info = f"""
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}:UTC
Logging:{str(config.BOT_APP_ID)[-5:]}:{config.BOT_APP_HASH[-5:]} - {config.BOT_NAME}
Version: {read_githead()}
白名单用户数量: {len(config.WHITELIST_USER)}
白名单群组数量: {len(config.WHITELIST_GROUP)}
缓存的贴纸数量: {sticker_count:,}
    """
    inst_info0 = await sail()
    inst_info1 = await nas()
    chat_info = f"""
Deepseek:
当前账号余额: {deepseek_result[0]['currency']}  {deepseek_result[0]['total_balance']}
消耗Token: {tokens:,}
"""
    # print(base_info, inst_info0, inst_info1, chat_info)
    return base_info, inst_info0, inst_info1, chat_info


# if __name__ == "__main__":
#     asyncio.run(get_info())

