
import sqlite3
import os
from datetime import datetime

DB_PATH = "vera.db"

MAP_ENTRIES = [
    # Canonical, Symbol, Source, Priority
    ('SPX', 'SPX',   'manual_csv', 10),
    ('SPX', '^SPX',  'yfinance',   10), # Found via DB check earlier
    ('SPX', '^GSPC', 'yfinance',   20), # Yahoo standard
    ('NDX', 'NDX',   'manual_csv', 10),
    ('NDX', '^NDX',  'yfinance',   10),
    ('DJI', 'DJI',   'manual_csv', 10),
    ('DJI', '^DJI',  'yfinance',   10),
]

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        
        # 1. Create Table
        print("[INFO] Creating asset_symbol_map table...")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS asset_symbol_map (
          canonical_id TEXT NOT NULL,
          symbol TEXT NOT NULL,
          source TEXT,
          priority INTEGER DEFAULT 50,
          is_active INTEGER DEFAULT 1,
          note TEXT,
          created_at TEXT,
          updated_at TEXT,
          PRIMARY KEY (canonical_id, symbol)
        );
        """)
        
        # 2. Create Index
        print("[INFO] Creating index idx_symbol_lookup...")
        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_symbol_lookup
        ON asset_symbol_map (symbol, is_active);
        """)
        
        # 3. Populate Data
        print("[INFO] Populating map entries...")
        sql = """
        INSERT OR IGNORE INTO asset_symbol_map
        (canonical_id, symbol, source, priority, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, 1, ?, ?)
        """
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for entry in MAP_ENTRIES:
            # canonical, symbol, source, priority
            cur.execute(sql, (entry[0], entry[1], entry[2], entry[3], now, now))
            
        conn.commit()
        print(f"[OK] Migration complete. Inserted {len(MAP_ENTRIES)} mapping rules.")
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
