import sqlite3, random
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

def insert_sticker(stk_id):
    conn, cursor = init_db()

    cursor.execute('SELECT count FROM sticker_info WHERE stk_id = ?', (stk_id,))
    result = cursor.fetchone()

    if result:
        new_count = result[0] + 1
        cursor.execute('UPDATE sticker_info SET count = ? WHERE stk_id = ?', (new_count, stk_id))
    else:
        new_count = 1
        cursor.execute('INSERT INTO sticker_info (stk_id, count) VALUES (?, 1)', (stk_id,))

    conn.commit()
    conn.close()
    return new_count

def get_sticker():
    conn, cursor = init_db()

    db_stk_id = cursor.execute('SELECT stk_id FROM sticker_info WHERE count > 4').fetchall()
    sticker_id = random.choice(db_stk_id)
    cursor.close()
    conn.close()

    return sticker_id

def get_sticker_count():
    conn, cursor = init_db()

    cursor.execute('SELECT COUNT(*) FROM sticker_info')
    result = cursor.fetchone()
    count = result[0] if result else 0

    cursor.close()
    conn.close()

    return count