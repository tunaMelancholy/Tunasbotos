from util.initdatabase import df_initialize_database
from config import STICKER_TRIGGER_COUNT
def random_sticker():
    conn, cursor = df_initialize_database()
    query = '''SELECT stk_id FROM sticker_info 
               WHERE count > ? 
               ORDER BY RANDOM() LIMIT 1'''
    sticker_id = cursor.execute(query, (STICKER_TRIGGER_COUNT,)).fetchone()
    conn.close()
    return sticker_id[0]