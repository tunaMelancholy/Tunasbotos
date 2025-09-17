import sqlite3

def df_initialize_database():
    conn = sqlite3.connect('msg.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            username TEXT,
            user_text TEXT,
            reply TEXT,
            size REAL
        )
    ''')
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userid TEXT,
                user_text TEXT
            )
        ''')
    cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                userid TEXT,
                count INTEGER
            )
        ''')
    cursor.execute('''
                CREATE TABLE IF NOT EXISTS configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    userid TEXT,
                    model TEXT
                )
            ''')
    conn.commit()
    return conn, cursor