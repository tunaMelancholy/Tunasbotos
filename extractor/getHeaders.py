def get_headers(Ori_url):
    CST_HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/135.0",
            "Content-Type":"application/json",
            "Referer":f"{Ori_url}",
            "Origin":f"{Ori_url}"

        }
    return CST_HEADERS