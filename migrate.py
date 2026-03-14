import sqlite3

DB_PATH = "chat.db"

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if not column_exists(cur, "messages", "image_url"):
        cur.execute("ALTER TABLE messages ADD COLUMN image_url TEXT")
        conn.commit()
        print("Migration applied: added image_url column to messages")
    else:
        print("Already up to date: image_url column exists")

    conn.close()

if __name__ == "__main__":
    migrate()
