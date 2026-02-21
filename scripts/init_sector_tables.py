
import sqlite3
import os

DB_PATH = "vera.db"

def init_sector_tables():
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. asset_classification
    print("Creating table: asset_classification...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS asset_classification (
      asset_id      TEXT NOT NULL,
      scheme        TEXT NOT NULL,          -- 'GICS' / 'SW' / 'CITIC' 等
      sector_code   TEXT,
      sector_name   TEXT,
      industry_code TEXT,
      industry_name TEXT,
      as_of_date    TEXT NOT NULL,          -- 'YYYY-MM-DD'
      is_active     INTEGER DEFAULT 1,
      PRIMARY KEY(asset_id, scheme, as_of_date)
    );
    """)

    # 2. sector_proxy_map
    print("Creating table: sector_proxy_map...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sector_proxy_map (
      scheme       TEXT NOT NULL,           -- 'GICS'
      sector_code  TEXT NOT NULL,           -- e.g. '45'
      sector_name  TEXT,
      proxy_etf_id TEXT NOT NULL,           -- e.g. 'XLK'
      priority     INTEGER DEFAULT 50,
      is_active    INTEGER DEFAULT 1,
      note         TEXT,
      PRIMARY KEY(scheme, sector_code, proxy_etf_id)
    );
    """)

    conn.commit()
    conn.close()
    print("✅ Sector overlay tables initialized successfully.")

if __name__ == "__main__":
    init_sector_tables()
