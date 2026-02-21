import sqlite3
from config import DB_PATH

def get_connection():
    """返回 SQLite 连接，启用 WAL 模式以提升并发性能"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL")
    # Optimize write performance
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    """初始化数据库"""
    conn = get_connection()
    with open("db/schema.sql", "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
