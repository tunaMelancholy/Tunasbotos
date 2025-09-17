import asyncio
import sqlite3
import jmespath
from curl_cffi import AsyncSession


async def update_database(api_count=5):

    db_path = "kemomimi.db"
    all_api_results = []

    try:
        async with AsyncSession() as session:
            tasks = []
            for i in range(api_count):
                task = fetch_api_data(session, page_index=i)
                tasks.append(task)

            all_api_results = await asyncio.gather(*tasks)

    except Exception as e:
        return f"Error: {e}"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("DROP TABLE IF EXISTS posts")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY,
                source TEXT,
                url TEXT
            )
        """)

        for data in all_api_results:
            if not data:
                continue

            expression = """
                post[*].{
                    "id": id,
                    "source": source,
                    "url": (@.sample_url || @.file_url)
                }
            """
            result = jmespath.search(expression, data)

            if not result:
                continue

            cursor.executemany("""
                INSERT OR IGNORE INTO posts (id, source, url)
                VALUES (?, ?, ?)
                """, [(item["id"], item["source"], item["url"]) for item in result])

        conn.commit()
        conn.close()

        return "OK"
    except Exception as e:
        return f"Error: {e}"

# tags="loli+animal_ears+-oppai_loli+-furry+-large_breasts+-animated+-3d+-fake_animal_ears+-fake tail "

async def fetch_api_data(session: AsyncSession, page_index=0, tags="loli+pussy+-oppai_loli+-furry+-large_breasts+-animated+-3d+-fake_animal_ears+-fake tail "):
    try:
        headers = {}
        base_url = f"https://gelbooru.com/index.php?page=dapi&s=post&q=index&api_key=fc6aeed50bae78b9c24be33aded02993aea53b3f4ce0ed6041e881a4dfd0862454076d69c24dadc51d2fdfac47f9baa59313cc36968c4940c621c4489e923813&user_id=1735774&json=1&q=index&limit=100&tags={tags}&pid={page_index}"

        response = await session.get(base_url, headers=headers, impersonate="chrome110")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return None

#
# async def main():
#     status = await update_database(api_count=20)
#     print(status)
#
#
# if __name__ == "__main__":
#     asyncio.run(main())