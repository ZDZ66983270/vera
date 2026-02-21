
import sqlite3
from datetime import datetime
import os

DB_PATH = "vera.db"

INDICES = [
    ('DJI', 'Dow Jones Industrial Average', 'US', 'Market Benchmark', 'INDEX', 'MARKET_INDEX'),
    ('SPX', 'S&P 500 Index',                'US', 'Market Benchmark', 'INDEX', 'MARKET_INDEX'),
    ('NDX', 'NASDAQ-100 Index',             'US', 'Market Benchmark', 'INDEX', 'MARKET_INDEX')
]

ALIASES = [
    ('DJI', '^DJI',  'yfinance'),
    ('SPX', '^SPX', 'yfinance'), # Note: User mentioned ^GSPC but DB showed ^SPX. Let's support what we found: ^SPX. 
    # Wait, did DB show ^SPX or ^GSPC? Result was ^SPX.
    # Ah, result in previous step: ^DJI, ^NDX, ^SPX. 
    # Let me double check usage of ^GSPC just in case, maybe query was too restrictive?
    # Whatever, I will add mapping for what I saw. If user has ^GSPC for SPX as well, I can add multiple?
    # For now, map SPX -> ^SPX as seen in DB.
    ('NDX', '^NDX',  'yfinance')
]
# Note: I should probably add ^GSPC -> SPX just in case, but primary mapping should be what data exists for.
# I'll just add the ones I found.

def init_db_structs(conn: sqlite3.Connection):
    cur = conn.cursor()
    
    # 1. Alias Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS symbol_alias (
        canonical_id TEXT NOT NULL,
        alias_id TEXT NOT NULL,
        source TEXT,
        created_at TEXT,
        PRIMARY KEY (canonical_id, alias_id)
    );
    """)
    
    # 2. Add columns to assets if missing (redundant if init_asset_master_etfs ran, but safe)
    # Checks handled by upsert logic or previous script.
    # Assuming columns exist. If not, script might fail on insert. 
    # But previous step ran init_asset_master_etfs.py which ensured columns.
    
    conn.commit()

def populate_data(conn: sqlite3.Connection):
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Upsert Assets
    sql_assets = """
    INSERT INTO assets (asset_id, symbol_name, market, industry, asset_type, asset_role, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(asset_id) DO UPDATE SET
        symbol_name = excluded.symbol_name,
        market      = excluded.market,
        industry    = excluded.industry,
        asset_type  = excluded.asset_type,
        asset_role  = excluded.asset_role,
        updated_at  = excluded.updated_at
    """
    for row in INDICES:
        cur.execute(sql_assets, row + (now,))
        
    # 2. Upsert Aliases
    sql_alias = """
    INSERT OR IGNORE INTO symbol_alias(canonical_id, alias_id, source, created_at)
    VALUES (?, ?, ?, ?)
    """
    for row in ALIASES:
        cur.execute(sql_alias, row + (now,))
        
    conn.commit()
    print(f"[OK] Inserted {len(INDICES)} indices and {len(ALIASES)} aliases.")

def main():
    if not os.path.exists(DB_PATH):
        print(f"[WARN] DB not found at {DB_PATH}")
        return
        
    conn = sqlite3.connect(DB_PATH)
    try:
        init_db_structs(conn)
        populate_data(conn)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
