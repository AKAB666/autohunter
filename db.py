import aiosqlite
from pathlib import Path

DB_PATH = Path("autohunter.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS watches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            price INTEGER,
            last_notified_price INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, url)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS seen_listings (
            url TEXT PRIMARY KEY,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.commit()

async def add_watch(user_id: int, url: str, title: str, price: int | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO watches(user_id,url,title,price,last_notified_price) VALUES(?,?,?,?,?)",
            (user_id, url, title, price, price)
        )
        await db.commit()

async def list_watches(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id,title,price,url FROM watches WHERE user_id=? ORDER BY id DESC",
            (user_id,)
        )
        return await cur.fetchall()

async def remove_watch(user_id: int, watch_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM watches WHERE user_id=? AND id=?", (user_id, watch_id))
        await db.commit()
        return cur.rowcount > 0

async def get_all_watches():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id,url,title,price,last_notified_price FROM watches")
        return await cur.fetchall()

async def update_watch_price(user_id: int, url: str, price: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE watches SET price=?,last_notified_price=? WHERE user_id=? AND url=?",
            (price, price, user_id, url)
        )
        await db.commit()

async def mark_seen(url: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("INSERT OR IGNORE INTO seen_listings(url) VALUES(?)", (url,))
        await db.commit()
        return cur.rowcount > 0
